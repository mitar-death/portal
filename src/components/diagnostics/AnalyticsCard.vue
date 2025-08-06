<template>
  <div class="diagnostics-card">
    <h2>AI System Analytics</h2>
    <div class="analytics-info">
      <div class="status-item">
        <span class="status-label">Connected AI Accounts:</span>
        <span class="status-value">
          {{ connectedClientsCount }}
          / {{ aiClientsList.length }}
        </span>
      </div>
      <div class="status-item">
        <span class="status-label">Active Conversations:</span>
        <span class="status-value">{{ conversationsCount }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">Monitored Groups:</span>
        <span class="status-value">{{ groupsCount }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">Messages Processed Today:</span>
        <span class="status-value">{{ totalMessages }}</span>
      </div>
    </div>
    <div v-if="activeSessions.length > 0" class="active-sessions">
      <h3>Active Sessions</h3>
      <div class="session-list">
        <div
          v-for="(session, index) in activeSessions"
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
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  aiClientsList: {
    type: Array,
    default: () => [],
  },
  conversationsCount: {
    type: Number,
    default: 0,
  },
  groupsCount: {
    type: Number,
    default: 0,
  },
  totalMessages: {
    type: Number,
    default: 0,
  },
  activeSessions: {
    type: Array,
    default: () => [],
  },
});

const connectedClientsCount = computed(() => {
  return props.aiClientsList.filter((c) => c.connected).length;
});

function formatTime(timestamp) {
  if (!timestamp) return "N/A";
  const date = new Date(timestamp);
  return date.toLocaleString();
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
  border-top: 4px solid #9c27b0; /* AI Analytics - purple */
  background-color: #f8f7fc;
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

.diagnostics-card h3 {
  margin-top: 20px;
  font-size: 1.2rem;
  color: #1a237e;
  font-weight: 600;
  margin-bottom: 12px;
}

.analytics-info {
  margin-top: 15px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.status-label {
  font-weight: 600;
  color: #666;
}

.status-value {
  font-weight: 700;
  color: #1a237e;
}

.active-sessions {
  margin-top: 20px;
  padding-top: 15px;
  border-top: 1px solid #eee;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.session-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background-color: #f1f1fe;
  border-radius: 8px;
}

.session-name {
  font-weight: 600;
  color: #333;
}

.session-info {
  font-size: 0.9rem;
  color: #666;
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
</style>