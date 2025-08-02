import { createRouter, createWebHistory } from 'vue-router'
import store from '../store'
import HomeView from '../views/HomeView.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView
  },
  {
    path: '/groups',
    name: 'groups',
    component: () => import('../views/GroupsView.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/diagnostics',
    name: 'diagnostics',
    component: () => import('../views/DiagnosticsView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/keywords',
    name: 'keywords',
    component: () => import('../views/KeywordsView.vue'),
    meta: {
      requiresAuth: true
    }
  },

  {
    path: '/ai-accounts',
    name: 'aiAccounts',
    component: () => import('../views/AIAccountsView.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/group-ai-assignments',
    name: 'groupAIAssignments',
    component: () => import('../views/GroupAIAssignmentView.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/telegram/groups/:id',
    name: 'telegramGroupDetails',
    component: () => import('../views/TelegramGroupDetails.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue')
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('../views/ProfileView.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../views/SettingsView.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/about',
    name: 'about',
    // route level code-splitting
    // this generates a separate chunk (about.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: () => import('../views/AboutView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

// Navigation guards
router.beforeEach(async (to, from, next) => {
  // Check if the route requires authentication
  if (to.matched.some(record => record.meta.requiresAuth)) {
    // First check if the user is authenticated according to the store
    if (!store.getters['auth/isAuthenticated']) {
      // If not authenticated, redirect to login page with a redirect parameter
      next({
        name: 'login',
        query: {
          from: to.fullPath,
          authChecked: 'true'
        }
      });
      return;
    }

    // If the local state says we're authenticated, validate with the server
    // But only do this check if coming from login or external navigation
    if (from.name !== 'login' && from.name !== null) {
      // For normal navigation between authenticated routes, trust the local state
      // This prevents excessive API calls when navigating between protected routes
      next();
      return;
    }

    try {
      // Coming from login or direct URL, verify auth with server
      const isAuthenticated = await store.dispatch('auth/checkAuthStatus');
      if (isAuthenticated) {
        // Auth confirmed by server, proceed
        next();
      } else {
        // Server says not authenticated, redirect to login
        next({
          name: 'login',
          query: {
            from: to.fullPath,
            sessionExpired: 'true'
          }
        });
      }
    } catch (error) {
      console.error('Auth check error in route guard:', error);
      // On error, assume not authenticated and redirect
      next({
        name: 'login',
        query: {
          from: to.fullPath,
          authChecked: 'true'
        }
      });
    }
  } else {
    // Route doesn't require auth, always proceed
    next();
  }
})

export default router
