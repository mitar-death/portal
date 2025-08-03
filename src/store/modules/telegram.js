// telegram.js - Telegram module for Vuex store
// Handles Telegram groups and related functionality
export default {
    namespaced: true,

    state: () => ({
        groups: [],
        keywords: []
    }),

    getters: {
        telegramGroups: state => state.groups,
        keywords: state => state.keywords
    },

    mutations: {
        SET_TELEGRAM_GROUPS(state, groups) {
            state.groups = groups
        },
        SET_KEYWORDS(state, keywords) {
            state.keywords = keywords
        },
        CLEAR_GROUPS(state) {
            state.groups = []
        }
    },

    actions: {
        async fetchTelegramGroups({ commit, rootState }) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`https://104.154.111.44/api/telegram/groups`, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include'
                })

                if (!response.ok) {
                    // If unauthorized, logout
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to fetch groups')
                }

                const data = await response.json()
                commit('SET_TELEGRAM_GROUPS', data.groups)
                return data.groups
            } catch (error) {
                console.error('Error fetching groups:', error)
                return Promise.reject(error)
            }
        },

        clearGroups({ commit }) {
            commit('CLEAR_GROUPS')
        },

        async fetchKeywords({ commit, rootState }) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`https://104.154.111.44/api/keywords`, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include'
                })

                if (!response.ok) {
                    // If unauthorized, logout
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to fetch keywords')
                }

                const data = await response.json()
                commit('SET_KEYWORDS', data.data.keywords)
                return data.data.keywords
            } catch (error) {
                console.error('Error fetching keywords:', error)
                return Promise.reject(error)
            }
        },

        async addKeyword({ commit, rootState, dispatch }, keyword) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`https://104.154.111.44/api/add/keywords`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include',
                    body: JSON.stringify({ keywords: [keyword] })
                })

                if (!response.ok) {
                    // If unauthorized, logout
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to add keyword')
                }

                const data = await response.json()
                commit('SET_KEYWORDS', data.data.keywords)
                return data.data.keywords
            } catch (error) {
                console.error('Error adding keyword:', error)
                return Promise.reject(error)
            }
        },

        async deleteKeyword({ commit, rootState, dispatch }, keyword) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`https://104.154.111.44/api/delete/keywords`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include',
                    body: JSON.stringify({ keywords: [keyword] })
                })

                if (!response.ok) {
                    // If unauthorized, logout
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to delete keyword')
                }

                const data = await response.json()
                commit('SET_KEYWORDS', data.data.keywords)
                return data.data.keywords
            } catch (error) {
                console.error('Error deleting keyword:', error)
                return Promise.reject(error)
            }
        }
    }
}
