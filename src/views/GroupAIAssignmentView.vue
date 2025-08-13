<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="headline">
            AI Messenger Group Assignments
            <v-spacer></v-spacer>
            <v-btn color="primary" @click="refreshData" :loading="loading">
              <v-icon left>mdi-refresh</v-icon>
              Refresh
            </v-btn>
          </v-card-title>

          <v-card-text>
            <p class="text-body-1 mb-4">
              Assign AI messenger accounts to specific groups. When a message in
              a group matches your keywords, the assigned AI account will
              automatically respond to that message.
            </p>

            <!-- Loading indicator -->
            <v-progress-linear
              v-if="loading"
              indeterminate
              color="primary"
            ></v-progress-linear>

            <!-- No AI accounts warning -->
            <v-alert
              v-if="aiAccounts.length === 0 && !loading"
              type="warning"
              class="mt-4"
            >
              You don't have any AI messenger accounts yet.
              <router-link to="/ai-accounts">Create an AI account</router-link>
              before assigning them to groups.
            </v-alert>

            <!-- No groups warning -->
            <v-alert
              v-if="groupAssignments.length === 0 && !loading"
              type="info"
              class="mt-4"
            >
              You don't have any Telegram groups loaded yet.
              <router-link to="/groups">Select groups to monitor</router-link>
              before assigning AI accounts to them.
            </v-alert>

            <!-- Assignment table -->
            <v-data-table
              v-if="groupAssignments.length > 0 && aiAccounts.length > 0"
              :headers="headers"
              :items="groupAssignments"
              :items-per-page="10"
              class="elevation-1"
            >
              <template #[`item.title`]="{ item }">
                {{ item.title }}
              </template>

              <template #[`item.ai_account_id`]="{ item }">
                <v-select
                  v-model="item.ai_account_id"
                  :items="aiAccountOptions"
                  density="compact"
                  label="Select AI Account"
                  @update:model-value="updateAssignment(item)"
                  :disabled="loading"
                  hide-details
                  variant="outlined"
                  item-title="text"
                  item-value="value"
                  :value="item.ai_account_id"
                ></v-select>
              </template>

              <template #[`item.is_active`]="{ item }">
                <v-switch
                  v-model="item.is_active"
                  color="success"
                  :disabled="!item.ai_account_id || loading"
                  @update:model-value="updateAssignment(item)"
                  hide-details
                  density="compact"
                ></v-switch>
              </template>

              <template #[`item.actions`]="{ item }">
                <v-btn
                  icon
                  color="red"
                  @click="clearAssignment(item)"
                  :disabled="!item.ai_account_id || loading"
                >
                  <v-icon>mdi-delete</v-icon>
                </v-btn>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from "vue";
import { useStore } from "vuex";

// Setup store
const store = useStore();

// Reactive state
const loading = ref(false);

// Table headers
const headers = [
  { title: "Group Name", key: "title", sortable: true },
  { title: "AI Account", key: "ai_account_id", sortable: false },
  { title: "Active", key: "is_active", sortable: false },
  { title: "Actions", key: "actions", sortable: false },
];

// Computed properties
const aiAccounts = computed(() => store.getters["ai/aiAccounts"]);
const groupAssignments = computed(() => store.getters["ai/groupAssignments"]);

const aiAccountOptions = computed(() => {
  // Create options array for v-select with an empty option
  const options = [{ text: "-- None --", value: null }];

  // Add each AI account as an option
  aiAccounts.value.forEach((account) => {
    // Include all accounts, but mark inactive ones
    const statusText = account.is_active ? "" : " (inactive)";
    options.push({
      text: `${account.name} (${account.phone_number})${statusText}`,
      value: account.id,
      disabled: !account.is_active,
    });
  });

  return options;
});

// Methods
const refreshData = async () => {
  loading.value = true;
  try {
    await Promise.all([
      store.dispatch("ai/fetchAIAccounts"),
      store.dispatch("ai/fetchGroupAssignments"),
    ]);

    // Use nextTick to ensure Vue has updated the DOM
    await nextTick(() => {
      // Force reactivity update by explicitly setting AI account IDs
      const groups = store.getters["ai/groupAssignments"];
      groups.forEach((group) => {
        // Ensure the ai_account_id is correctly set as a reactive property
        if (group.ai_account_id) {
          // This triggers reactivity in the v-select
          group.ai_account_id = group.ai_account_id;
        }
      });
    });
  } catch (error) {
    console.error("Failed to fetch data:", error);
    store.dispatch("ui/showSnackbar", {
      text: "Failed to load data",
      color: "error",
    });
  } finally {
    loading.value = false;
  }
};

const updateAssignment = async (group) => {
  // Store original values to restore if the update fails
  const originalAiAccountId = group.ai_account_id;
  const originalIsActive = group.is_active;

  loading.value = true;
  try {
    await store.dispatch("ai/updateGroupAssignment", {
      groupId: group.id,
      aiAccountId: group.ai_account_id,
      isActive: group.is_active,
    });

    // Show success message
    store.dispatch("ui/showSnackbar", {
      text: "Group assignment updated successfully",
      color: "success",
    });
  } catch (error) {
    console.error("Error updating assignment:", error);

    // Restore original values
    group.ai_account_id = originalAiAccountId;
    group.is_active = originalIsActive;

    // Show error message
    store.dispatch("ui/showSnackbar", {
      text: "Failed to update assignment. Please try again.",
      color: "error",
    });
  } finally {
    loading.value = false;
  }
};

const clearAssignment = async (group) => {
  // Set the AI account to null and update
  const originalAiAccountId = group.ai_account_id;
  group.ai_account_id = null;

  loading.value = true;
  try {
    await store.dispatch("ai/updateGroupAssignment", {
      groupId: group.id,
      aiAccountId: null,
      isActive: false,
    });

    // Show success message
    store.dispatch("ui/showSnackbar", {
      text: "Assignment removed successfully",
      color: "success",
    });
  } catch (error) {
    console.error("Error clearing assignment:", error);

    // Restore original value
    group.ai_account_id = originalAiAccountId;

    // Show error message
    store.dispatch("ui/showSnackbar", {
      text: "Failed to remove assignment. Please try again.",
      color: "error",
    });
  } finally {
    loading.value = false;
  }
};

// Lifecycle hooks
onMounted(() => {
  refreshData();
});
</script>
