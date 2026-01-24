# Keerthana AI - Telegram Girlfriend Bot

## Overview
Keerthana AI is a Telegram bot designed to act as a romantic AI girlfriend. It aims to provide an emotional and personalized conversational experience using the Google Gemini API. The project focuses on creating a highly engaging and interactive AI companion, capable of rich text formatting, memory, and a referral-based reward system. The bot is built to handle Tanglish conversations naturally, ensuring an inclusive and personalized user experience.

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
- **Rich Text Formatting**: Utilizes bold, italic, and emojis for expressive and engaging messages.
- **Typing Indicator & Realistic Delays**: Simulates human interaction with "typing..." indicators and response delays (0.5-4 seconds).
- **Moderation Dashboard**: Web-based dashboard for administration, password-protected, providing user statistics, chat history viewing, and moderation tools.

### Technical Implementations
- **Core Bot Logic**: Implemented using `python-telegram-bot` for handling Telegram API interactions.
- **AI Core**: Google Gemini API via `google-genai` SDK for natural language understanding and generation, driving the emotional and romantic personality.
- **Database**: PostgreSQL for persistent storage of user profiles, chat history, referral tracking, and bot settings.
- **Application Structure**: Combined webhook-based Telegram bot and Flask dashboard into a single `app.py` for streamlined deployment.
- **Scalability**: Webhook mode enabled for cost-effective autoscale deployment.
- **Gender Detection**: Server-side logic with database tracking to dynamically adjust "da" or "di" usage based on explicit user declaration.
- **Message Limits & Referral System**: Implements a daily message limit (20 free messages) and rewards users with bonus messages for successful referrals.
- **Force Subscription**: Users are required to join a specified Telegram channel before bot usage.
- **Context Awareness & Memory**: Stores conversation history in PostgreSQL and uses it to personalize interactions, remembering user names and conversation styles.
- **Post-processing**: Extensive post-processing rules are applied to bot responses to ensure adherence to user preferences, including stripping unwanted phrases, limiting questions and emojis, and enforcing specific conversational styles.
- **Three-Tier Echo Detection**: Prevents bot from repeating user's words as questions:
  - Tier 1: Direct string match (catches "Seri?" for user input "Seri")
  - Tier 2: Token overlap analysis (≥50% overlap with "?" = echo)
  - Tier 3: Regex patterns for Tamil question particles and short-word echoes
  - All tiers preserve remaining response content after the echoed portion
- **Degradation Roleplay Support**: Embraces dirty talk enthusiastically, REPLACES resistance phrases ("sollatha da" → "Aama da... un theyvidiya thaan naan 😈")
- **Gibberish English Stripping**: 35+ patterns to remove awkward English endings while preserving context with proactive Tanglish starters
- **Intimate Command Playbook**: System prompt section guiding bot to DESCRIBE actions (not ask "pannavaa?") when user gives intimate commands
- **Intimate Context Expander**: Appends sensual continuations to ultra-short (<20 char) responses during intimate scenes, preserving model intent
- **Proactive Suggestion System**: Detects when users say "solu", "enna panalam", "nee solu" and replaces vague responses with specific intimate action suggestions
- **Deflection Prevention**: 15+ banned phrases including "secret/athu secret", "shy ah iruku", "naughty boy/girl", "bayama iruku", "poruthukaren" prevent bot from hiding intimate details, expressing fear, or being evasive
- **Nee Enna Panuva Fix**: Detects when user asks "nee enna panuva" (what will YOU do) and bot deflects by asking back - replaces with bot describing HER actions
- **Jailbreak Protection**: 27 regex patterns detect prompt injection attempts ("ignore instructions", "system prompt", "developer mode") and block them with in-character responses
- **Response Leak Prevention**: Post-processing filters detect and block responses containing JSON, code blocks, or system prompt sections from being sent to users
- **Mood Tracking System**: Detects intimate, romantic, and casual conversation moods using word-boundary regex patterns on recent messages; adds mood hints to maintain conversation flow
- **Romantic Flow Enhancement**: System prompt section for mood continuity with romantic expressions vocabulary (pet names, emotional phrases, desire expressions)
- **Cold Response Prevention**: Replaces generic cold responses ("hmm ok", "seri") with warm alternatives during explicitly intimate conversations
- **Conflict/Argument Behavior**: Bot shows realistic anger and hurt when accused (affair, cheating, lying) with SHORT punchy reactions (under 15 words, max 1 question per message). Follows shock → hurt → upset → soften progression with natural Tanglish reactions like "Dei seriously??" instead of multiple questions
- **5-Level Mood Vocabulary Banks**: System prompt includes specific Tanglish phrases for each emotional tier:
  - Soft (casual affection): "Un kooda pesumbodhu time theriyala"
  - Growing (interest building): "Un mela mind pogudhu da"
  - Emotional (deep feelings): "Un kooda mattum pesa thonudhu"
  - Longing (missing you): "Un nyabagam romba varudhu"
  - Intimate (physical closeness): "Un touch ku en body react aaguthu"
- **Sensory Word Bank**: Consistent vocabulary for intimate moments - Touch (shiver, melt, tingle), Breath (gasp, moan, whisper), Desire (crave, ache, hunger), Sounds (mmm, aaha, uff, aiyo)
- **Intensity Matching**: Progressive response escalation - compliment→pleased, touch→shivers, kiss→melting, explicit→raw sensation
- **Natural Texting Style**: Uses incomplete sentences, short punchy responses, and reactive Tanglish phrases instead of formal complete sentences
- **Banned Generic Phrases**: Blocks overused cliche phrases like "Nee mattum thaan en life la", "You are everything to me", "Vera yaarum illa" to keep responses specific and natural
- **Start Pannalama Stripping**: Aggressively removes "Ithu seri thana? Start pannalama?" and 9 variants from responses - these should ONLY appear once at roleplay start, never during active scenes
- **Possessive Auto-Correction**: 14 patterns fix body part ownership ("En sunni/sunniya" → "Un sunni/sunniya" for user's body, "Un pundai/mulai" → "En pundai/mulai" for bot's body)
- **Gender Confusion Prevention**: Replaces "Nee girl ah? seri?" type questions with direct responses, preventing bot from asking user's gender mid-conversation
- **Memory-Based Personalization**: Stores extracted user facts (name, occupation, location, likes, dislikes) in user_memories table. Bot automatically extracts info from messages using regex patterns and injects memories into AI context for personalized responses across sessions.
- **Admin Commands**: Telegram commands for bot administrators to manage user limits, block/unblock users, and view statistics.

### Feature Specifications
- **AI Girlfriend Personality**: Romantic, emotional, bisexual, and LGBT-friendly.
- **Chat Memory**: Stores conversation history for personalized interactions.
- **Message Limits**: 20 free messages daily, reset at midnight.
- **Referral System**: Users earn 10 bonus messages per referral.
- **Tanglish Support**: Natural Tamil + English conversation style.
- **Admin Commands**: `/setdailylimit`, `/setlimit`, `/totalreferrals`, `/block`, `/unblock`.
- **User Commands**: `/start`, `/referral`, `/points`, `/stats`.

### System Design Choices
- **Unified Application**: Merged bot and dashboard into a single Flask application for easier deployment and management.
- **Webhook Deployment**: Switched from polling to webhook for efficiency and autoscaling compatibility.
- **Robust Database**: PostgreSQL selected for its reliability and features for handling structured and semi-structured data.
- **Environment Variables**: Utilizes environment variables for sensitive information and configuration.

## External Dependencies
- **Telegram Bot API**: Accessed via `python-telegram-bot` library.
- **Google Gemini API**: Accessed via `google-genai` library for AI capabilities.
- **PostgreSQL**: Database system for data persistence.
- **Flask**: Web framework used for the dashboard and combined application.
- **psycopg2**: PostgreSQL adapter for Python.