// ui.js - UI module for Vuex store
// Handles UI-related state like snackbar notifications

export default {
    namespaced: true,

    state: () => ({
        snackbar: {
            show: false,
            text: '',
            color: 'info'
        }
    }),

    getters: {
        snackbar: state => state.snackbar
    },

    mutations: {
        SHOW_SNACKBAR(state, { text, color }) {
            state.snackbar.text = text
            state.snackbar.color = color || 'info'
            state.snackbar.show = true
        },
        HIDE_SNACKBAR(state) {
            state.snackbar.show = false
        }
    },

    actions: {
        showSnackbar({ commit }, { text, color }) {
            commit('SHOW_SNACKBAR', { text, color })
        },
        hideSnackbar({ commit }) {
            commit('HIDE_SNACKBAR')
        }
    }
}
