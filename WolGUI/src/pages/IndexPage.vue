<template>
  <q-page class="q-pa-md">
    <!-- Stats Cards -->
    <div class="row q-col-gutter-md q-mb-lg">
      <div class="col-6 col-sm-3">
        <q-card class="stat-card">
          <q-card-section class="text-center">
            <q-icon name="computer" size="2.5rem" color="primary" />
            <div class="text-h4 q-mt-sm text-weight-bold">{{ machines.length }}</div>
            <div class="text-caption text-grey">设备总数</div>
          </q-card-section>
        </q-card>
      </div>
      <div class="col-6 col-sm-3">
        <q-card class="stat-card">
          <q-card-section class="text-center">
            <q-icon name="wifi" size="2.5rem" color="positive" />
            <div class="text-h4 q-mt-sm text-weight-bold">{{ onlineCount }}</div>
            <div class="text-caption text-grey">在线设备</div>
          </q-card-section>
        </q-card>
      </div>
      <div class="col-6 col-sm-3">
        <q-card class="stat-card">
          <q-card-section class="text-center">
            <q-icon name="folder" size="2.5rem" color="accent" />
            <div class="text-h4 q-mt-sm text-weight-bold">{{ groups.length }}</div>
            <div class="text-caption text-grey">设备分组</div>
          </q-card-section>
        </q-card>
      </div>
      <div class="col-6 col-sm-3">
        <q-card class="stat-card">
          <q-card-section class="text-center">
            <q-icon name="flash_on" size="2.5rem" color="warning" />
            <div class="text-h4 q-mt-sm text-weight-bold">{{ historyCount }}</div>
            <div class="text-caption text-grey">唤醒次数</div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Quick Wake Section -->
    <div class="row items-center q-mb-sm">
      <div class="page-title">快速唤醒</div>
      <q-space />
      <q-btn flat dense icon="refresh" label="刷新状态" color="primary" :loading="statusLoading" @click="refreshAllStatus" />
    </div>

    <div class="row q-col-gutter-md q-mb-lg">
      <div v-for="machine in machines" :key="machine.id" class="col-12 col-sm-6 col-md-4 col-lg-3">
        <q-card class="machine-card">
          <q-card-section>
            <div class="row items-center no-wrap q-mb-xs">
              <span class="status-dot q-mr-sm" :class="statusClass(machine)" />
              <div class="text-subtitle1 text-weight-medium ellipsis">{{ machine.name }}</div>
            </div>
            <div class="text-caption text-grey">
              <q-icon name="lan" size="xs" /> {{ machine.mac_address }}
            </div>
            <div v-if="machine.ip_address" class="text-caption text-grey">
              <q-icon name="language" size="xs" /> {{ machine.ip_address }}
            </div>
            <div v-if="machine.group_name" class="q-mt-xs">
              <q-chip dense size="sm" color="primary" text-color="white" icon="folder">
                {{ machine.group_name }}
              </q-chip>
            </div>
          </q-card-section>

          <!-- Wake Monitor Progress -->
          <template v-if="getMonitor(machine.id)">
            <q-separator />
            <q-card-section class="q-py-sm">
              <div class="row items-center no-wrap">
                <q-spinner-dots
                  v-if="!getMonitor(machine.id)?.finished"
                  size="1.2em"
                  color="warning"
                  class="q-mr-sm"
                />
                <q-icon
                  v-else-if="getMonitor(machine.id)?.status === 'online'"
                  name="check_circle"
                  color="positive"
                  size="1.2em"
                  class="q-mr-sm"
                />
                <q-icon
                  v-else
                  name="cancel"
                  color="negative"
                  size="1.2em"
                  class="q-mr-sm"
                />
                <div class="col text-caption">
                  {{ monitorLabel(machine.id) }}
                </div>
                <q-btn
                  v-if="getMonitor(machine.id)?.finished"
                  flat round dense
                  icon="close"
                  size="xs"
                  @click="dismiss(machine.id)"
                />
              </div>
              <q-linear-progress
                v-if="!getMonitor(machine.id)?.finished"
                :value="monitorProgress(machine.id)"
                color="warning"
                rounded
                class="q-mt-xs"
                size="4px"
              />
            </q-card-section>
          </template>

          <q-separator />
          <q-card-actions align="right">
            <q-btn flat dense color="primary" icon="power_settings_new" label="唤醒" :loading="wakingIds.has(machine.id)" @click="wakeMachine(machine)" />
          </q-card-actions>
        </q-card>
      </div>
      <div v-if="machines.length === 0 && !loading" class="col-12 text-center text-grey q-pa-xl">
        <q-icon name="devices" size="4rem" class="q-mb-md" />
        <div class="text-h6">暂无设备</div>
        <div class="q-mb-md">请先添加设备以使用唤醒功能</div>
        <q-btn color="primary" icon="add" label="添加设备" to="/machines" />
      </div>
    </div>

    <!-- Recent History -->
    <div class="page-title q-mb-sm">最近唤醒记录</div>
    <q-card flat bordered>
      <q-table :rows="recentHistory" :columns="historyColumns" flat :rows-per-page-options="[5]" hide-bottom row-key="id" :loading="loading" no-data-label="暂无唤醒记录">
        <template v-slot:body-cell-status="props">
          <q-td :props="props">
            <q-chip dense :color="props.row.status === 'success' ? 'positive' : 'negative'" text-color="white" size="sm">
              {{ props.row.status === 'success' ? '成功' : '失败' }}
            </q-chip>
          </q-td>
        </template>
        <template v-slot:body-cell-created_at="props">
          <q-td :props="props">{{ formatTime(props.row.created_at) }}</q-td>
        </template>
      </q-table>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useQuasar } from 'quasar';
import { machineApi, groupApi, historyApi } from 'src/services/api';
import { useWakeMonitor } from 'src/composables/useWakeMonitor';
import type { Machine, Group, WakeHistory } from 'src/types';

const $q = useQuasar();
const loading = ref(false);
const statusLoading = ref(false);
const machines = ref<Machine[]>([]);
const groups = ref<Group[]>([]);
const recentHistory = ref<WakeHistory[]>([]);
const historyCount = ref(0);
const wakingIds = ref(new Set<number>());
const statusMap = ref<Record<string, boolean | null>>({});

const { startPolling, getMonitor, dismiss } = useWakeMonitor();

const onlineCount = computed(() =>
  machines.value.filter((m) => statusMap.value[String(m.id)] === true).length,
);

const historyColumns = [
  { name: 'created_at', label: '时间', field: 'created_at', align: 'left' as const },
  { name: 'machine_name', label: '设备', field: 'machine_name', align: 'left' as const },
  { name: 'mac_address', label: 'MAC 地址', field: 'mac_address', align: 'left' as const },
  { name: 'status', label: '状态', field: 'status', align: 'center' as const },
  { name: 'message', label: '信息', field: 'message', align: 'left' as const },
];

function statusClass(machine: Machine) {
  // If monitor says online, override
  const mon = getMonitor(machine.id);
  if (mon?.status === 'online') return 'online';

  const s = statusMap.value[String(machine.id)];
  if (s === true) return 'online';
  if (s === false) return 'offline';
  return 'unknown';
}

function monitorLabel(machineId: number): string {
  const mon = getMonitor(machineId);
  if (!mon) return '';
  switch (mon.status) {
    case 'pending': return '准备检测…';
    case 'checking': return `检测中 (${mon.attempts}/${mon.max_attempts})  ${mon.elapsed}s`;
    case 'online': return `设备已上线 (${mon.elapsed}s)`;
    case 'timeout': return `检测超时 (${mon.attempts} 次尝试)`;
    case 'cancelled': return '已取消';
    case 'no_ip': return '未配置 IP，无法检测';
    default: return '';
  }
}

function monitorProgress(machineId: number): number {
  const mon = getMonitor(machineId);
  if (!mon || mon.max_attempts === 0) return 0;
  return mon.attempts / mon.max_attempts;
}

function formatTime(iso: string) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString('zh-CN');
}

async function loadData() {
  loading.value = true;
  try {
    const [machRes, grpRes, hisRes, cntRes] = await Promise.all([
      machineApi.list(),
      groupApi.list(),
      historyApi.list(5),
      historyApi.count(),
    ]);
    machines.value = machRes.data;
    groups.value = grpRes.data;
    recentHistory.value = hisRes.data;
    historyCount.value = cntRes.data.count;
  } catch {
    $q.notify({ type: 'negative', message: '加载数据失败' });
  } finally {
    loading.value = false;
  }
}

async function refreshAllStatus() {
  statusLoading.value = true;
  try {
    const res = await machineApi.statusAll();
    statusMap.value = res.data;
  } catch {
    $q.notify({ type: 'negative', message: '状态检查失败' });
  } finally {
    statusLoading.value = false;
  }
}

async function wakeMachine(machine: Machine) {
  wakingIds.value.add(machine.id);
  try {
    await machineApi.wake(machine.id);
    $q.notify({ type: 'positive', message: `已发送唤醒包至 ${machine.name}` });

    // Start polling the wake monitor for this machine
    startPolling(machine.id);

    // Refresh history
    const [hisRes, cntRes] = await Promise.all([
      historyApi.list(5),
      historyApi.count(),
    ]);
    recentHistory.value = hisRes.data;
    historyCount.value = cntRes.data.count;
  } catch {
    $q.notify({ type: 'negative', message: `唤醒 ${machine.name} 失败` });
  } finally {
    wakingIds.value.delete(machine.id);
  }
}

onMounted(() => {
  void loadData();
});
</script>
