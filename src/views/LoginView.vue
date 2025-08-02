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
  const isAuthenticated = await store.dispatch("auth/checkAuthStatus");
  if (isAuthenticated) {
    redirectToHome();
  }
});

function redirectToHome() {
  router.push("/");
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
