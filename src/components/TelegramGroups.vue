<template>
  <div>
    <v-card class="mb-4">
      <v-card-title
        >Telegram Groups
        <v-spacer></v-spacer>
        <v-text-field
          v-model="search"
          append-icon="mdi-magnify"
          label="Search"
          single-line
          hide-details
        ></v-text-field>
      </v-card-title>

      <v-card-subtitle v-if="selected.length > 0" class="pb-0">
        {{ selected.length }} groups selected
      </v-card-subtitle>

      <v-card-actions v-if="groups.length > 0">
        <v-btn
          color="primary"
          :disabled="selected.length === 0"
          @click="monitorSelectedGroups"
          prepend-icon="mdi-eye-check"
        >
          Monitor Groups
        </v-btn>

        <v-btn
          color="error"
          :disabled="selected.length === 0"
          @click="clearSelection"
          prepend-icon="mdi-close-circle"
          class="ml-2"
        >
          Clear Selection
        </v-btn>

        <v-btn
          color="success"
          :disabled="selected.length === 0"
          @click="showAssignAIDialog"
          prepend-icon="mdi-robot"
          class="ml-2"
        >
          Assign AI
        </v-btn>
      </v-card-actions>

      <v-data-table
        v-model="selected"
        :headers="headers"
        :items="groups"
        :search="search"
        :loading="loading"
        loading-text="Loading groups..."
        item-value="id"
        show-select
        class="mt-2"
        title="Available Telegram Groups"
        subtitle="Select groups to monitor"
      >
        <template v-slot:[`item.member_count`]="{ item }">
          {{ item.member_count.toLocaleString() }}
        </template>

        <template v-slot:[`item.type`]="{ item }">
          <v-chip
            :color="item.is_channel ? 'blue' : 'green'"
            text-color="white"
            small
          >
            {{ item.is_channel ? "Channel" : "Group" }}
          </v-chip>
        </template>

        <template v-slot:[`item.ai_assignment`]="{ item }">
          <v-chip
            v-if="getAssignmentForGroup(item.id)"
            color="purple"
            text-color="white"
            small
          >
            {{ getAIAccountName(getAssignmentForGroup(item.id).ai_account_id) }}
          </v-chip>
          <v-btn
            v-else
            size="small"
            variant="text"
            color="secondary"
            @click="showAssignAIDialog([item])"
          >
            Assign AI
          </v-btn>
        </template>

        <template v-slot:[`item.actions`]="{ item }">
          <v-btn icon small @click="viewDetails(item)">
            <v-icon>mdi-eye</v-icon>
          </v-btn>
          <v-btn
            size="small"
            color="info"
            class="ml-2"
            :to="`/telegram/groups/${item.id}`"
            title="View Group Page"
          >
            View
          </v-btn>
        </template>
      </v-data-table>
    </v-card>

    <!-- Group Details Dialog -->
    <v-dialog v-model="dialog" max-width="500">
      <v-card v-if="selectedGroup">
        <v-card-title>{{ selectedGroup.title }}</v-card-title>
        <v-card-text>
          <p v-if="selectedGroup.description">
            {{ selectedGroup.description }}
          </p>
          <p v-if="selectedGroup.username">@{{ selectedGroup.username }}</p>
          <p>Members: {{ selectedGroup.member_count.toLocaleString() }}</p>
          <p>Type: {{ selectedGroup.is_channel ? "Channel" : "Group" }}</p>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn text @click="dialog = false"> Close </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- AI Assignment Dialog -->
    <v-dialog v-model="assignAIDialog" max-width="600">
      <v-card>
        <v-card-title
          >Assign AI to {{ assignGroupsCount }} Group(s)</v-card-title
        >
        <v-card-text>
          <v-alert v-if="aiAccounts.length === 0" type="warning" class="mb-4">
            You don't have any AI messenger accounts yet.
            <router-link to="/ai-accounts">Create an AI account</router-link>
            before assigning them to groups.
          </v-alert>

          <template v-else>
            <p class="mb-4">
              Select an AI account to handle messages in the selected group(s):
            </p>

            <v-select
              v-model="selectedAIAccount"
              :items="aiAccountOptions"
              item-title="text"
              item-value="value"
              label="Select AI Account"
              variant="outlined"
              :disabled="assignmentLoading"
            ></v-select>

            <v-switch
              v-model="assignmentActive"
              label="Enable AI responses"
              color="success"
              :disabled="!selectedAIAccount || assignmentLoading"
              hide-details
              class="mt-4"
            ></v-switch>
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            text
            @click="assignAIDialog = false"
            :disabled="assignmentLoading"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            :disabled="
              !selectedAIAccount || assignmentLoading || aiAccounts.length === 0
            "
            :loading="assignmentLoading"
            @click="assignAIToGroups"
          >
            Assign
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Remove local snackbar, we'll use the global one from the store -->
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useStore } from "vuex";
import { useRouter } from "vue-router";

const store = useStore();
const router = useRouter();

const groups = computed(() => store.state.telegram.groups || []);
const aiAccounts = computed(() => store.getters["ai/aiAccounts"] || []);
const groupAssignments = computed(
  () => store.getters["ai/groupAssignments"] || []
);
import { apiUrl } from '@/services/api-service';

console.log("API URL in TelegramGroups.vue:", apiUrl);
const loading = ref(false);
const search = ref("");
const dialog = ref(false);
const selectedGroup = ref(null);
const selected = ref([]);
// Remove local snackbar state

// AI Assignment dialog
const assignAIDialog = ref(false);
const selectedAIAccount = ref(null);
const assignmentActive = ref(true);
const assignmentLoading = ref(false);
const groupsToAssign = ref([]);
const headers = [
  { text: "Title", value: "title" },
  { text: "Username", value: "username" },
  { text: "Members", value: "member_count" },
  { text: "Type", value: "type" },
  { text: "AI Assignment", value: "ai_assignment" },
  { text: "Actions", value: "actions", sortable: false },
];

const token = computed(() => store.state.auth.token);

const aiAccountOptions = computed(() => {
  // Create options array for v-select with an empty option
  const options = [{ text: "-- None --", value: null }];

  // Add each AI account as an option
  aiAccounts.value.forEach((account) => {
    if (account.is_active) {
      options.push({
        text: `${account.name} (${account.phone_number})`,
        value: account.id,
      });
    }
  });

  return options;
});

const assignGroupsCount = computed(() => groupsToAssign.value.length);

onMounted(async () => {
  await store.dispatch("telegram/fetchTelegramGroups");
  await store.dispatch("ai/fetchAIAccounts");
  await store.dispatch("ai/fetchGroupAssignments");

  // Pre-select groups that are already being monitored
  if (groups.value.length > 0) {
    const monitoredGroups = groups.value
      .filter(group => group.is_monitored === true)
      .map(group => group.id);  // Store just the IDs to match item-value
    if (monitoredGroups.length > 0) {
      selected.value = monitoredGroups;
      console.log(`Pre-selected ${monitoredGroups.length} monitored groups:`, monitoredGroups);
    }
  }
});

function getAssignmentForGroup(groupId) {
  return groupAssignments.value.find((assignment) => assignment.id === groupId);
}

function getAIAccountName(accountId) {
  const account = aiAccounts.value.find((acc) => acc.id === accountId);
  return account ? account.name : "Unknown";
}

function viewDetails(group) {
  selectedGroup.value = group;
  dialog.value = true;
}

function clearSelection() {
  selected.value = [];
}

function showAssignAIDialog(groups = null) {
  // If groups is null, use the selected groups
  groupsToAssign.value = groups || selected.value;

  // Reset the selection
  selectedAIAccount.value = null;
  assignmentActive.value = true;

  // Show the dialog
  assignAIDialog.value = true;
}

async function assignAIToGroups() {
  if (!token.value) {
    store.dispatch("ui/showSnackbar", {
      text: "You need to be logged in to assign AI accounts",
      color: "error",
    });
    return;
  }

  if (groupsToAssign.value.length === 0) {
    store.dispatch("ui/showSnackbar", {
      text: "Please select at least one group",
      color: "warning",
    });
    return;
  }

  assignmentLoading.value = true;

  try {
    // Process each group one by one
    for (const group of groupsToAssign.value) {
      const groupId = group.id || group;

      await store.dispatch("ai/updateGroupAssignment", {
        groupId: groupId,
        aiAccountId: selectedAIAccount.value,
        isActive: assignmentActive.value,
      });
    }

    store.dispatch("ui/showSnackbar", {
      text: `Successfully assigned AI to ${groupsToAssign.value.length} group(s)`,
      color: "success",
    });

    // Close the dialog
    assignAIDialog.value = false;
  } catch (error) {
    console.error("Error assigning AI:", error);
    store.dispatch("ui/showSnackbar", {
      text: "Failed to assign AI. Please try again.",
      color: "error",
    });
  } finally {
    assignmentLoading.value = false;
  }
}

async function monitorSelectedGroups() {
  if (!token.value) {
    store.dispatch("ui/showSnackbar", {
      text: "You need to be logged in to monitor groups",
      color: "error",
    });
    return;
  }

  if (selected.value.length === 0) {
    store.dispatch("ui/showSnackbar", {
      text: "Please select at least one group to monitor",
      color: "warning",
    });
    return;
  }

  // Since selected.value now contains IDs, we can use them directly
  const groupIds = selected.value;
  console.log("Monitoring groups with IDs:", groupIds);
  
  loading.value = true;
  try {
    const response = await fetch(`${apiUrl}/add/selected-groups`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token.value}`,
      },
      credentials: "include",
      body: JSON.stringify({ group_ids: groupIds }),
    });

    if (!response.ok) {
      throw new Error(`Failed to monitor groups: ${response.status}`);
    }

    const data = await response.json();
    store.dispatch("ui/showSnackbar", {
      text: `Successfully started monitoring ${selected.value.length} groups`,
      color: "success",
    });

    // Optional: Clear selection after successful monitoring
    // selected.value = [];
  } catch (error) {
    console.error("Error monitoring groups:", error);
    store.dispatch("ui/showSnackbar", {
      text: "Failed to monitor groups. Please try again.",
      color: "error",
    });
  } finally {
    loading.value = false;
  }
}

// Remove local showSnackbar function as we now use the store
</script>

<style scoped>
.v-data-table {
  border-radius: 4px;
}
</style>