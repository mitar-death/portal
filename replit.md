# TGPortal - Telegram Portal Application

## Project Overview
TGPortal is a Telegram monitoring and automated response application with Vue.js frontend and FastAPI backend. The application allows users to monitor Telegram groups, filter messages by keywords, and provide AI-powered automated responses.

## Architecture
- **Frontend**: Vue.js 3 with Vuetify UI framework running on port 5000
- **Backend**: FastAPI Python application running on port 8000
- **Database**: PostgreSQL (Replit managed)
- **Session Storage**: Redis (preferred) with automatic fallback to file-based Telegram sessions in `storage/sessions/`
- **Caching**: Redis (optional) with graceful degradation when unavailable

## Recent Setup Changes (September 21, 2025)
- ✅ Configured for Replit environment with proper host and port settings
- ✅ Frontend configured with `allowedHosts: 'all'` for iframe compatibility
- ✅ Backend configured to use localhost:8000 with CORS for Replit domain
- ✅ Database migrations successfully applied
- ✅ Made Pusher configuration optional (runs without Pusher credentials)
- ✅ Both workflows configured and running successfully
- ✅ Deployment configuration set for autoscale target
- ✅ **Enhanced Redis connection handling for cloud environments** (September 21, 2025)
  - Implemented Redis connection retry logic with exponential backoff
  - Added graceful fallback to file-based sessions when Redis is unavailable
  - Enhanced startup resilience to prevent Redis failures from crashing the application
  - Added comprehensive Redis health checks to monitoring system
  - Updated all services to handle Redis unavailability gracefully

## Current Configuration
### Frontend (Port 5000)
- Vue.js development server with hot reload
- Proxy configuration for `/api` routes to backend
- Configured for Replit iframe environment

### Backend (Port 8000)
- FastAPI with automatic documentation at `/docs`
- Database connection configured with Replit PostgreSQL
- CORS configured for development and Replit domain
- Optional Pusher WebSocket support
- Telegram API integration (requires user configuration)

## Required User Configuration
For full functionality, users need to configure:
1. **Telegram API Credentials**: `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`
2. **Google AI API Key**: `GOOGLE_STUDIO_API_KEY` for AI responses
3. **Pusher Credentials** (optional): For real-time WebSocket features
4. **Redis Configuration** (optional): `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`
   - Application works without Redis (falls back to file-based sessions)
   - Redis improves performance and session consistency across restarts

## Project Structure
```
├── server/          # FastAPI backend
│   ├── app/
│   │   ├── controllers/   # Business logic
│   │   ├── models/        # Database models
│   │   ├── routes/        # API endpoints
│   │   ├── services/      # External service integrations
│   │   └── core/          # Core configuration and utilities
│   └── migrations/    # Database migration files
├── src/             # Vue.js frontend
│   ├── components/    # Vue components
│   ├── views/         # Page views
│   ├── store/         # Vuex state management
│   └── services/      # API service layer
└── storage/         # Application data storage
    └── sessions/      # Telegram session files
```

## Deployment Notes
- Configured for autoscale deployment target
- Build process includes Vue.js compilation
- Production runs both frontend and backend services
- Database automatically managed by Replit