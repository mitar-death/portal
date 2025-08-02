# AI Messenger for Telegram Portal

The AI Messenger system allows you to set up automated responses to messages in Telegram groups that match your keywords.

## How It Works

1. **Keyword Monitoring**: The system monitors messages in your selected Telegram groups for keywords you've defined.

2. **AI Account**: When a message matches your keywords, the system uses a Telegram user account (not a bot) to respond to the message.

3. **AI-Powered Responses**: The system uses Google's Gemini AI to analyze the message and generate an appropriate response.

## Setup Instructions

### 1. Create a Telegram API Application

To use the AI Messenger, you need to create a Telegram API application:

1. Go to https://my.telegram.org/auth
2. Log in with your Telegram account
3. Click on "API development tools"
4. Fill in the form (you can use "TG Portal AI" as the app name and any description)
5. Submit the form
6. Note down your **api_id** and **api_hash** values - you'll need these later

### 2. Create an AI Account

1. In the TG Portal application, go to the "AI Messenger" section
2. Click "Add New Account"
3. Fill in the form:
   - **Account Name**: A name to identify this account (e.g., "Support AI")
   - **Phone Number**: The phone number of a Telegram account you want to use for responses
   - **API ID**: The api_id from your Telegram API application
   - **API Hash**: The api_hash from your Telegram API application
4. Click "Save"
5. Use the "Test" button to verify the account is working properly

> **Note**: The first time you use the account, you may need to authorize it by entering a verification code sent to the account's phone number or Telegram.

### 3. Assign AI Accounts to Groups

1. Go to the "AI Assignments" section
2. For each group you want to enable AI responses for:
   - Select an AI account from the dropdown
   - Toggle the "Active" switch to enable/disable responses
3. Changes are saved automatically

### 4. Add Keywords

1. Go to the "Keywords" section
2. Add keywords that should trigger AI responses
3. The more specific your keywords, the better the targeting will be

## How Responses Work

1. When a message contains one of your keywords, the system will:

   - Analyze the message content using Google's Gemini AI
   - Generate a contextually appropriate response
   - Send the response using your AI account

2. The system maintains conversation state, so it knows if it's continuing an existing conversation or starting a new one.

3. If the AI is unable to generate a response (e.g., if the API is unavailable), it will fall back to simple template responses.

## Best Practices

1. **Use Separate Accounts**: For best results, use dedicated Telegram accounts for your AI messenger, not your personal account.

2. **Be Specific with Keywords**: Choose specific keywords that indicate genuine interest or questions.

3. **Monitor Conversations**: Regularly check the conversations your AI is having to ensure they're appropriate and helpful.

4. **Update Keywords**: Refine your keywords based on the messages that trigger responses.

## Troubleshooting

1. **AI Account Not Responding**:

   - Check that the account is properly authorized
   - Verify that the account is assigned to the group
   - Ensure the assignment is set to "Active"

2. **No Keywords Matching**:

   - Review your keywords list
   - Consider adding variations of keywords
   - Check message logs to see what content is being received

3. **Authorization Issues**:
   - If the account isn't authorized, you may need to perform a new login
   - Use the "Test" button on the AI Accounts page to verify authorization status

# AI Messenger Feature Integration

This document provides an overview of the AI messenger functionality in TG Portal.

## Overview

The AI messenger feature allows automated responses to Telegram messages that match specified keywords. It works by:

1. Creating AI messenger accounts (Telegram user accounts)
2. Assigning these accounts to specific Telegram groups
3. Monitoring messages in these groups for keywords
4. Automatically responding to matching messages using the AI account

## Components

### Models

- `AIAccount`: Stores Telegram user account credentials used for automated messaging
- `Group`: Represents a Telegram group being monitored
- `GroupAIAccount`: Links AI accounts to specific groups

### Backend Services

- `MessengerAI`: Manages multiple AI accounts and their group assignments
- Enhanced monitoring to detect messages and trigger AI responses

### API Endpoints

- `/api/ai/accounts`: CRUD operations for AI accounts
- `/api/ai/accounts/test`: Test connection to an AI account
- `/api/ai/group-assignments`: Manage group-to-AI account assignments

### Frontend Components

- `AIAccountsView`: UI for creating and managing AI accounts
- `GroupAIAssignmentView`: UI for assigning AI accounts to groups
- Vuex store integration for state management
- Global snackbar for notifications

## State Management

The application uses Vuex for state management with the following features:

- AI accounts state in `state.ai.accounts`
- Group assignments state in `state.ai.groupAssignments`
- Actions for fetching, creating, updating, and deleting AI accounts
- Actions for managing group assignments
- Global snackbar system for notifications

## Setup Instructions

1. Create AI accounts in the AI Messenger Accounts section

   - You'll need Telegram API credentials from https://my.telegram.org/apps
   - Each account requires a name, phone number, API ID, and API Hash

2. Assign AI accounts to groups in the AI Assignments section

   - Select which AI account should respond in each group
   - Toggle the active status to enable/disable responses

3. Set up keywords in the Keywords section

   - These keywords will trigger AI responses when detected in messages

4. The system will now automatically monitor messages and respond when keywords are detected

## Important Notes

- AI accounts must be authorized before they can send messages
- You can test account connectivity using the test button in the AI accounts view
- Each group can only have one AI account assigned at a time
- AI accounts can be assigned to multiple groups

## Troubleshooting

If you encounter issues:

1. Check that the AI account is properly authorized
2. Verify the account is marked as active
3. Ensure the group assignment is also active
4. Check that you have defined keywords that can trigger responses
5. Make sure the group permissions allow the AI account to send messages
