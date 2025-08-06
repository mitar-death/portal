<template>
  <div class="diagnostics-container">
    <h1>System Diagnostics</h1>

    <SystemStatusPanel
    :isSystemHealthy="isSystemHealthy"
    :connectionStatus="connectionStatus"
    :lastUpdated="lastUpdated"
    :reinitializing="reinitializing"
    @reinitialize="reinitializeAI"
    />
    <div class="diagnostics-grid">
      <!-- System Resources -->
      <SystemResourcesCard 
        :systemResources="diagnostics.system_resources"
        :systemInfo="diagnostics.system_info"
        :diagnostics="diagnostics"
      />

      <!-- AI Client Status -->
      <AIStatusCard 
        :aiStatus="diagnostics.ai_status || {}" 
        :sessionInfo="diagnostics.session_info || {}" 
      />

      <AnalyticsCard
        :aiClientsList="aiClientsList" 
        :conversationsCount="activeConversations.length"
        :groupsCount="(diagnostics.group_mappings || []).length"
        :totalMessages="totalMessages"
        :activeSessions="getActiveSessions()"
      />
      <!-- Active Conversations -->
      <ConversationsCard 
        :conversations="activeConversations"
        :recentConversations="recentConversations"
        :searchResults="searchResults"
        :selectedConversation="selectedConversation"
        :messageSearchQuery="messageSearchQuery"
        :activeTab="activeTab"
        @update:selectedConversation="selectedConversation = $event"
        @update:activeTab="activeTab = $event"
        @update:messageSearchQuery="messageSearchQuery = $event; handleMessageSearch()"
      />

      <!-- Error Log -->
      <ErrorLogCard 
        :recentErrors="diagnostics.recent_errors || []"
        :expandedErrors="expandedErrors"
        @toggle-error="toggleErrorExpand"
      />
      
      <!-- AI Clients -->
      <AIClientsTable 
        :aiClients="aiClientsList"
        :groupMappings="diagnostics.group_mappings || []"
        :conversations="activeConversations"
      />

      <!-- Group Mappings -->
      <GroupMappingsTable 
        :groupMappings="diagnostics.group_mappings || []"
        :groupFilter="groupFilter"
        :aiClientsList="aiClientsList"
        :conversations="activeConversations"
        @update:groupFilter="groupFilter = $event"
      />
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

import SystemStatusPanel from "@/components/diagnostics/SystemStatusPanel.vue";
import SystemResourcesCard from "@/components/diagnostics/SystemResourcesCard.vue";
import AnalyticsCard from "@/components/diagnostics/AnalyticsCard.vue";
import ConversationsCard from "@/components/diagnostics/ConversationsCard.vue";
import AIStatusCard from "@/components/diagnostics/AIStatusCard.vue";
import AIClientsTable from "@/components/diagnostics/AIClientsTable.vue";
import GroupMappingsTable from "@/components/diagnostics/GroupMappingsTable.vue";
import ErrorLogCard from "@/components/diagnostics/ErrorLogCard.vue";


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

console.log("Checking system health...", diagnostics.value.ai_status);
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
    .slice(0, 5); 
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

// Alias for ErrorLogCard component
function toggleErrorExpand(errorIndex) {
  toggleErrorDetails(errorIndex);
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
    // Apply data integrity check to new conversations before storing
    if (
      newDiagnostics.conversations &&
      Array.isArray(newDiagnostics.conversations)
    ) {
      mergedDiagnostics.conversations = verifyConversationIntegrity(
        newDiagnostics.conversations
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

    pusherChannel.value = pusherClient.value.subscribe(channelName);

    // Set up event handlers
    pusherChannel.value.bind("pusher:subscription_succeeded", () => {
      connectionStatus.value = "connected";

      // Request immediate diagnostics update via API call
      fetchDiagnostics();
    });

    pusherChannel.value.bind("pusher:subscription_error", (error) => {
      connectionStatus.value = "error";

      // Try to reconnect after 5 seconds
      setTimeout(setupPusher, 5000);
    });

    // Handle diagnostics update events
    pusherChannel.value.bind("diagnostics_update", (message) => {

      // Extract the actual diagnostics data from the message
      // The backend may send { type: "diagnostics_update", data: diagnostics_data }
      const diagnosticsData = message.data || message;

      // Ensure we have a valid diagnostics object
      if (!diagnosticsData) {
        console.error("Received empty diagnostics data");
        return;
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
    // Verify the integrity of stored conversations
    const verifiedConversations =
      verifyConversationIntegrity(storedConversations);
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

<style >
.diagnostics-container {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
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

</style>