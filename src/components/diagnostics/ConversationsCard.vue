<template>
  <div class="diagnostics-card wide">
    <h2>Active Conversations</h2>

    <div class="conversations-header">
      <div class="conversations-tabs">
        <button
          class="tab-button"
          :class="{ active: activeTab === 'all' }"
          @click="changeTab('all')"
        >
          All Conversations ({{ activeConversations.length }})
        </button>
        <button
          class="tab-button"
          :class="{ active: activeTab === 'recent' }"
          @click="changeTab('recent')"
        >
          Recent Activity
        </button>
      </div>
      <div class="conversation-search">
        <input
          type="text"
          v-model="localSearchQuery"
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
            {{ conv.chat_type === "group" ? "Group Chat" : "Direct Message" }}
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
      <div
        v-if="props.messageSearchQuery && searchResults.length > 0"
        class="search-results-container"
      >
        <h3>Search Results ({{ getTotalSearchMatches() }} matches)</h3>
        <div class="search-results-list">
          <div
            v-for="result in searchResults"
            :key="result.conversation_id"
            class="search-result-group"
          >
            <div
              class="search-result-header"
              @click="toggleConversationHistory(result.conversation_id)"
            >
              <div class="search-result-name">{{ result.user_name }}</div>
              <div class="search-result-matches">
                {{ result.matches.length }} matches
              </div>
            </div>
          </div>
        </div>
        <div class="search-info">
          Click on a conversation to view full context
        </div>
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
                          message.is_ai_message || message.role === 'assistant',
                        'search-match':
                          props.messageSearchQuery &&
                          (
                            message.message ||
                            message.content ||
                            message.text ||
                            ''
                          )
                            .toLowerCase()
                            .includes(props.messageSearchQuery.toLowerCase()),
                      }"
                    >
                      <div class="message-header">
                        <span class="message-sender">{{
                          message.is_ai_message || message.role === "assistant"
                            ? "AI Assistant"
                            : conv.user_name || "User"
                        }}</span>
                        <span class="message-time" v-if="message.timestamp">{{
                          formatTime(message.timestamp)
                        }}</span>
                      </div>
                      <div class="message-content">
                        {{ message.message || message.content || message.text }}
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
</template>

<script setup>
import { ref, computed } from "vue";

const props = defineProps({
  conversations: {
    type: Array,
    default: () => [],
  },
  recentConversations: {
    type: Array,
    default: () => [],
  },
  searchResults: {
    type: Array,
    default: () => [],
  },
  selectedConversation: {
    type: String,
    default: null,
  },
  messageSearchQuery: {
    type: String,
    default: "",
  },
  activeTab: {
    type: String,
    default: "recent",
  },
});

const localSearchQuery = ref(props.messageSearchQuery || "");

const activeConversations = computed(() => {
  return props.conversations || [];
});

const emit = defineEmits([
  "update:selectedConversation",
  "update:activeTab",
  "update:messageSearchQuery",
]);

function changeTab(tab) {
  emit("update:activeTab", tab);
}

function handleMessageSearch() {
  emit("update:messageSearchQuery", localSearchQuery.value);
}

function toggleConversationHistory(conversationId) {
  if (props.selectedConversation === conversationId) {
    emit("update:selectedConversation", null);
  } else {
    emit("update:selectedConversation", conversationId);
  }
}

function getConversationStatusClass(conv) {
  if (!conv || !conv.status) return "status-inactive";

  const status = conv.status.toLowerCase();
  if (status === "active") return "status-ok";
  if (status === "pending") return "status-pending";
  return "status-inactive";
}

function formatTime(timestamp) {
  if (!timestamp) return "N/A";
  const date = new Date(timestamp);
  return date.toLocaleString();
}

function getTotalSearchMatches() {
  return props.searchResults.reduce(
    (total, result) => total + (result.matches?.length || 0),
    0
  );
}
</script>

<style scoped>
/* Improved tab buttons */
.conversations-tabs {
  display: flex;
  margin-bottom: 16px;
  border-bottom: 1px solid #e0e0e0;
  gap: 4px;
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

.status-indicator {
  display: flex;
  align-items: center;
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