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
        WebSocket:
        <span
          class="ws-status"
          :class="{
            'ws-connected': connectionStatus === 'connected',
            'ws-connecting': connectionStatus === 'connecting',
            'ws-error': connectionStatus === 'error',
            'ws-disconnected': connectionStatus === 'disconnected',
          }"
        >
          {{ connectionStatus }}
        </span>
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
        <h2>Active Conversations ({{ activeConversations.length }})</h2>
        <div class="conversations-list">
          <table v-if="activeConversations.length > 0">
            <thead>
              <tr>
                <th>User</th>
                <th>Chat Type</th>
                <th>Last Message</th>
                <th>Started</th>
                <th>Messages</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="conv in activeConversations"
                :key="conv.conversation_id"
              >
                <td>{{ conv.user_name || conv.user_id }}</td>
                <td>{{ conv.chat_type }}</td>
                <td>{{ formatTime(conv.last_message_time) }}</td>
                <td>{{ formatTime(conv.start_time) }}</td>
                <td>{{ conv.message_count }}</td>
                <td>
                  <span
                    class="status-indicator"
                    :class="getConversationStatusClass(conv)"
                  >
                    {{ conv.status }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="no-data">No active conversations</div>
        </div>
      </div>

      <!-- WebSocket Info -->
      <div class="diagnostics-card">
        <h2>WebSocket Connections</h2>
        <div v-if="diagnostics.websocket_info" class="websocket-info">
          <div class="status-item">
            <span class="status-label">Active Connections:</span>
            <span class="status-value">{{
              diagnostics.websocket_info.active_connections
            }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Connected Users:</span>
            <span class="status-value">{{
              diagnostics.websocket_info.connected_users
            }}</span>
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
          class="ai-clients-list"
        >
          <table>
            <thead>
              <tr>
                <th>Account</th>
                <th>Connection Status</th>
                <th>Authorization</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="client in diagnostics.ai_clients"
                :key="client.account_id"
              >
                <td>
                  {{ client.account_name || `Account ${client.account_id}` }}
                </td>
                <td>
                  <span
                    class="status-indicator"
                    :class="{
                      'status-ok': client.connected,
                      'status-error': !client.connected,
                    }"
                  >
                    {{ client.connected ? "Connected" : "Disconnected" }}
                  </span>
                </td>
                <td>
                  <span
                    class="status-indicator"
                    :class="{
                      'status-ok': client.authorized,
                      'status-error': !client.authorized,
                    }"
                  >
                    {{ client.authorized ? "Authorized" : "Unauthorized" }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="no-data">No AI clients available</div>
      </div>

      <!-- Group Mappings -->
      <div class="diagnostics-card wide">
        <h2>Group-to-AI Mappings</h2>
        <div
          v-if="
            diagnostics.group_mappings && diagnostics.group_mappings.length > 0
          "
          class="mappings-list"
        >
          <table>
            <thead>
              <tr>
                <th>Group ID</th>
                <th>AI Account</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="mapping in diagnostics.group_mappings"
                :key="mapping.group_id"
              >
                <td>{{ mapping.group_id }}</td>
                <td>{{ getAIAccountName(mapping.ai_account_id) }}</td>
                <td>
                  <span
                    class="status-indicator"
                    :class="{
                      'status-ok':
                        mapping.ai_client_connected &&
                        mapping.ai_client_authorized,
                      'status-warning':
                        mapping.ai_client_connected &&
                        !mapping.ai_client_authorized,
                      'status-error': !mapping.ai_client_connected,
                    }"
                  >
                    {{ getStatusText(mapping) }}
                  </span>
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
import { apiUrl } from '@/services/api-service';

console.log(`Using API URL in DiagnosticsView: ${apiUrl}`);

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

async function fetchDiagnostics() {
  try {
    const response = await fetch(`${apiUrl}/diagnostics`);
    if (!response.ok) {
      throw new Error("Failed to fetch diagnostics");
    }
    const data = await response.json();
    if (!data || !data.diagnostics) {
      console.error("Invalid diagnostics data received");
      return;
    }
    diagnostics.value = data.diagnostics;
    lastUpdated.value = new Date().toLocaleString();
  } catch (error) {
    console.error("Error fetching diagnostics:", error);
  }
}

async function reinitializeAI() {
  try {
    reinitializing.value = true;
    const response = await fetch(`${apiUrl}/diagnostics/reinitialize`, {
      method: "POST",
    });

    if (response.ok) {
      const data = await response.json();
      if (data && data.diagnostics) {
        diagnostics.value = data.diagnostics;
        lastUpdated.value = new Date().toLocaleString();
      }
    } else {
      console.error("Error reinitializing AI:", response.statusText);
    }

    // Request a fresh diagnostics update through WebSocket
    if (
      wsConnection.value &&
      wsConnection.value.readyState === WebSocket.OPEN
    ) {
      wsConnection.value.send(
        JSON.stringify({
          type: "get_diagnostics",
        })
      );
    }
  } catch (error) {
    console.error("Error reinitializing AI:", error);
    // Add to recent errors if the array exists
    if (diagnostics.value.recent_errors) {
      diagnostics.value.recent_errors.unshift({
        timestamp: new Date().toISOString(),
        message: "Failed to reinitialize AI system",
        details: error.message || "Unknown error occurred",
      });
    }
  } finally {
    reinitializing.value = false;
  }
}

function setupWebSocket() {
  // Get the authentication token from the store
  const token = store.getters["auth/getToken"];

  if (!token) {
    console.error("No authentication token available for WebSocket connection");
    return;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/diagnostics?token=${token}`;

  if (
    wsConnection.value &&
    wsConnection.value.readyState !== WebSocket.CLOSED
  ) {
    console.log(
      "Closing existing WebSocket connection before creating a new one"
    );
    wsConnection.value.close();
  }

  wsConnection.value = new WebSocket(wsUrl);
  connectionStatus.value = "connecting";

  wsConnection.value.onopen = () => {
    console.log("WebSocket connected for diagnostics");
    connectionStatus.value = "connected";

    // Request immediate diagnostics update
    wsConnection.value.send(
      JSON.stringify({
        type: "get_diagnostics",
      })
    );

    // Setup a ping interval to keep the connection alive
    const pingInterval = setInterval(() => {
      if (
        wsConnection.value &&
        wsConnection.value.readyState === WebSocket.OPEN
      ) {
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