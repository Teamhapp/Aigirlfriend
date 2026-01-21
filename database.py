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
def get_message_status(conn, user_id):
    global_limit = _get_global_limit_from_conn(conn)
    cur = conn.cursor()
    cur.execute('''
        SELECT daily_messages_used, bonus_messages, last_reset_date, custom_daily_limit 
        FROM users WHERE user_id = %s
    ''', (user_id,))
    result = cur.fetchone()
    cur.close()
    
    if not result:
        return {'daily_used': 0, 'daily_remaining': global_limit, 'bonus': 0, 'total_remaining': global_limit}
    
    daily_used, bonus, last_reset, custom_limit = result[0] or 0, result[1] or 0, result[2], result[3]
    user_limit = custom_limit if custom_limit else global_limit
    today = date.today()
    
    if last_reset is None or last_reset < today:
        daily_used = 0
    
    daily_remaining = max(0, user_limit - daily_used)
    total_remaining = daily_remaining + bonus
    
    return {
        'daily_used': daily_used,
        'daily_remaining': daily_remaining,
        'bonus': bonus,
        'total_remaining': total_remaining,
        'daily_limit': user_limit
    }

@with_db_retry()
def use_message(conn, user_id):
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT daily_messages_used, bonus_messages, last_reset_date, custom_daily_limit 
            FROM users WHERE user_id = %s
        ''', (user_id,))
        result = cur.fetchone()
        
        if not result:
            cur.close()
            return False, 0
        
        daily_used, bonus, last_reset, custom_limit = result[0] or 0, result[1] or 0, result[2], result[3]
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
            remaining = user_limit - 1 + bonus
            return True, remaining
        
        daily_remaining = user_limit - daily_used
        
        if daily_remaining > 0:
            cur.execute('''
                UPDATE users SET daily_messages_used = daily_messages_used + 1
                WHERE user_id = %s
            ''', (user_id,))
            conn.commit()
            cur.close()
            remaining = daily_remaining - 1 + bonus
            return True, remaining
        elif bonus > 0:
            cur.execute('''
                UPDATE users SET bonus_messages = bonus_messages - 1
                WHERE user_id = %s
            ''', (user_id,))
            conn.commit()
            cur.close()
            remaining = bonus - 1
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
