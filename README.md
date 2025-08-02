# tgportal

A Telegram portal application for monitoring and automated response to messages.

## Features

- Monitor messages in selected Telegram groups
- Filter messages by keywords
- AI-powered automated responses using Telegram user accounts
- Group management and AI account assignment

## Project setup
```
yarn install
```

### Compiles and hot-reloads for development
```
yarn serve
```

### Compiles and minifies for production
```
yarn build
```

### Lints and fixes files
```
yarn lint
```

## AI Messenger System

The AI Messenger system now includes enhanced diagnostic capabilities and improved error handling. See the following documentation for details:

- [AI Messenger Setup Guide](./README_AI_MESSENGER.md)
- [Troubleshooting Guide](./server/TROUBLESHOOTING_AI_MESSENGER.md)

## API Endpoints

### Diagnostics

The system now includes a diagnostic API endpoint:

```
GET /api/ai/diagnostics
```

This endpoint provides comprehensive information about the AI messenger system's state, including:
- Active user ID
- Monitored groups
- Keywords being monitored
- AI client status
- Group-to-AI mappings

### Customize configuration
See [Configuration Reference](https://cli.vuejs.org/config/).
