export interface Machine {
  id: number;
  name: string;
  mac_address: string;
  ip_address: string;
  broadcast_address: string;
  port: number;
  group_id: number | null;
  group_name: string | null;
  online: boolean | null;
  created_at: string;
  updated_at: string;
}

export interface MachineCreate {
  name: string;
  mac_address: string;
  ip_address?: string;
  broadcast_address?: string;
  port?: number;
  group_id?: number | null;
}

export interface MachineUpdate {
  name?: string;
  mac_address?: string;
  ip_address?: string;
  broadcast_address?: string;
  port?: number;
  group_id?: number | null;
}

export interface Group {
  id: number;
  name: string;
  description: string;
  machine_count: number;
  created_at: string;
  updated_at: string;
}

export interface GroupCreate {
  name: string;
  description?: string;
}

export interface GroupUpdate {
  name?: string;
  description?: string;
}

export interface WakeHistory {
  id: number;
  machine_id: number | null;
  machine_name: string;
  mac_address: string;
  status: string;
  message: string;
  created_at: string;
}

export interface ScheduledTask {
  id: number;
  name: string;
  cron_expression: string;
  scheduled_time: string;
  target_type: 'machine' | 'group';
  target_id: number;
  target_name: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ScheduledTaskCreate {
  name: string;
  cron_expression?: string;
  scheduled_time?: string;
  target_type: 'machine' | 'group';
  target_id: number;
  enabled?: boolean;
}

export interface ScheduledTaskUpdate {
  name?: string;
  cron_expression?: string;
  scheduled_time?: string;
  target_type?: 'machine' | 'group';
  target_id?: number;
  enabled?: boolean;
}
