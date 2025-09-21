<template>
  <v-card class="mx-auto my-12" max-width="400">
    <v-card-title class="text-center">Telegram Login</v-card-title>

    <v-card-text>
      <div v-if="step === 'authenticated'">
        <v-alert type="success" variant="tonal" class="mb-4">
          <v-alert-title>
            <v-icon icon="mdi-check-circle" class="me-2"></v-icon>
            Welcome Back!
          </v-alert-title>
          You are already logged in as <strong>{{ currentUser && currentUser.username }}</strong>
        </v-alert>

        <v-btn 
          color="primary" 
          block 
          class="mt-4" 
          @click="redirectToHome"
          prepend-icon="mdi-view-dashboard"
          size="large"
        >
          Go to Your Groups
        </v-btn>

        <v-btn 
          color="error" 
          variant="outlined" 
          block 
          class="mt-3" 
          @click="logout"
          prepend-icon="mdi-logout"
          :loading="loading"
        >
          Logout
        </v-btn>
      </div>

      <div v-else-if="step === 'phone'">
        <div class="text-body-2 text-medium-emphasis mb-4 text-center">
          <v-icon icon="mdi-telegram" color="primary" class="me-2"></v-icon>
          Enter your phone number to receive a verification code via Telegram
        </div>
        
        <v-text-field
          v-model="phone"
          label="Phone Number"
          placeholder="+1234567890"
          prepend-inner-icon="mdi-phone"
          variant="outlined"
          hint="Include country code (e.g., +1 for US)"
          persistent-hint
          :rules="[rules.required]"
          :error-messages="phoneError"
          @keydown.enter="requestCode"
          @input="clearPhoneError"
          :disabled="loading"
        ></v-text-field>

        <v-btn
          color="primary"
          block
          size="large"
          class="mt-4"
          :loading="loading"
          :disabled="!phone || loading"
          @click="requestCode"
          prepend-icon="mdi-send"
        >
          {{ loading ? 'Connecting to Telegram...' : 'Get Verification Code' }}
        </v-btn>
      </div>

      <div v-else-if="step === 'code'">
        <div class="text-body-2 text-medium-emphasis mb-4 text-center">
          <v-icon icon="mdi-message-text" color="success" class="me-2"></v-icon>
          Check your Telegram app for the verification code
        </div>
        
        <v-text-field
          v-model="code"
          label="Verification Code"
          placeholder="12345"
          prepend-inner-icon="mdi-lock"
          variant="outlined"
          hint="Enter the 5-digit code from Telegram"
          persistent-hint
          :rules="[rules.required, rules.codeLength]"
          :error-messages="codeError"
          @keydown.enter="verifyCode"
          @input="clearCodeError"
          :disabled="loading"
          maxlength="5"
          type="text"
          inputmode="numeric"
          pattern="[0-9]{5}"
        ></v-text-field>

        <v-btn
          color="primary"
          block
          size="large"
          class="mt-4"
          :loading="loading"
          :disabled="!code || loading"
          @click="verifyCode"
          prepend-icon="mdi-check-circle"
        >
          {{ loading ? 'Verifying...' : 'Complete Login' }}
        </v-btn>

        <v-btn 
          variant="outlined" 
          block 
          class="mt-3" 
          @click="step = 'phone'"
          :disabled="loading"
          prepend-icon="mdi-arrow-left"
        > 
          Use Different Number 
        </v-btn>
      </div>
    </v-card-text>

    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.text }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import { ref, defineEmits, onMounted, computed } from "vue";
import { useStore } from "vuex";
import { useRouter } from "vue-router";
import { fetchWithAuth } from "@/services/auth-interceptor";

const store = useStore();
const router = useRouter();
const emit = defineEmits(["login-success"]);

const step = ref("phone");
const phone = ref("");
const code = ref("");
const phone_code_hash = ref(""); // Store phone code hash for verification
const loading = ref(false);

// Error handling for enhanced UX
const phoneError = ref("");
const codeError = ref("");

import { apiUrl } from "@/services/api-service";
console.log("Using API URL in TelegramLogin:", apiUrl);

const snackbar = ref({
  show: false,
  text: "",
  color: "info",
});
const rules = {
  required: (value) => !!value || "Required.",
  codeLength: (value) => {
    if (!value) return true; // Let required rule handle empty values
    const cleanValue = value.toString().replace(/\D/g, ''); // Remove non-digits
    return cleanValue.length === 5 || "Verification code must be exactly 5 digits";
  }
};

// Get current user from store
const currentUser = computed(() => store.getters["auth/currentUser"]);

// Function to check if the user is already authenticated
async function checkAuthStatus() {
  loading.value = true;
  try {
    const currentRoute = router.currentRoute.value;

    // Skip actual API check if we have flags indicating auth issues
    if (
      currentRoute.query.authChecked === "true" ||
      currentRoute.query.sessionExpired === "true"
    ) {
      console.log("Skipping API auth check due to redirect flags");
      // Just check local state
      if (store.getters["auth/isAuthenticated"]) {
        step.value = "authenticated";
      } else {
        step.value = "phone";
      }
      return;
    }

    // First check local state for performance
    if (store.getters["auth/isAuthenticated"]) {
      step.value = "authenticated";

      // Then verify with backend to ensure sync
      const isAuthenticated = await store.dispatch("auth/checkAuthStatus");
      if (!isAuthenticated) {
        // Backend says not authenticated but frontend thinks we are - handle mismatch
        step.value = "phone";
        showSnackbar(
          "Your session has expired. Please log in again.",
          "warning"
        );
      }
    } else {
      // Not authenticated locally, check with backend
      const isAuthenticated = await store.dispatch("auth/checkAuthStatus");
      if (isAuthenticated) {
        step.value = "authenticated";
        showSnackbar("You are already logged in", "success");
      } else {
        step.value = "phone";
      }
    }
  } catch (error) {
    console.error("Error checking auth status:", error);
    // On error, clear local auth and show login form
    if (store.getters["auth/isAuthenticated"]) {
      await store.dispatch("auth/logout");
    }
    step.value = "phone";
  } finally {
    loading.value = false;
  }
}

// Redirect to home page
function redirectToHome() {
  const currentRoute = router.currentRoute.value;
  const fromPath = currentRoute.query.from;

  // Clear any auth flags when successfully navigating
  if (fromPath) {
    // Navigate to the original path but remove any auth flags to prevent future loops
    router.push({
      path: fromPath,
      query: {
        ...currentRoute.query,
        authChecked: undefined,
        sessionExpired: undefined,
      },
    });
  } else {
    router.push("/");
  }
}

// Logout function
async function logout() {
  loading.value = true;
  try {
    await store.dispatch("auth/logout");
    showSnackbar("Logged out successfully", "success");
    step.value = "phone";
  } catch (error) {
    console.error("Error during logout:", error);
    // Even if there's an error with the server, we still want to clear the local state
    // and allow the user to log in again
    showSnackbar(
      "Logged out locally, but there may have been an issue with the server",
      "warning"
    );
    step.value = "phone";
  } finally {
    loading.value = false;
  }
}

// Check authentication status when component mounts, but don't do this repeatedly
onMounted(() => {
  // Only check auth status if we're not in the authenticated step already
  if (step.value !== "authenticated") {
    checkAuthStatus();
  }
});

async function requestCode() {
  if (!phone.value) return;

  loading.value = true;
  try {
    // Use our auth interceptor instead of raw fetch
    const response = await fetchWithAuth(
      `${apiUrl}/auth/request-code`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ phone_number: phone.value }),
      },
      { redirect: false }
    ); // Don't auto-redirect during login flow

    const data = await response.json();

    if (response.ok) {
      if (data.data.action === "already_authorized") {
        // The user is already authorized on the backend
        showSnackbar("You are already logged in with Telegram", "success");

        // First, ensure local state matches backend
        if (!store.getters["auth/isAuthenticated"]) {
          await store.dispatch("auth/checkAuthStatus");
        }

        // Update UI to show authenticated state
        step.value = "authenticated";
      } else {
        // Normal flow - code was sent
        showSnackbar("Verification code sent to your phone", "success");
        step.value = "code";
        phone_code_hash.value = data.data.phone_code_hash;
        console.log("Received phone_code_hash:", data.data.phone_code_hash);
      }
    } else {
      console.error("API Error:", data);

      // Handle specific error scenarios
      if (
        response.status === 400 &&
        data.message &&
        data.message.includes("No active login session")
      ) {
        showSnackbar("Session expired. Please try again.", "warning");
        // Clear any existing auth state since there's a mismatch
        if (store.getters["auth/isAuthenticated"]) {
          await store.dispatch("auth/logout");
        }
      } else if (response.status === 401) {
        showSnackbar("Authentication error. Please try again.", "error");
        if (store.getters["auth/isAuthenticated"]) {
          await store.dispatch("auth/logout");
        }
      } else {
        showSnackbar(
          data.message || "Failed to send verification code",
          "error"
        );
      }
    }
  } catch (error) {
    console.error("Request Error:", error);
    showSnackbar(`Network error: ${error.message}`, "error");
  }
  loading.value = false;
}

async function verifyCode() {
  if (!code.value) return;

  loading.value = true;
  try {
    // Use our auth interceptor instead of raw fetch
    const response = await fetchWithAuth(
      `${apiUrl}/auth/verify-code`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          phone_number: phone.value,
          code: code.value,
          phone_code_hash: phone_code_hash.value, // Include the phone code hash
        }),
      },
      { redirect: false }
    ); // Don't auto-redirect during login flow

    const data = await response.json();
    console.log("Verify code response:", data);

    if (response.ok && data.success) {
      showSnackbar("Login successful!", "success");

      // Clear any existing auth state first
      if (store.getters["auth/isAuthenticated"]) {
        await store.dispatch("auth/logout");
      }

      // Then update with new auth data - handle JWT tokens properly
      await store.dispatch("auth/loginWithTelegram", {
        user: data.data.user,
        access_token: data.data.access_token,
        refresh_token: data.data.refresh_token,
        expires_in: data.data.expires_in,
        token_type: data.data.token_type
      });

      // Update UI to show authenticated state
      step.value = "authenticated";

      // Emit success event to parent
      emit("login-success", data.data.user);
      
      // Redirect to groups page instead of home for better UX
      const currentRoute = router.currentRoute.value;
      const fromPath = currentRoute.query.from;
      
      if (fromPath && fromPath !== '/login') {
        // User was trying to access a specific page, redirect there
        router.push({
          path: fromPath,
          query: {
            authChecked: true
          }
        });
      } else {
        // Default redirect to groups page for authenticated users
        router.push({
          path: "/groups",
          query: {
            authChecked: true,
            loginSuccess: true
          }
        });
      }
    } else {
      console.error("Verification API Error:", data);

      // Handle specific errors
      if (response.status === 401) {
        showSnackbar("Invalid verification code. Please try again.", "error");
      } else if (response.status >= 500) {
        showSnackbar(`Server error: ${data.message} Please try again later.`, "error");
      } else {
        showSnackbar(data.message || "Invalid verification code", "error");
      }

      // If there was a session mismatch, go back to phone input
      if (
        data.message.includes("session_expired") ||
        data.message.includes("session_not_found")
      ) {
        step.value = "phone";
      }
    }
  } catch (error) {
    console.error("Verification Request Error:", error);
    showSnackbar(`Network error: ${error.message}`, "error");
  }
  loading.value = false;
}

function showSnackbar(text, color = "info") {
  snackbar.value = {
    show: true,
    text,
    color,
  };

  // Also dispatch to the global UI store for app-wide notifications
  store.dispatch("ui/showSnackbar", { text, color });
}

// Enhanced error handling functions for better UX
function clearPhoneError() {
  phoneError.value = "";
}

function clearCodeError() {
  codeError.value = "";
}
</script>

<style scoped>
/* Add custom styling here if needed */
</style>
