<template>
  <div>
    <h1 class="text-h4 mb-4">Telegram Groups</h1>
    <TelegramGroups />
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { useStore } from "vuex";
import TelegramGroups from "@/components/TelegramGroups.vue";

const store = useStore();

onMounted(async () => {
  // Refresh groups data when this view is loaded
  await store.dispatch("telegram/fetchTelegramGroups");

  // Load AI accounts and assignments for group management
  await Promise.all([
    store.dispatch("ai/fetchAIAccounts"),
    store.dispatch("ai/fetchGroupAssignments"),
  ]);
});
</script>
