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
    // Skip the auth check if we were redirected here due to being not authenticated
    if (router.currentRoute.value.query.redirect !== 'home') {
      const isAuthenticated = await store.dispatch("auth/checkAuthStatus");
      if (isAuthenticated) {
        redirectToHome();
      }
    }
  } catch (error) {
    console.error("Error checking auth status on login page:", error);
  }
});

function redirectToHome() {
  // Check if there's a 'from' in the query, and redirect there if it exists
  const fromPath = router.currentRoute.value.query.from;
  if (fromPath) {
    router.push(fromPath);
  } else {
    router.push("/");
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
