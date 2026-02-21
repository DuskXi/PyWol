/**
 * Composable for polling wake-monitor status after sending a WOL packet.
 *
 * Anti-storm design:
 *   - Only ONE poll timer per machine_id (Map keyed by id).
 *   - A separate `active` Set prevents double-starts during async gap.
 *   - Timer auto-stops when backend reports `finished === true`.
 *   - All timers are cleared on component unmount (`onUnmounted`).
 *   - Fixed, non-overlapping interval (waits for response before scheduling next).
 */

import { ref, onUnmounted } from 'vue';
import { wakeApi } from 'src/services/api';
import type { WakeMonitor } from 'src/types';

const POLL_INTERVAL = 5_000; // 5 seconds
const DISPLAY_DURATION = 30_000; // keep finished result visible for 30s

export function useWakeMonitor() {
  const monitors = ref<Map<number, WakeMonitor>>(new Map());
  const timers = new Map<number, ReturnType<typeof setTimeout>>();
  // Tracks machines we are actively polling (guards against double-start)
  const active = new Set<number>();

  /** Start polling the monitor status for a machine. */
  function startPolling(machineId: number) {
    // If already polling this machine, don't double-up
    if (active.has(machineId)) return;
    active.add(machineId);
    void poll(machineId);
  }

  /** Single poll cycle — fetches status, updates map, reschedules if needed. */
  async function poll(machineId: number) {
    // Safety: bail if we've been stopped between scheduling and execution
    if (!active.has(machineId)) return;

    try {
      const res = await wakeApi.monitor(machineId);
      const data = res.data;
      monitors.value.set(machineId, data);
      // Trigger Vue reactivity (Map mutations aren't deeply reactive in ref)
      monitors.value = new Map(monitors.value);

      if (data.finished) {
        // Terminal state — stop polling, auto-remove after a short display period
        cleanup(machineId);
        setTimeout(() => {
          monitors.value.delete(machineId);
          monitors.value = new Map(monitors.value);
        }, DISPLAY_DURATION);
        return;
      }
    } catch {
      // API error — stop to avoid hammering a broken endpoint
      cleanup(machineId);
      return;
    }

    // Schedule next poll (only if still active)
    if (!active.has(machineId)) return;
    const timer = setTimeout(() => {
      void poll(machineId);
    }, POLL_INTERVAL);
    timers.set(machineId, timer);
  }

  /** Internal: remove a machine from all tracking structures. */
  function cleanup(machineId: number) {
    const timer = timers.get(machineId);
    if (timer) clearTimeout(timer);
    timers.delete(machineId);
    active.delete(machineId);
  }

  /** Stop polling for a specific machine. */
  function stopPolling(machineId: number) {
    cleanup(machineId);
  }

  /** Stop all active polling (called on unmount). */
  function stopAll() {
    for (const timer of timers.values()) {
      clearTimeout(timer);
    }
    timers.clear();
    active.clear();
  }

  /** Get monitor info for a specific machine. */
  function getMonitor(machineId: number): WakeMonitor | undefined {
    return monitors.value.get(machineId);
  }

  /** Clear a finished monitor from the display. */
  function dismiss(machineId: number) {
    cleanup(machineId);
    monitors.value.delete(machineId);
    monitors.value = new Map(monitors.value);
  }

  // Cleanup on component unmount — prevents orphaned timers
  onUnmounted(() => {
    stopAll();
  });

  return {
    monitors,
    startPolling,
    stopPolling,
    stopAll,
    getMonitor,
    dismiss,
  };
}
