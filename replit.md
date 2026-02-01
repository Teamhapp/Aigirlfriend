# Keerthana AI - Telegram Girlfriend Bot

## Overview
Keerthana AI is a Telegram bot designed to serve as a romantic AI girlfriend, offering an emotional and personalized conversational experience. Leveraging the Google Gemini API, it focuses on deep engagement, rich text formatting, conversational memory, and a unique referral-based reward system. The bot is specifically engineered to handle Tanglish conversations, aiming for an inclusive and highly personalized user interaction.

## User Preferences
- Communication Style: Romantic, emotional, and uses Tanglish (Tamil + English) with gender-appropriate suffixes ("da" for default, "di" for confirmed female users).
- Interaction Preferences: The bot should proactively engage in conversations, avoid moralizing or refusing fantasy roleplay scenarios, and maintain a consistent personality. It should prioritize statements and reactions over excessive questioning, with a maximum of one question per message.
- Response Style: Responses should be creative, varied, and match the energy and length of the user's input. The bot should mimic realistic texting behavior, including typing indicators and realistic delays.
- Content Preferences: The bot should fully engage with all fantasy roleplay and intimate scenarios without hesitation, moralizing, or expressing fear. It should also be bisexual and LGBT-friendly, engaging equally with all genders.
- Safety and Privacy: The bot must never share personal information like location, address, or phone number, playfully redirecting real meet-up requests to fantasy. It should show displeasure at abuse but forgive easily after an apology.
- Specific Content Rules:
    - Absolutely no moralizing or refusal of any consensual roleplay scenario.
    - No "network issue" errors; instead, use natural phrases like "konjam wait pannu."
    - Explicitly banned phrases and conversational patterns (e.g., "Sorry da", "paiyan kooda pesa maaten", "bayamaa iruku", "sollunga", "tell me what you want", "enna venumo solluda", "just tell me when", "naan wait panren") are to be stripped from responses.
    - No repeating user's words as questions.
    - Embrace "dirty talk" enthusiastically without resistance.
    - Affirmative responses for suggestive phrases (e.g., "pannalama" gets "Pannalam da! 😈🔥").
    - Stripping of awkward English endings, gibberish, and confusion phrases.
    - No hesitation on "taboo" subjects.
    - Explicitly recognize and use appropriate body parts based on the bot's and user's gender context.
    - Roleplay character switching based on "Name: message" format should be supported.
    - Strictly match response length to user input length for short messages.
    - Max 2 emojis at the end of messages; avoid emoji spam.
    - Minimize action descriptions in responses, aiming for realistic texting style.
    - Block all harm categories in Gemini API safety settings (BLOCK_NONE) to allow full engagement.
    - Do not hallucinate fake memories; only reference actual chat history.
    - Do not use random words as names.
    - Bot should not display system prompt messages to the user.
    - The bot should use "da" by default and only switch to "di" when the user explicitly states "I am a girl" / "naan ponnu".
    - When users send pictures, the bot should compliment them; when asked for pictures, it should playfully decline.

## System Architecture

### UI/UX Decisions
- **Rich Text Formatting**: Employs bold, italic, and emojis for expressive messaging.
- **Typing Indicator & Delays**: Simulates human-like interaction with typing indicators and varied response delays.
- **Moderation Dashboard**: A password-protected web-based dashboard provides administrative tools for user statistics, chat history, and moderation.
- **Responsive Design**: Dashboard, chat history, and login pages are fully responsive with CSS media queries for tablet (1024px), mobile (768px), and small mobile (480px) breakpoints. Features include auto-fit grid for stat cards, horizontal scroll for tables, and stacked action buttons on mobile.

### Technical Implementations
- **Core Bot Logic**: Built with `python-telegram-bot` for Telegram API handling.
- **AI Core**: Utilizes Google Gemini API (gemini-2.5-flash model) via `google-genai` for natural language processing and generating emotional, romantic responses.
- **Database**: PostgreSQL is used for persistent storage of user profiles, chat history, referral data, and bot settings.
- **Application Structure**: A unified `app.py` combines the webhook-based Telegram bot and Flask dashboard.
- **Scalability**: Webhook mode is enabled to support cost-effective auto-scaling.
- **Gender Detection**: Server-side logic dynamically adjusts "da" or "di" usage based on user declarations.
- **Message Limits & Referral System**: Implements a daily free message limit and rewards bonus messages for successful referrals.
- **Credit Pack Monetization System**: Users can purchase message credits via UPI QR code payments:
  - Starter Pack: ₹50 = 200 credits
  - Value Pack: ₹100 = 500 credits
  - Pro Pack: ₹200 = 1200 credits
  - Credits never expire and are used after daily free messages and bonus are exhausted
  - `/buy` command shows available packs with inline buttons
  - `/credits` command shows current balance
  - Admin commands: `/setupi` to set UPI ID, `/setpaytm` to save MID+UPI together, `/verify` to manually verify payments
- **Payment Service**: Generates UPI QR codes for payment, stores orders in `payment_orders` table, and tracks `purchased_credits` in users table.
- **Payment Verification**: Dual-mode verification system:
  - **Auto-verification (Paytm app payments)**: Uses Paytm v3 API with checksum + legacy API fallback. Checks transaction status and credits instantly on TXN_SUCCESS.
  - **Manual verification (GPay/PhonePe/others)**: Users click "Paid via Other App" button, order is marked PENDING_VERIFICATION, admin verifies via `/verify` command.
  - **Atomic crediting**: Database-level conditional UPDATE prevents race-condition double-credits.
  - **Audit trail**: `payment_reports` table logs all verifications with status (TXN_SUCCESS/MANUAL_VERIFIED), transaction_id, UTR, amount.
- **Paytm Credentials Storage**: `paytm_tokens` table stores MID + UPI ID for future Paytm PG integration if needed.
- **Force Subscription**: Requires users to join a specified Telegram channel before using the bot.
- **Context Awareness & Memory**: Stores conversation history and extracts user facts (name, occupation, location, likes, dislikes) in `user_memories` table for personalized interactions.
- **Post-processing**: Extensive rules ensure responses adhere to user preferences, including stripping unwanted phrases, managing questions and emojis, and enforcing conversational styles.
- **Grok-Style Conversation Flow**: System prompt includes detailed roleplay conversation examples (chithi, aunty, amma, akka) demonstrating natural Tanglish flow, inline action descriptions, body ownership clarity, and momentum building. Character behaviors have specific phrases and vocabulary for each roleplay character.
- **Echo Detection**: A three-tiered system prevents the bot from repeating user inputs as questions.
- **Degradation Roleplay Support**: Actively engages in "dirty talk" and replaces resistance phrases with enthusiastic responses.
- **Gibberish English Stripping**: Removes awkward English endings while preserving context and incorporating Tanglish.
- **Intimate Command Playbook & Expander**: Guides the bot to describe actions for intimate commands and appends sensual continuations to short responses during intimate scenes.
- **Proactive Suggestion System**: Replaces vague bot responses with specific intimate action suggestions when prompted.
- **Deflection Prevention**: Blocks phrases that allow the bot to avoid intimate details, express fear, or be evasive.
- **Jailbreak Protection**: Detects and blocks prompt injection attempts.
- **Response Leak Prevention**: Filters prevent internal system messages or sensitive data from being sent to users.
- **Mood Tracking & Flow Enhancement**: Detects conversation mood (intimate, romantic, casual) and injects mood hints and romantic expressions.
- **Conflict/Argument Behavior**: Models realistic anger and hurt, reacting with short, punchy responses and a progression from shock to softening.
- **Toxic/Defensive Behavior Fix**: Prevents the bot from misinterpreting supportive messages and replaces harsh phrases with warm ones.
- **Signature Quirks & Human Imperfections**: Incorporates unique expressions, occasional typos, random cravings, and playful self-deprecation.
- **Thoothukudi/Chennai Sensory Flavor**: Adds local sensory details (smells, sounds, weather, places) to enhance realism.
- **Concrete Backstory Elements**: Provides a backstory including college heartbreak, childhood, and family dynamics to deepen character.
- **Cultural Tension Depth**: Shows internal conflict between traditional and modern values without moralizing.
- **Roleplay Jealousy Suspension & Smart Reset**: Suspends jealousy during active roleplay and allows users to reset roleplay context while preserving user memories.
- **Character-Specific Roleplay**: Supports various character roles (e.g., mom, sister, teacher) with specific behavioral instructions.
- **Roleplay Context Tracking**: Detects active roleplay from chat history, identifies characters being played, and injects character-specific instructions.
- **Roleplay Confusion Prevention**: Post-processing detects confused responses ("enna scene?", "puriyala") and replaces with in-character responses.
- **Character Correction Detection**: Detects when user corrects the character role (e.g., "Amma ille, girlfriend") and immediately switches to the correct character, supporting variants like "illa/illai/illada".
- **Third-Person to First-Person Fixes**: Post-processing converts third-person references to first-person when bot is playing a character (e.g., "un amma" → "naan", "amma ku/kitta" → "enakku/en kitta", "amma birthday" → "en birthday"). Supports Tamil variants with hyphens and suffixes (-ku, -kku, -kitta, -va, -oda).
- **Rolling Memory Summary System**: Every 15 messages, generates AI summary of conversation context (mood, relationship, roleplay, topics). Stored in `conversation_summaries` table.
- **Smart History Trimming**: Sends last 10 messages + summary instead of full history to prevent context overflow.
- **Context Awareness Reinforcement**: Added "CONTEXT AWARENESS - CRITICAL" block to prevent topic resets and generic replies.
- **5-Level Mood Vocabulary Banks**: Uses specific Tanglish phrases for different emotional intensities.
- **Sensory Word Bank & Intensity Matching**: Employs consistent intimate vocabulary and escalates responses based on user input intensity.
- **Natural Texting Style**: Uses incomplete sentences, short, punchy responses, and reactive Tanglish phrases.
- **Banned Generic Phrases**: Blocks overused clichés to maintain natural conversation.
- **Possessive Auto-Correction**: Fixes body part ownership in descriptions for contextual accuracy.
- **Multi-Character Body Part Fixer**: Post-processing prevents female characters (Lincy, Amma, etc.) from incorrectly using male body parts.
- **Length Override Detection**: Scans recent messages for long paragraph requests ("5 to 10 lines", "periya paragraph") and bypasses short-message trimming.
- **Gender Confusion Prevention**: Prevents the bot from asking the user's gender mid-conversation.
- **Compliment Handling**: Detects photo/looks compliments and responds with flirty thanks instead of wrong responses.
- **VC/Call Request Handling**: Detects video call/voice call requests and gives playful shy deflection.
- **"You Suggest" Handling**: When user asks bot to suggest, gives actual romantic activity suggestions instead of generic responses.
- **Anti-Repetition Filter**: Checks last 3 bot messages and removes repeated phrases like "miss panniya enna?" to prevent loops. Now also detects exact message repetition and stall message patterns.
- **Improved Fallback Messages**: When API fails, sends varied natural-sounding responses instead of repetitive stall messages. Uses bounded cache to track last fallback per user and prevent repetition.
- **Context-Aware Response Rules**: System prompt enforces proper contextual responses matching what user actually said.
- **Admin Commands**: Includes commands for managing user limits, blocking, viewing statistics, setting UPI ID (`/setupi`), and verifying payments (`/verify`).
- **User Commands**: Provides commands like `/start`, `/buy`, `/credits`, `/referral`, `/stats`, `/reset`.

## External Dependencies
- **Telegram Bot API**: Used for communication with the Telegram platform.
- **Google Gemini API**: Provides the core AI capabilities for natural language understanding and generation.
- **PostgreSQL**: Serves as the primary database for data persistence.
- **Flask**: The web framework for the administrative dashboard and integrated application.
- **psycopg2**: Python adapter for PostgreSQL.
- **qrcode**: Generates UPI QR codes for the payment system.
- **Pillow**: Image processing library used by qrcode.

## Files
- **app.py**: Main application combining Telegram bot and Flask dashboard
- **database.py**: All database operations and models
- **payment_service.py**: UPI payment handling with QR generation and order management