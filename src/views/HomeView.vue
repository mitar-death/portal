<template>
  <v-container fluid>
    <v-row>
      <SidebarList
        :groups="groups"
        :selectedGroup="selectedGroup"
        @selectGroup="selectGroup"
        @loadGroups="loadGroups"
        :loading="loading"
        @loginTelegram="loginTelegram"
      />
      <!-- Main Content Area -->
      <v-col cols="12" md="9">
        <v-card elevation="2" class="ma-4 pa-4 fill-height">
          <div v-if="!selectedGroup" class="text-center grey--text">
            <v-icon size="48" class="mb-2">mdi-chat-outline</v-icon>
            <div>Select a group to view details</div>
          </div>
          <div v-else>
            <h2>{{ selectedGroup.title }}</h2>
            <!-- Future: load messages/details here -->
          </div>
        </v-card>
      </v-col>
    </v-row>
    <LoginModal v-model="dialog" @login-success="handleLoginSuccess" />
  </v-container>
</template>

<script setup>
import { ref, onMounted, computed } from "vue";
import { useStore } from "vuex";
import { useRouter } from "vue-router";
import SidebarList from "@/components/SidebarList.vue";
import LoginModal from "@/components/LoginModal.vue";

const store = useStore();
const router = useRouter();

// UI state
const dialog = ref(false);
const step = ref(1);

const user = ref(null);
const groups = ref([]);
const loading = ref(false);
const selectedGroup = ref(null);
const isAuthenticated = computed(() => store.getters["auth/isAuthenticated"]);

// Check authentication on component mount
onMounted(async () => {
  const authStatus = await store.dispatch("auth/checkAuthStatus");
  if (authStatus) {
    loadGroups();
  } else if (isAuthenticated.value === false) {
    // If not authenticated, redirect to login page
    router.push("/login");
  }
});

// Handlers

const loginTelegram = () => {
  dialog.value = true;
  step.value = 1;
};

// No longer needed as the TelegramLogin component handles verification

const loadGroups = async () => {
  loading.value = true;
  try {
    // Use our backend API instead of direct Telegram API
    const resp = await fetch("/api/telegram/groups", {
      headers: {
        Authorization: `Bearer ${store.getters["auth/authToken"]}`,
      },
      credentials: "include",
    });
    if (resp.ok) {
      const data = await resp.json();
      groups.value = data.groups || [];
    } else {
      console.error("Failed to load groups:", resp.status);
      // If unauthorized, redirect to login
      if (resp.status === 401) {
        store.dispatch("ui/showSnackbar", {
          text: "Session expired. Please login again.",
          color: "warning",
        });
        router.push("/login");
      }
    }
  } catch (error) {
    console.error("Error loading groups:", error);
  }
  loading.value = false;
};

const selectGroup = (group) => {
  selectedGroup.value = group;
};

// Handle successful login
const handleLoginSuccess = (userData) => {
  user.value = userData;
  dialog.value = false; // Close the login modal
  loadGroups();
};
</script>
