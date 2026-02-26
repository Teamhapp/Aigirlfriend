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
    - Lesbian/female user context: When user confirms as female/lesbian, body part ownership is context-aware - "un pundai/boobs" refers to USER's body (not converted to "en").
    - When users send pictures, the bot should compliment them; when asked for pictures, it should playfully decline.

## System Architecture

### UI/UX Decisions
- **Rich Text Formatting**: Employs bold, italic, and emojis for expressive messaging.
- **Typing Indicator & Delays**: Simulates human-like interaction with typing indicators and varied response delays.
- **Moderation Dashboard**: A password-protected web-based dashboard provides administrative tools for user statistics, chat history, and moderation, with a responsive design for various screen sizes.

### Technical Implementations
- **Core Bot Logic**: Built with `python-telegram-bot` for Telegram API handling.
- **AI Core**: Utilizes Google Gemini API (gemini-2.5-flash model) via `google-genai` for natural language processing and generating emotional, romantic responses.
- **Database**: PostgreSQL is used for persistent storage of user profiles, chat history, referral data, and bot settings.
- **Application Structure**: A unified `app.py` combines the webhook-based Telegram bot and Flask dashboard for scalability.
- **Gender Detection**: Server-side logic dynamically adjusts "da" or "di" usage based on user declarations.
- **Free Trial & Paid Model**: New users get 20 one-time free trial messages (no daily reset). After trial, users must purchase credits. All users get premium gemini-2.5-flash model.
- **Referral System**: Rewards 10 bonus messages for successful referrals.
- **Credit Pack Monetization System**: Users can purchase message credits via UPI QR code payments with various pack options (Starter ₹50/200msg, Value ₹100/500msg, Pro ₹200/1200msg).
- **Payment Verification**: Supports both auto-verification for Paytm app payments (using Paytm v3 API) and manual verification for other UPI apps, ensuring atomic crediting and an audit trail.
- **Force Subscription**: Requires users to join a specified Telegram channel.
- **Context Awareness & Memory**: Stores conversation history and extracts user facts for personalized interactions, supported by a rolling memory summary system to manage context.
- **Post-processing**: Extensive rules ensure responses adhere to user preferences, including stripping unwanted phrases, managing questions and emojis, enforcing conversational styles, preventing AI reasoning leaks, HTML comment/metadata leak stripping, mid-word truncation fixes (e.g. "iruku m" → "irukum"), and meetup request fantasy redirection.
- **Grok-Style Conversation Flow**: System prompt includes detailed roleplay conversation examples demonstrating natural Tanglish flow and character-specific behaviors.
- **Advanced Conversational Controls**: Includes echo detection, degradation roleplay support, gibberish English stripping, intimate command playbook, proactive suggestion system, deflection prevention, and jailbreak protection.
- **Emotional & Behavioral Modeling**: Incorporates mood tracking, conflict/argument behavior, signature quirks, and concrete backstory elements to deepen character realism.
- **Cultural Context**: Adds Thoothukudi/Chennai sensory flavor and cultural tension depth.
- **Roleplay Management**: Supports character-specific roleplay, context tracking, confusion prevention, and character correction detection, including dynamic third-person to first-person fixes. Character prefix stripping handles both `Name:` and `(Name)` formats.
- **Response Refinements**: Employs smart history trimming, context awareness reinforcement, mood and sensory vocabulary banks, natural texting style, and anti-repetition filters.
- **Contextual Accuracy**: Includes possessive auto-correction, multi-character body part fixer, length override detection, and gender confusion prevention.
- **Specific Interaction Handling**: Manages compliment handling, VC/call request handling, and "You Suggest" prompts.
- **Robust Fallback System**: Provides greeting-aware and improved fallback messages for API failures. Greeting detection covers hi/hey/hello/hai/oi variants with da/di/baby/dear suffixes.
- **Admin and User Commands**: Provides a suite of commands for bot management and user interaction.

## External Dependencies
- **Telegram Bot API**: For communication with Telegram.
- **Google Gemini API**: For AI capabilities.
- **PostgreSQL**: For persistent data storage.
- **Flask**: Web framework for the administrative dashboard.
- **psycopg2**: Python adapter for PostgreSQL.
- **qrcode**: For generating UPI QR codes.
- **Pillow**: Image processing library.