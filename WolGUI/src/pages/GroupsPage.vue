<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="page-title">分组管理</div>
      <q-space />
      <q-btn color="primary" icon="add" label="新建分组" @click="openAddDialog" />
    </div>

    <div class="row q-col-gutter-md">
      <div v-for="group in groups" :key="group.id" class="col-12 col-sm-6 col-md-4">
        <q-card class="group-card">
          <q-card-section>
            <div class="row items-center no-wrap">
              <q-icon name="folder" size="md" color="primary" class="q-mr-sm" />
              <div>
                <div class="text-subtitle1 text-weight-bold">{{ group.name }}</div>
                <div v-if="group.description" class="text-caption text-grey">{{ group.description }}</div>
              </div>
              <q-space />
              <q-chip dense color="primary" text-color="white">
                {{ group.machine_count }} 台设备
              </q-chip>
            </div>
          </q-card-section>

          <!-- Expandable machine list -->
          <q-expansion-item icon="computer" :label="`查看设备 (${group.machine_count})`" header-class="text-primary" dense v-if="group.machine_count > 0">
            <q-card>
              <q-list dense separator>
                <q-item v-for="machine in groupMachines[group.id] || []" :key="machine.id">
                  <q-item-section avatar>
                    <q-icon name="computer" size="sm" />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label>{{ machine.name }}</q-item-label>
                    <q-item-label caption>{{ machine.mac_address }}</q-item-label>
                  </q-item-section>
                  <q-item-section side>
                    <q-btn flat dense round icon="power_settings_new" color="positive" size="sm" @click="wakeSingleMachine(machine)">
                      <q-tooltip>唤醒</q-tooltip>
                    </q-btn>
                  </q-item-section>
                </q-item>
              </q-list>
            </q-card>
          </q-expansion-item>

          <q-separator />
          <q-card-actions align="right">
            <q-btn flat dense color="positive" icon="power_settings_new" label="全部唤醒" :loading="wakingGroups.has(group.id)" @click="wakeGroup(group)" :disable="group.machine_count === 0" />
            <q-btn flat dense color="primary" icon="edit" @click="openEditDialog(group)">
              <q-tooltip>编辑</q-tooltip>
            </q-btn>
            <q-btn flat dense color="negative" icon="delete" @click="confirmDelete(group)">
              <q-tooltip>删除</q-tooltip>
            </q-btn>
          </q-card-actions>
        </q-card>
      </div>

      <div v-if="groups.length === 0 && !loading" class="col-12 text-center text-grey q-pa-xl">
        <q-icon name="folder_off" size="4rem" class="q-mb-md" />
        <div class="text-h6">暂无分组</div>
        <div class="q-mb-md">创建分组来管理你的设备</div>
        <q-btn color="primary" icon="add" label="新建分组" @click="openAddDialog" />
      </div>
    </div>

    <!-- Add/Edit Dialog -->
    <q-dialog v-model="dialogOpen" persistent>
      <q-card style="min-width: 400px">
        <q-card-section>
          <div class="text-h6">{{ editingGroup ? '编辑分组' : '新建分组' }}</div>
        </q-card-section>
        <q-card-section>
          <q-form @submit.prevent="saveGroup" class="q-gutter-sm">
            <q-input v-model="form.name" label="分组名称 *" outlined dense :rules="[v => !!v || '请输入分组名称']" />
            <q-input v-model="form.description" label="描述" outlined dense type="textarea" autogrow />
            <div class="row justify-end q-gutter-sm q-mt-md">
              <q-btn flat label="取消" @click="dialogOpen = false" />
              <q-btn color="primary" :label="editingGroup ? '保存' : '创建'" type="submit" :loading="saving" />
            </div>
          </q-form>
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useQuasar } from 'quasar';
import { groupApi, machineApi } from 'src/services/api';
import type { Group, Machine } from 'src/types';

const $q = useQuasar();
const loading = ref(false);
const saving = ref(false);
const groups = ref<Group[]>([]);
const groupMachines = ref<Record<number, Machine[]>>({});
const wakingGroups = ref(new Set<number>());

const dialogOpen = ref(false);
const editingGroup = ref<Group | null>(null);
const form = ref({ name: '', description: '' });

function openAddDialog() {
  editingGroup.value = null;
  form.value = { name: '', description: '' };
  dialogOpen.value = true;
}

function openEditDialog(group: Group) {
  editingGroup.value = group;
  form.value = { name: group.name, description: group.description };
  dialogOpen.value = true;
}

async function saveGroup() {
  saving.value = true;
  try {
    if (editingGroup.value) {
      await groupApi.update(editingGroup.value.id, form.value);
      $q.notify({ type: 'positive', message: '分组更新成功' });
    } else {
      await groupApi.create(form.value);
      $q.notify({ type: 'positive', message: '分组创建成功' });
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

function confirmDelete(group: Group) {
  $q.dialog({
    title: '确认删除',
    message: `确定要删除分组 "${group.name}" 吗？组内设备不会被删除，但会变为未分组状态。`,
    cancel: { label: '取消', flat: true },
    ok: { label: '删除', color: 'negative' },
  }).onOk(() => {
    groupApi.delete(group.id).then(async () => {
      $q.notify({ type: 'positive', message: '分组已删除' });
      await loadData();
    }).catch(() => {
      $q.notify({ type: 'negative', message: '删除失败' });
    });
  });
}

async function wakeGroup(group: Group) {
  wakingGroups.value.add(group.id);
  try {
    await groupApi.wake(group.id);
    $q.notify({ type: 'positive', message: `已发送唤醒包至分组 "${group.name}" 的所有设备` });
  } catch {
    $q.notify({ type: 'negative', message: '分组唤醒失败' });
  } finally {
    wakingGroups.value.delete(group.id);
  }
}

async function wakeSingleMachine(machine: Machine) {
  try {
    await machineApi.wake(machine.id);
    $q.notify({ type: 'positive', message: `已发送唤醒包至 ${machine.name}` });
  } catch {
    $q.notify({ type: 'negative', message: `唤醒 ${machine.name} 失败` });
  }
}

async function loadGroupMachines() {
  for (const group of groups.value) {
    if (group.machine_count > 0) {
      try {
        const res = await groupApi.machines(group.id);
        groupMachines.value[group.id] = res.data;
      } catch {
        // Ignore
      }
    }
  }
}

async function loadData() {
  loading.value = true;
  try {
    const res = await groupApi.list();
    groups.value = res.data;
    await loadGroupMachines();
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
