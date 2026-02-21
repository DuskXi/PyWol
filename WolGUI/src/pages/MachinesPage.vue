<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="page-title">设备管理</div>
      <q-space />
      <q-btn color="primary" icon="add" label="添加设备" @click="openAddDialog" />
    </div>

    <!-- Toolbar -->
    <q-card flat bordered class="q-mb-md">
      <q-card-section class="q-pa-sm">
        <div class="row items-center q-gutter-sm">
          <q-select v-model="filterGroup" :options="groupOptions" label="按分组筛选" dense outlined clearable style="min-width: 180px" emit-value map-options />
          <q-space />
          <q-btn v-if="selectedIds.length > 0" color="warning" icon="power_settings_new" :label="`批量唤醒 (${selectedIds.length})`" :loading="batchWaking" @click="batchWake" />
          <q-btn flat dense icon="refresh" color="primary" :loading="statusLoading" @click="refreshAllStatus">
            <q-tooltip>刷新在线状态</q-tooltip>
          </q-btn>
        </div>
      </q-card-section>
    </q-card>

    <!-- Machine Table -->
    <q-card flat bordered>
      <q-table :rows="filteredMachines" :columns="columns" row-key="id" flat :loading="loading" selection="multiple" v-model:selected="selected" no-data-label="暂无设备" :pagination="{ rowsPerPage: 15 }">
        <template v-slot:body-cell-status="props">
          <q-td :props="props">
            <span class="status-dot" :class="statusClass(props.row)" />
          </q-td>
        </template>
        <template v-slot:body-cell-group_name="props">
          <q-td :props="props">
            <q-chip v-if="props.row.group_name" dense size="sm" color="primary" text-color="white">
              {{ props.row.group_name }}
            </q-chip>
            <span v-else class="text-grey">未分组</span>
          </q-td>
        </template>
        <template v-slot:body-cell-actions="props">
          <q-td :props="props">
            <q-btn flat dense round icon="power_settings_new" color="positive" :loading="wakingIds.has(props.row.id)" @click="wakeMachine(props.row)">
              <q-tooltip>唤醒</q-tooltip>
            </q-btn>
            <q-btn flat dense round icon="edit" color="primary" @click="openEditDialog(props.row)">
              <q-tooltip>编辑</q-tooltip>
            </q-btn>
            <q-btn flat dense round icon="delete" color="negative" @click="confirmDelete(props.row)">
              <q-tooltip>删除</q-tooltip>
            </q-btn>
          </q-td>
        </template>
      </q-table>
    </q-card>

    <!-- Add/Edit Dialog -->
    <q-dialog v-model="dialogOpen" persistent>
      <q-card style="min-width: 450px">
        <q-card-section>
          <div class="text-h6">{{ editingMachine ? '编辑设备' : '添加设备' }}</div>
        </q-card-section>
        <q-card-section>
          <q-form @submit.prevent="saveMachine" class="q-gutter-sm">
            <q-input v-model="form.name" label="设备名称 *" outlined dense :rules="[v => !!v || '请输入设备名称']" />
            <q-input v-model="form.mac_address" label="MAC 地址 *" outlined dense hint="格式: AA:BB:CC:DD:EE:FF" :rules="[v => !!v || '请输入 MAC 地址', v => /^([0-9A-Fa-f]{2}[:\-]?){5}[0-9A-Fa-f]{2}$/.test(v.replace(/[:\-]/g,'').length === 12 ? v : '') || '请输入有效的 MAC 地址']" />
            <q-input v-model="form.ip_address" label="IP 地址" outlined dense hint="可选，用于检测在线状态" />
            <q-input v-model="form.broadcast_address" label="广播地址" outlined dense />
            <q-input v-model.number="form.port" label="端口" outlined dense type="number" />
            <q-select v-model="form.group_id" :options="groupOptions" label="所属分组" outlined dense clearable emit-value map-options />
            <div class="row justify-end q-gutter-sm q-mt-md">
              <q-btn flat label="取消" @click="dialogOpen = false" />
              <q-btn color="primary" :label="editingMachine ? '保存' : '添加'" type="submit" :loading="saving" />
            </div>
          </q-form>
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useQuasar } from 'quasar';
import { machineApi, groupApi, wakeApi } from 'src/services/api';
import type { Machine, Group } from 'src/types';

const $q = useQuasar();
const loading = ref(false);
const saving = ref(false);
const statusLoading = ref(false);
const batchWaking = ref(false);
const machines = ref<Machine[]>([]);
const groups = ref<Group[]>([]);
const selected = ref<Machine[]>([]);
const filterGroup = ref<number | null>(null);
const wakingIds = ref(new Set<number>());
const statusMap = ref<Record<string, boolean | null>>({});

// Dialog state
const dialogOpen = ref(false);
const editingMachine = ref<Machine | null>(null);
const form = ref({
  name: '',
  mac_address: '',
  ip_address: '',
  broadcast_address: '255.255.255.255',
  port: 9,
  group_id: null as number | null,
});

const selectedIds = computed(() => selected.value.map((m) => m.id));

const groupOptions = computed(() =>
  groups.value.map((g) => ({ label: g.name, value: g.id })),
);

const filteredMachines = computed(() => {
  if (filterGroup.value == null) return machines.value;
  return machines.value.filter((m) => m.group_id === filterGroup.value);
});

const columns = [
  { name: 'status', label: '状态', field: 'id', align: 'center' as const, style: 'width: 50px' },
  { name: 'name', label: '设备名称', field: 'name', align: 'left' as const, sortable: true },
  { name: 'mac_address', label: 'MAC 地址', field: 'mac_address', align: 'left' as const },
  { name: 'ip_address', label: 'IP 地址', field: 'ip_address', align: 'left' as const },
  { name: 'group_name', label: '分组', field: 'group_name', align: 'left' as const },
  { name: 'port', label: '端口', field: 'port', align: 'center' as const },
  { name: 'actions', label: '操作', field: 'id', align: 'center' as const },
];

function statusClass(machine: Machine) {
  const s = statusMap.value[String(machine.id)];
  if (s === true) return 'online';
  if (s === false) return 'offline';
  return 'unknown';
}

function openAddDialog() {
  editingMachine.value = null;
  form.value = {
    name: '',
    mac_address: '',
    ip_address: '',
    broadcast_address: '255.255.255.255',
    port: 9,
    group_id: null,
  };
  dialogOpen.value = true;
}

function openEditDialog(machine: Machine) {
  editingMachine.value = machine;
  form.value = {
    name: machine.name,
    mac_address: machine.mac_address,
    ip_address: machine.ip_address,
    broadcast_address: machine.broadcast_address,
    port: machine.port,
    group_id: machine.group_id,
  };
  dialogOpen.value = true;
}

async function saveMachine() {
  saving.value = true;
  try {
    if (editingMachine.value) {
      await machineApi.update(editingMachine.value.id, form.value);
      $q.notify({ type: 'positive', message: '设备更新成功' });
    } else {
      await machineApi.create(form.value);
      $q.notify({ type: 'positive', message: '设备添加成功' });
    }
    dialogOpen.value = false;
    await loadData();
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '操作失败';
    $q.notify({ type: 'negative', message: msg });
  } finally {
    saving.value = false;
  }
}

function confirmDelete(machine: Machine) {
  $q.dialog({
    title: '确认删除',
    message: `确定要删除设备 "${machine.name}" 吗？此操作不可恢复。`,
    cancel: { label: '取消', flat: true },
    ok: { label: '删除', color: 'negative' },
  }).onOk(() => {
    machineApi.delete(machine.id).then(async () => {
      $q.notify({ type: 'positive', message: '设备已删除' });
      await loadData();
    }).catch(() => {
      $q.notify({ type: 'negative', message: '删除失败' });
    });
  });
}

async function wakeMachine(machine: Machine) {
  wakingIds.value.add(machine.id);
  try {
    await machineApi.wake(machine.id);
    $q.notify({ type: 'positive', message: `已发送唤醒包至 ${machine.name}` });
  } catch {
    $q.notify({ type: 'negative', message: `唤醒 ${machine.name} 失败` });
  } finally {
    wakingIds.value.delete(machine.id);
  }
}

async function batchWake() {
  batchWaking.value = true;
  try {
    await wakeApi.batch(selectedIds.value);
    $q.notify({ type: 'positive', message: `已发送唤醒包至 ${selectedIds.value.length} 台设备` });
    selected.value = [];
  } catch {
    $q.notify({ type: 'negative', message: '批量唤醒失败' });
  } finally {
    batchWaking.value = false;
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

async function loadData() {
  loading.value = true;
  try {
    const [machRes, grpRes] = await Promise.all([
      machineApi.list(),
      groupApi.list(),
    ]);
    machines.value = machRes.data;
    groups.value = grpRes.data;
  } catch {
    $q.notify({ type: 'negative', message: '加载数据失败' });
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadData();
});
</script>
