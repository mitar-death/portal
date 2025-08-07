<template>
  <div class="keywords-view">
    <v-container>
      <v-row>
        <v-col cols="12">
          <h1 class="text-h4 mb-4">Keywords Management</h1>
          <p class="text-subtitle-1 mb-8">
            Add keywords to filter Telegram messages. Only messages containing
            these keywords will be logged.
          </p>
        </v-col>
      </v-row>

      <v-row>
        <!-- Keyword Form -->
        <v-col cols="12" md="5">
          <v-card class="pa-4">
            <v-card-title>Add New Keyword</v-card-title>
            <v-card-text>
              <v-form @submit.prevent="addKeyword" ref="form">
                <v-text-field
                  v-model="newKeyword"
                  label="Keyword"
                  :rules="[(v) => !!v || 'Keyword is required']" required @keyup.enter="addKeyword"></v-text-field>

                <v-btn
                  color="primary"
                  type="submit"
                  :loading="loading"
                  :disabled="loading || !newKeyword"
                  class="mt-2"
                >
                  Add Keyword
                </v-btn>
              </v-form>
            </v-card-text>
          </v-card>
        </v-col>

        <!-- Keywords Table -->
        <v-col cols="12" md="7">
          <v-card>
            <v-card-title class="d-flex align-center">
              Keywords List
              <v-spacer></v-spacer>
              <v-text-field
                v-model="search"
                append-icon="mdi-magnify"
                label="Search"
                single-line
                hide-details
                density="compact"
                class="ml-2"
                style="max-width: 200px"
              ></v-text-field>
            </v-card-title>

            <v-data-table
              :headers="headers"
              :items="keywords"
              :search="search"
              :loading="loading"
              class="elevation-0"
              :items-per-page="10"
              :no-data-text="
                loading ? 'Loading keywords...' : 'No keywords found'
              "
            >
              <template #[`item.actions`]="{ item }">
                <v-btn
                  icon
                  size="small"
                  color="error"
                  variant="text"
                  @click="deleteKeyword(item.keyword)"
                  :loading="deletingKeyword === item.keyword"
                >
                  <v-icon>mdi-delete</v-icon>
                </v-btn>
              </template>
            </v-data-table>
          </v-card>
        </v-col>
      </v-row>
    </v-container>

    <!-- Remove local snackbar, we'll use the global one from the store -->
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from "vue";
import { useStore } from "vuex";

const store = useStore();
const loading = ref(false);
const newKeyword = ref("");
const search = ref("");
const deletingKeyword = ref(null);
const form = ref(null);

// Remove local snackbar state

// Table headers
const headers = [
  { title: "Keyword", key: "keyword", align: "start", sortable: true },
  { title: "Actions", key: "actions", align: "end", sortable: false },
];

// Formatted keywords for table
const keywords = computed(() => {
  return store.state.telegram.keywords.map((keyword) => ({
    keyword: keyword,
    raw: keyword,
  }));
});

console.log("Keywords:", keywords.value);

// Fetch keywords on component mount
onMounted(async () => {
  await store.dispatch("telegram/fetchKeywords");
});

// Add a new keyword
async function addKeyword() {
  if (!newKeyword.value.trim()) return;

  loading.value = true;
  try {
    await store.dispatch("telegram/addKeyword", newKeyword.value.trim());
    store.dispatch("ui/showSnackbar", {
      text: `Keyword "${newKeyword.value}" added successfully`,
      color: "success",
    });
    newKeyword.value = "";
    form.value.resetValidation();
  } catch (error) {
    store.dispatch("ui/showSnackbar", {
      text: `Failed to add keyword: ${error.message}`,
      color: "error",
    });
    console.error("Error adding keyword:", error);
  } finally {
    loading.value = false;
  }
}

// Delete a keyword
async function deleteKeyword(keyword) {
  deletingKeyword.value = keyword;
  try {
    await store.dispatch("telegram/deleteKeyword", keyword);
    store.dispatch("ui/showSnackbar", {
      text: `Keyword "${keyword}" deleted successfully`,
      color: "success",
    });
  } catch (error) {
    store.dispatch("ui/showSnackbar", {
      text: `Failed to delete keyword: ${error.message}`,
      color: "error",
    });
    console.error("Error deleting keyword:", error);
  } finally {
    deletingKeyword.value = null;
  }
}

// Remove the showSnackbar function, we'll use the store directly
</script>

<style scoped>
.keywords-view {
  padding-bottom: 24px;
}
</style>