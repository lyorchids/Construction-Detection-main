import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Home',
      component: () => import('../views/Home.vue'),
    },
    {
      path: '/image-detect',
      name: 'ImageDetect',
      component: () => import('../views/ImageDetect.vue'),
    },
    {
      path: '/video-detect',
      name: 'VideoDetect',
      component: () => import('../views/VideoDetect.vue'),
    },
    {
      path: '/history',
      name: 'History',
      component: () => import('../views/History.vue'),
    },
    {
      path: '/detail/:id',
      name: 'Detail',
      component: () => import('../views/Detail.vue'),
    },
    {
      path: '/cases',
      name: 'CaseList',
      component: () => import('../views/CaseList.vue'),
    },
    {
      path: '/cases/create',
      name: 'CaseCreate',
      component: () => import('../views/CaseCreate.vue'),
    },
    {
      path: '/cases/:id',
      name: 'CaseDetail',
      component: () => import('../views/CaseDetail.vue'),
    },
    {
      path: '/profiles',
      name: 'Profiles',
      component: () => import('../views/DetectionProfiles.vue'),
    },
  ],
})

export default router
