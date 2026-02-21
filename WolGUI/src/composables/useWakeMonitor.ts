/**
 * Composable for polling wake-monitor status after sending a WOL packet.
 *
 * Anti-storm design:
 *   - Only ONE poll timer per machine_id (Map keyed by id).
 *   - Timer auto-stops when backend reports `finished === true`.
 *   - All timers are cleared on component unmount (`onUnmounted`).
 *   - Fixed, non-overlapping interval (waits for response before scheduling next).
 */

import { ref, onUnmounted } from 'vue';
import { wakeApi } from 'src/services/api';
import type { WakeMonitor } from 'src/types';

const POLL_INTERVAL = 5_000; // 5 seconds

export function useWakeMonitor() {
  const monitors = ref<Map<number, WakeMonitor>>(new Map());
  const timers = new Map<number, ReturnType<typeof setTimeout>>();

  /** Start polling the monitor status for a machine. */
  function startPolling(machineId: number) {
    // If already polling this machine, don't double-up
    if (timers.has(machineId)) return;
    void poll(machineId);
  }

  /** Single poll cycle — fetches status, updates map, reschedules if needed. */
  async function poll(machineId: number) {
    try {
      const res = await wakeApi.monitor(machineId);
      const data = res.data;
      monitors.value.set(machineId, data);
      // Trigger Vue reactivity (Map mutations aren't deeply reactive in ref)
      monitors.value = new Map(monitors.value);

      if (data.finished) {
        // Terminal state — stop polling, auto-remove after a short display period
        stopPolling(machineId);
        setTimeout(() => {
          monitors.value.delete(machineId);
          monitors.value = new Map(monitors.value);
        }, 30_000); // keep showing result for 30s
        return;
      }
    } catch {
      // API error — stop to avoid hammering a broken endpoint
      stopPolling(machineId);
      return;
    }

    // Schedule next poll
    const timer = setTimeout(() => {
      void poll(machineId);
    }, POLL_INTERVAL);
    timers.set(machineId, timer);
  }

  /** Stop polling for a specific machine. */
  function stopPolling(machineId: number) {
    const timer = timers.get(machineId);
    if (timer) {
      clearTimeout(timer);
      timers.delete(machineId);
    }
  }

  /** Stop all active polling (called on unmount). */
  function stopAll() {
    for (const timer of timers.values()) {
      clearTimeout(timer);
    }
    timers.clear();
  }

  /** Get monitor info for a specific machine. */
  function getMonitor(machineId: number): WakeMonitor | undefined {
    return monitors.value.get(machineId);
  }

  /** Clear a finished monitor from the display. */
  function dismiss(machineId: number) {
    stopPolling(machineId);
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
