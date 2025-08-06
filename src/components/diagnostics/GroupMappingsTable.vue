<template>
  <div class="diagnostics-card wide">
    <h2>Group-to-AI Mappings</h2>
    <div class="group-filter">
      <input
        type="text"
        v-model="localGroupFilter"
        placeholder="Filter groups..."
        class="filter-input"
        @input="updateFilter(localGroupFilter)"
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
</template>

<script setup>
import { defineProps, ref, computed } from "vue";

const props = defineProps({
  groupMappings: {
    type: Array,
    default: () => [],
  },
  groupFilter: {
    type: String,
    default: "",
  },
  aiClientsList: {
    type: Array,
    default: () => [],
  },
  conversations: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["update:groupFilter"]);

const localGroupFilter = ref(props.groupFilter || "");

// Computed property for filtered group mappings
const filteredGroupMappings = computed(() => {
  if (!props.groupMappings || !Array.isArray(props.groupMappings)) return [];

  if (!props.groupFilter) return props.groupMappings;

  const filter = props.groupFilter.toLowerCase();
  return props.groupMappings.filter((mapping) => {
    const groupName = (
      mapping.group_name ||
      mapping.group_id ||
      ""
    ).toLowerCase();
    const aiAccountName = getAIAccountName(mapping.ai_account_id).toLowerCase();
    return groupName.includes(filter) || aiAccountName.includes(filter);
  });
});

// Watch for changes to the filter input and emit updates
function updateFilter(value) {
  emit("update:groupFilter", value);
}

// Helper functions
function formatTime(timestamp) {
  if (!timestamp) return "N/A";
  const date = new Date(timestamp);
  return date.toLocaleString();
}

function getAIAccountName(accountId) {
  if (!accountId) return "None";
  if (!props.aiClientsList) return `Account ${accountId}`;

  const client = props.aiClientsList.find((c) => c.account_id === accountId);
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

function getConversationsForGroup(groupId) {
  if (!props.conversations) return [];
  return props.conversations.filter((c) => c.group_id === groupId);
}

function getMessagesForGroup(groupId) {
  const conversations = getConversationsForGroup(groupId);
  return conversations.reduce(
    (sum, conv) => sum + (conv.message_count || 0),
    0
  );
}

function getLastActivityForGroup(groupId) {
  const conversations = getConversationsForGroup(groupId);
  if (conversations.length === 0) return null;

  // Find the most recent timestamp
  return conversations.reduce((latest, conv) => {
    const convTime = conv.last_activity ? new Date(conv.last_activity) : null;
    if (!convTime) return latest;
    if (!latest) return convTime;
    return convTime > latest ? convTime : latest;
  }, null);
}
</script>

<style scoped>
.group-mappings-table-container {
  width: 100%;
  overflow-x: auto;
}

.group-mappings-table {
  width: 100%;
  border-collapse: collapse;
}

.group-mappings-table th,
.group-mappings-table td {
  padding: 8px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.group-mappings-table th {
  background-color: #f2f2f2;
  font-weight: bold;
}

.mapping-active {
  background-color: rgba(76, 175, 80, 0.1);
}

.mapping-inactive {
  background-color: rgba(244, 67, 54, 0.1);
}

.status-badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: bold;
}

.status-badge-ok {
  background-color: #4caf50;
  color: white;
}

.status-badge-error {
  background-color: #f44336;
  color: white;
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
</style>
