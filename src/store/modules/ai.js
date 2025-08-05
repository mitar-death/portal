// ai.js - AI module for Vuex store

import { apiUrl } from '@/services/api-service';

console.log("API URL in ai.js:", apiUrl);

export default {
    namespaced: true,

    state: () => ({
        accounts: [],
        groupAssignments: []
    }),

    getters: {
        aiAccounts: state => state.accounts,
        groupAssignments: state => state.groupAssignments
    },

    mutations: {
        SET_AI_ACCOUNTS(state, accounts) {
            state.accounts = accounts
        },
        SET_GROUP_ASSIGNMENTS(state, assignments) {
            state.groupAssignments = assignments
        }
    },

    actions: {
        // AI Account Actions
        async fetchAIAccounts({ commit, rootState }) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`${apiUrl}/ai/accounts`, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include'
                })

                if (!response.ok) {
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to fetch AI accounts')
                }

                const data = await response.json()
                const accounts = data.data.accounts || []

                commit('SET_AI_ACCOUNTS', accounts)
                return accounts
            } catch (error) {
                console.error('Error fetching AI accounts:', error)
                return Promise.reject(error)
            }
        },

        async createAIAccount({ rootState, dispatch }, newAccount) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`${apiUrl}/ai/accounts`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include',
                    body: JSON.stringify(newAccount)
                })

                if (!response.ok) {
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to create AI account')
                }

                const result = await response.json()

                if (result.success) {
                    // Fetch updated accounts list
                    await dispatch('fetchAIAccounts')
                    dispatch('ui/showSnackbar', {
                        text: 'AI account created successfully',
                        color: 'success'
                    }, { root: true })
                    return result
                } else {
                    dispatch('ui/showSnackbar', {
                        text: result.message || 'Failed to create account',
                        color: 'error'
                    }, { root: true })
                    return Promise.reject(result.message)
                }
            } catch (error) {
                console.error('Error creating AI account:', error)
                dispatch('ui/showSnackbar', {
                    text: 'An error occurred while creating the account',
                    color: 'error'
                }, { root: true })
                return Promise.reject(error)
            }
        },

        async updateAIAccount({ rootState, dispatch }, { accountId, isActive }) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`${apiUrl}/ai/accounts`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        account_id: accountId,
                        is_active: isActive
                    })
                })

                if (!response.ok) {
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to update AI account')
                }

                const result = await response.json()

                if (result.success) {
                    // Update the account in the store
                    dispatch('fetchAIAccounts')
                    dispatch('ui/showSnackbar', {
                        text: `Account ${isActive ? 'activated' : 'deactivated'}`,
                        color: 'success'
                    }, { root: true })
                    return result
                } else {
                    dispatch('ui/showSnackbar', {
                        text: result.error || 'Failed to update account status',
                        color: 'error'
                    }, { root: true })
                    return Promise.reject(result.error)
                }
            } catch (error) {
                console.error('Error updating AI account:', error)
                dispatch('ui/showSnackbar', {
                    text: 'An error occurred while updating the account',
                    color: 'error'
                }, { root: true })
                return Promise.reject(error)
            }
        },

        async deleteAIAccount({ rootState, dispatch }, accountId) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`${apiUrl}/ai/accounts/delete`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        account_id: accountId
                    })
                })

                if (!response.ok) {
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to delete AI account')
                }

                const result = await response.json()

                if (result.success) {
                    // Fetch updated accounts list
                    await dispatch('fetchAIAccounts')
                    dispatch('ui/showSnackbar', {
                        text: 'Account deleted successfully',
                        color: 'success'
                    }, { root: true })
                    return result
                } else {
                    dispatch('ui/showSnackbar', {
                        text: result.error || 'Failed to delete account',
                        color: 'error'
                    }, { root: true })
                    return Promise.reject(result.error)
                }
            } catch (error) {
                console.error('Error deleting AI account:', error)
                dispatch('ui/showSnackbar', {
                    text: 'An error occurred while deleting the account',
                    color: 'error'
                }, { root: true })
                return Promise.reject(error)
            }
        },

        async testAIAccount({ rootState, dispatch }, accountId) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`${apiUrl}/ai/accounts/test`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        account_id: accountId
                    })
                })

                if (!response.ok) {
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to test AI account')
                }

                const data = await response.json()
                const result = {
                    success: data.success,
                    is_authorized: data.data.is_authorized,
                    message: data.message,
                }
                return result
            } catch (error) {
                console.error('Error testing AI account:', error)
                dispatch('ui/showSnackbar', {
                    text: 'An error occurred while testing the account',
                    color: 'error'
                }, { root: true })
                return Promise.reject(error)
            }
        },

        async loginAIAccount({ rootState, dispatch }, { accountId, action, phoneCode, password }) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const payload = {
                    account_id: accountId,
                    action: action // 'request_code' or 'verify_code'
                }

                // Add phone code for verification step
                if (action === 'verify_code' && phoneCode) {
                    payload.phone_code = phoneCode
                }

                // Add password for 2FA if provided
                if (password) {
                    payload.password = password
                }

                const response = await fetch(`${apiUrl}/ai/accounts/login`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include',
                    body: JSON.stringify(payload)
                })

                if (!response.ok) {
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to login AI account')
                }

                const data = await response.json()

                if (data.success) {
                    if (action === 'request_code') {
                        dispatch('ui/showSnackbar', {
                            text: 'Verification code sent. Please check your Telegram app.',
                            color: 'info'
                        }, { root: true })
                    } else if (action === 'verify_code') {
                        dispatch('ui/showSnackbar', {
                            text: 'Account successfully logged in',
                            color: 'success'
                        }, { root: true })
                    }
                } else {
                    dispatch('ui/showSnackbar', {
                        text: data.data.details || 'Login action failed',
                        color: 'error'
                    }, { root: true })
                }

                return data
            } catch (error) {
                console.error('Error in AI account login process:', error.details)
                dispatch('ui/showSnackbar', {
                    text: 'An error occurred during the login process',
                    color: 'error'
                }, { root: true })
                return Promise.reject(error)
            }
        },

        async logoutAIAccount({ rootState, dispatch }, accountId) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`${apiUrl}/ai/accounts/logout`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        account_id: accountId
                    })
                })

                if (!response.ok) {
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to logout AI account')
                }

                const result = await response.json()

                if (result.success) {
                    // Fetch updated accounts list to refresh session status
                    await dispatch('fetchAIAccounts')
                    dispatch('ui/showSnackbar', {
                        text: result.message || 'Account logged out successfully',
                        color: 'success'
                    }, { root: true })
                    return result
                } else {
                    dispatch('ui/showSnackbar', {
                        text: result.message || 'Failed to logout account',
                        color: 'error'
                    }, { root: true })
                    return Promise.reject(result.message)
                }
            } catch (error) {
                console.error('Error logging out AI account:', error.details)
                dispatch('ui/showSnackbar', {
                    text: 'An error occurred while logging out the account',
                    color: 'error'
                }, { root: true })
                return Promise.reject(error)
            }
        },

        async cleanupAISessions({ rootState, dispatch }) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`${apiUrl}/ai/accounts/cleanup-sessions`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include'
                })

                if (!response.ok) {
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to cleanup AI sessions')
                }

                const result = await response.json()

                if (result.success) {
                    // Fetch updated accounts list to refresh session status
                    await dispatch('fetchAIAccounts')
                    dispatch('ui/showSnackbar', {
                        text: result.message || 'Sessions cleaned up successfully',
                        color: 'success'
                    }, { root: true })
                    return result
                } else {
                    dispatch('ui/showSnackbar', {
                        text: result.message || 'Failed to cleanup sessions',
                        color: 'error'
                    }, { root: true })
                    return Promise.reject(result.message)
                }
            } catch (error) {
                console.error('Error cleaning up AI sessions:', error)
                dispatch('ui/showSnackbar', {
                    text: 'An error occurred while cleaning up sessions',
                    color: 'error'
                }, { root: true })
                return Promise.reject(error)
            }
        },

        // Group AI Assignment Actions
        async fetchGroupAssignments({ commit, rootState }) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`${apiUrl}/ai/group-assignments`, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include'
                })

                if (!response.ok) {
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to fetch group assignments')
                }

                const data = await response.json()
                commit('SET_GROUP_ASSIGNMENTS', data.data.groups || [])

                // Also update AI accounts if they were returned
                if (data.data.ai_accounts) {
                    commit('SET_AI_ACCOUNTS', data.data.ai_accounts)
                }

                return data
            } catch (error) {
                console.error('Error fetching group assignments:', error)
                return Promise.reject(error)
            }
        },

        async updateGroupAssignment({ rootState, dispatch }, { groupId, aiAccountId, isActive }) {
            if (!rootState.auth.token) return Promise.reject('Not authenticated')

            try {
                const response = await fetch(`${apiUrl}/ai/group-assignments`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${rootState.auth.token}`
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        group_id: groupId,
                        ai_account_id: aiAccountId,
                        is_active: isActive
                    })
                })

                if (!response.ok) {
                    if (response.status === 401) {
                        this.dispatch('auth/logout')
                    }
                    throw new Error('Failed to update group assignment')
                }

                const result = await response.json()

                if (result.success) {
                    // Fetch updated assignments list
                    await dispatch('fetchGroupAssignments')
                    dispatch('ui/showSnackbar', {
                        text: result.message || 'Assignment updated successfully',
                        color: 'success'
                    }, { root: true })
                    return result
                } else {
                    dispatch('ui/showSnackbar', {
                        text: result.error || 'Failed to update assignment',
                        color: 'error'
                    }, { root: true })
                    return Promise.reject(result.error)
                }
            } catch (error) {
                console.error('Error updating group assignment:', error)
                dispatch('ui/showSnackbar', {
                    text: 'An error occurred while updating the assignment',
                    color: 'error'
                }, { root: true })
                return Promise.reject(error)
            }
        }
    }
}
