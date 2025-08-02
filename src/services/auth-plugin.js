// auth-plugin.js
// Plugin to add global auth error handling

import { handleAuthError } from './auth-interceptor';
import router from '@/router';
import store from '@/store';

export default {
    install(app) {
        // Add a global property for easy access to auth functions
        app.config.globalProperties.$auth = {
            /**
             * Check if a user is authenticated
             */
            isAuthenticated() {
                return store.getters['auth/isAuthenticated'];
            },

            /**
             * Get the current user
             */
            currentUser() {
                return store.getters['auth/currentUser'];
            },

            /**
             * Handle a 401 error from any component
             */
            async handleAuthError(response, options = {}) {
                return handleAuthError(response, options);
            },

            /**
             * Logout and redirect to login page
             */
            async logout(redirectToLogin = true) {
                await store.dispatch('auth/logout');

                if (redirectToLogin) {
                    router.push({
                        path: '/login',
                        query: { authChecked: 'true' }
                    });
                }
            }
        };

        // Add a global navigation guard for auth protection
        router.beforeEach((to, from, next) => {
            // Check if the route requires authentication
            if (to.matched.some(record => record.meta.requiresAuth)) {
                // If not authenticated, redirect to login
                if (!store.getters['auth/isAuthenticated']) {
                    next({
                        path: '/login',
                        query: { from: to.fullPath, authChecked: 'true' }
                    });
                    return;
                }

                // If we think we're authenticated, verify with backend
                store.dispatch('auth/checkAuthStatus').then(isAuthenticated => {
                    if (!isAuthenticated) {
                        // If backend disagrees, redirect to login
                        next({
                            path: '/login',
                            query: { from: to.fullPath, sessionExpired: 'true' }
                        });
                    } else {
                        // All good, proceed
                        next();
                    }
                }).catch(() => {
                    // On error, assume not authenticated
                    next({
                        path: '/login',
                        query: { from: to.fullPath, authChecked: 'true' }
                    });
                });
            } else {
                // Not a protected route, proceed
                next();
            }
        });
    }
};
