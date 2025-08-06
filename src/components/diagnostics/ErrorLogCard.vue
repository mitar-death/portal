<template>
  <div class="diagnostics-card">
    <h2>Recent Errors</h2>
    <div class="conversation-search">
      <input
        type="text"
        v-model="errorSearchQuery"
        placeholder="Search in error messages..."
        class="search-input"
        @input="handleErrorSearch"
      />
    </div>
    <div class="error-log">
      <div v-if="recentErrors && recentErrors.length > 0">
        <div
          v-for="(error, index) in recentErrors"
          :key="index"
          class="error-item"
          :class="{ 'error-expanded': isErrorExpanded(index) }"
          @click="toggleError(index)"
        >
          <div class="error-header">
            <div class="error-time">{{ formatTime(error.timestamp) }}</div>
            <div class="error-severity" :class="getErrorSeverityClass(error)">
              {{ getErrorSeverity(error) }}
            </div>
          </div>
          <div class="error-message">{{ error.message }}</div>
          <div
            v-if="isErrorExpanded(index) && error.details"
            class="error-details"
          >
            {{ error.details }}
          </div>
          <div class="error-toggle">
            {{ isErrorExpanded(index) ? "▲ Hide Details" : "▼ Show Details" }}
          </div>
        </div>
      </div>
      <div v-else class="no-data">No recent errors</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  recentErrors: {
    type: Array,
    default: () => [],
  },
  expandedErrors: {
    type: Array,
    default: () => [],
  },
});

const errorSearchQuery = ref("");

const emit = defineEmits(["toggle-error"]);

function isErrorExpanded(index) {
  return props.expandedErrors.includes(index);
}

function handleErrorSearch() {
  // Emit the search query to parent component for filtering
  emit("search-errors", errorSearchQuery.value);
}

function toggleError(index) {
  emit("toggle-error", index);
}

function formatTime(timestamp) {
  if (!timestamp) return "N/A";
  const date = new Date(timestamp);
  return date.toLocaleString();
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
</script>

<style scoped>
.diagnostics-card {
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  padding: 24px;
  color: #333;
  transition: transform 0.2s, box-shadow 0.2s;
  border-top: 4px solid #f44336; /* Recent Errors - red */
  background-color: #fef8f8;
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

.error-log {
  max-height: 400px;
  overflow-y: auto;
}

.error-item {
  padding: 16px;
  margin-bottom: 16px;
  background-color: #fff;
  border-radius: 8px;
  border-left: 4px solid #f44336;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  cursor: pointer;
  transition: all 0.2s ease;
}

.error-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.error-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.error-time {
  font-size: 0.85rem;
  color: #757575;
}

.error-severity {
  font-size: 0.85rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 12px;
}

.severity-critical {
  background-color: #ffebee;
  color: #c62828;
}

.severity-warning {
  background-color: #fff8e1;
  color: #f57f17;
}

.severity-info {
  background-color: #e3f2fd;
  color: #1565c0;
}

.error-message {
  font-weight: 600;
  margin-bottom: 8px;
}

.error-details {
  margin-top: 12px;
  padding: 12px;
  background-color: #f5f5f5;
  border-radius: 6px;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 0.9rem;
}

.error-toggle {
  margin-top: 8px;
  font-size: 0.85rem;
  color: #1976d2;
  text-align: right;
}

.error-expanded {
  background-color: #fff9f9;
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
</style>