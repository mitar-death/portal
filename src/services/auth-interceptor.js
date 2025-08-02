// auth-interceptor.js
// A service to handle auth errors consistently across the application

import store from '@/store';
import router from '@/router';

/**
 * Handles authentication errors from API responses
 * @param {Response} response - The fetch API response object
 * @param {Object} options - Options for handling the error
 * @param {boolean} options.redirect - Whether to redirect to login page on auth error
 * @param {boolean} options.clearAuth - Whether to clear auth state on auth error
 * @returns {boolean} - Returns true if an auth error was handled
 */
export async function handleAuthError(response, { redirect = true, clearAuth = true } = {}) {
    if (response.status === 401) {
        console.warn('Authentication error detected in API response');

        // Clear auth state if requested
        if (clearAuth && store.getters['auth/isAuthenticated']) {
            await store.dispatch('auth/logout');
            console.log('Cleared auth state due to 401 error');
        }

        // Redirect to login page if requested
        if (redirect) {
            const currentPath = router.currentRoute.value.path;
            if (currentPath !== '/login') {
                router.push({
                    path: '/login',
                    query: {
                        from: currentPath,
                        sessionExpired: 'true'
                    }
                });
                console.log('Redirected to login page due to 401 error');
            }
        }

        return true;
    }

    return false;
}

/**
 * Creates a wrapped fetch function that automatically handles auth errors
 * @param {string} url - The URL to fetch
 * @param {Object} options - Fetch options
 * @param {Object} authOptions - Options for auth error handling
 * @returns {Promise<Response>} - The fetch response
 */
export async function fetchWithAuth(url, options = {}, authOptions = {}) {
    try {
        // Add auth header if we have a token
        const token = store.getters['auth/authToken'];
        if (token) {
            options.headers = {
                ...options.headers,
                'Authorization': `Bearer ${token}`
            };
        }

        // Always include credentials
        options.credentials = 'include';

        const response = await fetch(url, options);

        // Handle auth errors
        if (response.status === 401) {
            await handleAuthError(response, authOptions);
        }

        return response;
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

export default {
    handleAuthError,
    fetchWithAuth
};
