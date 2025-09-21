// auth.js - Authentication module for Vuex store
// Handles user authentication state and related actions
import { fetchWithAuth } from '@/services/auth-interceptor'
import { apiUrl } from '@/services/api-service'

// Load stored authentication data from local storage
const loadStoredAuth = () => {
    try {
        const user = JSON.parse(localStorage.getItem('tgportal_user'))
        const accessToken = localStorage.getItem('tgportal_access_token')
        const refreshToken = localStorage.getItem('tgportal_refresh_token')
        const tokenExpiry = localStorage.getItem('tgportal_token_expiry')
        // Legacy token support for backward compatibility
        const legacyToken = localStorage.getItem('tgportal_token')
        return { user, accessToken: accessToken || legacyToken, refreshToken, tokenExpiry }
    } catch (e) {
        return { user: null, accessToken: null, refreshToken: null, tokenExpiry: null }
    }
}

const { user, accessToken, refreshToken, tokenExpiry } = loadStoredAuth()

// Helper function to check if token is expired
const isTokenExpired = (tokenExpiry) => {
    if (!tokenExpiry) return true
    const expiryTime = new Date(tokenExpiry).getTime()
    const currentTime = Date.now()
    return currentTime >= expiryTime
}

console.log(`Using API URL in auth.js: ${apiUrl}`);
export default {
    namespaced: true,

    state: () => ({
        user,
        accessToken,
        refreshToken,
        tokenExpiry,
        isAuthenticated: !!accessToken && !isTokenExpired(tokenExpiry)
    }),

    getters: {
        isAuthenticated: state => state.isAuthenticated && !!state.accessToken && !isTokenExpired(state.tokenExpiry),
        currentUser: state => state.user,
        authToken: state => state.accessToken,
        accessToken: state => state.accessToken,
        refreshToken: state => state.refreshToken,
        tokenExpiry: state => state.tokenExpiry
    },

    mutations: {
        SET_AUTH(state, { user, accessToken, refreshToken, tokenExpiry }) {
            state.user = user
            state.accessToken = accessToken
            state.refreshToken = refreshToken
            state.tokenExpiry = tokenExpiry
            state.isAuthenticated = !!accessToken && !isTokenExpired(tokenExpiry)
        },
        SET_TOKENS(state, { accessToken, refreshToken, tokenExpiry }) {
            state.accessToken = accessToken
            state.refreshToken = refreshToken
            state.tokenExpiry = tokenExpiry
            state.isAuthenticated = !!accessToken && !isTokenExpired(tokenExpiry)
        },
        CLEAR_AUTH(state) {
            state.user = null
            state.accessToken = null
            state.refreshToken = null
            state.tokenExpiry = null
            state.isAuthenticated = false
        }
    },

    actions: {
        async checkAuthStatus({ commit, dispatch, state, getters }) {
            // If we've already checked auth and have a valid non-expired token/user, avoid unnecessary checks
            if (getters.isAuthenticated && state.user && state.accessToken) {
                return true;
            }

            // If token is expired but we have a refresh token, try to refresh
            if (state.refreshToken && isTokenExpired(state.tokenExpiry)) {
                try {
                    await dispatch('refreshToken')
                    return true
                } catch (error) {
                    console.log('Token refresh failed, clearing auth')
                    commit('CLEAR_AUTH')
                    dispatch('clearAuthStorage')
                }
            }

            try {
                // Use our auth interceptor service instead of raw fetch
                const response = await fetchWithAuth(`${apiUrl}/auth/status`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }, { redirect: false }); // Don't auto-redirect on 401

                if (!response.ok) {
                    // Clear auth state if server reports unauthorized or any other error
                    if (response.status === 401 || response.status >= 500) {
                        // Only clear if we thought we were authenticated
                        if (state.isAuthenticated) {
                            commit('CLEAR_AUTH');
                            dispatch('clearAuthStorage');
                            console.log('Cleared auth state due to server error:', response.status);
                        }
                    }
                    return false;
                }

                const data = await response.json();
                console.log('Auth status:', data);

                if (data.data.is_authorized && data.data.user_info) {
                    // If backend is authenticated but frontend is not,
                    // update the frontend state
                    const localUser = JSON.parse(localStorage.getItem('tgportal_user'));
                    const localToken = localStorage.getItem('tgportal_token');

                    if (!localUser || !localToken) {
                        // Backend says authorized but no local tokens - need to re-authenticate
                        // Don't fabricate tokens, prompt user to login again
                        commit('CLEAR_AUTH');
                        dispatch('clearAuthStorage');
                        return false;
                    }

                    return true;
                } else {
                    // Server says we're not authorized, clear any local auth state
                    if (state.isAuthenticated) {
                        commit('CLEAR_AUTH');
                        dispatch('clearAuthStorage');
                    }
                    return false;
                }
            } catch (error) {
                console.error('Error checking auth status:', error);
                return false;
            }
        },

        loginWithTelegram({ commit, dispatch }, { user, access_token, refresh_token, expires_in, token_type }) {
            // Calculate token expiry
            const tokenExpiry = expires_in ? 
                new Date(Date.now() + (expires_in * 1000)).toISOString() : 
                new Date(Date.now() + (30 * 60 * 1000)).toISOString() // Default 30 min

            // Store in local storage
            localStorage.setItem('tgportal_user', JSON.stringify(user))
            localStorage.setItem('tgportal_access_token', access_token)
            if (refresh_token) {
                localStorage.setItem('tgportal_refresh_token', refresh_token)
            }
            localStorage.setItem('tgportal_token_expiry', tokenExpiry)
            
            // Clean up legacy token
            localStorage.removeItem('tgportal_token')

            // Update state
            commit('SET_AUTH', { 
                user, 
                accessToken: access_token, 
                refreshToken: refresh_token, 
                tokenExpiry 
            })

            return Promise.resolve()
        },
        async logout({ commit, dispatch, state }) {
            try {
                // Clear frontend first
                commit('CLEAR_AUTH')
                dispatch('clearAuthStorage')

                // Clear other store data
                dispatch('telegram/clearGroups', null, { root: true })

                // Call backend only after frontend is clean
                const response = await fetchWithAuth(`${apiUrl}/auth/logout`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${state.accessToken}`
                    }
                }, { redirect: false, clearAuth: false }); // No need to handle auth errors during logout

                if (!response.ok) {
                    console.error('Logout API call failed:', response.statusText)
                    // Frontend is already cleared, so this is fine
                }

                return Promise.resolve()
            } catch (error) {
                console.error('Error during logout:', error)
                // Even if API call fails, we still want to clean up the frontend
                // Already done above, so just resolve
                return Promise.resolve()
            }
        },

        // Token refresh action
        async refreshToken({ commit, state, dispatch }) {
            if (!state.refreshToken) {
                throw new Error('No refresh token available')
            }

            try {
                const response = await fetchWithAuth(`${apiUrl}/auth/refresh`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${state.refreshToken}`
                    }
                }, { redirect: false, clearAuth: false })

                if (!response.ok) {
                    throw new Error('Token refresh failed')
                }

                const data = await response.json()
                
                if (data.success && data.data.access_token) {
                    const tokenExpiry = data.data.expires_in ? 
                        new Date(Date.now() + (data.data.expires_in * 1000)).toISOString() : 
                        new Date(Date.now() + (30 * 60 * 1000)).toISOString()

                    // Update tokens in storage
                    localStorage.setItem('tgportal_access_token', data.data.access_token)
                    if (data.data.refresh_token) {
                        localStorage.setItem('tgportal_refresh_token', data.data.refresh_token)
                    }
                    localStorage.setItem('tgportal_token_expiry', tokenExpiry)

                    // Update state
                    commit('SET_TOKENS', {
                        accessToken: data.data.access_token,
                        refreshToken: data.data.refresh_token || state.refreshToken,
                        tokenExpiry
                    })

                    return true
                } else {
                    throw new Error('Invalid refresh response')
                }
            } catch (error) {
                console.error('Token refresh failed:', error)
                // Clear auth on refresh failure
                commit('CLEAR_AUTH')
                dispatch('clearAuthStorage')
                throw error
            }
        },

        // Helper action to clear all auth storage
        clearAuthStorage() {
            localStorage.removeItem('tgportal_user')
            localStorage.removeItem('tgportal_access_token')
            localStorage.removeItem('tgportal_refresh_token')
            localStorage.removeItem('tgportal_token_expiry')
            // Clean up legacy token
            localStorage.removeItem('tgportal_token')
        }
    }
}
