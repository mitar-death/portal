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
        <!-- Dashboard Overview Section -->
        <v-card elevation="2" class="mb-4 ma-4 pa-4" v-if="!selectedGroup">
          <v-card-title class="text-h5 mb-3">
            <v-icon large color="primary" class="mr-2">mdi-view-dashboard</v-icon>
            Dashboard Overview
          </v-card-title>
          
          <!-- Summary Stats -->
          <v-row class="mb-4">
            <v-col cols="12" sm="6" md="3">
              <v-card class="pa-2" outlined>
                <div class="d-flex flex-column align-center">
                  <v-avatar color="primary" size="50" class="my-2">
                    <v-icon dark>mdi-account-group</v-icon>
                  </v-avatar>
                  <span class="text-h5 font-weight-bold">{{ groups.length }}</span>
                  <span class="text-subtitle-2">Total Groups</span>
                </div>
              </v-card>
            </v-col>
            
            <v-col cols="12" sm="6" md="3">
              <v-card class="pa-2" outlined>
                <div class="d-flex flex-column align-center">
                  <v-avatar color="success" size="50" class="my-2">
                    <v-icon dark>mdi-eye</v-icon>
                  </v-avatar>
                  <span class="text-h5 font-weight-bold">{{ monitoredGroups.length }}</span>
                  <span class="text-subtitle-2">Monitored Groups</span>
                </div>
              </v-card>
            </v-col>
            
            <v-col cols="12" sm="6" md="3">
              <v-card class="pa-2" outlined>
                <div class="d-flex flex-column align-center">
                  <v-avatar color="info" size="50" class="my-2">
                    <v-icon dark>mdi-tag-multiple</v-icon>
                  </v-avatar>
                  <span class="text-h5 font-weight-bold">{{ totalKeywords }}</span>
                  <span class="text-subtitle-2">Keywords</span>
                </div>
              </v-card>
            </v-col>
            
            <v-col cols="12" sm="6" md="3">
              <v-card class="pa-2" outlined>
                <div class="d-flex flex-column align-center">
                  <v-avatar color="warning" size="50" class="my-2">
                    <v-icon dark>mdi-robot</v-icon>
                  </v-avatar>
                  <span class="text-h5 font-weight-bold">{{ aiAccountsCount }}</span>
                  <span class="text-subtitle-2">AI Accounts</span>
                </div>
              </v-card>
            </v-col>
          </v-row>
          
          <!-- System Status -->
          <v-card outlined class="mb-4 pa-3">
            <div class="d-flex align-center">
              <v-icon :color="monitoredGroups.length > 0 ? 'success' : 'warning'" class="mr-2">
                {{ monitoredGroups.length > 0 ? 'mdi-check-circle' : 'mdi-alert-circle' }}
              </v-icon>
              <span class="text-subtitle-1">Monitoring Status: {{ monitoredGroups.length > 0 ? 'Active' : 'Not Active' }}</span>
              <v-spacer></v-spacer>
              <v-btn color="primary" :to="'/diagnostics'" small text>
                <v-icon small class="mr-1">mdi-chart-line</v-icon>
                System Diagnostics
              </v-btn>
            </div>
          </v-card>
          
          <!-- Monitored Groups Section -->
          <h3 class="text-h6 mb-3">
            <v-icon class="mr-2">mdi-eye-check</v-icon>
            Monitored Groups
          </h3>
          
          <v-alert v-if="monitoredGroups.length === 0" type="info" text>
            You're not monitoring any groups yet. Go to the 
            <router-link to="/groups">Groups</router-link> page to start monitoring.
          </v-alert>
          
          <v-row v-else>
            <v-col v-for="group in monitoredGroups.slice(0, 6)" :key="group.id" cols="12" sm="6" md="4">
              <v-card outlined class="group-card" @click="selectGroup(group)">
                <v-card-title class="text-subtitle-1">
                  <v-icon class="mr-2" small>
                    {{ group.is_channel ? 'mdi-bullhorn' : 'mdi-account-group' }}
                  </v-icon>
                  {{ truncateText(group.title, 20) }}
                </v-card-title>
                <v-divider></v-divider>
                <v-card-text class="pb-0">
                  <div v-if="group.username" class="mb-1 text-subtitle-2">
                    @{{ group.username }}
                  </div>
                  <div class="d-flex align-center mb-1">
                    <v-icon small class="mr-1">mdi-account-multiple</v-icon>
                    <span>{{ group.member_count.toLocaleString() }} members</span>
                  </div>
                  <div v-if="getAssignedAI(group.id)" class="d-flex align-center">
                    <v-icon small class="mr-1" color="primary">mdi-robot</v-icon>
                    <span>AI: {{ getAssignedAI(group.id) }}</span>
                  </div>
                </v-card-text>
                <v-card-actions>
                  <v-chip x-small :color="group.is_channel ? 'blue' : 'green'" text-color="white">
                    {{ group.is_channel ? 'Channel' : 'Group' }}
                  </v-chip>
                  <v-spacer></v-spacer>
                  <v-btn 
                    small 
                    icon 
                    color="primary" 
                    @click.stop="openTelegramLink(group)"
                    title="Open in Telegram"
                  >
                    <v-icon>mdi-telegram</v-icon>
                  </v-btn>
                </v-card-actions>
              </v-card>
            </v-col>
            
            <v-col v-if="monitoredGroups.length > 6" cols="12" class="text-center mt-2">
              <v-btn 
                color="primary" 
                text 
                to="/groups"
              >
                View all {{ monitoredGroups.length }} monitored groups
              </v-btn>
            </v-col>
          </v-row>
          
          <!-- Recent Keywords Section -->
          <h3 class="text-h6 mt-5 mb-3">
            <v-icon class="mr-2">mdi-tag</v-icon>
            Monitored Keywords
          </h3>
          
          <v-alert v-if="uniqueKeywords.length === 0" type="info" text>
            You haven't set up any keywords to monitor yet. Go to the 
            <router-link to="/keywords">Keywords</router-link> page to add some.
          </v-alert>
          
          <div v-else class="keyword-cloud pa-3">
            <v-chip
              v-for="keyword in uniqueKeywords.slice(0, 20)"
              :key="keyword"
              class="ma-1"
              color="info"
              small
            >
                {{ keyword.split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()).join(' ') }}
            </v-chip>
            
            <v-btn 
              v-if="uniqueKeywords.length > 20"
              text 
              small 
              color="primary" 
              class="mt-2"
              to="/keywords"
            >
              View all {{ uniqueKeywords.length }} keywords
            </v-btn>
          </div>
          
          <!-- Quick Actions -->
          <h3 class="text-h6 mt-5 mb-3">
            <v-icon class="mr-2">mdi-lightning-bolt</v-icon>
            Quick Actions
          </h3>
          
          <v-row>
            <v-col cols="12" sm="6" md="3">
              <v-btn 
                block 
                outlined 
                color="primary" 
                to="/groups" 
                height="60"
                class="text-none"
              >
                <v-icon left>mdi-account-group</v-icon>
                Manage Groups
              </v-btn>
            </v-col>
            
            <v-col cols="12" sm="6" md="3">
              <v-btn 
                block 
                outlined 
                color="success" 
                to="/keywords" 
                height="60"
                class="text-none"
              >
                <v-icon left>mdi-tag-multiple</v-icon>
                Manage Keywords
              </v-btn>
            </v-col>
            
            <v-col cols="12" sm="6" md="3">
              <v-btn 
                block 
                outlined 
                color="info" 
                to="/ai-accounts" 
                height="60"
                class="text-none"
              >
                <v-icon left>mdi-robot</v-icon>
                AI Accounts
              </v-btn>
            </v-col>
            
            <v-col cols="12" sm="6" md="3">
              <v-btn 
                block 
                outlined 
                color="warning" 
                to="/diagnostics" 
                height="60"
                class="text-none"
              >
                <v-icon left>mdi-bug</v-icon>
                System Diagnostics
              </v-btn>
            </v-col>
          </v-row>
        </v-card>

        <!-- Group Details Card (when a group is selected) -->
        <v-card v-if="selectedGroup" elevation="2" class="ma-4 pa-4 fill-height">
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
            
            <v-spacer></v-spacer>
            
            <v-btn 
              icon 
              color="grey" 
              @click="selectedGroup = null"
              title="Back to Dashboard"
            >
              <v-icon>mdi-close</v-icon>
            </v-btn>
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
                  
                  <v-list-item v-if="getAssignedAI(selectedGroup.id)">
                    <template v-slot:prepend>
                      <v-icon color="primary">mdi-robot</v-icon>
                    </template>
                    <v-list-item-title>AI Assignment</v-list-item-title>
                    <v-list-item-subtitle>
                      <v-chip size="small" color="purple" text-color="white">
                        {{ getAssignedAI(selectedGroup.id) }}
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
                      @click="openTelegramLink(selectedGroup)"
                    >
                      Open in Telegram
                    </v-btn>
                    
                    <v-btn
                      color="info"
                      variant="outlined"
                      prepend-icon="mdi-account-switch"
                      class="mb-2 mr-2"
                      :to="`/group-ai-assignments`"
                    >
                      Manage AI Assignment
                    </v-btn>
                    
                    <v-btn
                      color="warning"
                      variant="outlined"
                      prepend-icon="mdi-monitor"
                      class="mb-2"
                      @click="toggleMonitoring(selectedGroup)"
                      :loading="updatingMonitoring"
                    >
                      {{ selectedGroup.is_monitored ? 'Stop Monitoring' : 'Start Monitoring' }}
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
const updatingMonitoring = ref(false);
const isAuthenticated = computed(() => store.getters["auth/isAuthenticated"]);
import { apiUrl } from '@/services/api-service';

// Computed properties for dashboard metrics
const monitoredGroups = computed(() => {
  return groups.value.filter(group => group.is_monitored);
});

const uniqueKeywords = computed(() => {
  // Get keywords from store
  const storeKeywords = store.state.telegram.keywords || [];
  
  // Get keywords from groups
  const groupKeywords = groups.value
    .filter(group => group.keywords && group.keywords.length > 0)
    .flatMap(group => group.keywords);
  
  // Combine all keywords and remove duplicates
  const allKeywords = [...storeKeywords, ...groupKeywords];
  return Array.from(new Set(allKeywords))
    .sort((a, b) => a.localeCompare(b))
    .map(keyword => 
      keyword.split(' ').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
      ).join(' ')
    );
});

const totalKeywords = computed(() => {
  return uniqueKeywords.value.length;
});

const aiAccountsCount = computed(() => {
  // Get from store if available, otherwise default to 0
  return store.getters["ai/aiAccounts"]?.length || 0;
});

// Check authentication on component mount
onMounted(async () => {
  try {
    // First check if we've been redirected from a failed auth check to avoid loops
    const currentRoute = router.currentRoute.value;
    const isRedirectBack = currentRoute.query.authChecked === 'true' || currentRoute.query.sessionExpired === 'true';
    
    // Only check auth status if we haven't been redirected from a failed check
    if (!isRedirectBack) {
      // Use the global auth check from router beforeEach,
      // we don't need to manually check here since router guards already handled it
      if (isAuthenticated.value) {
        await loadGroups();
        
        // Load AI accounts information for the dashboard
        await store.dispatch("ai/fetchAIAccounts");
        await store.dispatch("ai/fetchGroupAssignments");
        await store.dispatch("telegram/fetchKeywords");
      }
    } else {
      console.log("Skipping auth check due to redirect flags");
      
      // If we're authenticated despite the redirect flags, load the data
      if (isAuthenticated.value) {
        await loadGroups();
        
        // Load AI accounts information for the dashboard
        await store.dispatch("ai/fetchAIAccounts");
        await store.dispatch("ai/fetchGroupAssignments");
        await store.dispatch("telegram/fetchKeywords");
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
      groups.value = (data.groups || []).map(group => ({
        ...group,
        // Add default values for fields that might be missing
        is_channel: group.is_channel || false,
        member_count: group.member_count || 0,
        description: group.description || 'No description available',
        is_monitored: group.is_monitored === true ? true : false, // Ensure boolean
        username: group.username || null,
        keywords: group.keywords || []
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
const openTelegramLink = (group) => {
  if (!group) return;
  
  let url;
  if (group.username) {
    // If the group has a username, use that for the link
    url = `https://t.me/${group.username}`;
  } else {
    // Otherwise use the invite link if available
    url = group.invite_link || `https://t.me/c/${group.id}`;
  }
  
  // Open in a new tab
  window.open(url, '_blank');
};

// Get assigned AI account name for a group
const getAssignedAI = (groupId) => {
  const assignments = store.getters["ai/groupAssignments"] || [];
  const groupAssignment = assignments.find(a => a.id === groupId);
  
  if (groupAssignment && groupAssignment.ai_account_id) {
    const aiAccounts = store.getters["ai/aiAccounts"] || [];
    const account = aiAccounts.find(a => a.id === groupAssignment.ai_account_id);
    return account ? account.name : "Unknown AI";
  }
  
  return null;
};

// Toggle monitoring status for a group
const toggleMonitoring = async (group) => {
  if (!group) return;
  
  updatingMonitoring.value = true;
  try {
    if (group.is_monitored) {
      // Implementation for stopping monitoring could go here
      // This depends on your backend API
      store.dispatch("ui/showSnackbar", {
        text: "Stop monitoring not implemented yet",
        color: "warning",
      });
    } else {
      // Start monitoring the group
      const response = await fetchWithAuth(`${apiUrl}/add/selected-groups`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ group_ids: [group.id] }),
      });

      if (response.ok) {
        // Update local state to reflect the change
        group.is_monitored = true;
        
        store.dispatch("ui/showSnackbar", {
          text: `Started monitoring "${group.title}"`,
          color: "success",
        });
      } else {
        throw new Error(`Failed to start monitoring: ${response.status}`);
      }
    }
  } catch (error) {
    console.error("Error toggling monitoring:", error);
    store.dispatch("ui/showSnackbar", {
      text: "Failed to update monitoring status",
      color: "error",
    });
  } finally {
    updatingMonitoring.value = false;
  }
};

// Helper function to truncate text
const truncateText = (text, maxLength) => {
  if (!text) return '';
  return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
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

.group-card {
  height: 100%;
  cursor: pointer;
  transition: transform 0.2s;
}

.group-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
}

.keyword-cloud {
  background-color: rgba(0, 0, 0, 0.02);
  border-radius: 8px;
}
</style>