// WebSocket service for real-time communication with JWT authentication
import store from '@/store';
import { ref, reactive } from 'vue';

class WebSocketService {
    constructor() {
        this.socket = null;
        this.isConnected = ref(false);
        this.isConnecting = ref(false);
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 1000; // Start with 1 second
        this.maxReconnectInterval = 30000; // Max 30 seconds
        this.listeners = new Map();
        this.connectionId = null;
        this.lastPongTime = null;
        this.pingInterval = null;
        this.connectionPromise = null;

        // Reactive state for components to observe
        this.state = reactive({
            connected: false,
            connecting: false,
            lastMessage: null,
            connectionError: null,
            diagnosticsMessages: [],
            aiMessages: [],
            systemHealth: null
        });

        console.log('WebSocket Service initialized');
    }

    /**
     * Get WebSocket URL based on current environment
     */
    getWebSocketUrl(endpoint = '/ws') {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        
        // For development, use the backend port
        if (process.env.NODE_ENV === 'development') {
            const backendPort = 8000;
            const backendHost = window.location.hostname;
            return `${protocol}//${backendHost}:${backendPort}${endpoint}`;
        }
        
        return `${protocol}//${host}${endpoint}`;
    }

    /**
     * Connect to WebSocket with JWT authentication
     */
    async connect(endpoint = '/ws/diagnostics') {
        // Prevent multiple simultaneous connection attempts
        if (this.isConnecting.value || this.isConnected.value) {
            console.log('WebSocket already connected or connecting');
            return this.connectionPromise;
        }

        this.isConnecting.value = true;
        this.state.connecting = true;
        this.state.connectionError = null;

        this.connectionPromise = new Promise((resolve, reject) => {
            try {
                // Get JWT token for authentication
                const accessToken = store.getters['auth/accessToken'];
                if (!accessToken) {
                    throw new Error('No access token available for WebSocket authentication');
                }

                // Construct WebSocket URL (without token in query params for security)
                const wsUrl = this.getWebSocketUrl(endpoint);
                console.log('Connecting to WebSocket:', endpoint);

                // Create WebSocket connection with JWT token in subprotocol header (secure method)
                // This sends the JWT token via Sec-WebSocket-Protocol header instead of query params
                const authProtocol = `bearer.${accessToken}`;
                this.socket = new WebSocket(wsUrl, [authProtocol]);

                // Connection opened
                this.socket.onopen = (event) => {
                    console.log('WebSocket connected successfully');
                    this.isConnected.value = true;
                    this.isConnecting.value = false;
                    this.state.connected = true;
                    this.state.connecting = false;
                    this.reconnectAttempts = 0;
                    this.reconnectInterval = 1000;
                    
                    // Start ping/pong for connection health
                    this.startPingPong();
                    
                    // Emit open event for listeners
                    this.emit('open', event);
                    
                    resolve(this.socket);
                };

                // Message received
                this.socket.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.handleMessage(data);
                    } catch (error) {
                        console.error('Error parsing WebSocket message:', error);
                        console.log('Raw message:', event.data);
                    }
                };

                // Connection closed
                this.socket.onclose = (event) => {
                    console.log('WebSocket connection closed:', event.code, event.reason);
                    this.handleDisconnection();
                    
                    // Emit close event for listeners
                    this.emit('close', { code: event.code, reason: event.reason });
                    
                    if (event.code !== 1000) { // Not a normal closure
                        this.scheduleReconnect();
                    }
                };

                // Connection error
                this.socket.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.state.connectionError = 'WebSocket connection error';
                    this.handleDisconnection();
                    
                    // Emit error event for listeners
                    this.emit('error', error);
                    
                    reject(error);
                };

            } catch (error) {
                console.error('Error creating WebSocket connection:', error);
                this.state.connectionError = error.message;
                this.isConnecting.value = false;
                this.state.connecting = false;
                reject(error);
            }
        });

        return this.connectionPromise;
    }

    /**
     * Handle incoming WebSocket messages
     */
    handleMessage(data) {
        console.log('WebSocket message received:', data);
        
        this.state.lastMessage = {
            ...data,
            timestamp: new Date().toISOString()
        };

        // Handle different message types
        switch (data.type) {
            case 'pong':
                this.lastPongTime = Date.now();
                break;
                
            case 'diagnostics_update':
                this.handleDiagnosticsUpdate(data);
                break;
                
            case 'chat_message':
                this.handleChatMessage(data);
                break;
                
            case 'conversation_update':
                this.handleConversationUpdate(data);
                break;
                
            case 'system_health':
                this.handleSystemHealth(data);
                break;
                
            case 'notification':
                this.handleNotification(data);
                break;
                
            default:
                console.log('Unknown message type:', data.type);
        }

        // Emit to registered listeners
        this.emit(data.type, data);
        this.emit('message', data); // General message listener
    }

    /**
     * Handle diagnostics updates
     */
    handleDiagnosticsUpdate(data) {
        this.state.diagnosticsMessages.unshift({
            ...data,
            id: `diag_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            timestamp: new Date().toISOString()
        });

        // Keep only last 100 diagnostics messages
        if (this.state.diagnosticsMessages.length > 100) {
            this.state.diagnosticsMessages = this.state.diagnosticsMessages.slice(0, 100);
        }
    }

    /**
     * Handle AI chat messages
     */
    handleChatMessage(data) {
        this.state.aiMessages.unshift({
            ...data,
            id: `ai_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            timestamp: new Date().toISOString()
        });

        // Keep only last 50 AI messages
        if (this.state.aiMessages.length > 50) {
            this.state.aiMessages = this.state.aiMessages.slice(0, 50);
        }
    }

    /**
     * Handle conversation updates
     */
    handleConversationUpdate(data) {
        // Update conversation in store or emit to listeners
        console.log('Conversation update:', data);
    }

    /**
     * Handle system health updates
     */
    handleSystemHealth(data) {
        this.state.systemHealth = {
            ...data.payload,
            timestamp: new Date().toISOString()
        };
    }

    /**
     * Handle notifications
     */
    handleNotification(data) {
        // Could integrate with UI notification system
        console.log('Notification received:', data);
        
        // Show notification using UI store if available
        if (store.hasModule && store.hasModule('ui')) {
            store.dispatch('ui/showSnackbar', {
                text: data.message || 'Notification received',
                color: data.level || 'info'
            });
        }
    }

    /**
     * Send message through WebSocket
     */
    send(message) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
            this.socket.send(messageStr);
            console.log('WebSocket message sent:', messageStr);
            return true;
        } else {
            console.warn('WebSocket not connected, cannot send message:', message);
            return false;
        }
    }

    /**
     * Start ping/pong for connection health monitoring
     */
    startPingPong() {
        this.stopPingPong(); // Clear any existing interval
        
        this.pingInterval = setInterval(() => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                this.send({ type: 'ping', timestamp: new Date().toISOString() });
                
                // Check if we received a pong recently
                if (this.lastPongTime && (Date.now() - this.lastPongTime > 30000)) {
                    console.warn('No pong received in 30 seconds, connection might be stale');
                    this.disconnect();
                    this.scheduleReconnect();
                }
            }
        }, 15000); // Ping every 15 seconds
    }

    /**
     * Stop ping/pong interval
     */
    stopPingPong() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    /**
     * Handle disconnection cleanup
     */
    handleDisconnection() {
        this.isConnected.value = false;
        this.isConnecting.value = false;
        this.state.connected = false;
        this.state.connecting = false;
        this.stopPingPong();
        this.connectionPromise = null;
        
        if (this.socket) {
            this.socket = null;
        }
    }

    /**
     * Schedule reconnection with exponential backoff
     */
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this.state.connectionError = 'Failed to reconnect after multiple attempts';
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1), this.maxReconnectInterval);
        
        console.log(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);
        
        setTimeout(() => {
            if (!this.isConnected.value && !this.isConnecting.value) {
                console.log('Attempting to reconnect...');
                this.connect('/ws/diagnostics').catch(error => {
                    console.error('Reconnection attempt failed:', error);
                });
            }
        }, delay);
    }

    /**
     * Manually disconnect WebSocket
     */
    disconnect() {
        console.log('Manually disconnecting WebSocket');
        
        if (this.socket) {
            this.socket.close(1000, 'Manual disconnect');
        }
        
        this.handleDisconnection();
    }

    /**
     * Add event listener
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
        
        return () => this.off(event, callback); // Return unsubscribe function
    }

    /**
     * Remove event listener
     */
    off(event, callback) {
        if (this.listeners.has(event)) {
            const callbacks = this.listeners.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    /**
     * Emit event to listeners
     */
    emit(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error('Error in WebSocket event listener:', error);
                }
            });
        }
    }

    /**
     * Get connection status
     */
    getStatus() {
        return {
            connected: this.isConnected.value,
            connecting: this.isConnecting.value,
            reconnectAttempts: this.reconnectAttempts,
            lastPongTime: this.lastPongTime,
            hasListeners: this.listeners.size > 0
        };
    }

    /**
     * Clear all messages and reset state
     */
    clearMessages() {
        this.state.diagnosticsMessages = [];
        this.state.aiMessages = [];
        this.state.lastMessage = null;
        this.state.systemHealth = null;
    }
}

// Create singleton instance
const webSocketService = new WebSocketService();

export default webSocketService;