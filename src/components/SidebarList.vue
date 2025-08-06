<template>
  <v-col cols="12" md="3">
    <v-card elevation="2" class="ma-4 pa-2">
      <v-list dense>
        <template v-if="props.loading">
          <v-skeleton-loader
            v-for="n in 5"
            :key="n"
            type="list-item-two-line"
            class="mb-2"
          />
        </template>
        <template v-else>
          <v-list-item
            v-for="grp in props.groups"
            :key="grp.id"
            @click="selectGroup(grp)"
            :class="{ 'bg-grey-lighten-4': props.selectedGroup?.id === grp.id }"
            :prepend-icon="grp.is_monitored ? 'mdi-eye-check' : ''"
          >
            <template v-slot:default>
              <v-list-item-title>{{ grp.title }}</v-list-item-title>
              <v-list-item-subtitle v-if="grp.is_monitored" class="text-success">
                Monitored
              </v-list-item-subtitle>
            </template>
          </v-list-item>
        </template>

        <v-divider class="my-2" />

        <v-list-item @click="props.loadGroups">
          <template v-slot:prepend>
            <v-icon>mdi-refresh</v-icon>
          </template>
          <v-list-item-title>Refresh</v-list-item-title>
        </v-list-item>
        <v-list-item v-if="isAuthenticated">
          <template v-slot:prepend>
            <v-avatar size="24">
              <v-icon>mdi-account-circle</v-icon>
            </v-avatar>
          </template>
          <v-list-item-title>
            Logged in as: {{ currentUser?.first_name || "User" }}
          </v-list-item-title>
        </v-list-item>
        <v-list-item v-else @click="loginTelegram">
          <template v-slot:prepend>
            <v-avatar size="24">
              <v-icon>mdi-account-circle</v-icon>
            </v-avatar>
          </template>
          <v-list-item-title>Login Telegram</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-card>
  </v-col>
</template>

<script setup>
import { defineProps, defineEmits, computed } from "vue";
import { useStore } from "vuex";
import { useRouter } from "vue-router";

const store = useStore();
const router = useRouter();
const isAuthenticated = computed(() => store.getters["auth/isAuthenticated"]);
const currentUser = computed(() => store.getters["auth/currentUser"]);

const props = defineProps({
  groups: {
    type: Array,
    required: true,
  },
  selectedGroup: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  user: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(["selectGroup", "loadGroups", "loginTelegram"]);

function selectGroup(grp) {
  emit("selectGroup", grp);
}

function loginTelegram() {
  router.push("/login");
}
</script>