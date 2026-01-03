import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'projects',
      component: () => import('@/views/ProjectList.vue'),
    },
    {
      path: '/projects/:slug',
      name: 'project-detail',
      component: () => import('@/views/ProjectDetail.vue'),
    },
    {
      path: '/projects/:slug/:recording',
      name: 'recording-editor',
      component: () => import('@/views/RecordingEditor.vue'),
    },
  ],
})

export default router
