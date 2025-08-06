<template>
  <div class="diagnostics-card wide">
    <h2>AI Clients ({{ aiClients.length }})</h2>
    <div v-if="aiClients.length > 0" class="ai-clients-table-container">
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
            v-for="client in aiClients"
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
    <div v-else class="no-data">No AI clients available.</div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  aiClients: {
    type: Array,
    default: () => [],
  },
  groupMappings: {
    type: Array,
    default: () => [],
  },
  conversations: {
    type: Array,
    default: () => [],
  },
});

function formatTime(timestamp) {
  if (!timestamp) return "N/A";
  const date = new Date(timestamp);
  return date.toLocaleString();
}

function formatPhoneNumber(phone) {
  if (!phone) return "N/A";
  // Only show last 4 digits for privacy
  return `xxxxx${phone.slice(-4)}`;
}

// Since we don't have access to these methods from the parent component,
// we'll implement them within this component
function getGroupsForAccount(accountId) {
  const groups = props.groupMappings || [];
  return groups.filter((group) => group.ai_account_id === accountId);
}

function getConversationsForAccount(accountId) {
  const convs = props.conversations || [];
  return convs.filter((conv) => conv.ai_account_id === accountId);
}

function getMessagesForAccount(accountId) {
  const convs = getConversationsForAccount(accountId);
  return convs.reduce((total, conv) => total + (conv.message_count || 0), 0);
}
</script>

<style scoped>
.diagnostics-card {
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  padding: 24px;
  color: #333;
  transition: transform 0.2s, box-shadow 0.2s;
  border-top: 4px solid #3f51b5; /* AI Clients - indigo */
  background-color: #f7f8fd;
}

.diagnostics-card.wide {
  grid-column: span 2;
}

.diagnostics-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
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

.ai-clients-table-container {
  overflow-x: auto;
  margin-top: 20px;
}

.ai-clients-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.ai-clients-table th,
.ai-clients-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #e0e0e0;
}

.ai-clients-table th {
  background-color: #f5f5f5;
  font-weight: 600;
  color: #424242;
}

.client-connected {
  background-color: #f1f8e9;
}

.client-warning {
  background-color: #fff8e1;
}

.client-disconnected {
  background-color: #fafafa;
  color: #757575;
}

.status-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 500;
}

.status-badge-ok {
  background-color: #e8f5e9;
  color: #2e7d32;
}

.status-badge-warning {
  background-color: #fff8e1;
  color: #f57f17;
}

.status-badge-error {
  background-color: #f5f5f5;
  color: #757575;
}

.no-data {
  padding: 24px;
  text-align: center;
  color: #78909c;
  font-style: italic;
  background-color: #f8fafc;
  border-radius: 8px;
  margin-top: 20px;
}
</style>