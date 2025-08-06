<template>
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
            :class="getResourceClass(diagnostics.system_resources.cpu_percent)"
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
              getResourceClass(diagnostics.system_resources.disk_usage_percent)
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
</template>

<script setup>
defineProps({
  systemResources: Object,
  systemInfo: Object,
  diagnostics: Object,
});

function getResourceClass(percent) {
  if (percent >= 90) return "critical";
  if (percent >= 75) return "warning";
  return "normal";
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
  border-top: 4px solid #2196f3; /* System Resources - blue */
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

.diagnostics-card h2::before {
  content: "";
  display: inline-block;
  width: 18px;
  height: 18px;
  margin-right: 8px;
  background-color: currentColor;
  mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M15,4V8H13V4H11V8H9V4H7V8H5V10H7V14H5V16H7V20H9V16H11V20H13V16H15V20H17V16H19V14H17V10H19V8H17V4H15M13,14H11V10H13V14Z' /%3E%3C/svg%3E");
  -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M15,4V8H13V4H11V8H9V4H7V8H5V10H7V14H5V16H7V20H9V16H11V20H13V16H15V20H17V16H19V14H17V10H19V8H17V4H15M13,14H11V10H13V14Z' /%3E%3C/svg%3E");
  mask-size: contain;
  -webkit-mask-size: contain;
  mask-repeat: no-repeat;
  -webkit-mask-repeat: no-repeat;
  opacity: 0.7;
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
</style>
