"""
Wake-then-monitor: after sending a WOL packet, poll the target machine
to check whether it comes online within a configurable window.

Anti-storm design
─────────────────
  1. Monitors are keyed by **machine_id** → only ONE per machine at a time.
  2. Re-waking the same machine *cancels* the old monitor and starts a fresh one.
  3. Each monitor has a hard cap on both **attempts** and **elapsed time**.
  4. Completed monitors are auto-evicted from memory after a short TTL
     so the dict never grows unboundedly.
  5. A generation counter prevents stale eviction tasks from deleting
     a newer monitor for the same machine.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from loguru import logger

from app.wol import check_host_online


# ── Status Enum ──────────────────────────────────────
class MonitorStatus(str, Enum):
    PENDING = "pending"        # Created, first check hasn't started yet
    CHECKING = "checking"      # Actively pinging
    ONLINE = "online"          # Target responded to ping
    TIMEOUT = "timeout"        # All attempts exhausted
    CANCELLED = "cancelled"    # Replaced by a newer wake request
    NO_IP = "no_ip"            # Machine has no IP configured


# ── Per-machine state ────────────────────────────────
@dataclass
class MonitorState:
    machine_id: int
    machine_name: str
    ip_address: str
    generation: int = 0                    # distinguishes successive monitors
    status: MonitorStatus = MonitorStatus.PENDING
    attempts: int = 0
    max_attempts: int = 15
    interval: float = 10.0                 # seconds between pings
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    _task: Optional[asyncio.Task] = field(default=None, repr=False)

    @property
    def elapsed(self) -> float:
        end = self.finished_at or time.time()
        return round(end - self.started_at, 1)

    @property
    def is_terminal(self) -> bool:
        """True when the monitor has reached a final state."""
        return self.status in (
            MonitorStatus.ONLINE,
            MonitorStatus.TIMEOUT,
            MonitorStatus.CANCELLED,
            MonitorStatus.NO_IP,
        )

    def to_dict(self) -> dict:
        return {
            "machine_id": self.machine_id,
            "machine_name": self.machine_name,
            "ip_address": self.ip_address,
            "status": self.status.value,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "elapsed": self.elapsed,
            "finished": self.is_terminal,
        }


# ── Manager ──────────────────────────────────────────
class WakeMonitorManager:
    """Singleton manager for post-wake monitoring tasks.

    Guarantees
    ──────────
      • At most ONE monitor per machine_id at any time.
      • Re-waking cancels the existing monitor (no accumulation).
      • Completed monitors are auto-evicted after ``_EVICT_AFTER`` seconds.
      • Generation counters prevent stale eviction tasks from removing
        a newer monitor for the same machine.
    """

    _EVICT_AFTER: int = 300  # keep finished monitor info for 5 min
    _MAX_CONCURRENT: int = 50  # hard cap on total active monitors

    def __init__(self) -> None:
        self._monitors: dict[int, MonitorState] = {}
        self._lock = asyncio.Lock()
        self._generation: int = 0  # global generation counter

    # ── public API ───────────────────────────────────
    async def start(
        self,
        machine_id: int,
        machine_name: str,
        ip_address: str,
        *,
        max_attempts: int = 15,
        interval: float = 10.0,
    ) -> MonitorState:
        """Start monitoring *machine_id*.

        If a monitor already exists for this machine it is cancelled first.
        """
        async with self._lock:
            self._cancel_existing(machine_id)

            # Hard cap — refuse if too many monitors are active
            active = sum(
                1 for s in self._monitors.values() if not s.is_terminal
            )
            if active >= self._MAX_CONCURRENT:
                logger.warning(
                    f"Monitor limit reached ({self._MAX_CONCURRENT}), "
                    f"refusing monitor for machine {machine_id}"
                )
                state = MonitorState(
                    machine_id=machine_id,
                    machine_name=machine_name,
                    ip_address=ip_address or "",
                    status=MonitorStatus.TIMEOUT,
                    finished_at=time.time(),
                )
                return state

            self._generation += 1
            gen = self._generation

            if not ip_address:
                state = MonitorState(
                    machine_id=machine_id,
                    machine_name=machine_name,
                    ip_address="",
                    generation=gen,
                    status=MonitorStatus.NO_IP,
                    finished_at=time.time(),
                )
                self._monitors[machine_id] = state
                self._schedule_eviction(machine_id, gen)
                return state

            state = MonitorState(
                machine_id=machine_id,
                machine_name=machine_name,
                ip_address=ip_address,
                generation=gen,
                max_attempts=max_attempts,
                interval=interval,
            )
            state._task = asyncio.create_task(
                self._run(state),
                name=f"wake-monitor-{machine_id}-g{gen}",
            )
            self._monitors[machine_id] = state
            logger.info(
                f"Monitor started: {machine_name} (id={machine_id}, "
                f"ip={ip_address}, max={max_attempts}, "
                f"interval={interval}s, gen={gen})"
            )
            return state

    def get(self, machine_id: int) -> Optional[dict]:
        """Return monitor info for one machine, or ``None``."""
        state = self._monitors.get(machine_id)
        return state.to_dict() if state else None

    def get_all(self) -> list[dict]:
        """Return a snapshot of every active/recent monitor."""
        return [s.to_dict() for s in self._monitors.values()]

    async def cancel(self, machine_id: int) -> bool:
        """Manually cancel a monitor.  Returns True if one was running."""
        async with self._lock:
            return self._cancel_existing(machine_id)

    async def shutdown(self) -> None:
        """Cancel all monitors (call on application shutdown)."""
        async with self._lock:
            for state in self._monitors.values():
                if state._task and not state._task.done():
                    state._task.cancel()
            self._monitors.clear()
            logger.info("All wake monitors cancelled (shutdown)")

    # ── internal ─────────────────────────────────────
    def _cancel_existing(self, machine_id: int) -> bool:
        old = self._monitors.get(machine_id)
        if old is None:
            return False
        if old._task and not old._task.done():
            old._task.cancel()
            old.status = MonitorStatus.CANCELLED
            old.finished_at = time.time()
            logger.info(
                f"Cancelled previous monitor for machine {machine_id} "
                f"(gen={old.generation})"
            )
        # Always remove — whether task was running or already finished
        self._monitors.pop(machine_id, None)
        return True

    async def _run(self, state: MonitorState) -> None:
        """Background coroutine: ping the machine until success or timeout."""
        try:
            # Brief initial delay — the machine needs a moment to boot.
            await asyncio.sleep(5)

            while state.attempts < state.max_attempts:
                state.status = MonitorStatus.CHECKING
                state.attempts += 1

                online = await check_host_online(state.ip_address, timeout=2)
                if online:
                    state.status = MonitorStatus.ONLINE
                    state.finished_at = time.time()
                    logger.info(
                        f"Machine {state.machine_name} (id={state.machine_id}) "
                        f"ONLINE after {state.attempts} attempt(s) "
                        f"({state.elapsed}s)"
                    )
                    self._schedule_eviction(
                        state.machine_id, state.generation
                    )
                    return

                # Wait before next attempt
                await asyncio.sleep(state.interval)

            # All attempts exhausted
            state.status = MonitorStatus.TIMEOUT
            state.finished_at = time.time()
            logger.info(
                f"Monitor timeout: {state.machine_name} (id={state.machine_id}) "
                f"after {state.attempts} attempt(s) ({state.elapsed}s)"
            )
            self._schedule_eviction(state.machine_id, state.generation)

        except asyncio.CancelledError:
            # Normal cancellation (re-wake or shutdown)
            state.status = MonitorStatus.CANCELLED
            state.finished_at = time.time()
        except Exception as exc:
            logger.error(
                f"Monitor error for machine {state.machine_id}: {exc}"
            )
            state.status = MonitorStatus.TIMEOUT
            state.finished_at = time.time()
            self._schedule_eviction(state.machine_id, state.generation)

    def _schedule_eviction(self, machine_id: int, generation: int) -> None:
        """Remove a finished monitor from memory after ``_EVICT_AFTER`` sec.

        The *generation* guard ensures that if the machine was re-waked
        between the finish and the eviction, the NEW monitor is not
        accidentally removed.
        """

        async def _evict() -> None:
            await asyncio.sleep(self._EVICT_AFTER)
            current = self._monitors.get(machine_id)
            if current is not None and current.generation == generation:
                self._monitors.pop(machine_id, None)

        asyncio.create_task(
            _evict(), name=f"evict-{machine_id}-g{generation}"
        )


# Singleton
wake_monitor = WakeMonitorManager()
