# Keerthana AI - Telegram Girlfriend Bot

## Overview
A romantic AI girlfriend Telegram bot with emotional personality, memory, force subscription, rich text formatting, and referral-based points system using Google Gemini API.

## Project Structure
```
├── app.py               # Combined webhook bot + Flask dashboard (production)
├── main.py              # Legacy polling-based bot (backup)
├── dashboard.py         # Legacy standalone dashboard (backup)
├── database.py          # PostgreSQL database operations
├── .gitignore          # Git ignore file
└── replit.md           # Project documentation
```

## Features
- **AI Girlfriend Personality**: Romantic, emotional conversations using Gemini AI (bisexual, LGBT-friendly)
- **Force Subscription**: Users must join @keerthanalovesu channel before using bot
- **Chat Memory**: Stores conversation history in PostgreSQL
- **Personalization**: Remembers user's preferred name and conversation style
- **Message Limits**: 20 free messages daily, resets at midnight
- **Referral System**: Users earn 10 bonus messages for each friend who joins
- **Rich Formatting**: Bold, italic, emojis for expressive messages
- **Tanglish Support**: Natural Tamil + English conversation style (uses "da" default, "di" only for confirmed girls)
- **Gender Detection**: Server-side tracking - only switches to "di" when user explicitly states "I am a girl" / "naan ponnu"

## Commands
- `/start` - Start the bot and register
- `/referral` - Get your unique referral link
- `/points` - Check your points balance
- `/stats` - View your statistics

### Admin Commands (ID: 6474452917 only)
- `/setlimit [user_id] [limit]` - Set custom daily message limit for a user
- `/block [user_id]` - Block a user from using the bot
- `/unblock [user_id]` - Unblock a user

## Environment Variables Required
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token from @BotFather
- `GEMINI_API_KEY` - Your Google Gemini API key
- `FORCE_SUB_CHANNEL` - Channel username for mandatory subscription (e.g., @yourchannel)
- `DATABASE_URL` - PostgreSQL connection string (auto-configured)
- `DASHBOARD_PASSWORD` - Password to access the moderation dashboard (required)
- `SESSION_SECRET` - Secret key for Flask sessions (optional, auto-generated if not set)
- `WEBHOOK_URL` - Production deployment URL for Telegram webhook (set in production environment only)

## Database Tables
- `users` - User profiles, points, referral counts
- `chat_messages` - Conversation history
- `referrals` - Referral tracking
- `points_transactions` - Points history

## Tech Stack
- Python 3.11+
- python-telegram-bot
- google-generativeai (Gemini API)
- PostgreSQL (psycopg2)

## Moderation Dashboard
Access the dashboard at the webview URL (port 5000). Features:
- Password-protected login (uses DASHBOARD_PASSWORD)
- Stats overview: total users, messages, active today
- User table: names, message counts, status, custom limits, referrals
- View chat history for any user with timestamps
- Block/Unblock users - blocked users cannot use the bot
- Set custom daily message limits for individual users
- Admin ID: 6474452917

## Recent Changes
- January 19, 2026: Fixed production webhook - bot now correctly registers webhook with production deployment URL
- January 19, 2026: Converted bot from polling to webhook mode for autoscale deployment (cost-effective)
- January 19, 2026: Merged bot and dashboard into single Flask app (app.py) on port 5000
- January 18, 2026: Fixed "di" bug - bot now ONLY uses "di" when user explicitly confirms gender (e.g., "I am a girl"), not when playfully saying "diii"
- January 18, 2026: Added server-side gender detection with database tracking and post-processing to enforce "da" default
- January 18, 2026: Fixed repetitive questioning - Keerthana now takes initiative with actions instead of always asking "sollu da"
- January 18, 2026: Enhanced Tanglish vocabulary, grammar patterns, and expanded chat history to 25 messages for better memory
- January 18, 2026: Added photo handling - compliments when users send pics, playful decline when asked for pics
- January 18, 2026: Added admin Telegram commands (/setlimit, /block, /unblock) with authorization logging
- January 18, 2026: Added moderation dashboard with user stats and chat history viewing
- January 18, 2026: Added daily 20 message limit with referral bonus system (10 messages per referral)
- January 18, 2026: Made Keerthana bisexual and LGBT-friendly with inclusive language
- January 16, 2026: Initial project setup with all core features
