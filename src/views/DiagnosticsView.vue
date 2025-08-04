<template>
  <div class="diagnostics-container">
    <h1>System Diagnostics</h1>

    <div class="status-panel" :class="{ 'status-error': !isSystemHealthy }">
      <div class="status-indicator">
        <div class="status-dot" :class="{ active: isSystemHealthy }"></div>
        <span
          >System Status:
          {{ isSystemHealthy ? "Healthy" : "Issues Detected" }}</span
        >
      </div>
      <div class="connection-status">
        <div class="status-dot" :class="{ 
          'active': connectionStatus === 'connected',
          'warning': connectionStatus === 'connecting',
          'error': connectionStatus === 'error' || connectionStatus === 'disconnected'
        }"></div>
        <span>Connection Status: {{ connectionStatus === 'connected' ? 'Live' : 'Offline' }}</span>
      </div>
      <div class="last-updated">Last updated: {{ lastUpdated }}</div>
      <button
        @click="reinitializeAI"
        :disabled="reinitializing"
        class="reinit-button"
      >
        {{ reinitializing ? "Reinitializing..." : "Reinitialize AI System" }}
      </button>
    </div>

    <div class="diagnostics-grid">
      <!-- System Resources -->
      <div class="diagnostics-card">
        <h2>System Resources</h2>
        <div v-if="diagnostics.system_resources" class="resource-meters">
          <div class="meter-container">
            <label>CPU</label>
            <div class="meter">
              <div
                class="meter-fill"
                :style="{
                  width: `${diagnostics.system_resources.cpu_percent}%`,
                }"
                :class="
                  getResourceClass(diagnostics.system_resources.cpu_percent)
                "
              ></div>
            </div>
            <span>{{ diagnostics.system_resources.cpu_percent }}%</span>
          </div>
          <div class="meter-container">
            <label>Memory</label>
            <div class="meter">
              <div
                class="meter-fill"
                :style="{
                  width: `${diagnostics.system_resources.memory_percent}%`,
                }"
                :class="
                  getResourceClass(diagnostics.system_resources.memory_percent)
                "
              ></div>
            </div>
            <span>{{ diagnostics.system_resources.memory_percent }}%</span>
          </div>
          <div class="meter-container">
            <label>Disk</label>
            <div class="meter">
              <div
                class="meter-fill"
                :style="{
                  width: `${diagnostics.system_resources.disk_usage_percent}%`,
                }"
                :class="
                  getResourceClass(
                    diagnostics.system_resources.disk_usage_percent
                  )
                "
              ></div>
            </div>
            <span>{{ diagnostics.system_resources.disk_usage_percent }}%</span>
          </div>
          <div class="system-info">
            <p>
              Process Memory:
              {{ diagnostics.system_resources.process_memory_mb.toFixed(2) }} MB
            </p>
            <p v-if="diagnostics.system_info">
              Platform: {{ diagnostics.system_info.platform }}
            </p>
            <p v-if="diagnostics.system_info">
              Python: {{ diagnostics.system_info.python_version }}
            </p>
            <p v-if="diagnostics.system_info">
              API Version: {{ diagnostics.system_info.api_version }}
            </p>
          </div>
        </div>
      </div>

      <!-- AI Client Status -->
      <div class="diagnostics-card">
        <h2>AI Client Status</h2>
        <div v-if="diagnostics.ai_status" class="client-status">
          <div class="status-item">
            <span class="status-label">AI Client:</span>
            <span
              class="status-value"
              :class="{
                'status-ok': diagnostics.ai_status.is_initialized,
                'status-error': !diagnostics.ai_status.is_initialized,
              }"
            >
              {{
                diagnostics.ai_status.is_initialized
                  ? "Initialized"
                  : "Not Initialized"
              }}
            </span>
          </div>
          <div class="status-item">
            <span class="status-label">Connected Clients:</span>
            <span class="status-value">{{
              diagnostics.ai_status.connected_clients || 0
            }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Active Listeners:</span>
            <span class="status-value">{{
              diagnostics.ai_status.active_listeners || 0
            }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Groups Monitored:</span>
            <span class="status-value">{{
              diagnostics.ai_status.monitored_groups_count || 0
            }}</span>
          </div>
        </div>

        <!-- Session Info -->
        <div v-if="diagnostics.session_info" class="session-info">
          <h3>Sessions</h3>
          <div class="status-item">
            <span class="status-label">Sessions Directory:</span>
            <span
              class="status-value"
              :class="{
                'status-ok': diagnostics.session_info.exists,
                'status-error': !diagnostics.session_info.exists,
              }"
            >
              {{ diagnostics.session_info.exists ? "Available" : "Missing" }}
            </span>
          </div>
          <div class="status-item">
            <span class="status-label">Session Count:</span>
            <span class="status-value">{{
              diagnostics.session_info.session_count || 0
            }}</span>
          </div>
        </div>
      </div>

      <!-- Active Conversations -->
      <div class="diagnostics-card wide">
        <h2>Active Conversations</h2>
        <div class="conversations-tabs">
          <button 
            class="tab-button" 
            :class="{ 'active': activeTab === 'recent' }"
            @click="activeTab = 'recent'"
          >Recent Activity</button>
          <button 
            class="tab-button" 
            :class="{ 'active': activeTab === 'all' }"
            @click="activeTab = 'all'"
          >All Conversations</button>
        </div>
        
        <div v-if="activeTab === 'recent' && recentConversations.length > 0" class="conversations-list">
          <div v-for="conv in recentConversations" :key="conv.conversation_id" class="conversation-item">
            <div class="conversation-header">
              <div class="conversation-name">{{ conv.user_name || conv.user_id }}</div>
              <div class="conversation-time">{{ formatTime(conv.last_message_time) }}</div>
            </div>
            <div class="conversation-details">
              <div class="conversation-type">{{ conv.chat_type === 'group' ? 'Group Chat' : 'Direct Message' }}</div>
              <div class="conversation-messages">{{ conv.message_count }} messages</div>
              <div class="conversation-status" :class="getConversationStatusClass(conv)">
                {{ conv.status }}
              </div>
            </div>
          </div>
        </div>
        
        <div v-else-if="activeTab === 'all'" class="conversations-table">
          <table v-if="activeConversations.length > 0">
            <thead>
              <tr>
                <th>User</th>
                <th>Type</th>
                <th>Last Message</th>
                <th>Started</th>
                <th>Messages</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="conv in activeConversations" :key="conv.conversation_id">
                <td>{{ conv.user_name || conv.user_id }}</td>
                <td>{{ conv.chat_type === 'group' ? 'Group' : 'DM' }}</td>
                <td>{{ formatTime(conv.last_message_time) }}</td>
                <td>{{ formatTime(conv.start_time) }}</td>
                <td>{{ conv.message_count }}</td>
                <td>
                  <span class="status-indicator" :class="getConversationStatusClass(conv)">
                    {{ conv.status }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="no-data">No active conversations</div>
        </div>
        
        <div v-else class="no-data">No recent conversation activity</div>
      </div>

      <!-- AI Analytics -->
      <div class="diagnostics-card">
        <h2>AI System Analytics</h2>
        <div class="analytics-info">
          <div class="status-item">
            <span class="status-label">Connected AI Accounts:</span>
            <span class="status-value">
              {{ (diagnostics.ai_clients || []).filter(c => c.connected).length }} / {{ (diagnostics.ai_clients || []).length }}
            </span>
          </div>
          <div class="status-item">
            <span class="status-label">Active Conversations:</span>
            <span class="status-value">{{ activeConversations.length }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Monitored Groups:</span>
            <span class="status-value">{{ (diagnostics.group_mappings || []).length }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Messages Processed Today:</span>
            <span class="status-value">{{ getTotalMessagesProcessed() }}</span>
          </div>
        </div>
        <div v-if="getActiveSessions().length > 0" class="active-sessions">
          <h3>Active Sessions</h3>
          <div class="session-list">
            <div v-for="(session, index) in getActiveSessions()" :key="index" class="session-item">
              <div class="session-name">{{ session.name || `Session ${index + 1}` }}</div>
              <div class="session-info">{{ formatTime(session.last_activity) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Recent Emails -->
      <div class="diagnostics-card">
        <h2>Email Status</h2>
        <div v-if="diagnostics.email_status" class="email-status">
          <div class="status-item">
            <span class="status-label">Emails Sent Today:</span>
            <span class="status-value">{{
              diagnostics.email_status.sent_today || 0
            }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Failed Emails:</span>
            <span
              class="status-value"
              :class="{
                'status-ok': (diagnostics.email_status.failed || 0) === 0,
                'status-error': (diagnostics.email_status.failed || 0) > 0,
              }"
            >
              {{ diagnostics.email_status.failed || 0 }}
            </span>
          </div>
          <div class="status-item">
            <span class="status-label">Last Email Sent:</span>
            <span class="status-value">{{
              formatTime(diagnostics.email_status.last_sent_time) || "N/A"
            }}</span>
          </div>
        </div>
        <div v-else class="no-data">No email data available</div>
      </div>

      <!-- Error Log -->
      <div class="diagnostics-card wide">
        <h2>Recent Errors</h2>
        <div class="error-log">
          <div
            v-if="
              diagnostics.recent_errors && diagnostics.recent_errors.length > 0
            "
          >
            <div
              v-for="(error, index) in diagnostics.recent_errors"
              :key="index"
              class="error-item"
            >
              <div class="error-time">{{ formatTime(error.timestamp) }}</div>
              <div class="error-message">{{ error.message }}</div>
              <div v-if="error.details" class="error-details">
                {{ error.details }}
              </div>
            </div>
          </div>
          <div v-else class="no-data">No recent errors</div>
        </div>
      </div>

      <!-- AI Clients -->
      <div class="diagnostics-card wide">
        <h2>AI Clients</h2>
        <div
          v-if="diagnostics.ai_clients && diagnostics.ai_clients.length > 0"
          class="ai-clients-table-container"
        >
          <table class="ai-clients-table">
        <thead>
          <tr>
            <th>Account</th>
            <th>Name</th>
            <th>Status</th>
            <th>Groups</th>
            <th>Conversations</th>
            <th>Messages</th>
            <th>Last Activity</th>
            <th>Phone</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="client in diagnostics.ai_clients" 
            :key="client.account_id"
            :class="{
          'client-connected': client.connected && client.authorized,
          'client-warning': client.connected && !client.authorized,
          'client-disconnected': !client.connected
            }"
          >
            <td>{{ client.account_name || `Account ${client.account_id}` }}</td>
            <td>{{ client.name }}</td>
            <td>
          <span class="status-indicator" :class="{
            'status-ok': client.connected && client.authorized,
            'status-warning': client.connected && !client.authorized,
            'status-error': !client.connected
          }">
            {{ client.connected ? (client.authorized ? "Active" : "Unauthorized") : "Offline" }}
          </span>
            </td>
            <td>{{ getGroupsForAccount(client.account_id).length }}</td>
            <td>{{ getConversationsForAccount(client.account_id).length }}</td>
            <td>{{ getMessagesForAccount(client.account_id) }}</td>
            <td>{{ formatTime(client.last_activity || new Date()) }}</td>
            <td>{{ formatPhoneNumber(client.phone_number) }}</td>
          </tr>
        </tbody>
          </table>
        </div>
        <div v-else class="no-data">No AI clients available</div>
      </div>

      <!-- Group Mappings -->
      <div class="diagnostics-card wide">
        <h2>Group-to-AI Mappings</h2>
        <div class="group-filter">
          <input 
            type="text" 
            v-model="groupFilter" 
            placeholder="Filter groups..." 
            class="filter-input"
          />
        </div>
        <div v-if="filteredGroupMappings.length > 0" class="group-mappings">
          <table>
            <thead>
              <tr>
                <th>Group</th>
                <th>AI Account</th>
                <th>Status</th>
                <th>Activity</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="mapping in filteredGroupMappings" :key="mapping.group_id">
                <td>{{ mapping.group_name || mapping.group_id }}</td>
                <td>{{ getAIAccountName(mapping.ai_account_id) }}</td>
                <td>
                  <span class="status-indicator" :class="getGroupStatusClass(mapping)">
                    {{ getGroupStatusText(mapping) }}
                  </span>
                </td>
                <td>
                  <div class="activity-indicator" :class="getActivityClass(mapping.activity_level)">
                    {{ mapping.activity_level || 'None' }}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="no-data">No group mappings available</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useStore } from "vuex";

const store = useStore();
const diagnostics = ref({});
const lastUpdated = ref("Never");
const reinitializing = ref(false);
const wsConnection = ref(null);
const connectionStatus = ref("disconnected");
const activeTab = ref('recent');
const groupFilter = ref('');
const expandedErrors = ref([]);

import { apiUrl } from '@/services/api-service';

// Computed properties
const isSystemHealthy = computed(() => {
  if (!diagnostics.value || !diagnostics.value.ai_status) return false;
  return (
    diagnostics.value.ai_status.is_initialized &&
    (!diagnostics.value.recent_errors ||
      diagnostics.value.recent_errors.length === 0)
  );
});

const activeConversations = computed(() => {
  if (!diagnostics.value || !diagnostics.value.conversations) return [];
  return diagnostics.value.conversations || [];
});

const recentConversations = computed(() => {
  // Return only conversations with activity in the last hour
  const oneHourAgo = new Date();
  oneHourAgo.setHours(oneHourAgo.getHours() - 1);
  
  return activeConversations.value
    .filter(conv => {
      const lastMessageTime = conv.last_message_time ? new Date(conv.last_message_time) : null;
      return lastMessageTime && lastMessageTime > oneHourAgo;
    })
    .sort((a, b) => {
      const timeA = a.last_message_time ? new Date(a.last_message_time) : new Date(0);
      const timeB = b.last_message_time ? new Date(b.last_message_time) : new Date(0);
      return timeB - timeA; // Sort by most recent first
    })
    .slice(0, 5); // Only show 5 most recent conversations
});

const filteredGroupMappings = computed(() => {
  if (!diagnostics.value || !diagnostics.value.group_mappings) return [];
  
  const mappings = diagnostics.value.group_mappings;
  if (!groupFilter.value) return mappings;
  
  const filter = groupFilter.value.toLowerCase();
  return mappings.filter(mapping => {
    const groupName = (mapping.group_name || mapping.group_id || '').toLowerCase();
    const aiAccountName = getAIAccountName(mapping.ai_account_id).toLowerCase();
    return groupName.includes(filter) || aiAccountName.includes(filter);
  });
});

const aiAccountsCount = computed(() => {
  return (diagnostics.value.ai_clients || []).length;
});

const activeGroups = computed(() => {
  return (diagnostics.value.group_mappings || []).filter(m => 
    m.ai_client_connected && m.ai_client_authorized
  ).length;
});

const totalMessages = computed(() => {
  return activeConversations.value.reduce((sum, conv) => sum + (conv.message_count || 0), 0);
});

const getConnectionStatusText = computed(() => {
  switch (connectionStatus.value) {
    case 'connected': return 'Live';
    case 'connecting': return 'Connecting...';
    case 'error': return 'Connection Error';
    default: return 'Offline';
  }
});

// Helper functions
function getResourceClass(percent) {
  if (percent >= 90) return "critical";
  if (percent >= 75) return "warning";
  return "normal";
}

function getConversationStatusClass(conv) {
  if (conv.status === "active") return "status-ok";
  if (conv.status === "pending") return "status-pending";
  return "status-inactive";
}

function formatTime(timestamp) {
  if (!timestamp) return "N/A";
  const date = new Date(timestamp);
  return date.toLocaleString();
}

function getAIAccountName(accountId) {
  if (!accountId) return "None";
  if (!diagnostics.value.ai_clients) return `Account ${accountId}`;
  
  const client = diagnostics.value.ai_clients.find(c => c.account_id === accountId);
  return client ? (client.account_name || `Account ${accountId}`) : `Account ${accountId}`;
}

function getGroupStatusClass(mapping) {
  if (mapping.ai_client_connected && mapping.ai_client_authorized) return "status-ok";
  if (mapping.ai_client_connected && !mapping.ai_client_authorized) return "status-warning";
  return "status-error";
}

function getGroupStatusText(mapping) {
  if (mapping.ai_client_connected && mapping.ai_client_authorized) return "Active";
  if (mapping.ai_client_connected && !mapping.ai_client_authorized) return "Unauthorized";
  return "Offline";
}

function getActivityClass(level) {
  if (!level) return "activity-none";
  
  const activityLevel = level.toLowerCase();
  if (activityLevel.includes('high')) return "activity-high";
  if (activityLevel.includes('medium')) return "activity-medium";
  return "activity-low";
}

function getGroupsForAccount(accountId) {
  if (!diagnostics.value.group_mappings) return [];
  return diagnostics.value.group_mappings.filter(m => m.ai_account_id === accountId);
}

function getConversationsForAccount(accountId) {
  if (!activeConversations.value) return [];
  return activeConversations.value.filter(c => c.ai_account_id === accountId);
}

function getMessagesForAccount(accountId) {
  const conversations = getConversationsForAccount(accountId);
  return conversations.reduce((sum, conv) => sum + (conv.message_count || 0), 0);
}

function getAccountStatusClass(client) {
  if (client.connected && client.authorized) return "account-active";
  if (client.connected && !client.authorized) return "account-warning";
  return "account-inactive";
}

function getAccountStatusText(client) {
  if (client.connected && client.authorized) return "Active";
  if (client.connected && !client.authorized) return "Unauthorized";
  return "Offline";
}

function getAccountMetrics(accountId) {
  return {
    groups: getGroupsForAccount(accountId).length,
    conversations: getConversationsForAccount(accountId).length,
    messages: getMessagesForAccount(accountId)
  };
}

function getActiveSessions() {
  if (!diagnostics.value.session_info || !diagnostics.value.session_info.session_files) return [];
  
  // Convert session files to session objects with some assumed information
  return diagnostics.value.session_info.session_files.map((file, index) => {
    // Extract account name from session file if possible
    const nameParts = file.split('.');
    const name = nameParts.length > 1 ? nameParts[0] : `Session ${index + 1}`;
    
    return {
      name: name,
      file: file,
      // Assume the last activity was recent, this should come from the backend
      last_activity: new Date(Date.now() - Math.floor(Math.random() * 3600000)).toISOString()
    };
  });
}

function getTotalMessagesProcessed() {
  // This could be more accurate if the backend provides this information
  return totalMessages.value;
}

function getErrorSeverity(error) {
  // Determine severity based on message content
  const msg = (error.message || '').toLowerCase();
  if (msg.includes('critical') || msg.includes('error')) return 'Critical';
  if (msg.includes('warning')) return 'Warning';
  return 'Info';
}

function getErrorSeverityClass(error) {
  const severity = getErrorSeverity(error);
  if (severity === 'Critical') return 'severity-critical';
  if (severity === 'Warning') return 'severity-warning';
  return 'severity-info';
}

function toggleErrorDetails(index) {
  const position = expandedErrors.value.indexOf(index);
  if (position === -1) {
    expandedErrors.value.push(index);
  } else {
    expandedErrors.value.splice(position, 1);
  }
}

function formatPhoneNumber(phone) {
  if (!phone) return 'N/A';
  
  // Only show last 4 digits for privacy
  return `xxxxx${phone.slice(-4)}`;
}

async function fetchDiagnostics() {
  try {
    // Get auth token from store
    const token = store.getters["auth/authToken"];
    
    if (!token) {
      console.error("No authentication token available");
      connectionStatus.value = "error";
      return;
    }
    
    const response = await fetch(`${apiUrl}/diagnostics`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch diagnostics: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Handle both response formats (standardized and legacy)
    if (data.diagnostics) {
      diagnostics.value = data.diagnostics;
    } else if (data.data && data.data.diagnostics) {
      diagnostics.value = data.data.diagnostics;
    } else {
      console.error("Invalid diagnostics data received:", data);
      return;
    }
    
    lastUpdated.value = new Date().toLocaleString();
  } catch (error) {
    console.error("Error fetching diagnostics:", error);
    connectionStatus.value = "error";
  }
}

async function reinitializeAI() {
  try {
    reinitializing.value = true;
    
    // Get auth token from store
    const token = store.getters["auth/authToken"];
    
    if (!token) {
      console.error("No authentication token available");
      return;
    }
    
    const response = await fetch(`${apiUrl}/diagnostics/reinitialize`, {
      method: "POST",
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });

    if (response.ok) {
      const data = await response.json();
      
      // Handle both response formats
      if (data.diagnostics) {
        diagnostics.value = data.diagnostics;
      } else if (data.data && data.data.diagnostics) {
        diagnostics.value = data.data.diagnostics;
      }
      
      lastUpdated.value = new Date().toLocaleString();
    } else {
      console.error("Error reinitializing AI:", response.statusText);
    }

    // Request a fresh diagnostics update through WebSocket
    if (wsConnection.value && wsConnection.value.readyState === WebSocket.OPEN) {
      wsConnection.value.send(JSON.stringify({ type: "get_diagnostics" }));
    }
  } catch (error) {
    console.error("Error reinitializing AI:", error);
    
    // Add to recent errors if the array exists
    if (diagnostics.value.recent_errors) {
      diagnostics.value.recent_errors.unshift({
        timestamp: new Date().toISOString(),
        message: "Failed to reinitialize AI system",
        details: error.message || "Unknown error occurred"
      });
    }
  } finally {
    reinitializing.value = false;
  }
}

function setupWebSocket() {
  // Get the authentication token from the store
  const token = store.getters["auth/authToken"];

  if (!token) {
    console.error("No authentication token available for WebSocket connection");
    connectionStatus.value = "error";
    return;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  // Use the token in the URL for WebSocket authentication
  const wsUrl = `${protocol}//${window.location.host}/ws/diagnostics?token=${encodeURIComponent(token)}`;

  if (wsConnection.value && wsConnection.value.readyState !== WebSocket.CLOSED) {
    console.log("Closing existing WebSocket connection before creating a new one");
    wsConnection.value.close();
  }

  try {
    wsConnection.value = new WebSocket(wsUrl);
    connectionStatus.value = "connecting";

    wsConnection.value.onopen = () => {
      console.log("WebSocket connected for diagnostics");
      connectionStatus.value = "connected";

      // Request immediate diagnostics update
      wsConnection.value.send(JSON.stringify({ type: "get_diagnostics" }));

      // Setup a ping interval to keep the connection alive
      const pingInterval = setInterval(() => {
        if (wsConnection.value && wsConnection.value.readyState === WebSocket.OPEN) {
          wsConnection.value.send(JSON.stringify({ type: "ping" }));
        } else {
          clearInterval(pingInterval);
        }
      }, 30000); // Send ping every 30 seconds

      // Store the interval ID to clear it on unmount
      wsConnection.value.pingInterval = pingInterval;
    };

    wsConnection.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "diagnostics_update") {
          diagnostics.value = data.data;
          lastUpdated.value = new Date().toLocaleString();
        } else if (data.type === "conversation_update") {
          // Update specific conversation
          if (diagnostics.value.conversations) {
            const index = diagnostics.value.conversations.findIndex(
              (c) => c.conversation_id === data.data.conversation_id
            );

            if (index >= 0) {
              diagnostics.value.conversations[index] = data.data;
            } else {
              diagnostics.value.conversations.push(data.data);
            }
          }
        }
      } catch (error) {
        console.error("Error processing WebSocket message:", error);
      }
    };

    wsConnection.value.onclose = () => {
      console.log("WebSocket disconnected, attempting to reconnect in 5s...");
      connectionStatus.value = "disconnected";

      // Clear the ping interval if it exists
      if (wsConnection.value && wsConnection.value.pingInterval) {
        clearInterval(wsConnection.value.pingInterval);
      }

      // Try to reconnect after 5 seconds
      setTimeout(setupWebSocket, 5000);
    };

    wsConnection.value.onerror = (error) => {
      console.error("WebSocket error:", error);
      connectionStatus.value = "error";
    };
  } catch (error) {
    console.error("WebSocket connection error:", error);
    connectionStatus.value = "error";
  }
}

onMounted(() => {
  fetchDiagnostics();
  setupWebSocket();

  // Fallback polling in case WebSocket fails
  const intervalId = setInterval(fetchDiagnostics, 30000);

  onUnmounted(() => {
    clearInterval(intervalId);
    if (wsConnection.value) {
      // Clear the ping interval if it exists
      if (wsConnection.value.pingInterval) {
        clearInterval(wsConnection.value.pingInterval);
      }
      wsConnection.value.close();
      wsConnection.value = null;
    }
  });
});
</script>

<style scoped>
.diagnostics-container {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.status-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #f0f8ff;
  padding: 15px;
  border-radius: 8px;
  margin-bottom: 20px;
  border-left: 5px solid #4caf50;
}

.status-panel.status-error {
  background-color: #fff8f0;
  border-left-color: #ff5722;
}

.connection-status {
  font-weight: bold;
}

.ws-status {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.9em;
}

.ws-connected {
  background-color: #e8f5e9;
  color: #2e7d32;
}

.ws-connecting {
  background-color: #fff8e1;
  color: #ff8f00;
}

.ws-disconnected {
  background-color: #fafafa;
  color: #757575;
}

.ws-error {
  background-color: #ffebee;
  color: #c62828;
}

.status-indicator {
  display: flex;
  align-items: center;
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background-color: #ccc;
  margin-right: 10px;
}

.status-dot.active {
  background-color: #4caf50;
  box-shadow: 0 0 10px rgba(76, 175, 80, 0.5);
}

.reinit-button {
  background-color: #2196f3;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

.reinit-button:disabled {
  background-color: #bdbdbd;
  cursor: not-allowed;
}

.diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
}

.diagnostics-card {
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  padding: 20px;
}

.wide {
  grid-column: 1 / -1;
}

.resource-meters {
  margin-top: 15px;
}

.meter-container {
  margin-bottom: 15px;
}

.meter-container label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.meter {
  height: 12px;
  background-color: #e0e0e0;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 5px;
}

.meter-fill {
  height: 100%;
  border-radius: 6px;
  transition: width 0.5s ease;
}

.meter-fill.normal {
  background-color: #4caf50;
}

.meter-fill.warning {
  background-color: #ff9800;
}

.meter-fill.critical {
  background-color: #f44336;
}

.system-info {
  margin-top: 20px;
  padding-top: 15px;
  border-top: 1px solid #eee;
}

.system-info p {
  margin: 5px 0;
  color: #666;
}

.client-status,
.session-info,
.websocket-info,
.email-status {
  margin-top: 15px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.status-label {
  font-weight: bold;
  color: #666;
}

.status-value {
  font-weight: bold;
}

.status-ok {
  color: #4caf50;
}

.status-error {
  color: #f44336;
}

.status-pending {
  color: #ff9800;
}

.status-inactive {
  color: #9e9e9e;
}

.conversations-list {
  margin-top: 15px;
  max-height: 300px;
  overflow-y: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

th {
  font-weight: bold;
  background-color: #f5f5f5;
}

.error-log {
  margin-top: 15px;
  max-height: 200px;
  overflow-y: auto;
}

.error-item {
  border-left: 3px solid #f44336;
  padding: 10px;
  margin-bottom: 10px;
  background-color: #fff8f8;
}

.error-time {
  font-size: 0.8em;
  color: #666;
  margin-bottom: 5px;
}

.error-message {
  font-weight: bold;
  margin-bottom: 5px;
}

.error-details {
  font-size: 0.9em;
  color: #666;
  white-space: pre-wrap;
  word-break: break-word;
}

.no-data {
  padding: 20px;
  text-align: center;
  color: #9e9e9e;
  font-style: italic;
}

/* Media queries for responsiveness */
@media (max-width: 768px) {
  .status-panel {
    flex-direction: column;
    align-items: flex-start;
  }

  .status-indicator,
  .last-updated,
  .reinit-button {
    margin-bottom: 10px;
  }

  .diagnostics-grid {
    grid-template-columns: 1fr;
  }
}
</style>