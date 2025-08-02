// auth.js - Authentication module for Vuex store
// Handles user authentication state and related actions

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
        async checkAuthStatus({ commit, dispatch }) {
            try {
                const response = await fetch('/api/auth/status', {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                if (!response.ok) {
                    throw new Error('Failed to fetch auth status');
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
                }

                return false;
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
        },

        async logout({ commit, dispatch, rootState }) {
            try {
                const response = await fetch('/api/auth/logout', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include'
                })

                if (!response.ok) {
                    console.error('Logout failed:', response.statusText)
                    return Promise.reject('Logout failed')
                }

                localStorage.removeItem('tgportal_user')
                localStorage.removeItem('tgportal_token')

                // Update state
                commit('CLEAR_AUTH')

                // Clear other store data
                dispatch('telegram/clearGroups', null, { root: true })

                return Promise.resolve()
            } catch (error) {
                console.error('Error during logout:', error)
                return Promise.reject(error)
            }
        }
    }
}
