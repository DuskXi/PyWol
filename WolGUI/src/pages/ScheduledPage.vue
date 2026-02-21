<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="page-title">定时任务</div>
      <q-space />
      <q-btn color="primary" icon="add" label="新建任务" @click="openAddDialog" />
    </div>

    <q-card flat bordered>
      <q-table :rows="tasks" :columns="columns" row-key="id" flat :loading="loading" no-data-label="暂无定时任务" :pagination="{ rowsPerPage: 15 }">
        <template v-slot:body-cell-enabled="props">
          <q-td :props="props">
            <q-toggle v-model="props.row.enabled" @update:model-value="(val: boolean) => toggleEnabled(props.row, val)" color="positive" />
          </q-td>
        </template>
        <template v-slot:body-cell-target="props">
          <q-td :props="props">
            <q-chip dense size="sm" :color="props.row.target_type === 'machine' ? 'primary' : 'accent'" text-color="white" :icon="props.row.target_type === 'machine' ? 'computer' : 'folder'">
              {{ props.row.target_name }}
            </q-chip>
          </q-td>
        </template>
        <template v-slot:body-cell-schedule="props">
          <q-td :props="props">
            <div v-if="props.row.cron_expression">
              <q-icon name="repeat" size="xs" class="q-mr-xs" />
              <code>{{ props.row.cron_expression }}</code>
            </div>
            <div v-else-if="props.row.scheduled_time">
              <q-icon name="event" size="xs" class="q-mr-xs" />
              {{ formatTime(props.row.scheduled_time) }}
            </div>
          </q-td>
        </template>
        <template v-slot:body-cell-actions="props">
          <q-td :props="props">
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
      <q-card style="min-width: 500px">
        <q-card-section>
          <div class="text-h6">{{ editingTask ? '编辑定时任务' : '新建定时任务' }}</div>
        </q-card-section>
        <q-card-section>
          <q-form @submit.prevent="saveTask" class="q-gutter-sm">
            <q-input v-model="form.name" label="任务名称 *" outlined dense :rules="[v => !!v || '请输入任务名称']" />

            <!-- Schedule type -->
            <q-option-group v-model="scheduleType" :options="scheduleTypeOptions" inline class="q-mb-sm" />

            <q-input v-if="scheduleType === 'cron'" v-model="form.cron_expression" label="Cron 表达式 *" outlined dense hint="格式: 分 时 日 月 星期 (例: 0 8 * * 1-5 表示工作日8点)" :rules="[v => !!v || '请输入 Cron 表达式']" />

            <q-input v-if="scheduleType === 'once'" v-model="form.scheduled_time" label="执行时间 *" outlined dense type="datetime-local" :rules="[v => !!v || '请选择执行时间']" />

            <!-- Target -->
            <q-select v-model="form.target_type" :options="targetTypeOptions" label="目标类型" outlined dense emit-value map-options />

            <q-select v-model="form.target_id" :options="targetOptions" label="选择目标 *" outlined dense emit-value map-options :rules="[v => v != null || '请选择目标']" />

            <q-toggle v-model="form.enabled" label="启用任务" color="positive" />

            <div class="row justify-end q-gutter-sm q-mt-md">
              <q-btn flat label="取消" @click="dialogOpen = false" />
              <q-btn color="primary" :label="editingTask ? '保存' : '创建'" type="submit" :loading="saving" />
            </div>
          </q-form>
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useQuasar } from 'quasar';
import { scheduledApi, machineApi, groupApi } from 'src/services/api';
import type { ScheduledTask, Machine, Group } from 'src/types';

const $q = useQuasar();
const loading = ref(false);
const saving = ref(false);
const tasks = ref<ScheduledTask[]>([]);
const machines = ref<Machine[]>([]);
const groups = ref<Group[]>([]);

const dialogOpen = ref(false);
const editingTask = ref<ScheduledTask | null>(null);
const scheduleType = ref<'cron' | 'once'>('cron');

const form = ref({
  name: '',
  cron_expression: '',
  scheduled_time: '',
  target_type: 'machine' as 'machine' | 'group',
  target_id: null as number | null,
  enabled: true,
});

const scheduleTypeOptions = [
  { label: '周期执行 (Cron)', value: 'cron' },
  { label: '单次执行', value: 'once' },
];

const targetTypeOptions = [
  { label: '单台设备', value: 'machine' },
  { label: '设备分组', value: 'group' },
];

const targetOptions = computed(() => {
  if (form.value.target_type === 'machine') {
    return machines.value.map((m) => ({ label: m.name, value: m.id }));
  }
  return groups.value.map((g) => ({ label: g.name, value: g.id }));
});

watch(() => form.value.target_type, () => {
  form.value.target_id = null;
});

const columns = [
  { name: 'enabled', label: '状态', field: 'enabled', align: 'center' as const, style: 'width: 80px' },
  { name: 'name', label: '任务名称', field: 'name', align: 'left' as const },
  { name: 'schedule', label: '执行计划', field: 'cron_expression', align: 'left' as const },
  { name: 'target', label: '目标', field: 'target_name', align: 'left' as const },
  { name: 'actions', label: '操作', field: 'id', align: 'center' as const },
];

function formatTime(iso: string) {
  if (!iso) return '';
  return new Date(iso).toLocaleString('zh-CN');
}

function openAddDialog() {
  editingTask.value = null;
  scheduleType.value = 'cron';
  form.value = {
    name: '',
    cron_expression: '',
    scheduled_time: '',
    target_type: 'machine',
    target_id: null,
    enabled: true,
  };
  dialogOpen.value = true;
}

function openEditDialog(task: ScheduledTask) {
  editingTask.value = task;
  scheduleType.value = task.cron_expression ? 'cron' : 'once';
  form.value = {
    name: task.name,
    cron_expression: task.cron_expression,
    scheduled_time: task.scheduled_time,
    target_type: task.target_type,
    target_id: task.target_id,
    enabled: task.enabled,
  };
  dialogOpen.value = true;
}

async function saveTask() {
  saving.value = true;
  try {
    const payload = {
      name: form.value.name,
      cron_expression: scheduleType.value === 'cron' ? form.value.cron_expression : '',
      scheduled_time: scheduleType.value === 'once' ? form.value.scheduled_time : '',
      target_type: form.value.target_type,
      target_id: form.value.target_id!,
      enabled: form.value.enabled,
    };

    if (editingTask.value) {
      await scheduledApi.update(editingTask.value.id, payload);
      $q.notify({ type: 'positive', message: '任务更新成功' });
    } else {
      await scheduledApi.create(payload);
      $q.notify({ type: 'positive', message: '任务创建成功' });
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

async function toggleEnabled(task: ScheduledTask, enabled: boolean) {
  try {
    await scheduledApi.update(task.id, { enabled });
    $q.notify({ type: 'info', message: enabled ? '任务已启用' : '任务已禁用' });
  } catch {
    task.enabled = !enabled; // Revert
    $q.notify({ type: 'negative', message: '操作失败' });
  }
}

function confirmDelete(task: ScheduledTask) {
  $q.dialog({
    title: '确认删除',
    message: `确定要删除定时任务 "${task.name}" 吗？`,
    cancel: { label: '取消', flat: true },
    ok: { label: '删除', color: 'negative' },
  }).onOk(() => {
    scheduledApi.delete(task.id).then(async () => {
      $q.notify({ type: 'positive', message: '任务已删除' });
      await loadData();
    }).catch(() => {
      $q.notify({ type: 'negative', message: '删除失败' });
    });
  });
}

async function loadData() {
  loading.value = true;
  try {
    const [taskRes, machRes, grpRes] = await Promise.all([
      scheduledApi.list(),
      machineApi.list(),
      groupApi.list(),
    ]);
    tasks.value = taskRes.data;
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
