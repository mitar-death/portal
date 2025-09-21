<template>
  <div class="diagnostics-card wide">
    <h2>Real-time AI Messages</h2>
    
    <!-- Connection Status -->
    <div class="connection-status">
      <div class="status-item">
        <span class="status-label">WebSocket Status:</span>
        <span class="status-value" :class="connectionStatusClass">
          {{ connectionStatusText }}
        </span>
      </div>
      <div class="connection-actions">
        <button 
          v-if="!isConnected" 
          @click="$emit('connect')"
          class="btn-connect"
        >
          Connect
        </button>
        <button 
          v-else 
          @click="$emit('disconnect')"
          class="btn-disconnect"
        >
          Disconnect
        </button>
        <button 
          @click="$emit('clear')"
          class="btn-clear"
        >
          Clear Messages
        </button>
      </div>
    </div>

    <!-- Messages Display -->
    <div class="messages-container">
      <div v-if="messages.length === 0" class="no-data">
        <div v-if="!isConnected">
          Connect to WebSocket to see real-time AI messages
        </div>
        <div v-else>
          Waiting for real-time AI messages...
        </div>
      </div>
      
      <div v-else class="messages-list">
        <div 
          v-for="message in messages" 
          :key="message.id"
          class="message-item"
          :class="getMessageTypeClass(message)"
        >
          <div class="message-header">
            <span class="message-type">{{ getMessageTypeLabel(message) }}</span>
            <span class="message-time">{{ formatTime(message.timestamp) }}</span>
          </div>
          
          <div class="message-content">
            <div v-if="message.type === 'chat_message'" class="chat-message">
              <div class="user-info">
                <strong>{{ message.user_name || 'Unknown User' }}</strong>
                <span v-if="message.group_name" class="group-name">
                  in {{ message.group_name }}
                </span>
              </div>
              <div class="message-text">{{ message.message || message.content || 'No content' }}</div>
              <div v-if="message.ai_response" class="ai-response">
                <strong>AI Response:</strong> {{ message.ai_response }}
              </div>
            </div>
            
            <div v-else-if="message.type === 'diagnostics_update'" class="diagnostics-message">
              <div class="diagnostic-type">{{ message.diagnostic_type || 'System Update' }}</div>
              <div class="diagnostic-content">{{ message.message || JSON.stringify(message.payload) }}</div>
            </div>
            
            <div v-else-if="message.type === 'system_health'" class="system-health">
              <div class="health-status">System Health Update</div>
              <div class="health-details">
                <span v-if="message.payload">
                  Status: {{ message.payload.status || 'Unknown' }}
                </span>
              </div>
            </div>
            
            <div v-else class="generic-message">
              <div class="message-data">{{ JSON.stringify(message, null, 2) }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  },
  connectionStatus: {
    type: String,
    default: 'disconnected'
  },
  isConnected: {
    type: Boolean,
    default: false
  }
});

defineEmits(['connect', 'disconnect', 'clear']);

const connectionStatusText = computed(() => {
  switch (props.connectionStatus) {
    case 'connected':
      return 'Connected';
    case 'connecting':
      return 'Connecting...';
    case 'error':
      return 'Connection Error';
    default:
      return 'Disconnected';
  }
});

const connectionStatusClass = computed(() => {
  switch (props.connectionStatus) {
    case 'connected':
      return 'status-ok';
    case 'connecting':
      return 'status-pending';
    case 'error':
      return 'status-error';
    default:
      return 'status-inactive';
  }
});

function getMessageTypeClass(message) {
  switch (message.type) {
    case 'chat_message':
      return 'message-chat';
    case 'diagnostics_update':
      return 'message-diagnostics';
    case 'system_health':
      return 'message-system';
    default:
      return 'message-generic';
  }
}

function getMessageTypeLabel(message) {
  switch (message.type) {
    case 'chat_message':
      return 'Chat Message';
    case 'diagnostics_update':
      return 'Diagnostics';
    case 'system_health':
      return 'System Health';
    case 'notification':
      return 'Notification';
    default:
      return 'Message';
  }
}

function formatTime(timestamp) {
  if (!timestamp) return 'N/A';
  const date = new Date(timestamp);
  return date.toLocaleTimeString();
}
</script>

<style scoped>
.connection-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px;
  background-color: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.connection-actions {
  display: flex;
  gap: 8px;
}

.btn-connect, .btn-disconnect, .btn-clear {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  transition: all 0.2s ease;
}

.btn-connect {
  background-color: #28a745;
  color: white;
}

.btn-connect:hover {
  background-color: #218838;
}

.btn-disconnect {
  background-color: #dc3545;
  color: white;
}

.btn-disconnect:hover {
  background-color: #c82333;
}

.btn-clear {
  background-color: #6c757d;
  color: white;
}

.btn-clear:hover {
  background-color: #5a6268;
}

.messages-container {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  background-color: #ffffff;
}

.messages-list {
  padding: 8px;
}

.message-item {
  margin-bottom: 12px;
  padding: 12px;
  border-radius: 8px;
  border-left: 4px solid #e9ecef;
  background-color: #f8f9fa;
  transition: all 0.2s ease;
}

.message-item:hover {
  background-color: #e9ecef;
}

.message-chat {
  border-left-color: #007bff;
  background-color: #f0f7ff;
}

.message-diagnostics {
  border-left-color: #ffc107;
  background-color: #fffbf0;
}

.message-system {
  border-left-color: #28a745;
  background-color: #f0fff4;
}

.message-generic {
  border-left-color: #6c757d;
  background-color: #f8f9fa;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 0.85rem;
}

.message-type {
  font-weight: 600;
  color: #495057;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.message-time {
  color: #6c757d;
  font-size: 0.8rem;
}

.message-content {
  font-size: 0.9rem;
  line-height: 1.4;
}

.user-info {
  margin-bottom: 4px;
}

.group-name {
  color: #6c757d;
  font-weight: normal;
  font-size: 0.85rem;
}

.message-text {
  background-color: white;
  padding: 8px;
  border-radius: 6px;
  margin: 4px 0;
  border: 1px solid #e9ecef;
}

.ai-response {
  background-color: #e3f2fd;
  padding: 8px;
  border-radius: 6px;
  margin-top: 8px;
  border: 1px solid #bbdefb;
  color: #1565c0;
}

.diagnostic-type {
  font-weight: 600;
  color: #856404;
  margin-bottom: 4px;
}

.diagnostic-content {
  background-color: white;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid #ffeaa7;
}

.health-status {
  font-weight: 600;
  color: #155724;
  margin-bottom: 4px;
}

.health-details {
  background-color: white;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid #c3e6cb;
}

.generic-message .message-data {
  background-color: white;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid #e9ecef;
  font-family: 'Courier New', monospace;
  font-size: 0.8rem;
  white-space: pre-wrap;
  overflow-x: auto;
}

.no-data {
  text-align: center;
  padding: 32px;
  color: #6c757d;
  font-style: italic;
}

/* Scrollbar styling */
.messages-container::-webkit-scrollbar {
  width: 8px;
}

.messages-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 8px;
}

.messages-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 8px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>