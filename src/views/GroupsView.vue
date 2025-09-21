<template>
  <div>
    <div class="d-flex justify-space-between align-center mb-4">
      <h1 class="text-h4">Telegram Groups</h1>
      
      <!-- Retry button for failed loads -->
      <v-btn 
        v-if="loadingState.hasError"
        @click="retryLoading"
        color="primary"
        :loading="loadingState.isRetrying"
        prepend-icon="mdi-refresh"
        variant="outlined"
      >
        Retry Loading
      </v-btn>
    </div>

    <!-- Loading indicator for initial load -->
    <v-card v-if="loadingState.isLoading && !loadingState.hasData" class="mb-4">
      <v-card-text class="text-center py-8">
        <v-progress-circular 
          :size="40" 
          color="primary" 
          indeterminate
          class="mb-4"
        ></v-progress-circular>
        <div class="text-h6 mb-2">Loading Groups...</div>
        <div class="text-body-2 text-medium-emphasis">
          Fetching your Telegram groups and AI assignments
        </div>
      </v-card-text>
    </v-card>

    <!-- Error state -->
    <v-alert 
      v-if="loadingState.hasError && !loadingState.isLoading"
      type="error" 
      variant="tonal"
      class="mb-4"
      closable
      @click:close="clearError"
    >
      <v-alert-title>Failed to Load Groups</v-alert-title>
      <div class="mb-3">{{ loadingState.errorMessage }}</div>
      <v-btn 
        @click="retryLoading"
        color="error"
        :loading="loadingState.isRetrying"
        size="small"
        variant="outlined"
      >
        Try Again
      </v-btn>
    </v-alert>

    <!-- Success indicator for login -->
    <v-alert 
      v-if="showLoginSuccess"
      type="success" 
      variant="tonal"
      class="mb-4"
      closable
      @click:close="showLoginSuccess = false"
    >
      <v-alert-title>Welcome Back!</v-alert-title>
      Successfully logged in and loaded your groups.
    </v-alert>

    <!-- Main content -->
    <TelegramGroups v-if="!loadingState.isLoading || loadingState.hasData" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, computed } from "vue";
import { useStore } from "vuex";
import { useRouter } from "vue-router";
import TelegramGroups from "@/components/TelegramGroups.vue";

const store = useStore();
const router = useRouter();

// Loading state management
const loadingState = reactive({
  isLoading: false,
  isRetrying: false,
  hasError: false,
  hasData: false,
  errorMessage: '',
  retryCount: 0,
  maxRetries: 3
});

// Show login success message if coming from login
const showLoginSuccess = ref(false);

// Check if user just logged in successfully
const currentRoute = computed(() => router.currentRoute.value);
if (currentRoute.value.query.loginSuccess === 'true') {
  showLoginSuccess.value = true;
  // Clean up the query parameter
  router.replace({ 
    path: '/groups',
    query: { 
      ...currentRoute.value.query, 
      loginSuccess: undefined 
    } 
  });
}

async function loadGroupsData() {
  loadingState.isLoading = true;
  loadingState.hasError = false;
  loadingState.errorMessage = '';

  try {
    // Check authentication first
    if (!store.getters['auth/isAuthenticated']) {
      throw new Error('Please log in to view your groups');
    }

    // Load groups and related data with timeout
    const loadPromises = [
      store.dispatch("telegram/fetchTelegramGroups"),
      store.dispatch("ai/fetchAIAccounts"),
      store.dispatch("ai/fetchGroupAssignments"),
    ];

    // Add a reasonable timeout for the operations
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => reject(new Error('Loading timed out. Please check your connection.')), 15000);
    });

    await Promise.race([
      Promise.all(loadPromises),
      timeoutPromise
    ]);

    loadingState.hasData = true;
    loadingState.retryCount = 0; // Reset retry count on success
    
  } catch (error) {
    console.error('Error loading groups data:', error);
    loadingState.hasError = true;
    
    // Provide user-friendly error messages
    const errorMessage = error.message || error.toString() || 'Unknown error';
    
    if (errorMessage.includes('Not authenticated')) {
      loadingState.errorMessage = 'Authentication expired. Please log in again.';
      // Redirect to login after a short delay
      setTimeout(() => {
        router.push('/login');
      }, 2000);
    } else if (errorMessage.includes('Failed to fetch') || errorMessage.includes('401')) {
      loadingState.errorMessage = 'Authentication error. Please log in again.';
      // Redirect to login immediately for auth errors
      setTimeout(() => {
        router.push('/login');
      }, 1000);
    } else if (errorMessage.includes('timeout')) {
      loadingState.errorMessage = 'Loading timed out. Please try again.';
    } else {
      loadingState.errorMessage = errorMessage || 'An unexpected error occurred while loading groups.';
    }
  } finally {
    loadingState.isLoading = false;
    loadingState.isRetrying = false;
  }
}

async function retryLoading() {
  if (loadingState.retryCount >= loadingState.maxRetries) {
    loadingState.errorMessage = `Maximum retry attempts (${loadingState.maxRetries}) exceeded. Please refresh the page or contact support.`;
    return;
  }

  loadingState.retryCount++;
  loadingState.isRetrying = true;
  
  // Add a small delay before retrying for better UX
  await new Promise(resolve => setTimeout(resolve, 1000));
  
  await loadGroupsData();
}

function clearError() {
  loadingState.hasError = false;
  loadingState.errorMessage = '';
}

onMounted(async () => {
  await loadGroupsData();
});
</script>
