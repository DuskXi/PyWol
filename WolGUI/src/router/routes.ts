import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    children: [
      { path: '', component: () => import('pages/IndexPage.vue') },
      { path: 'machines', component: () => import('pages/MachinesPage.vue') },
      { path: 'groups', component: () => import('pages/GroupsPage.vue') },
      { path: 'history', component: () => import('pages/HistoryPage.vue') },
      { path: 'scheduled', component: () => import('pages/ScheduledPage.vue') },
    ],
  },
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
];

export default routes;
