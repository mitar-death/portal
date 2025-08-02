<template>
  <v-card class="mx-auto my-12" max-width="400">
    <v-card-title class="text-center">Telegram Login</v-card-title>

    <v-card-text>
      <div v-if="step === 'authenticated'">
        <v-alert type="success" class="mb-4">
          You are already logged in as {{ currentUser && currentUser.username }}
        </v-alert>

        <v-btn color="primary" block class="mt-4" @click="redirectToHome">
          Go to Dashboard
        </v-btn>

        <v-btn color="error" outlined block class="mt-2" @click="logout">
          Logout
        </v-btn>
      </div>

      <div v-else-if="step === 'phone'">
        <v-text-field
          v-model="phone"
          label="Phone Number"
          prepend-icon="mdi-phone"
          hint="Enter your Telegram phone number with country code"
          :rules="[rules.required]"
        ></v-text-field>

        <v-btn
          color="primary"
          block
          class="mt-4"
          :loading="loading"
          @click="requestCode"
        >
          Request Code
        </v-btn>
      </div>

      <div v-else-if="step === 'code'">
        <v-text-field
          v-model="code"
          label="Verification Code"
          prepend-icon="mdi-lock"
          hint="Enter the code sent to your Telegram"
          :rules="[rules.required]"
        ></v-text-field>

        <v-btn
          color="primary"
          block
          class="mt-4"
          :loading="loading"
          @click="verifyCode"
        >
          Verify Code
        </v-btn>

        <v-btn text block class="mt-2" @click="step = 'phone'"> Back </v-btn>
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

const store = useStore();
const router = useRouter();
const emit = defineEmits(["login-success"]);

const step = ref("phone");
const phone = ref("");
const code = ref("");
const phone_code_hash = ref(""); // Store phone code hash for verification
const loading = ref(false);
const snackbar = ref({
  show: false,
  text: "",
  color: "info",
});
const rules = {
  required: (value) => !!value || "Required.",
};

// Get current user from store
const currentUser = computed(() => store.getters["auth/currentUser"]);

// Function to check if the user is already authenticated
async function checkAuthStatus() {
  loading.value = true;
  try {
    const currentRoute = router.currentRoute.value;
    
    // Skip actual API check if we have flags indicating auth issues
    if (currentRoute.query.authChecked === 'true' || 
        currentRoute.query.sessionExpired === 'true') {
      console.log("Skipping API auth check due to redirect flags");
      // Just check local state
      if (store.getters["auth/isAuthenticated"]) {
        step.value = "authenticated";
      } else {
        step.value = "phone";
      }
      return;
    }
    
    const isAuthenticated = await store.dispatch("auth/checkAuthStatus");
    if (isAuthenticated) {
      step.value = "authenticated";
      showSnackbar("You are already logged in", "success");
    }
  } catch (error) {
    console.error("Error checking auth status:", error);
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
      query: { ...currentRoute.query, authChecked: undefined, sessionExpired: undefined }
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
    showSnackbar("Failed to logout", "error");
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
    // Use the relative API path to our FastAPI backend
    const response = await fetch("/api/auth/request-code", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ phone_number: phone.value }),
      credentials: "include",
    });

    const data = await response.json();

    if (response.ok) {
      if (data.action === "already_authorized") {
        // The user is already authorized on the backend
        showSnackbar("You are already logged in with Telegram", "success");
        // Update UI to show authenticated state
        step.value = "authenticated";
        // Check auth status to sync frontend with backend
        await checkAuthStatus();
      } else {
        // Normal flow - code was sent
        showSnackbar("Verification code sent to your phone", "success");
        step.value = "code";
        phone_code_hash.value = data.phone_code_hash;
        console.log("Received phone_code_hash:", data.phone_code_hash);
      }
    } else {
      console.error("API Error:", data);
      showSnackbar(data.detail || "Failed to send verification code", "error");
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
    const response = await fetch("/api/auth/verify-code", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        phone_number: phone.value,
        code: code.value,
        phone_code_hash: phone_code_hash.value, // Include the phone code hash
      }),
      credentials: "include", // Add credentials to maintain session cookies
    });

    const data = await response.json();
    console.log("Verify code response:", data);

    if (response.ok && data.success) {
      showSnackbar("Login successful!", "success");
      // Let Vuex handle the localStorage
      // The dispatch will take care of storing in localStorage
      await store.dispatch("auth/loginWithTelegram", {
        user: data.user,
        token: data.token,
      });

      // Update UI to show authenticated state
      step.value = "authenticated";

      // Emit success event to parent
      emit("login-success", data.user);
    } else {
      console.error("Verification API Error:", data);
      showSnackbar(data.detail || "Invalid verification code", "error");
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
</script>

<style scoped>
/* Add custom styling here if needed */
</style>
