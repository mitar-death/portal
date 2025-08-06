<template>
  <div class="diagnostics-container">
    <h1>System Diagnostics</h1>

    <div class="status-panel" :class="{ 'status-error': !isSystemHealthy }">
      <div class="status-indicator">
        <div class="status-dot" :class="{ active: isSystemHealthy }"></div>
        <span
          class="status-text"
          :class="{ 'status-text-healthy': isSystemHealthy }"
        >
          System Status:
          {{ isSystemHealthy ? "Healthy" : "Issues Detected" }}
        </span>
      </div>
      <div class="connection-status">
        <div
          class="status-dot"
          :class="{
            active: connectionStatus === 'connected',
            warning: connectionStatus === 'connecting',
            error:
              connectionStatus === 'error' ||
              connectionStatus === 'disconnected',
          }"
        ></div>
        <span
          class="status-text"
          :class="{ 'status-text-connected': connectionStatus === 'connected' }"
        >
          Connection Status:
          {{ connectionStatus === "connected" ? "Live" : "Offline" }}
        </span>
      </div>
      <div class="last-updated" style="color: #333 !important">
        Last updated: {{ lastUpdated }}
      </div>
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

      <!-- AI Analytics -->
      <div class="diagnostics-card">
        <h2>AI System Analytics</h2>
        <div class="analytics-info">
          <div class="status-item">
            <span class="status-label">Connected AI Accounts:</span>
            <span class="status-value">
              {{ aiClientsList.filter((c) => c.connected).length }}
              / {{ aiClientsList.length }}
            </span>
          </div>
          <div class="status-item">
            <span class="status-label">Active Conversations:</span>
            <span class="status-value">{{ activeConversations.length }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Monitored Groups:</span>
            <span class="status-value">{{
              (diagnostics.group_mappings || []).length
            }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Messages Processed Today:</span>
            <span class="status-value">{{ getTotalMessagesProcessed() }}</span>
          </div>
        </div>
        <div v-if="getActiveSessions().length > 0" class="active-sessions">
          <h3>Active Sessions</h3>
          <div class="session-list">
            <div
              v-for="(session, index) in getActiveSessions()"
              :key="index"
              class="session-item"
            >
              <div class="session-name">
                {{ session.name || `Session ${index + 1}` }}
              </div>
              <div class="session-info">
                {{ formatTime(session.last_activity) }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Active Conversations -->
      <div class="diagnostics-card wide">
        <h2>Active Conversations</h2>

        <div class="conversations-header">
          <div class="conversations-tabs">
            <button
              class="tab-button"
              :class="{ active: activeTab === 'all' }"
              @click="activeTab = 'all'"
            >
              All Conversations
            </button>
            <button
              class="tab-button"
              :class="{ active: activeTab === 'recent' }"
              @click="activeTab = 'recent'"
            >
              Recent Activity
            </button>
          </div>
          <div class="conversation-search">
            <input
              type="text"
              v-model="messageSearchQuery"
              placeholder="Search in messages..."
              class="search-input"
              @input="handleMessageSearch"
            />
          </div>
        </div>

        <div
          v-if="activeTab === 'recent' && recentConversations.length > 0"
          class="conversations-list"
        >
          <div
            v-for="conv in recentConversations"
            :key="conv.conversation_id"
            class="conversation-item"
          >
            <div class="conversation-header">
              <div class="conversation-name">
                {{ conv.user_name || conv.user_id }}
              </div>
              <div class="conversation-time">
                {{ formatTime(conv.last_message_time) }}
              </div>
            </div>
            <div class="conversation-details">
              <div class="conversation-type">
                {{
                  conv.chat_type === "group" ? "Group Chat" : "Direct Message"
                }}
              </div>
              <div class="conversation-messages">
                {{ conv.message_count }} messages
              </div>
              <div
                class="conversation-status"
                :class="getConversationStatusClass(conv)"
              >
                {{ conv.status }}
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'all'" class="conversations-table">
          <!-- Search Results Section -->
          <div v-if="messageSearchQuery && searchResults.length > 0" class="search-results-container">
            <h3>Search Results ({{ getTotalSearchMatches() }} matches)</h3>
            <div class="search-results-list">
              <div v-for="result in searchResults" :key="result.conversation_id" class="search-result-group">
                <div class="search-result-header" @click="toggleConversationHistory(result.conversation_id)">
                  <div class="search-result-name">{{ result.user_name }}</div>
                  <div class="search-result-matches">{{ result.matches.length }} matches</div>
                </div>
              </div>
            </div>
            <div class="search-info">Click on a conversation to view full context</div>
          </div>
          
          <table v-if="activeConversations.length > 0">
            <thead>
              <tr>
                <th>User</th>
                <th>Type</th>
                <th>Last Message</th>
                <th>Started</th>
                <th>Messages</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <template
                v-for="conv in activeConversations"
                :key="conv.conversation_id"
              >
                <tr
                  :class="{
                    'selected-conversation':
                      selectedConversation === conv.conversation_id,
                  }"
                >
                  <td>{{ conv.user_name || conv.user_id }}</td>
                  <td>{{ conv.chat_type === "group" ? "Group" : "DM" }}</td>
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
                  <td>
                    <button
                      class="view-history-btn"
                      @click="toggleConversationHistory(conv.conversation_id)"
                    >
                      {{
                        selectedConversation === conv.conversation_id
                          ? "Hide History"
                          : "View History"
                      }}
                    </button>
                  </td>
                </tr>
                <tr
                  v-if="selectedConversation === conv.conversation_id"
                  class="conversation-history-row"
                >
                  <td colspan="7">
                    <div class="conversation-history-container">
                      <h4>Conversation History</h4>
                      <div
                        v-if="conv.history && conv.history.length"
                        class="message-list"
                      >
                        <div
                          v-for="(message, msgIndex) in conv.history"
                          :key="msgIndex"
                          class="message-item"
                          :class="{
                            'user-message':
                              !message.is_ai_message &&
                              message.role !== 'assistant',
                            'ai-message':
                              message.is_ai_message ||
                              message.role === 'assistant',
                            'search-match': messageSearchQuery && 
                              (message.message || message.content || message.text || '')
                                .toLowerCase()
                                .includes(messageSearchQuery.toLowerCase())
                          }"
                        >
                          <div class="message-header">
                            <span class="message-sender">{{
                              message.is_ai_message ||
                              message.role === "assistant"
                                ? "AI Assistant"
                                : conv.user_name || "User"
                            }}</span>
                            <span
                              class="message-time"
                              v-if="message.timestamp"
                              >{{ formatTime(message.timestamp) }}</span
                            >
                          </div>
                          <div class="message-content">
                            {{
                              message.message || message.content || message.text
                            }}
                          </div>
                        </div>
                      </div>
                      <div v-else class="no-history">
                        No message history available for this conversation.
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
          <div v-else class="no-data">No active conversations</div>
        </div>

        <div v-else class="no-data">No recent conversation activity</div>
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
        <h2>AI Clients ({{ aiClientsList.length }})</h2>
        <div v-if="aiClientsList.length > 0" class="ai-clients-table-container">
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
                v-for="client in aiClientsList"
                :key="client.account_id"
                :class="{
                  'client-connected': client.connected && client.authorized,
                  'client-warning': client.connected && !client.authorized,
                  'client-disconnected': !client.connected,
                }"
              >
                <td>
                  <strong>{{
                    client.account_name || `Account ${client.account_id}`
                  }}</strong>
                </td>
                <td>{{ client.name }}</td>
                <td>
                  <span
                    class="status-badge"
                    :class="{
                      'status-badge-ok': client.connected && client.authorized,
                      'status-badge-warning':
                        client.connected && !client.authorized,
                      'status-badge-error': !client.connected,
                    }"
                  >
                    {{
                      client.connected
                        ? client.authorized
                          ? "Active"
                          : "Unauthorized"
                        : "Offline"
                    }}
                  </span>
                </td>
                <td>{{ getGroupsForAccount(client.account_id).length }}</td>
                <td>
                  {{ getConversationsForAccount(client.account_id).length }}
                </td>
                <td>{{ getMessagesForAccount(client.account_id) }}</td>
                <td>{{ formatTime(client.last_activity || new Date()) }}</td>
                <td>{{ formatPhoneNumber(client.phone_number) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="no-data">
          No AI clients available.
          <span v-if="diagnostics.ai_clients === undefined"
            >AI clients data is missing from diagnostics.</span
          >
          <span
            v-else-if="
              diagnostics.ai_clients && diagnostics.ai_clients.length === 0
            "
            >AI clients array is empty.</span
          >
          <span v-else
            >AI clients data type: {{ typeof diagnostics.ai_clients }}</span
          >
        </div>
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
              <tr
                v-for="mapping in filteredGroupMappings"
                :key="mapping.group_id"
              >
                <td>{{ mapping.group_name || mapping.group_id }}</td>
                <td>{{ getAIAccountName(mapping.ai_account_id) }}</td>
                <td>
                  <span
                    class="status-indicator"
                    :class="getGroupStatusClass(mapping)"
                  >
                    {{ getGroupStatusText(mapping) }}
                  </span>
                </td>
                <td>
                  <div
                    class="activity-indicator"
                    :class="getActivityClass(mapping.activity_level)"
                  >
                    {{ mapping.activity_level || "None" }}
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
import { initPusher, disconnectPusher } from "@/utils/pusher-setup";
import {
  loadConversationsFromStorage,
  updateConversationInStorage,
  saveConversationsToStorage,
  debouncedUpdateConversation, // Add debounced function
  verifyConversationIntegrity, // Add verification function
} from "@/utils/local-storage";
import "@/views/search-styles.css";

const store = useStore();
const diagnostics = ref({});
const lastUpdated = ref("Never");
const reinitializing = ref(false);
const pusherClient = ref(null);
const pusherChannel = ref(null);
const connectionStatus = ref("disconnected");
const activeTab = ref("recent");
const groupFilter = ref("");
const messageSearchQuery = ref("");
const searchResults = ref([]);
const expandedErrors = ref([]);
const selectedConversation = ref(null); // Track which conversation history is being viewed

import { apiUrl } from "@/services/api-service";

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

const aiClientsList = computed(() => {
  if (!diagnostics.value || !diagnostics.value.ai_clients) {
    console.warn("No AI clients available in diagnostics data");
    return [];
  }

  const clients = diagnostics.value.ai_clients;
  console.log(`Computed aiClientsList has ${clients.length} clients`);
  return clients;
});

const recentConversations = computed(() => {
  // Return only conversations with activity in the last hour
  const oneHourAgo = new Date();
  oneHourAgo.setHours(oneHourAgo.getHours() - 1);

  // Make sure we have conversations data
  if (!activeConversations.value || !Array.isArray(activeConversations.value)) {
    console.log(
      "No active conversations available for recent conversations view"
    );
    return [];
  }

  console.log(
    `Filtering ${activeConversations.value.length} conversations for recent activity`
  );

  const filtered = activeConversations.value
    .filter((conv) => {
      if (!conv || !conv.conversation_id) {
        console.warn(
          "Found invalid conversation in active conversations:",
          conv
        );
        return false;
      }

      const lastMessageTime = conv.last_message_time
        ? new Date(conv.last_message_time)
        : null;

      const isRecent = lastMessageTime && lastMessageTime > oneHourAgo;

      if (isRecent) {
        console.log(
          `Recent conversation found: ${conv.conversation_id}, time: ${conv.last_message_time}`
        );
      }

      return isRecent;
    })
    .sort((a, b) => {
      const timeA = a.last_message_time
        ? new Date(a.last_message_time)
        : new Date(0);
      const timeB = b.last_message_time
        ? new Date(b.last_message_time)
        : new Date(0);
      return timeB - timeA; // Sort by most recent first
    })
    .slice(0, 5); // Only show 5 most recent conversations

  console.log(`Found ${filtered.length} recent conversations`);
  return filtered;
});

const filteredGroupMappings = computed(() => {
  if (!diagnostics.value || !diagnostics.value.group_mappings) return [];

  const mappings = diagnostics.value.group_mappings;
  if (!groupFilter.value) return mappings;

  const filter = groupFilter.value.toLowerCase();
  return mappings.filter((mapping) => {
    const groupName = (
      mapping.group_name ||
      mapping.group_id ||
      ""
    ).toLowerCase();
    const aiAccountName = getAIAccountName(mapping.ai_account_id).toLowerCase();
    return groupName.includes(filter) || aiAccountName.includes(filter);
  });
});

const aiAccountsCount = computed(() => {
  return (diagnostics.value.ai_clients || []).length;
});

const activeGroups = computed(() => {
  return (diagnostics.value.group_mappings || []).filter(
    (m) => m.ai_client_connected && m.ai_client_authorized
  ).length;
});

const totalMessages = computed(() => {
  return activeConversations.value.reduce(
    (sum, conv) => sum + (conv.message_count || 0),
    0
  );
});

const selectedConversationData = computed(() => {
  if (!selectedConversation.value || !diagnostics.value.conversations)
    return null;

  return diagnostics.value.conversations.find(
    (c) => c && c.conversation_id === selectedConversation.value
  );
});

const getConnectionStatusText = computed(() => {
  switch (connectionStatus.value) {
    case "connected":
      return "Live";
    case "connecting":
      return "Connecting...";
    case "error":
      return "Connection Error";
    default:
      return "Offline";
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

  const client = diagnostics.value.ai_clients.find(
    (c) => c.account_id === accountId
  );
  return client
    ? client.account_name || `Account ${accountId}`
    : `Account ${accountId}`;
}

function getGroupStatusClass(mapping) {
  if (mapping.ai_client_connected && mapping.ai_client_authorized)
    return "status-ok";
  if (mapping.ai_client_connected && !mapping.ai_client_authorized)
    return "status-warning";
  return "status-error";
}

function getGroupStatusText(mapping) {
  if (mapping.ai_client_connected && mapping.ai_client_authorized)
    return "Active";
  if (mapping.ai_client_connected && !mapping.ai_client_authorized)
    return "Unauthorized";
  return "Offline";
}

function getActivityClass(level) {
  if (!level) return "activity-none";

  const activityLevel = level.toLowerCase();
  if (activityLevel.includes("high")) return "activity-high";
  if (activityLevel.includes("medium")) return "activity-medium";
  return "activity-low";
}

function getGroupsForAccount(accountId) {
  if (!diagnostics.value.group_mappings) return [];
  return diagnostics.value.group_mappings.filter(
    (m) => m.ai_account_id === accountId
  );
}

function getConversationsForAccount(accountId) {
  if (!activeConversations.value) return [];
  return activeConversations.value.filter((c) => c.ai_account_id === accountId);
}

function getMessagesForAccount(accountId) {
  const conversations = getConversationsForAccount(accountId);
  return conversations.reduce(
    (sum, conv) => sum + (conv.message_count || 0),
    0
  );
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
    messages: getMessagesForAccount(accountId),
  };
}

function getActiveSessions() {
  if (
    !diagnostics.value.session_info ||
    !diagnostics.value.session_info.session_files
  )
    return [];

  // Convert session files to session objects with some assumed information
  return diagnostics.value.session_info.session_files.map((file, index) => {
    // Extract account name from session file if possible
    const nameParts = file.split(".");
    const name = nameParts.length > 1 ? nameParts[0] : `Session ${index + 1}`;

    return {
      name: name,
      file: file,
      // Assume the last activity was recent, this should come from the backend
      last_activity: new Date(
        Date.now() - Math.floor(Math.random() * 3600000)
      ).toISOString(),
    };
  });
}

function getTotalMessagesProcessed() {
  // This could be more accurate if the backend provides this information
  return totalMessages.value;
}

function getTotalSearchMatches() {
  // Count total matches across all search results
  return searchResults.value.reduce((total, result) => {
    return total + (result.matches ? result.matches.length : 0);
  }, 0);
}

function getErrorSeverity(error) {
  // Determine severity based on message content
  const msg = (error.message || "").toLowerCase();
  if (msg.includes("critical") || msg.includes("error")) return "Critical";
  if (msg.includes("warning")) return "Warning";
  return "Info";
}

function getErrorSeverityClass(error) {
  const severity = getErrorSeverity(error);
  if (severity === "Critical") return "severity-critical";
  if (severity === "Warning") return "severity-warning";
  return "severity-info";
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
  if (!phone) return "N/A";

  // Only show last 4 digits for privacy
  return `xxxxx${phone.slice(-4)}`;
}

// Function to toggle conversation history display
function toggleConversationHistory(conversationId) {
  if (!conversationId) {
    console.error("Invalid conversation ID provided");
    return;
  }

  if (selectedConversation.value === conversationId) {
    // If already selected, close it
    selectedConversation.value = null;
  } else {
    // Otherwise, open this conversation
    selectedConversation.value = conversationId;
    console.log(`Showing history for conversation: ${conversationId}`);

    // Find the selected conversation to check if it has history
    const conversation = diagnostics.value.conversations?.find(
      (c) => c && c.conversation_id === conversationId
    );

    if (!conversation) {
      console.error(`Could not find conversation with ID: ${conversationId}`);
      return;
    }

    if (!conversation.history || conversation.history.length === 0) {
      console.log(`No history available for conversation: ${conversationId}`);
    }
  }
}

// Function to handle message search
function handleMessageSearch() {
  if (!messageSearchQuery.value.trim()) {
    searchResults.value = [];
    return;
  }

  const query = messageSearchQuery.value.toLowerCase().trim();
  const results = [];

  // Search through all conversations and their messages
  if (diagnostics.value.conversations && Array.isArray(diagnostics.value.conversations)) {
    diagnostics.value.conversations.forEach(conv => {
      if (conv && conv.history && Array.isArray(conv.history)) {
        // Find matching messages in this conversation
        const matchingMessages = conv.history.filter(message => {
          const content = (message.message || message.content || message.text || "").toLowerCase();
          return content.includes(query);
        });

        // If we found matches, add them to results with conversation context
        if (matchingMessages.length > 0) {
          results.push({
            conversation_id: conv.conversation_id,
            user_name: conv.user_name || conv.user_id,
            chat_type: conv.chat_type,
            matches: matchingMessages
          });
        }
      }
    });
  }

  searchResults.value = results;
  
  // If we have results, automatically open the first conversation with matches
  if (results.length > 0 && !selectedConversation.value) {
    selectedConversation.value = results[0].conversation_id;
  }
}

// Helper function to merge stored conversations with fresh data
function mergeWithStoredConversations(newDiagnostics) {
  // Validate input
  if (!newDiagnostics) {
    console.error("Invalid diagnostics data received");
    return diagnostics.value || {};
  }

  // Create a new object that preserves all data from both sources
  // Start with current diagnostics data as the base
  const mergedDiagnostics = { ...diagnostics.value };

  // Then apply all new diagnostics data (except conversations which we'll handle specially)
  Object.keys(newDiagnostics).forEach((key) => {
    if (key !== "conversations") {
      mergedDiagnostics[key] = newDiagnostics[key];
    }
  });

  if (newDiagnostics.ai_clients && Array.isArray(newDiagnostics.ai_clients)) {
    mergedDiagnostics.ai_clients = newDiagnostics.ai_clients;
  } else if (
    diagnostics.value.ai_clients &&
    Array.isArray(diagnostics.value.ai_clients)
  ) {
    mergedDiagnostics.ai_clients = diagnostics.value.ai_clients;
  }

  // If we don't have stored conversations, just use the new conversations
  if (
    !diagnostics.value ||
    !diagnostics.value.conversations ||
    !Array.isArray(diagnostics.value.conversations)
  ) {
    console.log("No stored conversations to merge with");
    // Apply data integrity check to new conversations before storing
    if (
      newDiagnostics.conversations &&
      Array.isArray(newDiagnostics.conversations)
    ) {
      mergedDiagnostics.conversations = verifyConversationIntegrity(
        newDiagnostics.conversations
      );
      console.log(
        `Verified ${mergedDiagnostics.conversations.length} conversations from server`
      );
    } else {
      mergedDiagnostics.conversations = [];
    }
    return mergedDiagnostics;
  }

  // If no conversations in new data, keep our stored ones
  if (
    !newDiagnostics.conversations ||
    !Array.isArray(newDiagnostics.conversations)
  ) {
    console.log("No conversations in new data, keeping stored ones");
    mergedDiagnostics.conversations = verifyConversationIntegrity(
      diagnostics.value.conversations
    );
    return mergedDiagnostics;
  }

  // Get current stored conversations
  const storedConversations = diagnostics.value.conversations.filter(
    (c) => c && c.conversation_id
  );

  // For any conversation that exists in both, update with server data
  // but keep any conversations that only exist locally (and are recent)
  const oneHourAgo = new Date();
  oneHourAgo.setHours(oneHourAgo.getHours() - 1);

  // First, update existing conversations with server data
  const mergedConversations = newDiagnostics.conversations
    .filter((c) => c && c.conversation_id) // Filter invalid conversations from server
    .map((serverConv) => {
      // Get message count directly from history if available and not already set
      if (
        !serverConv.message_count &&
        serverConv.history &&
        Array.isArray(serverConv.history)
      ) {
        serverConv.message_count = serverConv.history.length;
      }

      // Ensure the status field is set
      if (!serverConv.status) {
        serverConv.status = "active";
      }

      // Try to find matching local conversation
      const localConv = storedConversations.find(
        (c) => c && c.conversation_id === serverConv.conversation_id
      );

      if (localConv) {
        // Create a merged conversation object
        const mergedConv = { ...localConv, ...serverConv };

        // Special handling for history - use the sophisticated merge approach
        if (
          serverConv.history &&
          localConv.history &&
          Array.isArray(serverConv.history) &&
          Array.isArray(localConv.history)
        ) {
          // Create a map of message timestamps or content to detect duplicates
          const messageMap = new Map();

          // First add all messages from server conversation
          serverConv.history.forEach((msg) => {
            const key =
              msg.timestamp ||
              msg.id ||
              msg.message ||
              msg.text ||
              JSON.stringify(msg);
            messageMap.set(key, msg);
          });

          // Then add local messages that aren't duplicates
          localConv.history.forEach((msg) => {
            const key =
              msg.timestamp ||
              msg.id ||
              msg.message ||
              msg.text ||
              JSON.stringify(msg);
            if (!messageMap.has(key)) {
              messageMap.set(key, msg);
            }
          });

          // Convert back to array and sort by timestamp if available
          mergedConv.history = Array.from(messageMap.values());
          mergedConv.history.sort((a, b) => {
            const timeA = a.timestamp ? new Date(a.timestamp) : new Date(0);
            const timeB = b.timestamp ? new Date(b.timestamp) : new Date(0);
            return timeA - timeB;
          });

          // Update message count based on history
          mergedConv.message_count = mergedConv.history.length;
        } else if (serverConv.history && serverConv.history.length > 0) {
          mergedConv.history = serverConv.history;
          mergedConv.message_count = serverConv.history.length;
        } else if (localConv.history && localConv.history.length > 0) {
          mergedConv.history = localConv.history;
          mergedConv.message_count = localConv.history.length;
        }

        // Make sure we have a last_updated timestamp
        mergedConv.last_updated = new Date().toISOString();

        return mergedConv;
      }
      return serverConv;
    });

  // Then add any local-only conversations that are still recent
  storedConversations.forEach((localConv) => {
    // Skip if we already included this conversation in the merge
    const exists = mergedConversations.some(
      (c) => c && c.conversation_id === localConv.conversation_id
    );

    if (!exists) {
      const lastMessageTime = localConv.last_message_time
        ? new Date(localConv.last_message_time)
        : localConv.last_updated
        ? new Date(localConv.last_updated)
        : null;

      // Only keep recent conversations that aren't in the server data
      if (lastMessageTime && lastMessageTime > oneHourAgo) {
        console.log(
          `Keeping local-only conversation: ${localConv.conversation_id}`
        );
        mergedConversations.push(localConv);
      }
    }
  });

  // Sort conversations by most recent activity
  mergedConversations.sort((a, b) => {
    const timeA = a.last_message_time
      ? new Date(a.last_message_time)
      : a.last_updated
      ? new Date(a.last_updated)
      : new Date(0);
    const timeB = b.last_message_time
      ? new Date(b.last_message_time)
      : b.last_updated
      ? new Date(b.last_updated)
      : new Date(0);
    return timeB - timeA; // Sort by most recent first
  });

  // Perform a final integrity check on all conversations
  const verifiedConversations =
    verifyConversationIntegrity(mergedConversations);

  mergedDiagnostics.conversations = verifiedConversations;
  console.log(
    `Merged and verified ${verifiedConversations.length} conversations`
  );

  return mergedDiagnostics;
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
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch diagnostics: ${response.status}`);
    }

    const data = await response.json();

    // Extract diagnostics data based on response format
    let newDiagnostics = {};
    if (data.diagnostics) {
      newDiagnostics = data.diagnostics;
    } else if (data.data && data.data.diagnostics) {
      newDiagnostics = data.data.diagnostics;
    } else {
      console.error("Invalid diagnostics data received:", data);
      return;
    }

    // Log AI clients if they exist
    if (newDiagnostics.ai_clients && Array.isArray(newDiagnostics.ai_clients)) {
      console.log(
        `Received ${newDiagnostics.ai_clients.length} AI clients from server API`
      );
    } else {
      console.warn("No AI clients received from server API");
    }

    const mergedDiagnostics = mergeWithStoredConversations(newDiagnostics);

    diagnostics.value = mergedDiagnostics;

    // Force reactivity on the AI clients list
    if (
      mergedDiagnostics.ai_clients &&
      Array.isArray(mergedDiagnostics.ai_clients)
    ) {
      // This will trigger a reactive update specifically for the ai_clients array
      diagnostics.value = {
        ...diagnostics.value,
        ai_clients: [...mergedDiagnostics.ai_clients],
      };
    }

    // Save conversations to local storage without debounce to ensure they're saved
    if (
      mergedDiagnostics.conversations &&
      Array.isArray(mergedDiagnostics.conversations)
    ) {
      // Use direct save instead of debounced to ensure it happens immediately
      saveConversationsToStorage(mergedDiagnostics.conversations);
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
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
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

    // Request a fresh diagnostics update through Pusher
    if (pusherChannel.value) {
      // Trigger a refresh event or simply fetch data again
      fetchDiagnostics();
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

async function setupPusher() {
  // Get the authentication token from the store
  const token = store.getters["auth/authToken"];

  if (!token) {
    console.error("No authentication token available for Pusher connection");
    connectionStatus.value = "error";
    return;
  }

  // Clean up existing connection if any
  if (pusherClient.value) {
    console.log(
      "Disconnecting existing Pusher client before creating a new one"
    );
    disconnectPusher(pusherClient.value);
    pusherClient.value = null;
    pusherChannel.value = null;
  }

  try {
    connectionStatus.value = "connecting";

    // Initialize Pusher client
    const pusher = await initPusher();

    if (!pusher) {
      console.error("Failed to initialize Pusher client");
      connectionStatus.value = "error";
      return;
    }

    pusherClient.value = pusher;

    // Connect to the diagnostics channel
    const channelName = `diagnostics`;
    console.log(`Subscribing to Pusher channel: ${channelName}`);

    pusherChannel.value = pusherClient.value.subscribe(channelName);

    // Set up event handlers
    pusherChannel.value.bind("pusher:subscription_succeeded", () => {
      console.log("Pusher subscription succeeded for diagnostics");
      connectionStatus.value = "connected";

      // Request immediate diagnostics update via API call
      fetchDiagnostics();
    });

    pusherChannel.value.bind("pusher:subscription_error", (error) => {
      console.error("Pusher subscription error:", error);
      connectionStatus.value = "error";

      // Try to reconnect after 5 seconds
      setTimeout(setupPusher, 5000);
    });

    // Handle diagnostics update events
    pusherChannel.value.bind("diagnostics_update", (message) => {
      console.log("Pusher diagnostics_update received");

      // Extract the actual diagnostics data from the message
      // The backend may send { type: "diagnostics_update", data: diagnostics_data }
      const diagnosticsData = message.data || message;

      // Ensure we have a valid diagnostics object
      if (!diagnosticsData) {
        console.error("Received empty diagnostics data");
        return;
      }

      // Log received AI clients data if any
      if (
        diagnosticsData.ai_clients &&
        Array.isArray(diagnosticsData.ai_clients)
      ) {
        console.log(
          `Received ${diagnosticsData.ai_clients.length} AI clients in diagnostics update`
        );
      }

      // Merge with stored conversations
      const mergedData = mergeWithStoredConversations(diagnosticsData);

      // Update the diagnostics with merged data
      diagnostics.value = mergedData;

      // Force reactivity on the AI clients list
      if (mergedData.ai_clients && Array.isArray(mergedData.ai_clients)) {
        // This will trigger a reactive update specifically for the ai_clients array
        diagnostics.value = {
          ...diagnostics.value,
          ai_clients: [...mergedData.ai_clients],
        };
      }

      // Update the timestamp
      lastUpdated.value = new Date().toLocaleString();

      // Save conversations to local storage immediately to avoid loss
      if (mergedData.conversations && Array.isArray(mergedData.conversations)) {
        saveConversationsToStorage(mergedData.conversations);
      }
    });

    // Handle individual conversation updates
    pusherChannel.value.bind("conversation_update", (message) => {
      // Extract the actual conversation data from the message
      // The backend sends { type: "conversation_update", data: conversation_data }
      const conversationData = message.data || message;

      if (!conversationData || !conversationData.conversation_id) {
        console.error(
          "Missing or invalid conversation_id in received data:",
          message
        );
        return;
      }

      // Ensure required fields exist
      if (!conversationData.last_updated && conversationData.timestamp) {
        conversationData.last_updated = conversationData.timestamp;
      } else if (!conversationData.last_updated) {
        conversationData.last_updated = new Date().toISOString();
      }

      if (
        !conversationData.last_message_time &&
        conversationData.last_updated
      ) {
        conversationData.last_message_time = conversationData.last_updated;
      }

      // Set default start_time if not present
      if (!conversationData.start_time) {
        conversationData.start_time =
          conversationData.last_updated || new Date().toISOString();
      }

      // Ensure status field exists
      if (!conversationData.status) {
        conversationData.status = "active";
      }

      // Update message_count based on history if available
      if (
        conversationData.history &&
        Array.isArray(conversationData.history) &&
        !conversationData.message_count
      ) {
        conversationData.message_count = conversationData.history.length;
      }

      if (!diagnostics.value.conversations) {
        diagnostics.value.conversations = [];
      }

      // Find existing conversation to update
      const index = diagnostics.value.conversations.findIndex(
        (c) => c && c.conversation_id === conversationData.conversation_id
      );

      if (index >= 0) {
        // Get the existing conversation
        const existingConv = diagnostics.value.conversations[index];

        // Special handling for history field - more sophisticated merging
        let mergedHistory = [];

        // If both have history, carefully merge
        if (
          existingConv.history &&
          conversationData.history &&
          Array.isArray(existingConv.history) &&
          Array.isArray(conversationData.history)
        ) {
          // Create a map of message timestamps or content to detect duplicates
          const messageMap = new Map();

          // First add all messages from existing conversation
          existingConv.history.forEach((msg) => {
            // Create a unique key using multiple properties to avoid collisions
            const key =
              msg.timestamp ||
              msg.id ||
              JSON.stringify({
                message: msg.message || msg.content || msg.text || "",
                is_ai_message: !!msg.is_ai_message,
                timestamp: msg.timestamp || "",
              });
            messageMap.set(key, msg);
          });

          // Then add new messages that aren't duplicates
          conversationData.history.forEach((msg) => {
            // Create a unique key using multiple properties to avoid collisions
            const key =
              msg.timestamp ||
              msg.id ||
              JSON.stringify({
                message: msg.message || msg.content || msg.text || "",
                is_ai_message: !!msg.is_ai_message,
                timestamp: msg.timestamp || "",
              });
            if (!messageMap.has(key)) {
              messageMap.set(key, msg);
            }
          });

          // Convert back to array and sort by timestamp if available
          mergedHistory = Array.from(messageMap.values());
          mergedHistory.sort((a, b) => {
            const timeA = a.timestamp ? new Date(a.timestamp) : new Date(0);
            const timeB = b.timestamp ? new Date(b.timestamp) : new Date(0);
            return timeA - timeB;
          });
        } else if (
          conversationData.history &&
          Array.isArray(conversationData.history)
        ) {
          mergedHistory = [...conversationData.history];
        } else if (
          existingConv.history &&
          Array.isArray(existingConv.history)
        ) {
          mergedHistory = [...existingConv.history];
        }

        // Create merged conversation with the new data taking precedence, except for history
        const mergedConv = {
          ...existingConv,
          ...conversationData,
          history: mergedHistory,
          last_updated: new Date().toISOString(), // Always update timestamp
        };

        // Update message count based on merged history
        if (mergedHistory.length > 0) {
          mergedConv.message_count = mergedHistory.length;
        }

        // Update the conversation in the array
        diagnostics.value.conversations[index] = mergedConv;

        // Save to local storage using the debounced function for better reliability
        debouncedUpdateConversation(mergedConv);
      } else {
        // Add new conversation with timestamp
        const newConv = {
          ...conversationData,
          last_updated: new Date().toISOString(),
        };

        // Add to diagnostics
        diagnostics.value.conversations.push(newConv);

        // Save to local storage using the debounced function
        debouncedUpdateConversation(newConv);
      }

      // Force a UI update by triggering a sort on the conversations array
      // This ensures the table display gets updated
      diagnostics.value.conversations.sort((a, b) => {
        const timeA = a.last_message_time
          ? new Date(a.last_message_time)
          : a.last_updated
          ? new Date(a.last_updated)
          : new Date(0);
        const timeB = b.last_message_time
          ? new Date(b.last_message_time)
          : b.last_updated
          ? new Date(b.last_updated)
          : new Date(0);
        return timeB - timeA; // Sort by most recent first
      });

      // Also update the last updated timestamp
      lastUpdated.value = new Date().toLocaleString();
    });

    // Set up client connection state handlers
    pusherClient.value.connection.bind("state_change", (states) => {
      if (states.current === "connected") {
        connectionStatus.value = "connected";

        // When we reconnect after a disconnection, fetch fresh data
        if (
          states.previous === "connecting" &&
          states.previous !== "initialized"
        ) {
          fetchDiagnostics();
        }
      } else if (states.current === "connecting") {
        connectionStatus.value = "connecting";
      } else if (
        states.current === "failed" ||
        states.current === "disconnected"
      ) {
        connectionStatus.value = "disconnected";

        // Try to reconnect after 5 seconds if disconnected
        if (states.current === "disconnected") {
          console.log("Scheduling Pusher reconnection in 5 seconds");
          setTimeout(setupPusher, 5000);
        }
      }
    });

    // Add debug logging for auth errors
    pusherClient.value.connection.bind("error", (error) => {
      console.error("Pusher connection error:", error);

      let errorDetails = "Unknown error";
      if (error && error.error) {
        if (error.error.data && error.error.data.code) {
          errorDetails = `Error code: ${error.error.data.code}`;

          if (error.error.data.code === 4201) {
            errorDetails +=
              " - Authentication failed. Check your Pusher credentials.";
          } else if (error.error.data.code === 4000) {
            errorDetails +=
              " - Connection error. Check your network connection.";
          }
        } else if (error.error.type) {
          errorDetails = `Error type: ${error.error.type}`;
        }
      }

      console.error("Pusher error details:", errorDetails);
      connectionStatus.value = "error";

      // Add to recent errors if the array exists
      if (diagnostics.value.recent_errors) {
        const errorObj = {
          timestamp: new Date().toISOString(),
          message: "Pusher connection error",
          details: errorDetails,
          type: "connection",
        };
        // Add to beginning of array and limit to 20 errors
        diagnostics.value.recent_errors.unshift(errorObj);
        if (diagnostics.value.recent_errors.length > 20) {
          diagnostics.value.recent_errors =
            diagnostics.value.recent_errors.slice(0, 20);
        }
      }
    });
  } catch (error) {
    console.error("Pusher setup error:", error);
    connectionStatus.value = "error";

    // Try to reconnect after 5 seconds
    setTimeout(setupPusher, 5000);
  }
}

onMounted(() => {
  // First, try to load conversations from local storage
  const storedConversations = loadConversationsFromStorage();
  if (storedConversations && storedConversations.length > 0) {
    console.log(
      `Loaded ${storedConversations.length} conversations from local storage during mount`
    );

    // Verify the integrity of stored conversations
    const verifiedConversations =
      verifyConversationIntegrity(storedConversations);
    console.log(
      `Verified ${verifiedConversations.length} conversations (removed ${
        storedConversations.length - verifiedConversations.length
      } invalid ones)`
    );

    // Initialize diagnostics with verified stored conversations
    diagnostics.value = {
      ...diagnostics.value,
      conversations: verifiedConversations,
    };

    // Update the last updated timestamp
    lastUpdated.value = new Date().toLocaleString() + " (cached)";
  }

  fetchDiagnostics();

  setupPusher();

  // Fallback polling in case Pusher fails - use a longer interval to reduce load
  const intervalId = setInterval(() => {
    fetchDiagnostics();
  }, 1200000);

  // Clean up on unmount
  onUnmounted(() => {
    clearInterval(intervalId);

    // Save any pending conversations before unmounting
    if (
      diagnostics.value.conversations &&
      Array.isArray(diagnostics.value.conversations)
    ) {
      console.log("Saving conversations before unmounting");
      saveConversationsToStorage(diagnostics.value.conversations);
    }

    // Clean up Pusher connection
    if (pusherClient.value) {
      // Unsubscribe from channel
      if (pusherChannel.value) {
        pusherClient.value.unsubscribe(pusherChannel.value.name);
      }

      // Disconnect Pusher client
      disconnectPusher(pusherClient.value);
      pusherClient.value = null;
      pusherChannel.value = null;
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
  background-color: #e8f5e9;
  padding: 20px;
  border-radius: 12px;
  margin-bottom: 30px;
  border-left: 5px solid #2e7d32;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  position: relative;
  overflow: hidden;
}

.status-panel::after {
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 120px;
  background: linear-gradient(
    90deg,
    rgba(232, 245, 233, 0) 0%,
    rgba(232, 245, 233, 0.8) 100%
  );
  z-index: 1;
  pointer-events: none;
}

.status-panel.status-error {
  background-color: #ffebee;
  border-left-color: #c62828;
}

.status-panel.status-error::after {
  background: linear-gradient(
    90deg,
    rgba(255, 235, 238, 0) 0%,
    rgba(255, 235, 238, 0.8) 100%
  );
}

.connection-status {
  font-weight: bold;
  display: flex;
  align-items: center;
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

.status-text {
  color: #333;
  font-weight: 600;
}

.status-text-healthy {
  color: #1b5e20;
}

.status-text-connected {
  color: #1b5e20;
  font-weight: 600;
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background-color: #ccc;
  margin-right: 5px;
}

.status-dot.active {
  background-color: #4caf50;
  box-shadow: 0 0 10px rgba(76, 175, 80, 0.5);
}

.reinit-button {
  background-color: #1976d2;
  color: white;
  border: none;
  padding: 10px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  box-shadow: 0 2px 6px rgba(25, 118, 210, 0.3);
}

.reinit-button::before {
  content: "";
  display: inline-block;
  width: 16px;
  height: 16px;
  margin-right: 8px;
  background-color: currentColor;
  mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z' /%3E%3C/svg%3E");
  -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z' /%3E%3C/svg%3E");
  mask-size: contain;
  -webkit-mask-size: contain;
  mask-repeat: no-repeat;
  -webkit-mask-repeat: no-repeat;
}

.reinit-button:hover:not(:disabled) {
  background-color: #1565c0;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(25, 118, 210, 0.4);
}

.reinit-button:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(25, 118, 210, 0.3);
}

.reinit-button:disabled {
  background-color: #bdbdbd;
  cursor: not-allowed;
  box-shadow: none;
}

.diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
}

.diagnostics-card {
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  padding: 24px;
  color: #333;
  transition: transform 0.2s, box-shadow 0.2s;
  border-top: 4px solid #e0e0e0;
}

.diagnostics-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
}

/* Card type variations with distinct colors */
.diagnostics-card:nth-of-type(1) {
  border-top-color: #2196f3; /* System Resources - blue */
}

.diagnostics-card:nth-of-type(2) {
  border-top-color: #4caf50; /* AI Client Status - green */
}

.diagnostics-card:nth-of-type(3) {
  border-top-color: #9c27b0; /* Active Conversations - purple */
  background-color: #f8f7fc;
}

.diagnostics-card:nth-of-type(4) {
  border-top-color: #ff9800; /* AI Analytics - orange */
  background-color: #fffaf5;
}

.diagnostics-card:nth-of-type(5) {
  border-top-color: #00bcd4; /* Email Status - teal */
  background-color: #f5fcfd;
}

.diagnostics-card:nth-of-type(6) {
  border-top-color: #f44336; /* Recent Errors - red */
  background-color: #fef8f8;
}

.diagnostics-card:nth-of-type(7) {
  border-top-color: #3f51b5; /* AI Clients - indigo */
  background-color: #f7f8fd;
}

.diagnostics-card:nth-of-type(8) {
  border-top-color: #607d8b; /* Group Mappings - blue-grey */
  background-color: #f7fafb;
}

.diagnostics-card h2 {
  margin-top: 0;
  font-size: 1.5rem;
  color: #1a237e;
  font-weight: 600;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
}

.diagnostics-card h2::before {
  content: "";
  display: inline-block;
  width: 18px;
  height: 18px;
  margin-right: 8px;
  background-color: currentColor;
  mask-size: contain;
  -webkit-mask-size: contain;
  mask-repeat: no-repeat;
  -webkit-mask-repeat: no-repeat;
  opacity: 0.7;
}

/* Add icons for each card type */
.diagnostics-card:nth-of-type(1) h2::before {
  mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M15,4V8H13V4H11V8H9V4H7V8H5V10H7V14H5V16H7V20H9V16H11V20H13V16H15V20H17V16H19V14H17V10H19V8H17V4H15M13,14H11V10H13V14Z' /%3E%3C/svg%3E");
  -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M15,4V8H13V4H11V8H9V4H7V8H5V10H7V14H5V16H7V20H9V16H11V20H13V16H15V20H17V16H19V14H17V10H19V8H17V4H15M13,14H11V10H13V14Z' /%3E%3C/svg%3E");
}

.diagnostics-card p {
  margin: 10px 0;
  color: #555;
  line-height: 1.5;
}

.diagnostics-card .status-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px dashed rgba(0, 0, 0, 0.06);
}

.diagnostics-card .status-item:last-child {
  border-bottom: none;
}

.diagnostics-card .status-label {
  font-weight: 600;
  color: #546e7a;
}

.diagnostics-card .status-value {
  font-weight: 600;
  background-color: rgba(0, 0, 0, 0.04);
  padding: 2px 8px;
  border-radius: 12px;
  min-width: 40px;
  text-align: center;
}

/* Better table styling */
table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin-top: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border-radius: 8px;
  overflow: hidden;
}

th,
td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #eceff1;
}

th {
  font-weight: 600;
  background-color: #f5f7f9;
  color: #37474f;
  text-transform: uppercase;
  font-size: 0.85rem;
  letter-spacing: 0.5px;
}

tbody tr:last-child td {
  border-bottom: none;
}

tbody tr:hover {
  background-color: rgba(0, 0, 0, 0.02);
}

/* Improved status badges */
.status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 0.85em;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
  position: relative;
  min-width: 80px;
}

.status-badge::before {
  content: "";
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}

.status-badge-ok {
  background-color: #e8f5e9;
  color: #1b5e20;
}

.status-badge-ok::before {
  background-color: #2e7d32;
  box-shadow: 0 0 6px rgba(46, 125, 50, 0.6);
}

.status-badge-warning {
  background-color: #fff8e1;
  color: #e65100;
}

.status-badge-warning::before {
  background-color: #e65100;
  box-shadow: 0 0 6px rgba(230, 81, 0, 0.6);
}

.status-badge-error {
  background-color: #ffebee;
  color: #b71c1c;
}

.status-badge-error::before {
  background-color: #b71c1c;
  box-shadow: 0 0 6px rgba(183, 28, 28, 0.6);
}

/* Better activity indicators */
.activity-indicator {
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 0.85em;
  display: inline-flex;
  align-items: center;
  min-width: 80px;
  justify-content: center;
}

.activity-indicator::before {
  content: "";
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  animation: pulse 2s infinite;
}

.activity-high {
  background-color: #ffebee;
  color: #b71c1c;
}

.activity-high::before {
  background-color: #b71c1c;
  animation-duration: 1s;
}

.activity-medium {
  background-color: #e3f2fd;
  color: #0277bd;
}

.activity-medium::before {
  background-color: #0277bd;
  animation-duration: 1.5s;
}

.activity-low {
  background-color: #e8f5e9;
  color: #2e7d32;
}

.activity-low::before {
  background-color: #2e7d32;
  animation-duration: 2s;
}

.activity-none {
  background-color: #f5f5f5;
  color: #616161;
}

.activity-none::before {
  background-color: #9e9e9e;
  animation: none;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.5);
  }
  70% {
    box-shadow: 0 0 0 5px rgba(0, 0, 0, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(0, 0, 0, 0);
  }
}

/* Improved tab buttons */
.conversations-tabs {
  display: flex;
  margin-bottom: 16px;
  border-bottom: 1px solid #e0e0e0;
  gap: 4px;
}

.tab-button {
  padding: 10px 16px;
  background-color: transparent;
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  font-weight: 600;
  color: #78909c;
  transition: all 0.2s ease;
  font-size: 0.95rem;
  position: relative;
  overflow: hidden;
}

.tab-button.active {
  color: #1976d2;
  border-bottom-color: #1976d2;
}

.tab-button::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 0;
  background-color: rgba(25, 118, 210, 0.1);
  transition: height 0.2s ease;
  z-index: -1;
}

.tab-button:hover::after {
  height: 100%;
}

/* Better conversation items */
.conversation-item {
  background-color: white;
  border-radius: 8px;
  margin-bottom: 12px;
  padding: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.conversation-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.conversation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f0f0;
}

.conversation-name {
  font-weight: 600;
  color: #37474f;
  font-size: 1.05rem;
}

.conversation-time {
  color: #78909c;
  font-size: 0.85rem;
  font-weight: 500;
}

.conversation-details {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.conversation-type,
.conversation-messages {
  color: #546e7a;
  font-size: 0.9rem;
  background-color: #f5f7f9;
  padding: 2px 8px;
  border-radius: 12px;
}

/* Filter input styling */
.filter-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  color: #37474f;
  background-color: white;
  transition: all 0.2s ease;
  margin-bottom: 16px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
}

.filter-input:focus {
  outline: none;
  border-color: #1976d2;
  box-shadow: 0 2px 8px rgba(25, 118, 210, 0.15);
}

.filter-input::placeholder {
  color: #b0bec5;
}

/* Error section styling */
.error-item {
  border-radius: 8px;
  margin-bottom: 16px;
  background-color: #fff5f5;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border-left: 4px solid #f44336;
}

.error-time {
  font-size: 0.85rem;
  color: #78909c;
  padding: 8px 16px;
  background-color: rgba(0, 0, 0, 0.02);
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.error-message {
  font-weight: 600;
  color: #d32f2f;
  padding: 12px 16px 8px;
  font-size: 1rem;
}

.error-details {
  padding: 0 16px 12px;
  color: #455a64;
  font-size: 0.9rem;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: monospace;
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 4px;
  margin: 0 16px 12px;
}

/* "No data" message styling */
.no-data {
  padding: 24px;
  text-align: center;
  color: #78909c;
  font-style: italic;
  background-color: #f8fafc;
  border-radius: 8px;
  margin-top: 16px;
  border: 1px dashed #cfd8dc;
  font-size: 1rem;
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
  color: #1b5e20;
  font-weight: bold;
}

.status-error {
  color: #b71c1c;
  font-weight: bold;
}

.status-warning {
  color: #e65100;
  font-weight: bold;
}

.status-pending {
  color: #0277bd;
  font-weight: bold;
}

.status-inactive {
  color: #424242;
}

.conversations-list {
  margin-top: 15px;
  max-height: 300px;
  overflow-y: auto;
}

/* Conversation history styles */
.selected-conversation {
  background-color: rgba(25, 118, 210, 0.05);
}

.conversation-history-row {
  background-color: #f5f9ff;
}

.conversation-history-container {
  padding: 15px;
  border-top: 1px solid #e0e0e0;
  max-height: 300px;
  overflow-y: auto;
}

.conversation-history-container h4 {
  margin-top: 0;
  margin-bottom: 10px;
  color: #1976d2;
  font-size: 1rem;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-item {
  padding: 10px 15px;
  border-radius: 8px;
  position: relative;
  max-width: 85%;
}

.user-message {
  align-self: flex-end;
  background-color: #e3f2fd;
  border-bottom-right-radius: 2px;
  margin-left: 15%;
}

.ai-message {
  align-self: flex-start;
  background-color: #f5f5f5;
  border-bottom-left-radius: 2px;
  margin-right: 15%;
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
  font-size: 0.8rem;
}

.message-sender {
  font-weight: 600;
  color: #455a64;
}

.message-time {
  color: #78909c;
  font-size: 0.75rem;
}

.message-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.no-history {
  text-align: center;
  padding: 20px;
  color: #9e9e9e;
  font-style: italic;
}

.view-history-btn {
  background-color: transparent;
  border: 1px solid #1976d2;
  color: #1976d2;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s ease;
}

.view-history-btn:hover {
  background-color: #1976d2;
  color: white;
}

.debug-btn {
  background-color: #673ab7;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  margin-top: 10px;
  display: block;
  width: fit-content;
  margin: 10px auto 0;
}

.debug-btn:hover {
  background-color: #5e35b1;
}
</style>