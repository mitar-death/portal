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

<script>
import { useTheme } from "vuetify";

export default {
  name: "SettingsView",

  data() {
    const theme = useTheme();

    return {
      darkMode: theme.global.current.value.dark,
      notifications: localStorage.getItem("notifications") === "true",
      confirmDialog: false,
      confirmResetDialog: false,
      isResettingAI: false,
      resetStatus: null,
    };
  },

  methods: {
    toggleDarkMode(value) {
      const theme = useTheme();
      theme.global.name.value = value ? "dark" : "light";
    },

    toggleNotifications(value) {
      localStorage.setItem("notifications", value);
    },

    confirmLogout() {
      this.confirmDialog = true;
    },

    confirmResetAI() {
      this.confirmResetDialog = true;
    },

    async resetAIMessenger() {
      this.confirmResetDialog = false;
      this.isResettingAI = true;
      this.resetStatus = null;

      try {
        const response = await fetch("/api/ai/reinitialize", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
        });

        const result = await response.json();

        if (result.success) {
          this.resetStatus = {
            type: "success",
            message: "AI Messenger successfully reset and reinitialized",
          };
        } else {
          this.resetStatus = {
            type: "warning",
            message: `Reset partial: ${result.message}`,
          };
        }
      } catch (error) {
        console.error("Error resetting AI messenger:", error);
        this.resetStatus = {
          type: "error",
          message: `Failed to reset AI messenger: ${error.message}`,
        };
      } finally {
        this.isResettingAI = false;
      }
    },

    async logoutFromAllDevices() {
      this.confirmDialog = false;
      await this.$store.dispatch("logout");
      this.$router.push("/");
    },
  },
};
</script>
