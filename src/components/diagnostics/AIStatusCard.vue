<template>
  <div class="diagnostics-card">
    <h2>AI Client Status</h2>
    <div class="client-status">
      <div class="status-item">
        <span class="status-label">AI Client:</span>
        <span
          class="status-value"
          :class="{
            'status-ok': aiStatus?.is_initialized,
            'status-error': !aiStatus?.is_initialized,
          }"
        >
          {{ aiStatus?.is_initialized ? "Initialized" : "Not Initialized" }}
        </span>
      </div>
      <div class="status-item">
        <span class="status-label">Connected Clients:</span>
        <span class="status-value">{{ aiStatus?.connected_clients ?? 0 }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">Active Listeners:</span>
        <span class="status-value">{{ aiStatus?.active_listeners ?? 0 }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">Groups Monitored:</span>
        <span class="status-value">{{
          aiStatus?.monitored_groups_count ?? 0
        }}</span>
      </div>
    </div>

    <!-- Session Info -->
    <div class="session-info">
      <h3>Sessions</h3>
      <div class="status-item">
        <span class="status-label">Sessions Directory:</span>
        <span
          class="status-value"
          :class="{
            'status-ok': sessionInfo?.exists,
            'status-error': !sessionInfo?.exists,
          }"
        >
          {{ sessionInfo?.exists ? "Available" : "Missing" }}
        </span>
      </div>
      <div class="status-item">
        <span class="status-label">Session Count:</span>
        <span class="status-value">{{ sessionInfo?.session_count ?? 0 }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  aiStatus: {
    type: Object,
    required: false,
    default: () => ({
      is_initialized: false,
      connected_clients: 0,
      active_listeners: 0,
      monitored_groups_count: 0,
    }),
  },
  sessionInfo: {
    type: Object,
    required: false,
    default: () => ({
      exists: false,
      session_count: 0,
    }),
  },
});

</script>

<style scoped>
.diagnostics-card {
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  padding: 24px;
  color: #333;
  transition: transform 0.2s, box-shadow 0.2s;
  border-top: 4px solid #4caf50; /* AI Client Status - green */
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

.client-status,
.session-info {
  margin-top: 15px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px dashed rgba(0, 0, 0, 0.06);
}

.status-item:last-child {
  border-bottom: none;
}

.status-label {
  font-weight: 600;
  color: #546e7a;
}

.status-value {
  font-weight: 600;
  background-color: rgba(0, 0, 0, 0.04);
  padding: 2px 8px;
  border-radius: 12px;
  min-width: 40px;
  text-align: center;
}

.status-ok {
  color: #1b5e20;
  font-weight: bold;
}

.status-error {
  color: #b71c1c;
  font-weight: bold;
}
</style>
