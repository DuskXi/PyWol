<template>
  <q-layout view="lHh LpR lFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-btn flat dense round icon="menu" aria-label="菜单" @click="toggleDrawer" />
        <q-toolbar-title>
          <q-icon name="power_settings_new" class="q-mr-sm" />
          PyWol
        </q-toolbar-title>
        <q-btn flat round :icon="$q.dark.isActive ? 'light_mode' : 'dark_mode'" @click="$q.dark.toggle()" />
      </q-toolbar>
    </q-header>

    <q-drawer v-model="drawerOpen" show-if-above bordered :width="220">
      <q-list>
        <q-item-label header class="text-weight-bold q-pb-none">导航菜单</q-item-label>
        <q-item v-for="nav in navItems" :key="nav.to" :to="nav.to" clickable v-ripple :active="$route.path === nav.to" active-class="bg-primary text-white">
          <q-item-section avatar>
            <q-icon :name="nav.icon" />
          </q-item-section>
          <q-item-section>{{ nav.label }}</q-item-section>
        </q-item>
      </q-list>

      <q-separator class="q-my-sm" />

      <div class="q-pa-md text-caption text-grey text-center">
        PyWol v0.1.0<br />Wake-on-LAN 管理工具
      </div>
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const drawerOpen = ref(false);

const navItems = [
  { label: '仪表盘', icon: 'dashboard', to: '/' },
  { label: '设备管理', icon: 'computer', to: '/machines' },
  { label: '分组管理', icon: 'folder', to: '/groups' },
  { label: '唤醒历史', icon: 'history', to: '/history' },
  { label: '定时任务', icon: 'schedule', to: '/scheduled' },
];

function toggleDrawer() {
  drawerOpen.value = !drawerOpen.value;
}
</script>
