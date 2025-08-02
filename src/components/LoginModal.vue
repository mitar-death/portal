<template>
  <v-dialog
    :model-value="modelValue"
    persistent
    max-width="400"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title class="headline"> Login with Telegram </v-card-title>

      <v-card-text>
        <TelegramLogin @login-success="handleLoginSuccess" />
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { defineProps, defineEmits } from "vue";
import { useRouter } from "vue-router";
import TelegramLogin from "./TelegramLogin.vue";

defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["update:modelValue", "login-success"]);
const router = useRouter();

const handleLoginSuccess = (userData) => {
  emit("update:modelValue", false);
  emit("login-success", userData);
  // Redirect to home page or dashboard after login
  router.push("/");
};
</script>
