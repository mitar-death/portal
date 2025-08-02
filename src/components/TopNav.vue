<template>
  <v-app-bar app flat dense>
    <v-avatar size="32" class="mr-3">
      <img
        v-if="isAuthenticated && currentUser && currentUser.photo_url"
        :src="currentUser.photo_url"
        alt="User Avatar"
      />
      <v-icon v-else>mdi-account-circle</v-icon>
    </v-avatar>

    <v-toolbar-title class="text-subtitle-1 font-weight-bold">
      TG Portal
    </v-toolbar-title>

    <v-spacer />

    <template v-if="isAuthenticated">
      <v-btn to="/" text>
        <v-icon left>mdi-view-dashboard</v-icon>
        Dashboard
      </v-btn>
      <v-btn to="/groups" text>
        <v-icon left>mdi-account-group</v-icon>
        Groups
      </v-btn>
      <v-btn to="/keywords" text>
        <v-icon left>mdi-tag</v-icon>
        Keywords
      </v-btn>
      <v-btn to="/ai-accounts" text>
        <v-icon left>mdi-robot</v-icon>
        AI Messenger
      </v-btn>
      <v-btn to="/group-ai-assignments" text>
        <v-icon left>mdi-account-switch</v-icon>
        AI Assignments
      </v-btn>

      <v-text-field
        flat
        hide-details
        dense
        rounded
        placeholder="Search"
        prepend-inner-icon="mdi-magnify"
        class="mx-4"
        style="max-width: 300px"
      />

      <v-menu offset-y>
        <template v-slot:activator="{ props }">
          <v-btn icon v-bind="props">
            <v-icon>mdi-dots-vertical</v-icon>
          </v-btn>
        </template>
        <v-list>
          <v-list-item @click="goToProfile">
            <v-list-item-title>
              <v-icon left>mdi-account</v-icon>
              Profile
            </v-list-item-title>
          </v-list-item>
          <v-list-item @click="goToSettings">
            <v-list-item-title>
              <v-icon left>mdi-cog</v-icon>
              Settings
            </v-list-item-title>
          </v-list-item>
          <v-divider />
          <v-list-item @click="logout">
            <v-list-item-title>
              <v-icon left>mdi-logout</v-icon>
              Logout
            </v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
    </template>

    <template v-else>
      <v-btn @click="openLoginModal" color="primary">
        <v-icon left>mdi-login</v-icon>
        Login
      </v-btn>
    </template>
  </v-app-bar>
</template>

<script setup>
import { computed } from "vue";
import { useStore } from "vuex";
import { useRouter } from "vue-router";

const store = useStore();
const router = useRouter();

// Computed properties
const isAuthenticated = computed(() => store.getters["auth/isAuthenticated"]);
const currentUser = computed(() => store.getters["auth/currentUser"]);

// Methods
function openLoginModal() {
  router.push("/login");
}

function goToProfile() {
  router.push("/profile");
}

function goToSettings() {
  router.push("/settings");
}

async function logout() {
  await store.dispatch("auth/logout");
  router.push("/");
}
</script>
