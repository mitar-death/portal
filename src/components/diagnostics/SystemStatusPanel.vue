<template>
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
            connectionStatus === 'error' || connectionStatus === 'disconnected',
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
      @click="reinitializeSystem"
      :disabled="reinitializing"
      class="reinit-button"
    >
      {{ reinitializing ? "Reinitializing..." : "Reinitialize AI System" }}
    </button>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from "vue";

const props = defineProps({
  isSystemHealthy: {
    type: Boolean,
    default: true,
  },
  connectionStatus: {
    type: String,
    default: "connected",
  },
  lastUpdated: {
    type: String,
    default: new Date().toLocaleString(),
  },
  reinitializing: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["reinitialize"]);

function reinitializeSystem() {
  emit("reinitialize");
}
</script>

<style scoped>
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

.connection-status {
  font-weight: bold;
  display: flex;
  align-items: center;
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background-color: #ccc;
  margin-right: 5px;
}
.status-text {
  color: #333;
  font-weight: 600;
}

.status-dot.active {
  background-color: #4caf50;
  box-shadow: 0 0 10px rgba(76, 175, 80, 0.5);
}

.status-text-healthy {
  color: #1b5e20;
}

.status-text-connected {
  color: #1b5e20;
  font-weight: 600;
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
</style>