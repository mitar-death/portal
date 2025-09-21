// telegram.js - Telegram module for Vuex store
// Handles Telegram groups and related functionality

import { apiUrl } from '@/services/api-service';
import { fetchWithAuth } from '@/services/auth-interceptor';

console.log(`Using API URL in telegram.js: ${apiUrl}`);
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
        async fetchTelegramGroups({ commit, rootGetters }) {
            // Use JWT authentication instead of old token system
            if (!rootGetters['auth/isAuthenticated']) {
                return Promise.reject('Not authenticated')
            }

            try {
                // Use fetchWithAuth for proper JWT handling and token refresh
                const response = await fetchWithAuth(`${apiUrl}/telegram/groups`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })

                if (!response.ok) {
                    throw new Error(`Failed to fetch groups: ${response.status}`)
                }

                const data = await response.json()
                // Handle different response structures
                const groups = data.groups || data.data?.groups || data.data || []
                commit('SET_TELEGRAM_GROUPS', groups)
                return groups
            } catch (error) {
                console.error('Error fetching groups:', error)
                return Promise.reject(error)
            }
        },

        clearGroups({ commit }) {
            commit('CLEAR_GROUPS')
        },

        async fetchKeywords({ commit, rootGetters }) {
            // Use JWT authentication instead of old token system
            if (!rootGetters['auth/isAuthenticated']) {
                return Promise.reject('Not authenticated')
            }

            try {
                // Use fetchWithAuth for proper JWT handling and token refresh
                const response = await fetchWithAuth(`${apiUrl}/keywords`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })

                if (!response.ok) {
                    throw new Error(`Failed to fetch keywords: ${response.status}`)
                }

                const data = await response.json()
                const keywords = data.data?.keywords || data.keywords || []
                commit('SET_KEYWORDS', keywords)
                return keywords
            } catch (error) {
                console.error('Error fetching keywords:', error)
                return Promise.reject(error)
            }
        },

        async addKeyword({ commit, rootGetters }, keyword) {
            // Use JWT authentication instead of old token system
            if (!rootGetters['auth/isAuthenticated']) {
                return Promise.reject('Not authenticated')
            }

            try {
                // Use fetchWithAuth for proper JWT handling and token refresh
                const response = await fetchWithAuth(`${apiUrl}/add/keywords`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ keywords: [keyword] })
                })

                if (!response.ok) {
                    throw new Error(`Failed to add keyword: ${response.status}`)
                }

                const data = await response.json()
                const keywords = data.data?.keywords || data.keywords || []
                commit('SET_KEYWORDS', keywords)
                return keywords
            } catch (error) {
                console.error('Error adding keyword:', error)
                return Promise.reject(error)
            }
        },

        async deleteKeyword({ commit, rootGetters }, keyword) {
            // Use JWT authentication instead of old token system
            if (!rootGetters['auth/isAuthenticated']) {
                return Promise.reject('Not authenticated')
            }

            try {
                // Use fetchWithAuth for proper JWT handling and token refresh
                const response = await fetchWithAuth(`${apiUrl}/delete/keywords`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ keywords: [keyword] })
                })

                if (!response.ok) {
                    throw new Error(`Failed to delete keyword: ${response.status}`)
                }

                const data = await response.json()
                const keywords = data.data?.keywords || data.keywords || []
                commit('SET_KEYWORDS', keywords)
                return keywords
            } catch (error) {
                console.error('Error deleting keyword:', error)
                return Promise.reject(error)
            }
        }
    }
}
