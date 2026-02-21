import { api } from 'src/boot/axios';
import type {
  Machine,
  MachineCreate,
  MachineUpdate,
  Group,
  GroupCreate,
  GroupUpdate,
  WakeHistory,
  WakeMonitor,
  ScheduledTask,
  ScheduledTaskCreate,
  ScheduledTaskUpdate,
} from 'src/types';

export const machineApi = {
  list: (groupId?: number) =>
    api.get<Machine[]>('/machines', {
      params: groupId != null ? { group_id: groupId } : {},
    }),
  get: (id: number) => api.get<Machine>(`/machines/${id}`),
  create: (data: MachineCreate) => api.post<Machine>('/machines', data),
  update: (id: number, data: MachineUpdate) =>
    api.put<Machine>(`/machines/${id}`, data),
  delete: (id: number) => api.delete(`/machines/${id}`),
  wake: (id: number) => api.post(`/machines/${id}/wake`),
  status: (id: number) =>
    api.get<{ online: boolean | null; ip_address?: string }>(
      `/machines/${id}/status`,
    ),
  statusAll: () =>
    api.get<Record<string, boolean | null>>('/machines/status/all'),
};

export const groupApi = {
  list: () => api.get<Group[]>('/groups'),
  get: (id: number) => api.get<Group>(`/groups/${id}`),
  create: (data: GroupCreate) => api.post<Group>('/groups', data),
  update: (id: number, data: GroupUpdate) =>
    api.put<Group>(`/groups/${id}`, data),
  delete: (id: number) => api.delete(`/groups/${id}`),
  machines: (id: number) => api.get<Machine[]>(`/groups/${id}/machines`),
  wake: (id: number) => api.post(`/groups/${id}/wake`),
};

export const historyApi = {
  list: (limit = 50, offset = 0) =>
    api.get<WakeHistory[]>('/history', { params: { limit, offset } }),
  count: () => api.get<{ count: number }>('/history/count'),
  clear: () => api.delete('/history'),
};

export const scheduledApi = {
  list: () => api.get<ScheduledTask[]>('/scheduled'),
  create: (data: ScheduledTaskCreate) =>
    api.post<ScheduledTask>('/scheduled', data),
  update: (id: number, data: ScheduledTaskUpdate) =>
    api.put<ScheduledTask>(`/scheduled/${id}`, data),
  delete: (id: number) => api.delete(`/scheduled/${id}`),
};

export const wakeApi = {
  batch: (machineIds: number[]) =>
    api.post('/wake/batch', { machine_ids: machineIds }),
  monitors: () => api.get<WakeMonitor[]>('/wake/monitors'),
  monitor: (machineId: number) =>
    api.get<WakeMonitor>(`/wake/monitors/${machineId}`),
  cancelMonitor: (machineId: number) =>
    api.delete(`/wake/monitors/${machineId}`),
};
