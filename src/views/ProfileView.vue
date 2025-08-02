<template>
  <div>
    <h1 class="text-h4 mb-4">User Profile</h1>

    <v-card class="mx-auto" max-width="600">
      <v-card-title>Profile Information</v-card-title>

      <v-card-text v-if="currentUser">
        <v-list>
          <v-list-item>
            <template v-slot:prepend>
              <v-icon icon="mdi-account"></v-icon>
            </template>
            <v-list-item-title>
              {{ currentUser.first_name }} {{ currentUser.last_name || "" }}
            </v-list-item-title>
            <v-list-item-subtitle> Name </v-list-item-subtitle>
          </v-list-item>

          <v-list-item v-if="currentUser.username">
            <template v-slot:prepend>
              <v-icon icon="mdi-at"></v-icon>
            </template>
            <v-list-item-title>
              {{ currentUser.username }}
            </v-list-item-title>
            <v-list-item-subtitle> Username </v-list-item-subtitle>
          </v-list-item>

          <v-list-item>
            <template v-slot:prepend>
              <v-icon icon="mdi-phone"></v-icon>
            </template>
            <v-list-item-title>
              {{ currentUser.phone_number }}
            </v-list-item-title>
            <v-list-item-subtitle> Phone Number </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card-text>

      <v-card-text v-else>
        <p>Loading user information...</p>
      </v-card-text>
    </v-card>
  </div>
</template>

<script>
import { mapGetters } from "vuex";

export default {
  name: "ProfileView",

  computed: {
    ...mapGetters(["currentUser"]),
  },
};
</script>
