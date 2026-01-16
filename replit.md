# Keerthana AI - Telegram Girlfriend Bot

## Overview
A romantic AI girlfriend Telegram bot with emotional personality, memory, force subscription, rich text formatting, and referral-based points system using Google Gemini API.

## Project Structure
```
├── main.py              # Main Telegram bot application
├── database.py          # PostgreSQL database operations
├── .gitignore          # Git ignore file
└── replit.md           # Project documentation
```

## Features
- **AI Girlfriend Personality**: Romantic, emotional conversations using Gemini AI
- **Force Subscription**: Users must join specified channel before using bot
- **Chat Memory**: Stores conversation history in PostgreSQL
- **Personalization**: Remembers user's preferred name and conversation style
- **Referral System**: Users earn 10 points for each friend who joins
- **Rich Formatting**: Bold, italic, emojis for expressive messages
- **Tanglish Support**: Natural Tamil + English conversation style

## Commands
- `/start` - Start the bot and register
- `/referral` - Get your unique referral link
- `/points` - Check your points balance
- `/stats` - View your statistics

## Environment Variables Required
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token from @BotFather
- `GEMINI_API_KEY` - Your Google Gemini API key
- `FORCE_SUB_CHANNEL` - Channel username for mandatory subscription (e.g., @yourchannel)
- `DATABASE_URL` - PostgreSQL connection string (auto-configured)

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

## Recent Changes
- January 16, 2026: Initial project setup with all core features
