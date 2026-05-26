import { createRouter, createWebHistory } from 'vue-router'
import { useAppStore, type CurrentUser } from '../stores/app'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginPage.vue'),
      meta: { public: true },
    },
    {
      path: '/student',
      name: 'student',
      component: () => import('../App.vue'),
      meta: { roleMode: 'student' },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../App.vue'),
      meta: { roleMode: 'admin', requiresAdmin: true },
    },
    {
      path: '/',
      redirect: '/student',
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/student',
    },
  ],
})

async function fetchCurrentUser(): Promise<CurrentUser | null> {
  try {
    const response = await fetch('/api/auth/me', {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return null
    const payload = await response.json()
    return (payload.data || payload) as CurrentUser
  } catch {
    return null
  }
}

router.beforeEach(async to => {
  const store = useAppStore()
  const user = await fetchCurrentUser()
  store.setCurrentUser(user)

  if (to.meta.public) {
    if (!user) return true
    return user.role === 'admin' ? '/admin' : '/student'
  }

  if (!user) return '/login'
  if (to.meta.requiresAdmin && user.role !== 'admin') return '/student'

  const roleMode = to.meta.roleMode
  if (roleMode === 'student' || roleMode === 'admin') {
    store.switchRole(roleMode)
  }

  return true
})

export default router
