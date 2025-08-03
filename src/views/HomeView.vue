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
            <v-card-title class="d-flex align-center">
              <v-avatar size="42" color="primary" class="mr-3">
                <v-icon dark>{{ selectedGroup.is_channel ? 'mdi-bullhorn' : 'mdi-account-group' }}</v-icon>
              </v-avatar>
              <div>
                <h2 class="text-h5 mb-1">{{ selectedGroup.title }}</h2>
                <div class="text-subtitle-2 text-grey">
                  {{ selectedGroup.is_channel ? 'Channel' : 'Group' }} • {{ selectedGroup.member_count || '?' }} members
                </div>
              </div>
            </v-card-title>
            
            <v-divider class="my-3"></v-divider>
            
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-list>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon color="primary">mdi-identifier</v-icon>
                      </template>
                      <v-list-item-title>ID</v-list-item-title>
                      <v-list-item-subtitle>{{ selectedGroup.id }}</v-list-item-subtitle>
                    </v-list-item>
                    
                    <v-list-item v-if="selectedGroup.username">
                      <template v-slot:prepend>
                        <v-icon color="primary">mdi-at</v-icon>
                      </template>
                      <v-list-item-title>Username</v-list-item-title>
                      <v-list-item-subtitle>@{{ selectedGroup.username }}</v-list-item-subtitle>
                    </v-list-item>
                    
                    <v-list-item v-if="selectedGroup.description">
                      <template v-slot:prepend>
                        <v-icon color="primary">mdi-information-outline</v-icon>
                      </template>
                      <v-list-item-title>Description</v-list-item-title>
                      <v-list-item-subtitle>{{ selectedGroup.description }}</v-list-item-subtitle>
                    </v-list-item>
                    
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon color="primary">mdi-eye-outline</v-icon>
                      </template>
                      <v-list-item-title>Monitoring Status</v-list-item-title>
                      <v-list-item-subtitle>
                        <v-chip
                          size="small"
                          :color="selectedGroup.is_monitored ? 'success' : 'grey'"
                        >
                          {{ selectedGroup.is_monitored ? 'Active' : 'Inactive' }}
                        </v-chip>
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-col>
                
                <v-col cols="12" md="6">
                  <v-card outlined>
                    <v-card-title class="text-subtitle-1">Group Actions</v-card-title>
                    <v-card-text>
                      <v-btn 
                        color="primary" 
                        variant="outlined" 
                        prepend-icon="mdi-eye" 
                        class="mb-2 mr-2"
                        :to="`/telegram/groups/${selectedGroup.id}`"
                      >
                        View Details
                      </v-btn>
                      
                      <v-btn 
                        color="success" 
                        variant="outlined" 
                        prepend-icon="mdi-message-text-outline" 
                        class="mb-2"
                        @click="openTelegramLink"
                      >
                        Open in Telegram
                      </v-btn>
                    </v-card-text>
                  </v-card>
                  
                  <v-card outlined class="mt-3" v-if="selectedGroup.keywords && selectedGroup.keywords.length">
                    <v-card-title class="text-subtitle-1">Monitored Keywords</v-card-title>
                    <v-card-text>
                      <v-chip
                        v-for="keyword in selectedGroup.keywords"
                        :key="keyword"
                        class="ma-1"
                        color="info"
                        size="small"
                      >
                        {{ keyword }}
                      </v-chip>
                    </v-card-text>
                  </v-card>
                </v-col>
              </v-row>
            </v-card-text>
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
import { fetchWithAuth } from "@/services/auth-interceptor";

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
const apiUrl = process.env.VUE_APP_API_URL || '/api';

console.log(`Using API URL in HomeView: ${apiUrl}`);
// Check authentication on component mount
onMounted(async () => {
  try {
    // First check if we've been redirected from a failed auth check to avoid loops
    const currentRoute = router.currentRoute.value;
    const isRedirectBack = currentRoute.query.authChecked === 'true' || 
                         currentRoute.query.sessionExpired === 'true';
    
    // Only check auth status if we haven't been redirected from a failed check
    if (!isRedirectBack) {
      // Use the global auth check from router beforeEach,
      // we don't need to manually check here since router guards already handled it
      if (isAuthenticated.value) {
        loadGroups();
      }
    } else {
      console.log("Skipping auth check due to redirect flags");
      
      // If we're authenticated despite the redirect flags, load the data
      if (isAuthenticated.value) {
        loadGroups();
      }
    }
  } catch (error) {
    console.error("Error in HomeView onMounted:", error);
    store.dispatch("ui/showSnackbar", {
      text: "Error initializing dashboard",
      color: "error",
    });
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
    // Use our auth interceptor instead of raw fetch
    const resp = await fetchWithAuth(`${apiUrl}/telegram/groups`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    if (resp.ok) {
      const data = await resp.json();
      // Process the groups to ensure all fields we need are available
      groups.value = (data.groups || []).map(group => ({
        ...group,
        // Add default values for fields that might be missing
        is_channel: group.is_channel || false,
        member_count: group.member_count || 0,
        description: group.description || 'No description available',
        is_monitored: group.is_monitored || false,
        keywords: group.keywords || [],
        username: group.username || null
      }));
      
      // If we had a selected group, update it with the new data
      if (selectedGroup.value) {
        const updatedGroup = groups.value.find(g => g.id === selectedGroup.value.id);
        if (updatedGroup) {
          selectedGroup.value = updatedGroup;
        }
      }
    } else {
      console.error("Failed to load groups:", resp.status);
      // Our auth interceptor will handle 401 errors automatically
      if (resp.status !== 401) {
        store.dispatch("ui/showSnackbar", {
          text: "Failed to load groups: " + (resp.statusText || resp.status),
          color: "error",
        });
      }
    }
  } catch (error) {
    console.error("Error loading groups:", error);
    store.dispatch("ui/showSnackbar", {
      text: "Network error loading groups",
      color: "error",
    });
  }
  loading.value = false;
};

const selectGroup = (group) => {
  selectedGroup.value = group;
};

// Open the selected group in Telegram
const openTelegramLink = () => {
  if (!selectedGroup.value) return;
  
  let url;
  if (selectedGroup.value.username) {
    // If the group has a username, use that for the link
    url = `https://t.me/${selectedGroup.value.username}`;
  } else {
    // Otherwise use the invite link if available
    url = selectedGroup.value.invite_link || `https://t.me/c/${selectedGroup.value.id}`;
  }
  
  // Open in a new tab
  window.open(url, '_blank');
};

// Handle successful login
const handleLoginSuccess = (userData) => {
  user.value = userData;
  dialog.value = false; // Close the login modal
  loadGroups();
};
</script>

<style scoped>
.v-card-title {
  word-break: break-word;
}

.v-list-item-subtitle {
  word-break: break-word;
}

.v-card.outlined {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
}
</style>
