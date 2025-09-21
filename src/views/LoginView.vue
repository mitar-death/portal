<template>
  <div class="login-view">
    <v-row justify="center" align="center" class="fill-height">
      <v-col cols="12" md="6" lg="4">
        <TelegramLogin @login-success="redirectToHome" />
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { useStore } from "vuex";
import { useRouter } from "vue-router";
import TelegramLogin from "@/components/TelegramLogin.vue";

const store = useStore();
const router = useRouter();

// Check if user is already authenticated when the login page loads
onMounted(async () => {
  try {
    const currentRoute = router.currentRoute.value;

    // Skip the auth check if we were redirected due to authentication issues
    // This prevents infinite loops between login and home pages
    if (
      currentRoute.query.authChecked === "true" ||
      currentRoute.query.sessionExpired === "true" ||
      currentRoute.query.redirect === "home"
    ) {
      console.log("Skipping auth check due to redirect flags");
      return;
    }

    const isAuthenticated = await store.dispatch("auth/checkAuthStatus");
    if (isAuthenticated) {
      redirectToHome();
    } else {
      // If we had tokens but backend says we're not authenticated,
      // clear everything to ensure consistency
      if (store.getters["auth/isAuthenticated"]) {
        await store.dispatch("auth/logout");
        console.log("Cleared inconsistent auth state on login page");
      }
    }
  } catch (error) {
    console.error("Error checking auth status on login page:", error);
    // On error, clear auth state to be safe
    if (store.getters["auth/isAuthenticated"]) {
      await store.dispatch("auth/logout");
    }
  }
});

function redirectToHome() {
  // Check if there's a 'from' in the query, and redirect there if it exists
  const currentRoute = router.currentRoute.value;
  const fromPath = currentRoute.query.from;

  // Clear any auth flags when successfully navigating
  if (fromPath && fromPath !== '/login') {
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
    // Default redirect to groups page for authenticated users instead of home
    router.push({
      path: "/groups",
      query: {
        authChecked: true,
        loginSuccess: true
      }
    });
  }
}
</script>

<style scoped>
.login-view {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
