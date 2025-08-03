<template>
  <div>
    <h1 class="text-h4 mb-4">Settings</h1>

    <v-card class="mx-auto mb-4" max-width="600">
      <v-card-title>Application Settings</v-card-title>

      <v-card-text>
        <v-list>
          <v-list-item>
            <v-switch
              v-model="darkMode"
              label="Dark Mode"
              @change="toggleDarkMode"
            ></v-switch>
          </v-list-item>

          <v-list-item>
            <v-switch
              v-model="notifications"
              label="Enable Notifications"
              @change="toggleNotifications"
            ></v-switch>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <v-card class="mx-auto mb-4" max-width="600">
      <v-card-title>AI Messenger Maintenance</v-card-title>

      <v-card-text>
        <p class="mb-4">
          If the AI messenger is not responding to messages, you can reset it
          here.
        </p>
        <v-btn color="primary" @click="confirmResetAI" :loading="isResettingAI">
          Reset AI Messenger
        </v-btn>
        <v-alert
          v-if="resetStatus"
          class="mt-3"
          :type="resetStatus.type"
          dismissible
        >
          {{ resetStatus.message }}
        </v-alert>
      </v-card-text>
    </v-card>

    <v-card class="mx-auto" max-width="600" color="error">
      <v-card-title class="text-white">Danger Zone</v-card-title>

      <v-card-text>
        <v-btn color="error" variant="outlined" @click="confirmLogout">
          Logout from all devices
        </v-btn>
      </v-card-text>
    </v-card>

    <!-- Confirmation Dialog -->
    <v-dialog v-model="confirmDialog" max-width="400">
      <v-card>
        <v-card-title>Confirm Action</v-card-title>
        <v-card-text>
          Are you sure you want to logout from all devices? This will revoke
          your current session.
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" text @click="confirmDialog = false"
            >Cancel</v-btn
          >
          <v-btn color="error" @click="logoutFromAllDevices">Confirm</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- AI Reset Confirmation Dialog -->
    <v-dialog v-model="confirmResetDialog" max-width="400">
      <v-card>
        <v-card-title>Reset AI Messenger</v-card-title>
        <v-card-text>
          Are you sure you want to reset the AI Messenger? This will
          reinitialize all AI accounts and mappings.
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" text @click="confirmResetDialog = false"
            >Cancel</v-btn
          >
          <v-btn color="warning" @click="resetAIMessenger">Reset</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { useTheme } from "vuetify";
import { ref } from "vue";

const theme = useTheme();

const darkMode = ref(theme.global.current.value.dark);
const notifications = ref(localStorage.getItem("notifications") === "true");
const confirmDialog = ref(false);
const confirmResetDialog = ref(false);
const isResettingAI = ref(false);
const resetStatus = ref(null);
const backendUrl = process.env.BACKEND_URL || "http://localhost:8030";

const toggleDarkMode = (value) => {
  theme.global.name.value = value ? "dark" : "light";
};

const toggleNotifications = (value) => {
  localStorage.setItem("notifications", value);
};

const confirmLogout = () => {
  confirmDialog.value = true;
};

const confirmResetAI = () => {
  confirmResetDialog.value = true;
};

const resetAIMessenger = async () => {
  confirmResetDialog.value = false;
  isResettingAI.value = true;
  resetStatus.value = null;

  try {
    const response = await fetch(`${backendUrl}/api/ai/reinitialize`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
    });

    const result = await response.json();

    if (result.success) {
      resetStatus.value = {
        type: "success",
        message: "AI Messenger successfully reset and reinitialized",
      };
    } else {
      resetStatus.value = {
        type: "warning",
        message: `Reset partial: ${result.message}`,
      };
    }
  } catch (error) {
    console.error("Error resetting AI messenger:", error);
    resetStatus.value = {
      type: "error",
      message: `Failed to reset AI messenger: ${error.message}`,
    };
  } finally {
    isResettingAI.value = false;
  }
};

const logoutFromAllDevices = async () => {
  confirmDialog.value = false;
  await store.dispatch("logout");
  router.push("/");
};
</script>
