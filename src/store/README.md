# Vuex Store Restructuring

## Overview

The Vuex store has been restructured to use a modular approach, which provides better organization, maintainability, and scalability as the application grows.

## Modules

The store has been split into the following modules:

### 1. Auth Module (`/src/store/modules/auth.js`)

Handles authentication-related state:

- User information
- Authentication token
- Login/logout functionality

### 2. Telegram Module (`/src/store/modules/telegram.js`)

Manages Telegram-related functionality:

- Telegram groups
- Keywords for message filtering
- Group monitoring

### 3. AI Module (`/src/store/modules/ai.js`)

Manages AI messaging functionality:

- AI accounts
- Group assignments
- Account login and testing

### 4. UI Module (`/src/store/modules/ui.js`)

Handles UI-related state:

- Snackbar notifications

## Accessing the Store in Components

Since we're using namespaced modules, you need to use a slightly different syntax to access store properties:

### Getters

```javascript
// Old way
const user = computed(() => store.getters.currentUser);

// New way
const user = computed(() => store.getters["auth/currentUser"]);
```

### Actions

```javascript
// Old way
await store.dispatch("fetchAIAccounts");

// New way
await store.dispatch("ai/fetchAIAccounts");
```

### State

```javascript
// Old way
const groups = computed(() => store.state.telegram.groups);

// New way
const groups = computed(() => store.state.telegram.groups);
// (remains the same if accessing a module's top-level state)
```

## Benefits of the New Structure

1. **Better Organization**: Related functionality is grouped together.
2. **Improved Maintainability**: Changes to one area won't affect others.
3. **Reusability**: Modules can be reused across different parts of the application.
4. **Scalability**: Easier to add new features without complicating the store.
5. **Namespacing**: Prevents naming collisions between actions, mutations, and getters.

## Naming Conventions

All module functions follow these naming conventions:

- **State**: Uses camelCase property names
- **Getters**: Uses camelCase names
- **Mutations**: Uses UPPER_SNAKE_CASE names
- **Actions**: Uses camelCase names

This consistent naming helps make the codebase more predictable and easier to understand.
