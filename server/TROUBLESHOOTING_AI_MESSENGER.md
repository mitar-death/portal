# AI Messenger Diagnostics and Troubleshooting Guide

## Recent Improvements

The AI Messenger system has been enhanced with improved diagnostic capabilities and error handling to ensure reliable operation. Key improvements include:

1. **Enhanced Logging**: Detailed logging throughout the message handling process to identify where issues might occur.
2. **Diagnostic API Endpoint**: A new `/api/ai/diagnostics` endpoint that provides detailed information about the AI messenger system's state.
3. **Session Directory Management**: Dedicated session directory for AI accounts at `storage/sessions/ai_accounts`.
4. **Consistent Group ID Handling**: Ensured consistent handling of group IDs as strings for reliable lookups.
5. **Client Connection Verification**: Added verification of client connection status before sending messages.
6. **Better Error Reporting**: Improved error reporting with detailed information about failures.
7. **Auto-Recovery System**: Periodic health checks to detect and fix issues with the AI messenger.
8. **Reinitialization Endpoint**: A new `/api/ai/reinitialize` endpoint to force reinitialization of the AI messenger.

## Common Issues and Solutions

### AI Not Responding to Keyword Matches

If your AI is detecting keywords but not responding to messages, check the following:

1. **Verify Group-AI Mappings**:

   - Check that the group is properly mapped to an AI account in the "Group AI Assignment" view.
   - Make sure the AI account assigned to the group is active.

2. **Check AI Account Status**:

   - Verify the AI account is properly logged in (green status indicator in the AI Accounts view).
   - Try logging out and back in to the AI account if necessary.

3. **Use the Reinitialization Endpoint**:

   - If the AI messenger stops responding, use the "Reset AI Messenger" button in the Settings page.
   - Alternatively, use the `/api/ai/reinitialize` endpoint to force a reset:

   ```
   POST /api/ai/reinitialize
   ```

   - This will clean up and reinitialize all AI clients and mappings.

4. **Examine Diagnostic Data**:

   - Use the diagnostic endpoint (`/api/ai/diagnostics`) to check:
     - Whether the AI client is properly connected and authorized
     - If the group ID appears in the group-AI mappings
     - If the keywords are properly loaded

5. **Review Logs**:
   - Check the server logs at `storage/logs/app.log` for errors or warnings related to:
     - Missing sender_id in messages
     - Group ID format mismatches
     - AI client authorization issues
     - "messenger_ai is None" messages

### Auto-Recovery Features

The AI messenger system now includes automatic recovery features:

1. **Periodic Health Checks**: The system performs health checks every 5 minutes to ensure the AI messenger is running properly.
2. **Auto-Reinitialization**: If the system detects that the AI messenger is not initialized or in a bad state, it will attempt to reinitialize it.
3. **Message-Level Recovery**: If a message with keywords is received but the AI messenger is not initialized, the system will attempt to reinitialize it before processing the message.

### Using the Diagnostics API

The new diagnostics API provides comprehensive information about the AI messenger system's state:

```
GET /api/ai/diagnostics
```

The response includes:

- Active user ID
- Monitored groups
- Keywords being monitored
- AI client status (connected, authorized)
- Group-to-AI mappings
- AI account status for each group

Use this information to diagnose issues with the AI messenger system.

## Monitoring

The AI messenger system now includes enhanced monitoring capabilities:

1. **Client Connection Status**: The system regularly checks if the Telegram client is connected and authorized.
2. **Group-AI Mapping Verification**: Verifies that group IDs are correctly formatted and mapped to active AI accounts.
3. **Message Processing Logging**: Logs each step of the message processing pipeline for easier debugging.

## Manual Debugging Steps

If you're experiencing issues with the AI messenger:

1. **Use the Reset Feature**:

   - Go to Settings and click "Reset AI Messenger"
   - This will force a complete reset and reinitialization of the AI messenger system

2. **Verify Keyword Detection**:

   - Send a test message with a known keyword to a monitored group
   - Check the logs to see if the keyword is detected

3. **Check Group Mapping**:

   - Verify that the group's Telegram ID matches the ID stored in the database
   - Use the diagnostic endpoint to see all current mappings

4. **Test AI Account**:

   - Use the "Test Account" button in the AI Accounts view
   - This verifies that the account can connect to Telegram

5. **Inspect Session Files**:
   - Check if session files exist in `storage/sessions/ai_accounts`
   - Missing or corrupt session files can cause authentication issues

## Error Messages and Their Meaning

| Error Message                   | Meaning                                             | Solution                                                                 |
| ------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------ |
| "messenger_ai is None"          | The AI messenger system is not initialized          | Use the "Reset AI Messenger" button in Settings                          |
| "No AI account mapped to group" | The group doesn't have an AI account assigned       | Assign an AI account in the Group AI Assignment view                     |
| "AI account not initialized"    | The AI account exists but failed to initialize      | Check the API ID and hash, then logout and login again                   |
| "No sender_id provided"         | Message is missing sender information               | This is usually a Telegram API issue - try updating the Telethon library |
| "Failed to send message"        | The AI account couldn't send a message to the group | Verify the AI account has permission to send messages in the group       |
