// auth.js - Authentication module for Vuex store
// Handles user authentication state and related actions
import { fetchWithAuth } from '@/services/auth-interceptor'

// Load stored authentication data from local storage
const loadStoredAuth = () => {
    try {
        const user = JSON.parse(localStorage.getItem('tgportal_user'))
        const token = localStorage.getItem('tgportal_token')
        return { user, token }
    } catch (e) {
        return { user: null, token: null }
    }
}

const { user, token } = loadStoredAuth()

export default {
    namespaced: true,

    state: () => ({
        user,
        token,
        isAuthenticated: !!token
    }),

    getters: {
        isAuthenticated: state => state.isAuthenticated,
        currentUser: state => state.user,
        authToken: state => state.token
    },

    mutations: {
        SET_AUTH(state, { user, token }) {
            state.user = user
            state.token = token
            state.isAuthenticated = !!token
        },
        CLEAR_AUTH(state) {
            state.user = null
            state.token = null
            state.isAuthenticated = false
        }
    },

    actions: {
        async checkAuthStatus({ commit, dispatch, state }) {
            // If we've already checked auth and have a valid token/user, avoid unnecessary checks
            if (state.isAuthenticated && state.user && state.token) {
                return true;
            }

            try {
                // Use our auth interceptor service instead of raw fetch
                const response = await fetchWithAuth("/api/auth/status", {
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
                            localStorage.removeItem('tgportal_user');
                            localStorage.removeItem('tgportal_token');
                            console.log('Cleared auth state due to server error:', response.status);
                        }
                    }
                    return false;
                }

                const data = await response.json();
                console.log('Auth status:', data);

                if (data.is_authorized && data.user_info) {
                    // If backend is authenticated but frontend is not,
                    // update the frontend state
                    const localUser = JSON.parse(localStorage.getItem('tgportal_user'));
                    const localToken = localStorage.getItem('tgportal_token');

                    if (!localUser || !localToken) {
                        // Generate a token based on user id
                        const token = `token_${data.user_info.id}`;
                        const user = {
                            id: data.user_info.id,
                            username: data.user_info.username,
                            first_name: data.user_info.first_name,
                            last_name: data.user_info.last_name,
                            phone_number: data.user_info.phone
                        };

                        // Update local storage and state
                        await dispatch('loginWithTelegram', { user, token });

                        // Call UI module to show a notification
                        dispatch('ui/showSnackbar', {
                            text: 'Reconnected to existing Telegram session',
                            color: 'success'
                        }, { root: true });
                    }

                    return true;
                } else {
                    // Server says we're not authorized, clear any local auth state
                    if (state.isAuthenticated) {
                        commit('CLEAR_AUTH');
                        localStorage.removeItem('tgportal_user');
                        localStorage.removeItem('tgportal_token');
                    }
                    return false;
                }
            } catch (error) {
                console.error('Error checking auth status:', error);
                return false;
            }
        },

        loginWithTelegram({ commit }, { user, token }) {
            // Store in local storage
            localStorage.setItem('tgportal_user', JSON.stringify(user))
            localStorage.setItem('tgportal_token', token)

            // Update state
            commit('SET_AUTH', { user, token })

            return Promise.resolve()
        }, async logout({ commit, dispatch, rootState }) {
            try {
                // Always clear local storage and state first to prevent UI issues
                localStorage.removeItem('tgportal_user')
                localStorage.removeItem('tgportal_token')

                // Update state
                commit('CLEAR_AUTH')

                // Clear other store data
                dispatch('telegram/clearGroups', null, { root: true })

                // Call backend only after frontend is clean
                const response = await fetchWithAuth(`https://104.154.111.44/api/auth/logout`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }, { redirect: false, clearAuth: false }); // No need to handle auth errors during logout

                if (!response.ok) {
                    console.error('Logout API call failed:', response.statusText)
                    // No need to reject since we've already cleared frontend state
                }

                return Promise.resolve()
            } catch (error) {
                console.error('Error during logout:', error)
                // Even if API call fails, we still want to clean up the frontend
                // Already done above, so just resolve
                return Promise.resolve()
            }
        }
    }
}
