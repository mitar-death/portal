// auth-interceptor.js
// A service to handle auth errors consistently across the application

import store from '@/store';
import router from '@/router';

/**
 * Handles authentication errors from API responses with JWT token refresh
 * @param {Response} response - The fetch API response object
 * @param {Object} options - Options for handling the error
 * @param {boolean} options.redirect - Whether to redirect to login page on auth error
 * @param {boolean} options.clearAuth - Whether to clear auth state on auth error
 * @param {boolean} options.retry - Whether this is a retry attempt (prevents infinite loops)
 * @returns {boolean} - Returns true if an auth error was handled
 */
export async function handleAuthError(response, { redirect = true, clearAuth = true, retry = false } = {}) {
    if (response.status === 401) {
        console.warn('Authentication error detected in API response');

        // Try to refresh token if we have a refresh token and this isn't a retry
        if (!retry && store.getters['auth/refreshToken']) {
            try {
                console.log('Attempting token refresh...');
                await store.dispatch('auth/refreshToken');
                console.log('Token refreshed successfully');
                return false; // Don't clear auth, token was refreshed
            } catch (error) {
                console.warn('Token refresh failed:', error.message);
                // Fall through to clear auth and redirect
            }
        }

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
 * Creates a wrapped fetch function that automatically handles auth errors with JWT refresh
 * @param {string} url - The URL to fetch
 * @param {Object} options - Fetch options
 * @param {Object} authOptions - Options for auth error handling
 * @param {boolean} authOptions.retry - Whether this is a retry attempt (internal use)
 * @returns {Promise<Response>} - The fetch response
 */
export async function fetchWithAuth(url, options = {}, authOptions = {}) {
    try {
        // Add auth header if we have an access token and none was provided
        const accessToken = store.getters['auth/accessToken'];
        if (accessToken && !options.headers?.Authorization) {
            options.headers = {
                ...options.headers,
                'Authorization': `Bearer ${accessToken}`
            };
        }

        // Always include credentials
        // options.credentials = 'include';

        const response = await fetch(url, options);

        // Handle auth errors with token refresh
        if (response.status === 401) {
            const wasHandled = await handleAuthError(response, {
                ...authOptions,
                retry: authOptions.retry || false
            });

            // If token was refreshed (wasHandled is false), retry the request once
            if (!wasHandled && !authOptions.retry) {
                console.log('Retrying request after token refresh...');
                // Create fresh options without the old Authorization header so new token gets injected
                const retryOptions = { 
                    ...options, 
                    headers: { ...(options.headers || {}) } 
                };
                // Remove the old Authorization header if it was injected
                delete retryOptions.headers.Authorization;
                return await fetchWithAuth(url, retryOptions, { ...authOptions, retry: true });
            }
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
