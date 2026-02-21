<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="page-title">唤醒历史</div>
      <q-space />
      <q-btn flat color="negative" icon="delete_sweep" label="清空记录" @click="confirmClear" :disable="rows.length === 0" />
      <q-btn flat color="primary" icon="refresh" class="q-ml-sm" @click="loadData" :loading="loading" />
    </div>

    <q-card flat bordered>
      <q-table :rows="rows" :columns="columns" row-key="id" flat :loading="loading" :pagination="pagination" @request="onRequest" no-data-label="暂无唤醒记录">
        <template v-slot:body-cell-status="props">
          <q-td :props="props">
            <q-chip dense :color="props.row.status === 'success' ? 'positive' : 'negative'" text-color="white" size="sm" :icon="props.row.status === 'success' ? 'check_circle' : 'error'">
              {{ props.row.status === 'success' ? '成功' : '失败' }}
            </q-chip>
          </q-td>
        </template>
        <template v-slot:body-cell-created_at="props">
          <q-td :props="props">
            {{ formatTime(props.row.created_at) }}
          </q-td>
        </template>
      </q-table>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useQuasar } from 'quasar';
import { historyApi } from 'src/services/api';
import type { WakeHistory } from 'src/types';

const $q = useQuasar();
const loading = ref(false);
const rows = ref<WakeHistory[]>([]);
const pagination = ref({
  page: 1,
  rowsPerPage: 15,
  rowsNumber: 0,
  sortBy: '' as string,
  descending: false,
});

const columns = [
  { name: 'created_at', label: '时间', field: 'created_at', align: 'left' as const, sortable: true },
  { name: 'machine_name', label: '设备名称', field: 'machine_name', align: 'left' as const },
  { name: 'mac_address', label: 'MAC 地址', field: 'mac_address', align: 'left' as const },
  { name: 'status', label: '状态', field: 'status', align: 'center' as const },
  { name: 'message', label: '详情', field: 'message', align: 'left' as const },
];

function formatTime(iso: string) {
  if (!iso) return '';
  return new Date(iso).toLocaleString('zh-CN');
}

async function onRequest(props: { pagination: { page: number; rowsPerPage: number; rowsNumber?: number; sortBy: string; descending: boolean } }) {
  const { page, rowsPerPage } = props.pagination;
  loading.value = true;
  try {
    const offset = (page - 1) * rowsPerPage;
    const [hisRes, cntRes] = await Promise.all([
      historyApi.list(rowsPerPage, offset),
      historyApi.count(),
    ]);
    rows.value = hisRes.data;
    pagination.value.page = page;
    pagination.value.rowsPerPage = rowsPerPage;
    pagination.value.rowsNumber = cntRes.data.count;
  } catch {
    $q.notify({ type: 'negative', message: '加载历史记录失败' });
  } finally {
    loading.value = false;
  }
}

function confirmClear() {
  $q.dialog({
    title: '确认清空',
    message: '确定要清空所有唤醒历史记录吗？此操作不可恢复。',
    cancel: { label: '取消', flat: true },
    ok: { label: '清空', color: 'negative' },
  }).onOk(() => {
    historyApi.clear().then(async () => {
      $q.notify({ type: 'positive', message: '历史记录已清空' });
      await loadData();
    }).catch(() => {
      $q.notify({ type: 'negative', message: '清空失败' });
    });
  });
}

async function loadData() {
  await onRequest({ pagination: pagination.value });
}

onMounted(() => {
  void loadData();
});
</script>
