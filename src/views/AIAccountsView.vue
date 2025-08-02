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

            <v-list v-else two-line>
              <v-list-item v-for="account in aiAccounts" :key="account.id">
                <v-list-item-avatar>
                  <v-icon :color="account.is_active ? 'success' : 'grey'">
                    {{
                      account.is_active
                        ? "mdi-account-check"
                        : "mdi-account-off"
                    }}
                  </v-icon>
                </v-list-item-avatar>

                <v-list-item-content>
                  <v-list-item-title>{{ account.name }}</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ account.phone_number }}
                    <v-chip
                      v-if="account.session_status === 'authorized'"
                      x-small
                      color="success"
                      class="ml-2"
                    >
                      Authenticated
                    </v-chip>
                    <v-chip
                      v-else-if="account.session_status === 'unauthorized'"
                      x-small
                      color="warning"
                      class="ml-2"
                    >
                      Login Required
                    </v-chip>
                    <v-chip
                      v-else-if="account.session_status === 'error'"
                      x-small
                      color="error"
                      class="ml-2"
                    >
                      Error
                    </v-chip>
                  </v-list-item-subtitle>
                </v-list-item-content>

                <v-list-item-action>
                  <v-switch
                    v-model="account.is_active"
                    @update:model-value="toggleAccountStatus(account)"
                    color="success"
                    hide-details
                  ></v-switch>
                </v-list-item-action>

                <v-list-item-action>
                  <v-btn icon @click="testAccount(account.id)">
                    <v-icon color="primary">mdi-test-tube</v-icon>
                    Test
                  </v-btn>
                </v-list-item-action>

                <v-list-item-action>
                  <v-btn
                    v-if="account.session_status !== 'authorized'"
                    icon
                    @click="showLoginDialogForAccount(account)"
                  >
                    <v-icon color="primary">mdi-login</v-icon>
                    Login
                  </v-btn>
                  <v-btn v-else icon @click="logoutAccount(account)">
                    <v-icon color="warning">mdi-logout</v-icon>
                    Logout
                  </v-btn>
                </v-list-item-action>

                <v-list-item-action>
                  <v-btn icon @click="confirmDeleteAccount(account)">
                    <v-icon color="red">mdi-delete</v-icon>
                    Delete
                  </v-btn>
                </v-list-item-action>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- New Account Dialog -->
    <v-dialog v-model="showNewAccountDialog" max-width="600px">
      <v-card>
        <v-card-title>Add New AI Messenger Account</v-card-title>
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
            <v-btn v-else color="info" @click="testAccount(accountForLogin.id)">
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

const testResult = reactive({
  success: false,
  is_authorized: false,
  message: "",
});

// Form refs
const form = ref(null);
const codeForm = ref(null);

// Computed properties
const aiAccounts = computed(() => store.getters["ai/aiAccounts"]);

// Methods
const fetchAIAccounts = async () => {
  loading.value = true;
  try {
    await store.dispatch("ai/fetchAIAccounts");

    // Check session status for each account
    for (const account of aiAccounts.value) {
      await checkAccountSessionStatus(account);
    }
  } catch (error) {
    console.error("Error fetching accounts:", error);
  } finally {
    loading.value = false;
  }
};

// Check if an account has a valid session
const checkAccountSessionStatus = async (account) => {
  try {
    // Test connection to determine if account is authorized
    const result = await store.dispatch("ai/testAIAccount", account.id);
    account.session_status = result.is_authorized
      ? "authorized"
      : "unauthorized";
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
  if (!form.value.validate()) {
    return;
  }

  saving.value = true;
  try {
    await store.dispatch("ai/createAIAccount", newAccount);

    // Reset form and close dialog
    form.value.reset();
    showNewAccountDialog.value = false;
  } catch (error) {
    console.error("Error creating account:", error);
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
    showDeleteDialog.value = false;
  } catch (error) {
    console.error("Error deleting account:", error);
  } finally {
    deleting.value = false;
  }
};

const testAccount = async (accountId) => {
  try {
    // Store the account ID for later use if we need to log in
    accountForLogin.value = { id: accountId };

    // Test the account
    const result = await store.dispatch("ai/testAIAccount", accountId);
    Object.assign(testResult, result);
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
    } else if (result.action === "already_authorized") {
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

      // Refresh the accounts list
      await fetchAIAccounts();
    } else if (result.action === "password_required") {
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
onMounted(() => {
  fetchAIAccounts();
});
</script>
