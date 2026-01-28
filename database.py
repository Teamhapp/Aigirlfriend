import os
import psycopg2
from datetime import datetime, date
import logging
import time
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    """Create a fresh database connection for each request (best for autoscale)"""
    return psycopg2.connect(DATABASE_URL)

def release_connection(conn):
    """Close the connection when done"""
    try:
        if conn and not conn.closed:
            conn.close()
    except Exception:
        pass

def with_db_retry(max_retries=3):
    """Decorator to retry database operations on connection errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                conn = None
                try:
                    conn = get_connection()
                    return func(conn, *args, **kwargs)
                except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                    last_error = e
                    logger.warning(f"DB connection error (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                except Exception as e:
                    raise
                finally:
                    if conn:
                        release_connection(conn)
            raise last_error
        return wrapper
    return decorator

def init_database():
    conn = get_connection()
    try:
        cur = conn.cursor()
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                preferred_name VARCHAR(255),
                points INTEGER DEFAULT 0,
                referral_count INTEGER DEFAULT 0,
                referred_by BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_blocked BOOLEAN DEFAULT FALSE,
                custom_daily_limit INTEGER DEFAULT NULL,
                daily_messages_used INTEGER DEFAULT 0,
                bonus_messages INTEGER DEFAULT 0,
                last_reset_date DATE DEFAULT CURRENT_DATE
            )
        ''')
        
        try:
            cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_messages_used INTEGER DEFAULT 0')
            cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS bonus_messages INTEGER DEFAULT 0')
            cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS last_reset_date DATE DEFAULT CURRENT_DATE')
            cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE')
            cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_daily_limit INTEGER DEFAULT NULL')
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS confirmed_gender VARCHAR(20) DEFAULT NULL")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS suffix_preference VARCHAR(10) DEFAULT 'da'")
        except Exception:
            pass
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                role VARCHAR(20),
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT REFERENCES users(user_id),
                referred_id BIGINT REFERENCES users(user_id),
                points_awarded INTEGER DEFAULT 10,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(referred_id)
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS points_transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                amount INTEGER,
                transaction_type VARCHAR(50),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cur.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cur.execute('''
            INSERT INTO bot_settings (key, value) 
            VALUES ('global_daily_limit', '20')
            ON CONFLICT (key) DO NOTHING
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS user_memories (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                memory_type VARCHAR(50),
                memory_key VARCHAR(100),
                memory_value TEXT,
                confidence FLOAT DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, memory_type, memory_key)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_user_memories_user_id ON user_memories(user_id)')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                summary TEXT,
                mood VARCHAR(50),
                relationship_level VARCHAR(50),
                active_roleplay VARCHAR(100),
                last_topic TEXT,
                message_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_conversation_summaries_user_id ON conversation_summaries(user_id)')
        
        try:
            cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS purchased_credits INTEGER DEFAULT 0')
        except Exception:
            pass
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS payment_orders (
                id SERIAL PRIMARY KEY,
                order_id VARCHAR(20) UNIQUE NOT NULL,
                user_id BIGINT REFERENCES users(user_id),
                txn_ref VARCHAR(20),
                pack_id VARCHAR(20),
                amount_paise INTEGER,
                credits INTEGER,
                status VARCHAR(30) DEFAULT 'PENDING',
                verified_by BIGINT,
                paytm_txn_id VARCHAR(50),
                utr VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_payment_orders_user_id ON payment_orders(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_payment_orders_status ON payment_orders(status)')
        
        try:
            cur.execute('ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS paytm_txn_id VARCHAR(50)')
            cur.execute('ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS utr VARCHAR(50)')
        except Exception:
            pass
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS paytm_tokens (
                id SERIAL PRIMARY KEY,
                mid VARCHAR(50) NOT NULL,
                upi_id VARCHAR(100) NOT NULL,
                merchant_key VARCHAR(100),
                status VARCHAR(20) DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        release_connection(conn)

@with_db_retry()
def get_or_create_user(conn, user_id, username=None, first_name=None, referred_by=None):
    try:
        cur = conn.cursor()
        
        cur.execute('SELECT user_id, preferred_name, points, referral_count FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        
        if user:
            cur.execute('''
                UPDATE users SET last_active = %s, username = COALESCE(%s, username), 
                first_name = COALESCE(%s, first_name) WHERE user_id = %s
            ''', (datetime.now(), username, first_name, user_id))
            conn.commit()
            result = {'user_id': user[0], 'preferred_name': user[1], 'points': user[2], 'referral_count': user[3], 'is_new': False}
        else:
            cur.execute('''
                INSERT INTO users (user_id, username, first_name, referred_by)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id, preferred_name, points, referral_count
            ''', (user_id, username, first_name, referred_by))
            new_user = cur.fetchone()
            conn.commit()
            result = {'user_id': new_user[0], 'preferred_name': new_user[1], 'points': new_user[2], 'referral_count': new_user[3], 'is_new': True, 'referred_by': referred_by}
        
        cur.close()
        return result
    except Exception as e:
        logger.error(f"Error in get_or_create_user: {e}")
        conn.rollback()
        raise

@with_db_retry()
def clear_chat_history(conn, user_id):
    """Clear all chat history for a user to restart roleplay fresh"""
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM chat_messages WHERE user_id = %s', (user_id,))
        conn.commit()
        cur.close()
        logger.info(f"Cleared chat history for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        conn.rollback()
        return False

@with_db_retry()
def get_confirmed_gender(conn, user_id):
    cur = conn.cursor()
    cur.execute('SELECT confirmed_gender FROM users WHERE user_id = %s', (user_id,))
    result = cur.fetchone()
    cur.close()
    return result[0] if result else None

@with_db_retry()
def set_confirmed_gender(conn, user_id, gender):
    try:
        cur = conn.cursor()
        cur.execute('UPDATE users SET confirmed_gender = %s WHERE user_id = %s', (gender, user_id))
        conn.commit()
        cur.close()
        logger.info(f"Set confirmed gender for user {user_id} to {gender}")
        return True
    except Exception as e:
        logger.error(f"Error setting gender: {e}")
        conn.rollback()
        return False

@with_db_retry()
def get_suffix_preference(conn, user_id):
    cur = conn.cursor()
    cur.execute('SELECT suffix_preference FROM users WHERE user_id = %s', (user_id,))
    result = cur.fetchone()
    cur.close()
    return result[0] if result else 'da'

@with_db_retry()
def set_suffix_preference(conn, user_id, suffix):
    try:
        cur = conn.cursor()
        cur.execute('UPDATE users SET suffix_preference = %s WHERE user_id = %s', (suffix, user_id))
        conn.commit()
        cur.close()
        logger.info(f"Set suffix preference for user {user_id} to {suffix}")
        return True
    except Exception as e:
        logger.error(f"Error setting suffix preference: {e}")
        conn.rollback()
        return False

@with_db_retry()
def award_referral_points(conn, referrer_id, referred_id):
    try:
        cur = conn.cursor()
        
        cur.execute('SELECT id FROM referrals WHERE referred_id = %s', (referred_id,))
        if cur.fetchone():
            cur.close()
            return False
        
        cur.execute('''
            INSERT INTO referrals (referrer_id, referred_id, points_awarded)
            VALUES (%s, %s, 10)
        ''', (referrer_id, referred_id))
        
        cur.execute('''
            UPDATE users SET points = points + 10, referral_count = referral_count + 1, bonus_messages = bonus_messages + 10
            WHERE user_id = %s
        ''', (referrer_id,))
        
        cur.execute('''
            INSERT INTO points_transactions (user_id, amount, transaction_type, description)
            VALUES (%s, 10, 'referral', %s)
        ''', (referrer_id, f'Referral bonus for inviting user {referred_id}'))
        
        conn.commit()
        cur.close()
        logger.info(f"Awarded 10 points and 10 bonus messages to user {referrer_id} for referral")
        return True
    except Exception as e:
        logger.error(f"Error awarding referral points: {e}")
        conn.rollback()
        return False

DEFAULT_DAILY_MESSAGE_LIMIT = 20

def get_global_daily_limit():
    """Get the global daily message limit from settings"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM bot_settings WHERE key = 'global_daily_limit'")
        result = cur.fetchone()
        cur.close()
        if result:
            return int(result[0])
        return DEFAULT_DAILY_MESSAGE_LIMIT
    except Exception as e:
        logger.warning(f"Error getting global daily limit: {e}")
        return DEFAULT_DAILY_MESSAGE_LIMIT
    finally:
        if conn:
            release_connection(conn)

DAILY_MESSAGE_LIMIT = get_global_daily_limit()

@with_db_retry()
def set_global_daily_limit(conn, new_limit):
    """Set the global daily message limit for all users"""
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO bot_settings (key, value, updated_at) 
            VALUES ('global_daily_limit', %s, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP
        ''', (str(new_limit), str(new_limit)))
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        logger.error(f"Error setting global daily limit: {e}")
        conn.rollback()
        return False

def _get_global_limit_from_conn(conn):
    """Get global daily limit using existing connection"""
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM bot_settings WHERE key = 'global_daily_limit'")
        result = cur.fetchone()
        cur.close()
        if result:
            return int(result[0])
    except Exception:
        pass
    return DEFAULT_DAILY_MESSAGE_LIMIT

@with_db_retry()
def get_bot_setting(conn, key):
    """Get a bot setting value by key"""
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM bot_settings WHERE key = %s", (key,))
        result = cur.fetchone()
        cur.close()
        if result:
            return result[0]
    except Exception:
        pass
    return None

@with_db_retry()
def set_bot_setting(conn, key, value):
    """Set a bot setting value"""
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO bot_settings (key, value, updated_at) 
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP
        ''', (key, value, value))
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        logger.error(f"Error setting bot setting: {e}")
        conn.rollback()
        return False

@with_db_retry()
def get_message_status(conn, user_id):
    global_limit = _get_global_limit_from_conn(conn)
    cur = conn.cursor()
    cur.execute('''
        SELECT daily_messages_used, bonus_messages, last_reset_date, custom_daily_limit, COALESCE(purchased_credits, 0)
        FROM users WHERE user_id = %s
    ''', (user_id,))
    result = cur.fetchone()
    cur.close()
    
    if not result:
        return {'daily_used': 0, 'daily_remaining': global_limit, 'bonus': 0, 'purchased': 0, 'total_remaining': global_limit}
    
    daily_used, bonus, last_reset, custom_limit, purchased = result[0] or 0, result[1] or 0, result[2], result[3], result[4] or 0
    user_limit = custom_limit if custom_limit else global_limit
    today = date.today()
    
    if last_reset is None or last_reset < today:
        daily_used = 0
    
    daily_remaining = max(0, user_limit - daily_used)
    total_remaining = daily_remaining + bonus + purchased
    
    return {
        'daily_used': daily_used,
        'daily_remaining': daily_remaining,
        'bonus': bonus,
        'purchased': purchased,
        'total_remaining': total_remaining,
        'daily_limit': user_limit
    }

@with_db_retry()
def use_message(conn, user_id):
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT daily_messages_used, bonus_messages, last_reset_date, custom_daily_limit, COALESCE(purchased_credits, 0)
            FROM users WHERE user_id = %s
        ''', (user_id,))
        result = cur.fetchone()
        
        if not result:
            cur.close()
            return False, 0
        
        daily_used, bonus, last_reset, custom_limit, purchased = result[0] or 0, result[1] or 0, result[2], result[3], result[4] or 0
        global_limit = _get_global_limit_from_conn(conn)
        user_limit = custom_limit if custom_limit else global_limit
        today = date.today()
        
        if last_reset is None or last_reset < today:
            cur.execute('''
                UPDATE users SET daily_messages_used = 1, last_reset_date = %s
                WHERE user_id = %s
            ''', (today, user_id))
            conn.commit()
            cur.close()
            remaining = user_limit - 1 + bonus + purchased
            return True, remaining
        
        daily_remaining = user_limit - daily_used
        
        if daily_remaining > 0:
            cur.execute('''
                UPDATE users SET daily_messages_used = daily_messages_used + 1
                WHERE user_id = %s
            ''', (user_id,))
            conn.commit()
            cur.close()
            remaining = daily_remaining - 1 + bonus + purchased
            return True, remaining
        elif bonus > 0:
            cur.execute('''
                UPDATE users SET bonus_messages = bonus_messages - 1
                WHERE user_id = %s
            ''', (user_id,))
            conn.commit()
            cur.close()
            remaining = bonus - 1 + purchased
            return True, remaining
        elif purchased > 0:
            cur.execute('''
                UPDATE users SET purchased_credits = purchased_credits - 1
                WHERE user_id = %s
            ''', (user_id,))
            conn.commit()
            cur.close()
            remaining = purchased - 1
            logger.info(f"[CREDITS] User {user_id} used 1 purchased credit, {purchased - 1} remaining")
            return True, remaining
        else:
            cur.close()
            return False, 0
    except Exception as e:
        logger.error(f"Error using message: {e}")
        conn.rollback()
        return False, 0

@with_db_retry()
def get_user_points(conn, user_id):
    cur = conn.cursor()
    cur.execute('SELECT points, referral_count FROM users WHERE user_id = %s', (user_id,))
    result = cur.fetchone()
    cur.close()
    return {'points': result[0], 'referral_count': result[1]} if result else {'points': 0, 'referral_count': 0}

@with_db_retry()
def update_preferred_name(conn, user_id, name):
    try:
        cur = conn.cursor()
        cur.execute('UPDATE users SET preferred_name = %s WHERE user_id = %s', (name, user_id))
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        logger.error(f"Error updating preferred name: {e}")
        conn.rollback()
        return False

@with_db_retry()
def save_message(conn, user_id, role, content):
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO chat_messages (user_id, role, content)
            VALUES (%s, %s, %s)
        ''', (user_id, role, content))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error saving message: {e}")
        conn.rollback()

@with_db_retry()
def get_chat_history(conn, user_id, limit=20):
    cur = conn.cursor()
    cur.execute('''
        SELECT role, content FROM chat_messages
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    ''', (user_id, limit))
    messages = cur.fetchall()
    cur.close()
    return [{'role': msg[0], 'content': msg[1]} for msg in reversed(messages)]

@with_db_retry()
def get_message_count(conn, user_id):
    """Get total message count for a user"""
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM chat_messages WHERE user_id = %s', (user_id,))
    count = cur.fetchone()[0]
    cur.close()
    return count

@with_db_retry()
def save_conversation_summary(conn, user_id, summary, mood=None, relationship_level=None, active_roleplay=None, last_topic=None, message_count=0):
    """Save or update conversation summary for a user"""
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO conversation_summaries (user_id, summary, mood, relationship_level, active_roleplay, last_topic, message_count, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                summary = EXCLUDED.summary,
                mood = COALESCE(EXCLUDED.mood, conversation_summaries.mood),
                relationship_level = COALESCE(EXCLUDED.relationship_level, conversation_summaries.relationship_level),
                active_roleplay = EXCLUDED.active_roleplay,
                last_topic = EXCLUDED.last_topic,
                message_count = EXCLUDED.message_count,
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, summary, mood, relationship_level, active_roleplay, last_topic, message_count))
        conn.commit()
        cur.close()
        logger.info(f"Saved conversation summary for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving conversation summary: {e}")
        conn.rollback()

@with_db_retry()
def get_conversation_summary(conn, user_id):
    """Get conversation summary for a user"""
    cur = conn.cursor()
    cur.execute('''
        SELECT summary, mood, relationship_level, active_roleplay, last_topic, message_count, updated_at
        FROM conversation_summaries WHERE user_id = %s
    ''', (user_id,))
    result = cur.fetchone()
    cur.close()
    if result:
        return {
            'summary': result[0],
            'mood': result[1],
            'relationship_level': result[2],
            'active_roleplay': result[3],
            'last_topic': result[4],
            'message_count': result[5],
            'updated_at': result[6]
        }
    return None

@with_db_retry()
def clear_conversation_summary(conn, user_id):
    """Clear conversation summary for a user (on reset)"""
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM conversation_summaries WHERE user_id = %s', (user_id,))
        conn.commit()
        cur.close()
        logger.info(f"Cleared conversation summary for user {user_id}")
    except Exception as e:
        logger.error(f"Error clearing conversation summary: {e}")
        conn.rollback()

@with_db_retry()
def get_user_stats(conn, user_id):
    cur = conn.cursor()
    cur.execute('''
        SELECT u.points, u.referral_count, u.preferred_name, u.created_at,
               (SELECT COUNT(*) FROM chat_messages WHERE user_id = %s) as message_count
        FROM users u WHERE u.user_id = %s
    ''', (user_id, user_id))
    result = cur.fetchone()
    cur.close()
    if result:
        return {
            'points': result[0],
            'referral_count': result[1],
            'preferred_name': result[2],
            'member_since': result[3],
            'message_count': result[4]
        }
    return None

@with_db_retry()
def get_all_users(conn):
    cur = conn.cursor()
    cur.execute('''
        SELECT u.user_id, u.username, u.first_name, u.preferred_name, 
               u.daily_messages_used, u.bonus_messages, u.referral_count,
               u.created_at, u.last_active, u.is_blocked, u.custom_daily_limit,
               (SELECT COUNT(*) FROM chat_messages WHERE user_id = u.user_id) as message_count
        FROM users u
        ORDER BY u.last_active DESC
    ''')
    users = cur.fetchall()
    cur.close()
    return [{
        'user_id': u[0],
        'username': u[1],
        'first_name': u[2],
        'preferred_name': u[3],
        'daily_messages_used': u[4] or 0,
        'bonus_messages': u[5] or 0,
        'referral_count': u[6] or 0,
        'created_at': u[7],
        'last_active': u[8],
        'is_blocked': u[9] or False,
        'custom_daily_limit': u[10],
        'message_count': u[11]
    } for u in users]

@with_db_retry()
def get_user_chat_history(conn, user_id, limit=100):
    cur = conn.cursor()
    cur.execute('''
        SELECT role, content, created_at FROM chat_messages
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    ''', (user_id, limit))
    messages = cur.fetchall()
    cur.close()
    return [{'role': m[0], 'content': m[1], 'created_at': m[2]} for m in reversed(messages)]

@with_db_retry()
def get_dashboard_stats(conn):
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM users')
    total_users = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM chat_messages')
    total_messages = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE last_active > NOW() - INTERVAL '24 hours'")
    active_today = cur.fetchone()[0]
    cur.close()
    return {
        'total_users': total_users,
        'total_messages': total_messages,
        'active_today': active_today
    }

@with_db_retry()
def is_user_blocked(conn, user_id):
    cur = conn.cursor()
    cur.execute('SELECT is_blocked FROM users WHERE user_id = %s', (user_id,))
    result = cur.fetchone()
    cur.close()
    return result[0] if result else False

@with_db_retry()
def block_user(conn, user_id):
    try:
        cur = conn.cursor()
        cur.execute('UPDATE users SET is_blocked = TRUE WHERE user_id = %s', (user_id,))
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        conn.rollback()
        return False

@with_db_retry()
def unblock_user(conn, user_id):
    try:
        cur = conn.cursor()
        cur.execute('UPDATE users SET is_blocked = FALSE WHERE user_id = %s', (user_id,))
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        logger.error(f"Error unblocking user: {e}")
        conn.rollback()
        return False

@with_db_retry()
def set_user_daily_limit(conn, user_id, limit):
    try:
        cur = conn.cursor()
        if limit is None or limit == 0:
            cur.execute('UPDATE users SET custom_daily_limit = NULL WHERE user_id = %s', (user_id,))
        else:
            cur.execute('UPDATE users SET custom_daily_limit = %s WHERE user_id = %s', (limit, user_id))
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        logger.error(f"Error setting user daily limit: {e}")
        conn.rollback()
        return False

@with_db_retry()
def get_user_daily_limit(conn, user_id):
    cur = conn.cursor()
    cur.execute('SELECT custom_daily_limit FROM users WHERE user_id = %s', (user_id,))
    result = cur.fetchone()
    cur.close()
    if result and result[0]:
        return result[0]
    return _get_global_limit_from_conn(conn)

@with_db_retry()
def get_total_referral_stats(conn):
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM referrals')
    total_referrals = cur.fetchone()[0]
    cur.execute('SELECT SUM(referral_count) FROM users')
    total_from_users = cur.fetchone()[0] or 0
    cur.execute('''
        SELECT u.user_id, u.preferred_name, u.username, u.referral_count 
        FROM users u 
        WHERE u.referral_count > 0 
        ORDER BY u.referral_count DESC 
        LIMIT 10
    ''')
    top_referrers = cur.fetchall()
    cur.close()
    return {
        'total_referrals': total_referrals,
        'total_from_users': total_from_users,
        'top_referrers': [
            {'user_id': r[0], 'name': r[1] or r[2] or str(r[0]), 'count': r[3]} 
            for r in top_referrers
        ]
    }

@with_db_retry()
def save_user_memory(conn, user_id, memory_type, memory_key, memory_value, confidence=1.0):
    """Save or update a memory for a user"""
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO user_memories (user_id, memory_type, memory_key, memory_value, confidence, updated_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, memory_type, memory_key) 
            DO UPDATE SET memory_value = %s, confidence = %s, updated_at = CURRENT_TIMESTAMP
        ''', (user_id, memory_type, memory_key, memory_value, confidence, memory_value, confidence))
        conn.commit()
        cur.close()
        logger.info(f"Saved memory for user {user_id}: {memory_type}/{memory_key}")
        return True
    except Exception as e:
        logger.error(f"Error saving memory: {e}")
        conn.rollback()
        return False

@with_db_retry()
def get_user_memories(conn, user_id, memory_type=None, limit=50):
    """Get all memories for a user, optionally filtered by type"""
    cur = conn.cursor()
    if memory_type:
        cur.execute('''
            SELECT memory_type, memory_key, memory_value, confidence, updated_at
            FROM user_memories WHERE user_id = %s AND memory_type = %s
            ORDER BY updated_at DESC LIMIT %s
        ''', (user_id, memory_type, limit))
    else:
        cur.execute('''
            SELECT memory_type, memory_key, memory_value, confidence, updated_at
            FROM user_memories WHERE user_id = %s
            ORDER BY updated_at DESC LIMIT %s
        ''', (user_id, limit))
    memories = cur.fetchall()
    cur.close()
    return [
        {'type': m[0], 'key': m[1], 'value': m[2], 'confidence': m[3], 'updated_at': m[4]}
        for m in memories
    ]

@with_db_retry()
def delete_user_memory(conn, user_id, memory_type, memory_key):
    """Delete a specific memory"""
    try:
        cur = conn.cursor()
        cur.execute('''
            DELETE FROM user_memories 
            WHERE user_id = %s AND memory_type = %s AND memory_key = %s
        ''', (user_id, memory_type, memory_key))
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        conn.rollback()
        return False

@with_db_retry()
def create_payment_order(conn, user_id, order_id, txn_ref, pack_id, amount_paise, credits):
    """Create a new payment order"""
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO payment_orders (order_id, user_id, txn_ref, pack_id, amount_paise, credits, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'PENDING')
        ''', (order_id, user_id, txn_ref, pack_id, amount_paise, credits))
        conn.commit()
        cur.close()
        logger.info(f"Created payment order {order_id} for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error creating payment order: {e}")
        conn.rollback()
        return False

@with_db_retry()
def get_payment_order(conn, order_id):
    """Get payment order by order_id"""
    cur = conn.cursor()
    cur.execute('''
        SELECT order_id, user_id, txn_ref, pack_id, amount_paise, credits, status, verified_by, created_at, updated_at
        FROM payment_orders WHERE order_id = %s
    ''', (order_id,))
    order = cur.fetchone()
    cur.close()
    if order:
        return {
            'order_id': order[0],
            'user_id': order[1],
            'txn_ref': order[2],
            'pack_id': order[3],
            'amount_paise': order[4],
            'credits': order[5],
            'status': order[6],
            'verified_by': order[7],
            'created_at': order[8],
            'updated_at': order[9]
        }
    return None

@with_db_retry()
def update_payment_order_status(conn, order_id, status, verified_by=None):
    """Update payment order status"""
    try:
        cur = conn.cursor()
        if verified_by:
            cur.execute('''
                UPDATE payment_orders 
                SET status = %s, verified_by = %s, updated_at = CURRENT_TIMESTAMP
                WHERE order_id = %s
            ''', (status, verified_by, order_id))
        else:
            cur.execute('''
                UPDATE payment_orders 
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE order_id = %s
            ''', (status, order_id))
        conn.commit()
        cur.close()
        logger.info(f"Updated order {order_id} status to {status}")
        return True
    except Exception as e:
        logger.error(f"Error updating payment order: {e}")
        conn.rollback()
        return False

@with_db_retry()
def add_purchased_credits(conn, user_id, credits):
    """Add purchased credits to user account"""
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE users 
            SET purchased_credits = COALESCE(purchased_credits, 0) + %s
            WHERE user_id = %s
        ''', (credits, user_id))
        conn.commit()
        cur.close()
        logger.info(f"Added {credits} purchased credits to user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error adding purchased credits: {e}")
        conn.rollback()
        return False

@with_db_retry()
def get_purchased_credits(conn, user_id):
    """Get user's purchased credits balance"""
    cur = conn.cursor()
    cur.execute('SELECT COALESCE(purchased_credits, 0) FROM users WHERE user_id = %s', (user_id,))
    result = cur.fetchone()
    cur.close()
    return result[0] if result else 0

@with_db_retry()
def use_purchased_credit(conn, user_id):
    """Deduct one purchased credit from user, returns True if deducted"""
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE users 
            SET purchased_credits = purchased_credits - 1
            WHERE user_id = %s AND purchased_credits > 0
            RETURNING purchased_credits
        ''', (user_id,))
        result = cur.fetchone()
        conn.commit()
        cur.close()
        return result is not None
    except Exception as e:
        logger.error(f"Error using purchased credit: {e}")
        conn.rollback()
        return False

@with_db_retry()
def get_pending_payment_orders(conn):
    """Get all pending payment orders for admin verification"""
    cur = conn.cursor()
    cur.execute('''
        SELECT po.order_id, po.user_id, u.username, u.first_name, 
               po.pack_id, po.amount_paise, po.credits, po.status, po.created_at
        FROM payment_orders po
        JOIN users u ON po.user_id = u.user_id
        WHERE po.status IN ('PENDING', 'PENDING_VERIFICATION')
        ORDER BY po.created_at DESC
    ''')
    orders = cur.fetchall()
    cur.close()
    return [{
        'order_id': o[0],
        'user_id': o[1],
        'username': o[2],
        'first_name': o[3],
        'pack_id': o[4],
        'amount_paise': o[5],
        'credits': o[6],
        'status': o[7],
        'created_at': o[8]
    } for o in orders]

@with_db_retry()
def expire_old_payment_orders(conn):
    """Expire orders older than 30 minutes"""
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE payment_orders 
            SET status = 'EXPIRED', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'PENDING' 
            AND created_at < NOW() - INTERVAL '30 minutes'
        ''')
        affected = cur.rowcount
        conn.commit()
        cur.close()
        if affected > 0:
            logger.info(f"Expired {affected} old payment orders")
        return affected
    except Exception as e:
        logger.error(f"Error expiring orders: {e}")
        conn.rollback()
        return 0

@with_db_retry()
def get_user_payment_orders(conn, user_id, limit=10):
    """Get user's recent payment orders"""
    cur = conn.cursor()
    cur.execute('''
        SELECT order_id, pack_id, amount_paise, credits, status, created_at
        FROM payment_orders 
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    ''', (user_id, limit))
    orders = cur.fetchall()
    cur.close()
    return [{
        'order_id': o[0],
        'pack_id': o[1],
        'amount_paise': o[2],
        'credits': o[3],
        'status': o[4],
        'created_at': o[5]
    } for o in orders]

@with_db_retry()
def save_paytm_credentials(conn, mid, upi_id, merchant_key=None):
    """Save or update Paytm merchant credentials"""
    try:
        cur = conn.cursor()
        cur.execute('SELECT id FROM paytm_tokens LIMIT 1')
        existing = cur.fetchone()
        
        if existing:
            if merchant_key:
                cur.execute('''
                    UPDATE paytm_tokens 
                    SET mid = %s, upi_id = %s, merchant_key = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                ''', (mid, upi_id, merchant_key, existing[0]))
            else:
                cur.execute('''
                    UPDATE paytm_tokens 
                    SET mid = %s, upi_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                ''', (mid, upi_id, existing[0]))
        else:
            cur.execute('''
                INSERT INTO paytm_tokens (mid, upi_id, merchant_key)
                VALUES (%s, %s, %s)
            ''', (mid, upi_id, merchant_key))
        
        conn.commit()
        cur.close()
        logger.info(f"Saved Paytm credentials: MID={mid}, UPI={upi_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving Paytm credentials: {e}")
        conn.rollback()
        return False

@with_db_retry()
def get_paytm_credentials(conn):
    """Get Paytm merchant credentials"""
    cur = conn.cursor()
    cur.execute('SELECT mid, upi_id, merchant_key, status FROM paytm_tokens WHERE status = %s LIMIT 1', ('Active',))
    creds = cur.fetchone()
    cur.close()
    if creds:
        return {
            'mid': creds[0],
            'upi_id': creds[1],
            'merchant_key': creds[2],
            'status': creds[3]
        }
    return None

@with_db_retry()
def update_payment_order_utr(conn, order_id, paytm_txn_id=None, utr=None, status=None):
    """Update payment order with Paytm transaction details"""
    try:
        cur = conn.cursor()
        updates = ['updated_at = CURRENT_TIMESTAMP']
        values = []
        
        if paytm_txn_id:
            updates.append('paytm_txn_id = %s')
            values.append(paytm_txn_id)
        if utr:
            updates.append('utr = %s')
            values.append(utr)
        if status:
            updates.append('status = %s')
            values.append(status)
        
        values.append(order_id)
        
        query = f"UPDATE payment_orders SET {', '.join(updates)} WHERE order_id = %s"
        cur.execute(query, tuple(values))
        conn.commit()
        cur.close()
        logger.info(f"Updated order {order_id} with UTR={utr}, status={status}")
        return True
    except Exception as e:
        logger.error(f"Error updating payment order UTR: {e}")
        conn.rollback()
        return False
