# Keerthana AI — Telegram Girlfriend Bot

Telegram AI girlfriend bot powered by Google Gemini with Tanglish (Tamil+English) conversations, referral system, and UPI credit payments.

## Deploy

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/Teamhapp/Aigirlfriend)

Click the button above — Heroku will prompt you for all required config vars, provision a free PostgreSQL database, and deploy automatically.

### Required Config Vars

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `GEMINI_API_KEY` | From [aistudio.google.com](https://aistudio.google.com) |
| `HEROKU_APP_NAME` | Your Heroku app name (e.g. `my-app-name`) |
| `DASHBOARD_PASSWORD` | Password for the `/dashboard` admin panel |
| `SESSION_SECRET` | Any long random string (auto-generated) |

### Optional Config Vars

| Variable | Description |
|---|---|
| `GEMINI_API_KEY_1` … `_19` | Extra Gemini keys for rotation (more = higher rate limits) |
| `FORCE_SUB_CHANNEL` | Channel username users must join before chatting |
| `PAYTM_MERCHANT_ID/KEY` | For UPI auto-payment verification |
| `PAYTM_UPI_ID` | Your UPI ID for receiving credits |

---

## Auto-Deploy from GitHub

Every push to `main` auto-deploys to Heroku via GitHub Actions.

**Setup (one time):**

1. Go to your repo → **Settings → Secrets → Actions**
2. Add these secrets:

| Secret | Value |
|---|---|
| `HEROKU_API_KEY` | From Heroku → Account → API Key |
| `HEROKU_APP_NAME` | Your Heroku app name |
| `HEROKU_EMAIL` | Your Heroku account email |

After that, every `git push origin main` deploys automatically.

---

## Features

- Tanglish (Tamil + English) romantic conversation
- Google Gemini 2.5 Flash with 20-key rotation
- 20 free trial messages → paid credit packs (₹50/₹100/₹200)
- UPI payments with Paytm auto-verify + manual admin approval
- Referral system (10 bonus messages per referral)
- Admin dashboard with user stats, chat history, moderation
- Force-subscription channel gate
- PostgreSQL for persistent memory and chat history
