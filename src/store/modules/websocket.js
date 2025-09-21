// Vuex store module for WebSocket state management
import webSocketService from '@/services/websocket';

const state = {
    connected: false,
    connecting: false,
    connectionError: null,
    lastMessage: null,
    diagnosticsMessages: [],
    aiMessages: [],
    systemHealth: null,
    listeners: new Map(),
    connectionAttempts: 0
};

const getters = {
    isConnected: (state) => state.connected,
    isConnecting: (state) => state.connecting,
    connectionError: (state) => state.connectionError,
    lastMessage: (state) => state.lastMessage,
    diagnosticsMessages: (state) => state.diagnosticsMessages,
    aiMessages: (state) => state.aiMessages,
    systemHealth: (state) => state.systemHealth,
    connectionStatus: (state) => ({
        connected: state.connected,
        connecting: state.connecting,
        error: state.connectionError,
        attempts: state.connectionAttempts
    }),
    recentDiagnostics: (state) => state.diagnosticsMessages.slice(0, 10),
    recentAiMessages: (state) => state.aiMessages.slice(0, 10)
};

const mutations = {
    SET_CONNECTION_STATUS(state, { connected, connecting }) {
        state.connected = connected;
        state.connecting = connecting;
    },
    
    SET_CONNECTION_ERROR(state, error) {
        state.connectionError = error;
    },
    
    CLEAR_CONNECTION_ERROR(state) {
        state.connectionError = null;
    },
    
    SET_LAST_MESSAGE(state, message) {
        state.lastMessage = message;
    },
    
    ADD_DIAGNOSTICS_MESSAGE(state, message) {
        state.diagnosticsMessages.unshift(message);
        // Keep only last 100 messages
        if (state.diagnosticsMessages.length > 100) {
            state.diagnosticsMessages = state.diagnosticsMessages.slice(0, 100);
        }
    },
    
    ADD_AI_MESSAGE(state, message) {
        state.aiMessages.unshift(message);
        // Keep only last 50 messages
        if (state.aiMessages.length > 50) {
            state.aiMessages = state.aiMessages.slice(0, 50);
        }
    },
    
    SET_SYSTEM_HEALTH(state, health) {
        state.systemHealth = health;
    },
    
    CLEAR_MESSAGES(state) {
        state.diagnosticsMessages = [];
        state.aiMessages = [];
        state.lastMessage = null;
        state.systemHealth = null;
    },
    
    INCREMENT_CONNECTION_ATTEMPTS(state) {
        state.connectionAttempts++;
    },
    
    RESET_CONNECTION_ATTEMPTS(state) {
        state.connectionAttempts = 0;
    }
};

const actions = {
    /**
     * Connect to WebSocket
     */
    async connect({ commit, dispatch }) {
        try {
            commit('SET_CONNECTION_STATUS', { connected: false, connecting: true });
            commit('CLEAR_CONNECTION_ERROR');
            commit('INCREMENT_CONNECTION_ATTEMPTS');
            
            // Connect to diagnostics endpoint by default
            await webSocketService.connect('/ws/diagnostics');
            
            commit('SET_CONNECTION_STATUS', { connected: true, connecting: false });
            commit('RESET_CONNECTION_ATTEMPTS');
            
            // Set up listeners to sync with Vuex state
            dispatch('setupWebSocketListeners');
            
            return true;
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
            commit('SET_CONNECTION_STATUS', { connected: false, connecting: false });
            commit('SET_CONNECTION_ERROR', error.message);
            throw error;
        }
    },
    
    /**
     * Disconnect from WebSocket
     */
    disconnect({ commit }) {
        try {
            webSocketService.disconnect();
            commit('SET_CONNECTION_STATUS', { connected: false, connecting: false });
            commit('CLEAR_CONNECTION_ERROR');
            commit('RESET_CONNECTION_ATTEMPTS');
            
            return true;
        } catch (error) {
            console.error('Error disconnecting WebSocket:', error);
            throw error;
        }
    },
    
    /**
     * Send message through WebSocket
     */
    sendMessage({ state }, message) {
        if (!state.connected) {
            throw new Error('WebSocket is not connected');
        }
        
        return webSocketService.send(message);
    },
    
    /**
     * Setup WebSocket event listeners to sync with Vuex state
     */
    setupWebSocketListeners({ commit }) {
        // Listen for connection status changes
        webSocketService.on('open', () => {
            commit('SET_CONNECTION_STATUS', { connected: true, connecting: false });
            commit('CLEAR_CONNECTION_ERROR');
        });
        
        webSocketService.on('close', () => {
            commit('SET_CONNECTION_STATUS', { connected: false, connecting: false });
        });
        
        webSocketService.on('error', (error) => {
            commit('SET_CONNECTION_ERROR', error.message || 'WebSocket error');
        });
        
        // Listen for different message types
        webSocketService.on('message', (data) => {
            commit('SET_LAST_MESSAGE', data);
        });
        
        webSocketService.on('diagnostics_update', (data) => {
            commit('ADD_DIAGNOSTICS_MESSAGE', {
                ...data,
                id: `diag_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                timestamp: new Date().toISOString()
            });
        });
        
        webSocketService.on('chat_message', (data) => {
            commit('ADD_AI_MESSAGE', {
                ...data,
                id: `ai_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                timestamp: new Date().toISOString()
            });
        });
        
        webSocketService.on('system_health', (data) => {
            commit('SET_SYSTEM_HEALTH', {
                ...data.payload,
                timestamp: new Date().toISOString()
            });
        });
        
        webSocketService.on('notification', (data) => {
            // Handle notifications through UI store if available
            console.log('WebSocket notification:', data);
        });
    },
    
    /**
     * Clear all messages
     */
    clearMessages({ commit }) {
        commit('CLEAR_MESSAGES');
        webSocketService.clearMessages();
    },
    
    /**
     * Get WebSocket service status
     */
    getStatus() {
        return webSocketService.getStatus();
    },
    
    /**
     * Add custom event listener
     */
    addEventListener({ state }, { event, callback }) {
        return webSocketService.on(event, callback);
    },
    
    /**
     * Remove event listener
     */
    removeEventListener({ state }, { event, callback }) {
        webSocketService.off(event, callback);
    },
    
    /**
     * Sync state with WebSocket service
     */
    syncState({ commit }) {
        // Sync reactive state from WebSocket service
        const serviceState = webSocketService.state;
        
        commit('SET_CONNECTION_STATUS', {
            connected: serviceState.connected,
            connecting: serviceState.connecting
        });
        
        if (serviceState.connectionError) {
            commit('SET_CONNECTION_ERROR', serviceState.connectionError);
        }
        
        if (serviceState.lastMessage) {
            commit('SET_LAST_MESSAGE', serviceState.lastMessage);
        }
        
        // Sync messages
        serviceState.diagnosticsMessages.forEach(msg => {
            commit('ADD_DIAGNOSTICS_MESSAGE', msg);
        });
        
        serviceState.aiMessages.forEach(msg => {
            commit('ADD_AI_MESSAGE', msg);
        });
        
        if (serviceState.systemHealth) {
            commit('SET_SYSTEM_HEALTH', serviceState.systemHealth);
        }
    }
};

export default {
    namespaced: true,
    state,
    getters,
    mutations,
    actions
};