<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="headline">
            AI Messenger Accounts
            <v-spacer></v-spacer>
            <v-btn color="warning" class="mr-2" @click="cleanupAllSessions">
              Cleanup Sessions
            </v-btn>
            <v-btn color="primary" @click="showNewAccountDialog = true">
              Add New Account
            </v-btn>
          </v-card-title>

          <v-card-text>
            <p class="text-body-1 mb-4">
              AI Messenger accounts are Telegram accounts used to respond to
              messages that match your keywords. These accounts will
              automatically engage with users when messages contain your
              specified keywords.
            </p>

            <!-- Loading indicator -->
            <v-progress-linear
              v-if="loading"
              indeterminate
              color="primary"
            ></v-progress-linear>

            <!-- Account List -->
            <v-alert
              v-if="aiAccounts.length === 0 && !loading"
              type="info"
              class="mt-4"
            >
              You don't have any AI messenger accounts yet. Add one to start
              responding to messages automatically.
            </v-alert>

            <v-row v-else>
              <v-col v-for="account in aiAccounts" :key="account.id" cols="12" md="6" lg="4">
              <v-card elevation="2" class="mb-4">
                <v-list-item three-line>
                <v-list-item-avatar>
                  <v-icon :color="account.is_active ? 'success' : 'grey'">
                  {{ account.is_active ? "mdi-account-check" : "mdi-account-off" }}
                  </v-icon>
                </v-list-item-avatar>

                <v-list-item-content>
                  <v-list-item-title class="text-h6">{{ account.name }}</v-list-item-title>
                  <v-list-item-subtitle>
                  +{{ account.phone_number }}
                  </v-list-item-subtitle>
                  <div class="mt-2">
                  <v-chip
                    v-if="account.session_status === 'authorized'"
                    x-small
                    color="success"
                  >
                    Authenticated
                  </v-chip>
                  <v-chip
                    v-else-if="account.session_status === 'unauthorized'"
                    x-small
                    color="warning"
                  >
                    Login Required
                  </v-chip>
                  <v-chip
                    v-else-if="account.session_status === 'error'"
                    x-small
                    color="error"
                  >
                    Error
                  </v-chip>
                  </div>
                </v-list-item-content>
                </v-list-item>

                <v-divider></v-divider>

                <v-card-actions>
                <v-switch
                  v-model="account.is_active"
                  @update:model-value="toggleAccountStatus(account)"
                  color="success"
                  hide-details
                  label="Active"
                  class="ml-2"
                ></v-switch>
                <v-spacer></v-spacer>

                <v-btn small icon @click="testAccount(account.id)" title="Test Account">
                  <v-icon color="primary">mdi-test-tube</v-icon>
                </v-btn>

                <v-btn
                  small
                  icon
                  @click="showLoginDialogForAccount(account)"
                  v-if="account.session_status !== 'authorized'"
                  title="Login"
                >
                  <v-icon color="primary">mdi-login</v-icon>
                </v-btn>

                <v-btn
                  small
                  icon
                  @click="logoutAccount(account)"
                  v-if="account.session_status === 'authorized'"
                  title="Logout"
                >
                  <v-icon color="warning">mdi-logout</v-icon>
                </v-btn>

                <v-btn
                  small
                  icon
                  @click="showEditDialog(account)"
                  title="Edit"
                >
                  <v-icon color="primary">mdi-pencil</v-icon>
                </v-btn>

                <v-btn small icon @click="confirmDeleteAccount(account)" title="Delete">
                  <v-icon color="red">mdi-delete</v-icon>
                </v-btn>
                </v-card-actions>
              </v-card>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- New Account Dialog -->
    <v-dialog v-model="showNewAccountDialog" max-width="600px">
      <v-card>
        <v-card-title>Add New AI Messenger Account</v-card-title>
        <v-alert
          v-if="validationError"
          type="error"
          dismissible
          @click:close="validationError = ''"
          class="mb-4 m-3"
        >
          {{ validationError }}
        </v-alert>
        <v-card-text>
          <v-form ref="form" v-model="valid" lazy-validation>
            <v-text-field
              v-model="newAccount.name"
              label="Account Name"
              required
              :rules="[(v) => !!v || 'Name is required']"
            ></v-text-field>

            <v-text-field
              v-model="newAccount.phone_number"
              label="Phone Number"
              required
              prefix="+"
              :rules="[
                (v) => !!v || 'Phone number is required',
                (v) =>
                  /^\d+$/.test(v) || 'Phone number must contain only digits',
              ]"
            ></v-text-field>

            <v-text-field
              v-model="newAccount.api_id"
              label="API ID"
              required
              :rules="[(v) => !!v || 'API ID is required']"
            ></v-text-field>

            <v-text-field
              v-model="newAccount.api_hash"
              label="API Hash"
              required
              :rules="[(v) => !!v || 'API Hash is required']"
            ></v-text-field>

            <v-alert type="info" class="mt-4">
              You need to get API ID and API Hash from
              <a href="https://my.telegram.org/apps" target="_blank"
                >https://my.telegram.org/apps</a
              >
            </v-alert>
          </v-form>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            color="grey darken-1"
            text
            @click="showNewAccountDialog = false"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            :disabled="!valid"
            :loading="saving"
            @click="saveNewAccount"
          >
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="showDeleteDialog" max-width="400px">
      <v-card>
        <v-card-title class="headline">Confirm Deletion</v-card-title>
        <v-card-text>
          Are you sure you want to delete the account "{{
            accountToDelete?.name
          }}"? This action cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="grey darken-1" text @click="showDeleteDialog = false">
            Cancel
          </v-btn>
          <v-btn
            color="red darken-1"
            text
            :loading="deleting"
            @click="deleteAccount"
          >
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Test Result Dialog -->
    <v-dialog v-model="showTestResultDialog" max-width="500px">
      <v-card>
        <v-card-title class="headline">
          <v-icon
            :color="testResult.success ? 'success' : 'error'"
            class="mr-2"
          >
            {{ testResult.success ? "mdi-check-circle" : "mdi-alert-circle" }}
          </v-icon>
          Account Test Result
        </v-card-title>
        <v-card-text>
          <p>{{ testResult.message }}</p>

          <v-alert
            v-if="testResult.success && !testResult.is_authorized"
            type="warning"
            class="mt-4"
          >
            This account is not authorized yet. You'll need to perform login
            steps before it can be used.
            <div class="text-center mt-3">
              <v-btn color="primary" @click="loginFromTestDialog">
                Login Now
              </v-btn>
            </div>
          </v-alert>

          <v-alert
            v-if="testResult.success && testResult.is_authorized"
            type="success"
            class="mt-4"
          >
            This account is properly authenticated and ready to use.
            <div v-if="testResult.session_path" class="text-caption mt-2">
              Session file location: {{ testResult.session_path }}
            </div>
          </v-alert>

          <v-alert v-if="!testResult.success" type="error" class="mt-4">
            {{ testResult.error || "An error occurred during the test." }}
            <div v-if="testResult.details" class="text-caption mt-2">
              {{ testResult.details }}
            </div>
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" text @click="showTestResultDialog = false">
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Login Dialog - Request Code -->
    <v-dialog v-model="showLoginDialog" max-width="500px">
      <v-card>
        <v-card-title class="headline">
          <v-icon color="primary" class="mr-2">mdi-login</v-icon>
          Login to AI Account
        </v-card-title>
        <v-card-text>
          <v-alert
            v-if="
              accountForLogin && accountForLogin.session_status === 'authorized'
            "
            type="info"
          >
            This account appears to be already authenticated. Testing the
            connection can verify its status.
          </v-alert>
          <p
            v-if="
              accountForLogin && accountForLogin.session_status !== 'authorized'
            "
          >
            To use this AI account, you need to login to Telegram first.
          </p>
          <p
            v-if="
              accountForLogin && accountForLogin.session_status !== 'authorized'
            "
          >
            Click the button below to request a verification code. A code will
            be sent to the Telegram app on your phone.
          </p>
          <div class="mt-4 text-center">
            <v-btn
              v-if="
                accountForLogin &&
                accountForLogin.session_status !== 'authorized'
              "
              color="primary"
              :loading="requestingCode"
              @click="requestLoginCode"
            >
              Request Verification Code
            </v-btn>
            <v-btn v-else color="info" @click="testAccount(accountForLogin.id, true)">
              Test Connection
            </v-btn>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="grey darken-1" text @click="showLoginDialog = false">
            Cancel
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Code Verification Dialog -->
    <v-dialog v-model="showCodeVerificationDialog" max-width="500px">
      <v-card>
        <v-card-title class="headline">
          <v-icon color="primary" class="mr-2">mdi-key</v-icon>
          Enter Verification Code
        </v-card-title>
        <v-card-text>
          <p>
            A verification code was sent to your Telegram app. Please enter the
            code below.
          </p>
          <v-form ref="codeForm" v-model="codeValid">
            <v-text-field
              v-model="verificationCode"
              label="Verification Code"
              required
              :rules="[(v) => !!v || 'Code is required']"
              autofocus
              type="text"
              outlined
              class="mt-4"
            ></v-text-field>

            <v-text-field
              v-if="twoFactorRequired"
              v-model="twoFactorPassword"
              label="Two-Factor Password"
              required
              :rules="[(v) => !!v || 'Password is required']"
              type="password"
              outlined
              class="mt-4"
            ></v-text-field>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            color="grey darken-1"
            text
            @click="showCodeVerificationDialog = false"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            :loading="verifyingCode"
            :disabled="!codeValid"
            @click="verifyCode"
          >
            Submit
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Logout Confirmation Dialog -->
    <v-dialog v-model="showLogoutDialog" max-width="400px">
      <v-card>
        <v-card-title class="headline">
          <v-icon color="warning" class="mr-2">mdi-logout</v-icon>
          Confirm Logout
        </v-card-title>
        <v-card-text>
          <p>
            Are you sure you want to log out from the account "{{
              accountForLogout?.name
            }}"?
          </p>
          <p class="subtitle-2">
            This will delete the session file and require re-authentication to
            use this account again.
          </p>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="grey darken-1" text @click="showLogoutDialog = false">
            Cancel
          </v-btn>
          <v-btn
            color="warning"
            :loading="verifyingCode"
            @click="confirmLogout"
          >
            Logout
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Cleanup Sessions Confirmation Dialog -->
    <v-dialog v-model="showCleanupDialog" max-width="400px">
      <v-card>
        <v-card-title class="headline">
          <v-icon color="warning" class="mr-2">mdi-delete-sweep</v-icon>
          Confirm Sessions Cleanup
        </v-card-title>
        <v-card-text>
          <p>Are you sure you want to clean up all AI account sessions?</p>
          <p class="subtitle-2">
            This will delete all session files and require re-authentication for
            all accounts. This action cannot be undone.
          </p>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="grey darken-1" text @click="showCleanupDialog = false">
            Cancel
          </v-btn>
          <v-btn color="warning" @click="confirmCleanup">
            Clean Up All Sessions
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Edit Account Dialog -->
    <v-dialog v-model="showEditAccountDialog" max-width="600px">
      <v-card>
        <v-card-title class="headline">
          <v-icon color="primary" class="mr-2">mdi-pencil</v-icon>
          Edit AI Account
        </v-card-title>
        <v-card-text>
          <v-alert
            v-if="editValidationError"
            type="error"
            dismissible
            @click:close="editValidationError = ''"
            class="mb-4"
          >
            {{ editValidationError }}
          </v-alert>
          <v-form ref="editForm" v-model="editFormValid" lazy-validation>
            <v-text-field
              v-model="editAccount.name"
              label="Account Name"
              required
              :rules="[(v) => !!v || 'Name is required']"
            ></v-text-field>

            <v-switch
              v-model="editAccount.is_active"
              color="success"
              label="Active"
              hide-details
              class="mb-4"
            ></v-switch>

            <v-text-field
              v-model="editAccount.shareable_link"
              label="Shareable Link"
              hint="Optional shareable link for this account"
              persistent-hint
            ></v-text-field>

            <v-textarea
              v-model="editAccount.ai_response_context"
              label="AI Response Context"
              hint="Additional context for AI responses (optional)"
              persistent-hint
              rows="4"
              auto-grow
            ></v-textarea>
          </v-form>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            color="grey darken-1"
            text
            @click="showEditAccountDialog = false"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            :disabled="!editFormValid"
            :loading="editingSaving"
            @click="updateAccount"
          >
            Save Changes
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from "vue";
import { useStore } from "vuex";

// Setup store
const store = useStore();

// Reactive state
const loading = ref(false);
const saving = ref(false);
const deleting = ref(false);
const requestingCode = ref(false);
const verifyingCode = ref(false);

const valid = ref(true);
const codeValid = ref(true);
const showNewAccountDialog = ref(false);
const showDeleteDialog = ref(false);
const showTestResultDialog = ref(false);
const showLoginDialog = ref(false);
const showCodeVerificationDialog = ref(false);
const validationError = ref("");
const newAccount = reactive({
  name: "",
  phone_number: "",
  api_id: "",
  api_hash: "",
});

const accountToDelete = ref(null);
const accountForLogin = ref(null);
const accountForLogout = ref(null);
const verificationCode = ref("");
const twoFactorPassword = ref("");
const twoFactorRequired = ref(false);
const showLogoutDialog = ref(false);
const showCleanupDialog = ref(false);
const showEditAccountDialog = ref(false);
const editFormValid = ref(true);
const editingSaving = ref(false);
const editValidationError = ref("");
const editAccount = reactive({
  id: null,
  name: "",
  is_active: true,
  shareable_link: "",
  ai_response_context: ""
});

const testResult = reactive({
  success: false,
  is_authorized: false,
  message: "",
});

// Form refs
const form = ref(null);
const codeForm = ref(null);
const editForm = ref(null);

// Computed properties
const aiAccounts = computed(() => store.getters["ai/aiAccounts"]);

// Get account session status from localStorage or API
const getAccountSessionStatus = async (account, forceRefresh = false) => {
  // Check if we have a cached result and it's not a forced refresh
  if (!forceRefresh) {
    const cachedStatus = getAccountStatusFromCache(account.id);
    if (cachedStatus) {
      account.session_status = cachedStatus.is_authorized
        ? "authorized"
        : "unauthorized";
      return cachedStatus.is_authorized;
    }
  }
  
  // If no cache or force refresh, check via API
  return await checkAccountSessionStatus(account);
};

// Get account status from localStorage cache
const getAccountStatusFromCache = (accountId) => {
  try {
    const cacheKey = `ai_account_status_${accountId}`;
    const cachedData = localStorage.getItem(cacheKey);
    
    if (cachedData) {
      const parsedData = JSON.parse(cachedData);
      
      // Check if cache is still valid (24 hours)
      const now = new Date().getTime();
      const cacheTime = parsedData.timestamp;
      const cacheAge = now - cacheTime;
      const cacheExpiration = 24 * 60 * 60 * 1000; // 24 hours in milliseconds
      
      if (cacheAge < cacheExpiration) {
        return parsedData;
      } else {
        // Clear expired cache
        localStorage.removeItem(cacheKey);
      }
    }
  } catch (error) {
    console.error("Error reading from localStorage:", error);
    // Clear potentially corrupted cache
    localStorage.removeItem(`ai_account_status_${accountId}`);
  }
  
  return null;
};

// Save account status to localStorage
const saveAccountStatusToCache = (accountId, status) => {
  try {
    const cacheKey = `ai_account_status_${accountId}`;
    const cacheData = {
      ...status,
      timestamp: new Date().getTime()
    };
    
    localStorage.setItem(cacheKey, JSON.stringify(cacheData));
  } catch (error) {
    console.error("Error saving to localStorage:", error);
  }
};

// Check if an account has a valid session via API
const checkAccountSessionStatus = async (account) => {
  try {
    // Test connection to determine if account is authorized
    const result = await store.dispatch("ai/testAIAccount", account.id);
    account.session_status = result.is_authorized
      ? "authorized"
      : "unauthorized";
    
    // Save the result to cache
    saveAccountStatusToCache(account.id, result);
    
    return result.is_authorized;
  } catch (error) {
    console.error(
      `Error checking account session status for ${account.name}:`,
      error
    );
    account.session_status = "error";
    return false;
  }
};

const saveNewAccount = async () => {
  validationError.value = '';

  if (!form.value.validate()) {
    return;
  }

  saving.value = true;
  try {
    const result = await store.dispatch("ai/createAIAccount", newAccount);

    // Reset form and close dialog
    form.value.reset();
    showNewAccountDialog.value = false;
    
    // If we have an account ID in the result, initialize its cache
    if (result && result.data && result.data.account_id) {
      saveAccountStatusToCache(result.data.account_id, {
        success: true,
        is_authorized: false,
        message: "Account created, authentication required"
      });
    }
  } catch (error) {
    console.error("Error creating account:", error);
      // Display validation error from the server
      validationError.value = error || "Validation error";

  } finally {
    saving.value = false;
  }
};

const toggleAccountStatus = async (account) => {
  try {
    await store.dispatch("ai/updateAIAccount", {
      accountId: account.id,
      isActive: account.is_active,
    });
  } catch (error) {
    // Revert the toggle if there was an error
    account.is_active = !account.is_active;
  }
};

const showEditDialog = (account) => {
  // Initialize edit form with account data
  editAccount.id = account.id;
  editAccount.name = account.name;
  editAccount.is_active = account.is_active;
  editAccount.shareable_link = account.shareable_link || "";
  editAccount.ai_response_context = account.ai_response_context || "";
  
  // Reset validation
  editValidationError.value = "";
  
  // Show the dialog
  showEditAccountDialog.value = true;
};

const updateAccount = async () => {
  if (!editFormValid.value) {
    return;
  }
  
  editingSaving.value = true;
  try {
    await store.dispatch("ai/updateAIAccount", {
      accountId: editAccount.id,
      name: editAccount.name,
      isActive: editAccount.is_active,
      shareable_link: editAccount.shareable_link,
      ai_response_context: editAccount.ai_response_context
    });
    
    // Close dialog after successful update
    showEditAccountDialog.value = false;
  } catch (error) {
    console.error("Error updating account:", error);
    editValidationError.value = error.message || "Failed to update account";
  } finally {
    editingSaving.value = false;
  }
};

const confirmDeleteAccount = (account) => {
  accountToDelete.value = account;
  showDeleteDialog.value = true;
};

const deleteAccount = async () => {
  if (!accountToDelete.value) {
    return;
  }

  deleting.value = true;
  try {
    await store.dispatch("ai/deleteAIAccount", accountToDelete.value.id);
    
    // Remove the account from localStorage cache
    localStorage.removeItem(`ai_account_status_${accountToDelete.value.id}`);
    
    showDeleteDialog.value = false;
  } catch (error) {
    console.error("Error deleting account:", error);
  } finally {
    deleting.value = false;
  }
};

const testAccount = async (accountId, forceRefresh = true) => {
  try {
    // Store the account ID for later use if we need to log in
    accountForLogin.value = { id: accountId };

    // Find the account object
    const account = aiAccounts.value.find(acc => acc.id === accountId);
    
    // Test the account with force refresh (skip cache)
    let result;
    if (account) {
      await getAccountSessionStatus(account, forceRefresh); // Force refresh from API by default
      // Get the fresh result after forced API call
      result = await store.dispatch("ai/testAIAccount", accountId);
    } else {
      // Fallback if account not found in local state
      result = await store.dispatch("ai/testAIAccount", accountId);
    }
    
    console.log("Test result:", result);
    Object.assign(testResult, result);
    
    // Update the cache with the fresh result
    saveAccountStatusToCache(accountId, result);
    
    showTestResultDialog.value = true;
  } catch (error) {
    console.error("Error testing account:", error);
  }
};

const loginFromTestDialog = () => {
  // Find the account that was just tested
  const account = aiAccounts.value.find(
    (acc) => acc.id === accountForLogin.value?.id
  );

  // Close the test dialog and open the login dialog
  showTestResultDialog.value = false;

  if (account) {
    showLoginDialogForAccount(account);
  }
};

const showLoginDialogForAccount = (account) => {
  // First get the latest status from cache
  const cachedStatus = getAccountStatusFromCache(account.id);
  if (cachedStatus) {
    account.session_status = cachedStatus.is_authorized ? "authorized" : "unauthorized";
  }
  
  accountForLogin.value = account;
  showLoginDialog.value = true;
  verificationCode.value = "";
  twoFactorPassword.value = "";
  twoFactorRequired.value = false;
};

const logoutAccount = async (account) => {
  accountForLogout.value = account;
  showLogoutDialog.value = true;
};

const confirmLogout = async () => {
  try {
    await store.dispatch("ai/logoutAIAccount", accountForLogout.value.id);
    
    // Clear the cache for this account
    localStorage.removeItem(`ai_account_status_${accountForLogout.value.id}`);
    
    // Session status will be updated in the fetchAIAccounts call triggered by the action
    showLogoutDialog.value = false;
  } catch (error) {
    console.error("Error logging out account:", error);
  }
};

const cleanupAllSessions = async () => {
  showCleanupDialog.value = true;
};

const confirmCleanup = async () => {
  try {
    await store.dispatch("ai/cleanupAISessions");
    
    // Clear all account status caches
    aiAccounts.value.forEach(account => {
      localStorage.removeItem(`ai_account_status_${account.id}`);
    });
    
    // Session status will be updated in the fetchAIAccounts call triggered by the action
    showCleanupDialog.value = false;
  } catch (error) {
    console.error("Error cleaning up sessions:", error);
  }
};

const requestLoginCode = async () => {
  if (!accountForLogin.value) {
    return;
  }

  requestingCode.value = true;
  try {
    // Call the login API with request_code action
    const result = await store.dispatch("ai/loginAIAccount", {
      accountId: accountForLogin.value.id,
      action: "request_code",
    });

    if (result.success) {
      // Close the login dialog and open the code verification dialog
      showLoginDialog.value = false;
      showCodeVerificationDialog.value = true;
    } else if (result.data.action === "already_authorized") {
      // If already authorized, just close the dialog
      showLoginDialog.value = false;
    }
  } catch (error) {
    console.error("Error requesting verification code:", error);
  } finally {
    requestingCode.value = false;
  }
};

const verifyCode = async () => {
  if (!accountForLogin.value || !verificationCode.value) {
    return;
  }

  if (!codeForm.value.validate()) {
    return;
  }

  verifyingCode.value = true;
  try {
    // Call the login AI account action with verify_code action
    const result = await store.dispatch("ai/loginAIAccount", {
      accountId: accountForLogin.value.id,
      action: "verify_code",
      phoneCode: verificationCode.value,
      password: twoFactorRequired.value ? twoFactorPassword.value : null,
    });

    if (result.success) {
      // Successfully verified
      showCodeVerificationDialog.value = false;

      // Update the cache with the new authorized status
      saveAccountStatusToCache(accountForLogin.value.id, {
        success: true,
        is_authorized: true,
        message: "Account authenticated successfully"
      });

      // Refresh the accounts list
      await store.dispatch("ai/fetchAIAccounts");
      
      // Update account statuses from cache
      for (const account of aiAccounts.value) {
        await getAccountSessionStatus(account, account.id === accountForLogin.value.id);
      }
    } else if (result.data.action === "password_required") {
      // Two-factor authentication is required
      twoFactorRequired.value = true;
    }
  } catch (error) {
    console.error("Error verifying code:", error);
  } finally {
    verifyingCode.value = false;
  }
};

// Lifecycle hooks
onMounted(async () => {
  // Load accounts from store first for quick UI rendering
  await store.dispatch("ai/fetchAIAccounts");
  
  // Then check their status (from cache when available)
  loading.value = true;
  try {
    for (const account of aiAccounts.value) {
      await getAccountSessionStatus(account, false); // Don't force refresh
    }
  } catch (error) {
    console.error("Error checking account statuses:", error);
  } finally {
    loading.value = false;
  }
});
</script>
