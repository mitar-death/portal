<template>
  <v-app>
    <!-- Top Navigation -->
    <TopNav />
    <v-main>
      <v-container fluid>
        <router-view />
      </v-container>
      
      <!-- Login Dialog -->
      <LoginModal v-model="showLoginModal" @login-success="handleLoginSuccess" />
      
      <!-- Global Snackbar -->
      <v-snackbar
        v-model="snackbar.show"
        :color="snackbar.color"
        :timeout="5000"
        top
      >
        {{ snackbar.text }}
        <template v-slot:action="{ attrs }">
          <v-btn
            text
            v-bind="attrs"
            @click="hideSnackbar"
          >
            Close
          </v-btn>
        </template>
      </v-snackbar>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useStore } from 'vuex';
import TopNav from "./components/TopNav.vue";
import LoginModal from "./components/LoginModal.vue";

const store = useStore();
const showLoginModal = ref(false);

const isAuthenticated = computed(() => store.getters['auth/isAuthenticated']);
const snackbar = computed(() => store.getters['ui/snackbar']);

// Check authentication status on app startup
onMounted(async () => {
  // Check if backend is authenticated but frontend isn't
  const authStatus = await store.dispatch('auth/checkAuthStatus');
  
  // If authenticated, fetch user's groups
  if (isAuthenticated.value) {
    store.dispatch('telegram/fetchTelegramGroups');
  }
});
</script>
