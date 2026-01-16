import os
import psycopg2
from psycopg2 import pool
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')

connection_pool = None

def init_pool():
    global connection_pool
    if connection_pool is None:
        connection_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DATABASE_URL)
    return connection_pool

def get_connection():
    pool = init_pool()
    return pool.getconn()

def release_connection(conn):
    if connection_pool:
        connection_pool.putconn(conn)

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
                is_blocked BOOLEAN DEFAULT FALSE
            )
        ''')
        
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
        
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        release_connection(conn)

def get_or_create_user(user_id, username=None, first_name=None, referred_by=None):
    conn = get_connection()
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
            return {'user_id': user[0], 'preferred_name': user[1], 'points': user[2], 'referral_count': user[3], 'is_new': False}
        else:
            cur.execute('''
                INSERT INTO users (user_id, username, first_name, referred_by)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id, preferred_name, points, referral_count
            ''', (user_id, username, first_name, referred_by))
            new_user = cur.fetchone()
            conn.commit()
            
            if referred_by:
                award_referral_points(referred_by, user_id)
            
            return {'user_id': new_user[0], 'preferred_name': new_user[1], 'points': new_user[2], 'referral_count': new_user[3], 'is_new': True}
    except Exception as e:
        logger.error(f"Error in get_or_create_user: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        release_connection(conn)

def award_referral_points(referrer_id, referred_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        
        cur.execute('SELECT id FROM referrals WHERE referred_id = %s', (referred_id,))
        if cur.fetchone():
            return False
        
        cur.execute('''
            INSERT INTO referrals (referrer_id, referred_id, points_awarded)
            VALUES (%s, %s, 10)
        ''', (referrer_id, referred_id))
        
        cur.execute('''
            UPDATE users SET points = points + 10, referral_count = referral_count + 1
            WHERE user_id = %s
        ''', (referrer_id,))
        
        cur.execute('''
            INSERT INTO points_transactions (user_id, amount, transaction_type, description)
            VALUES (%s, 10, 'referral', %s)
        ''', (referrer_id, f'Referral bonus for inviting user {referred_id}'))
        
        conn.commit()
        logger.info(f"Awarded 10 points to user {referrer_id} for referral")
        return True
    except Exception as e:
        logger.error(f"Error awarding referral points: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        release_connection(conn)

def get_user_points(user_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT points, referral_count FROM users WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        return {'points': result[0], 'referral_count': result[1]} if result else {'points': 0, 'referral_count': 0}
    finally:
        cur.close()
        release_connection(conn)

def update_preferred_name(user_id, name):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('UPDATE users SET preferred_name = %s WHERE user_id = %s', (name, user_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error updating preferred name: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        release_connection(conn)

def save_message(user_id, role, content):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO chat_messages (user_id, role, content)
            VALUES (%s, %s, %s)
        ''', (user_id, role, content))
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving message: {e}")
        conn.rollback()
    finally:
        cur.close()
        release_connection(conn)

def get_chat_history(user_id, limit=20):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT role, content FROM chat_messages
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        ''', (user_id, limit))
        messages = cur.fetchall()
        return [{'role': msg[0], 'content': msg[1]} for msg in reversed(messages)]
    finally:
        cur.close()
        release_connection(conn)

def get_user_stats(user_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT u.points, u.referral_count, u.preferred_name, u.created_at,
                   (SELECT COUNT(*) FROM chat_messages WHERE user_id = %s) as message_count
            FROM users u WHERE u.user_id = %s
        ''', (user_id, user_id))
        result = cur.fetchone()
        if result:
            return {
                'points': result[0],
                'referral_count': result[1],
                'preferred_name': result[2],
                'member_since': result[3],
                'message_count': result[4]
            }
        return None
    finally:
        cur.close()
        release_connection(conn)
