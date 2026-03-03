"""
database.py — MongoDB backend (replaces PostgreSQL / psycopg2).
All public function signatures are identical to the old version so app.py
needs zero changes.  The @with_db_retry() decorator now injects a `db`
(pymongo.Database) object as the first positional argument instead of a
psycopg2 connection.
"""

import os
import logging
import functools
from datetime import datetime, timedelta
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, ConnectionFailure

logger = logging.getLogger(__name__)

# ── Constants (same as before so app.py can import them) ─────────────────────
DEFAULT_DAILY_MESSAGE_LIMIT = 0
FREE_TRIAL_LIMIT = 20

# ── Connection ────────────────────────────────────────────────────────────────
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/keerthana_bot')

_client = None
_db_obj = None


def _parse_db_name(uri: str) -> str:
    try:
        path = uri.split('/')[-1].split('?')[0].strip()
        return path if path else 'keerthana_bot'
    except Exception:
        return 'keerthana_bot'


def get_db():
    global _client, _db_obj
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10000)
        db_name = _parse_db_name(MONGODB_URI)
        _db_obj = _client[db_name]
    return _db_obj


# Compatibility shims used by inline imports in app.py
def get_connection():
    return get_db()


def release_connection(conn):
    pass  # No-op — MongoClient manages its own pool


# ── Retry decorator ───────────────────────────────────────────────────────────
def with_db_retry(max_retries=3):
    """Inject db as first arg; retry on transient connection failures."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            global _client, _db_obj
            last_err = None
            for attempt in range(max_retries):
                try:
                    db = get_db()
                    return func(db, *args, **kwargs)
                except ConnectionFailure as e:
                    last_err = e
                    logger.warning(f'[DB] Retry {attempt + 1}/{max_retries}: {e}')
                    _client = None
                    _db_obj = None
                except Exception:
                    raise
            raise last_err
        return wrapper
    return decorator


# ── Schema / Index initialisation ─────────────────────────────────────────────
def init_database():
    db = get_db()

    db.users.create_index('user_id', unique=True)
    db.users.create_index('last_active')
    db.users.create_index('is_blocked')

    db.chat_messages.create_index([('user_id', ASCENDING), ('created_at', ASCENDING)])
    db.chat_messages.create_index('created_at')

    db.referrals.create_index('referred_id', unique=True)
    db.referrals.create_index('referrer_id')

    db.bot_settings.create_index('key', unique=True)

    db.user_memories.create_index(
        [('user_id', ASCENDING), ('memory_type', ASCENDING), ('memory_key', ASCENDING)],
        unique=True,
    )
    db.user_memories.create_index('user_id')

    db.conversation_summaries.create_index('user_id', unique=True)

    db.payment_orders.create_index('order_id', unique=True)
    db.payment_orders.create_index('user_id')
    db.payment_orders.create_index('status')

    db.paytm_tokens.create_index('mid', unique=True)

    # Ensure default global_daily_limit exists
    db.bot_settings.update_one(
        {'key': 'global_daily_limit'},
        {'$setOnInsert': {'key': 'global_daily_limit', 'value': '20', 'updated_at': datetime.now()}},
        upsert=True,
    )
    logger.info('[DB] MongoDB indexes created / verified.')


# ── User management ───────────────────────────────────────────────────────────
@with_db_retry()
def get_or_create_user(db, user_id, username=None, first_name=None, referred_by=None):
    try:
        set_fields = {'last_active': datetime.now()}
        if username:
            set_fields['username'] = username
        if first_name:
            set_fields['first_name'] = first_name

        existing = db.users.find_one_and_update(
            {'user_id': user_id},
            {'$set': set_fields},
            return_document=True,
        )
        if existing:
            return {
                'user_id': existing['user_id'],
                'preferred_name': existing.get('preferred_name'),
                'points': existing.get('points', 0),
                'referral_count': existing.get('referral_count', 0),
                'is_new': False,
            }

        # New user
        now = datetime.now()
        doc = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'preferred_name': None,
            'points': 0,
            'referral_count': 0,
            'referred_by': referred_by,
            'created_at': now,
            'last_active': now,
            'is_blocked': False,
            'custom_daily_limit': None,
            'daily_messages_used': 0,
            'bonus_messages': 0,
            'last_reset_date': now.strftime('%Y-%m-%d'),
            'confirmed_gender': None,
            'suffix_preference': 'da',
            'free_trial_messages': FREE_TRIAL_LIMIT,
            'purchased_credits': 0,
        }
        db.users.insert_one(doc)
        return {
            'user_id': user_id,
            'preferred_name': None,
            'points': 0,
            'referral_count': 0,
            'is_new': True,
            'referred_by': referred_by,
        }
    except DuplicateKeyError:
        result = db.users.find_one({'user_id': user_id})
        return {
            'user_id': result['user_id'],
            'preferred_name': result.get('preferred_name'),
            'points': result.get('points', 0),
            'referral_count': result.get('referral_count', 0),
            'is_new': False,
        }
    except Exception as e:
        logger.error(f'[DB] get_or_create_user error: {e}')
        raise


@with_db_retry()
def clear_chat_history(db, user_id):
    try:
        db.chat_messages.delete_many({'user_id': user_id})
        logger.info(f'[DB] Cleared chat history for user {user_id}')
        return True
    except Exception as e:
        logger.error(f'[DB] clear_chat_history error: {e}')
        return False


@with_db_retry()
def get_confirmed_gender(db, user_id):
    doc = db.users.find_one({'user_id': user_id}, {'confirmed_gender': 1})
    return doc.get('confirmed_gender') if doc else None


@with_db_retry()
def set_confirmed_gender(db, user_id, gender):
    try:
        db.users.update_one({'user_id': user_id}, {'$set': {'confirmed_gender': gender}})
        return True
    except Exception as e:
        logger.error(f'[DB] set_confirmed_gender error: {e}')
        return False


@with_db_retry()
def get_suffix_preference(db, user_id):
    doc = db.users.find_one({'user_id': user_id}, {'suffix_preference': 1})
    return doc.get('suffix_preference', 'da') if doc else 'da'


@with_db_retry()
def set_suffix_preference(db, user_id, suffix):
    try:
        db.users.update_one({'user_id': user_id}, {'$set': {'suffix_preference': suffix}})
        return True
    except Exception as e:
        logger.error(f'[DB] set_suffix_preference error: {e}')
        return False


@with_db_retry()
def award_referral_points(db, referrer_id, referred_id):
    try:
        db.referrals.insert_one({
            'referrer_id': referrer_id,
            'referred_id': referred_id,
            'points_awarded': 10,
            'created_at': datetime.now(),
        })
        db.users.update_one(
            {'user_id': referrer_id},
            {'$inc': {'bonus_messages': 10, 'referral_count': 1}},
        )
        logger.info(f'[DB] Referral awarded: {referrer_id} → {referred_id}')
        return True
    except DuplicateKeyError:
        logger.warning(f'[DB] Referral already exists for referred_id={referred_id}')
        return False
    except Exception as e:
        logger.error(f'[DB] award_referral_points error: {e}')
        return False


# ── Global settings ───────────────────────────────────────────────────────────
def get_global_daily_limit():
    try:
        db = get_db()
        doc = db.bot_settings.find_one({'key': 'global_daily_limit'})
        if doc:
            return int(doc['value'])
        return DEFAULT_DAILY_MESSAGE_LIMIT
    except Exception as e:
        logger.warning(f'[DB] get_global_daily_limit error: {e}')
        return DEFAULT_DAILY_MESSAGE_LIMIT


DAILY_MESSAGE_LIMIT = get_global_daily_limit()


@with_db_retry()
def set_global_daily_limit(db, new_limit):
    try:
        db.bot_settings.update_one(
            {'key': 'global_daily_limit'},
            {'$set': {'value': str(new_limit), 'updated_at': datetime.now()}},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f'[DB] set_global_daily_limit error: {e}')
        return False


@with_db_retry()
def get_bot_setting(db, key):
    try:
        doc = db.bot_settings.find_one({'key': key})
        return doc['value'] if doc else None
    except Exception:
        return None


@with_db_retry()
def set_bot_setting(db, key, value):
    try:
        db.bot_settings.update_one(
            {'key': key},
            {'$set': {'value': value, 'updated_at': datetime.now()}},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f'[DB] set_bot_setting error: {e}')
        return False


# ── Message credits ───────────────────────────────────────────────────────────
@with_db_retry()
def get_message_status(db, user_id):
    doc = db.users.find_one(
        {'user_id': user_id},
        {'free_trial_messages': 1, 'bonus_messages': 1, 'purchased_credits': 1},
    )
    if not doc:
        return {'free_trial': 0, 'bonus': 0, 'purchased': 0, 'total_remaining': 0}
    ft = doc.get('free_trial_messages', 0) or 0
    bm = doc.get('bonus_messages', 0) or 0
    pc = doc.get('purchased_credits', 0) or 0
    return {'free_trial': ft, 'bonus': bm, 'purchased': pc, 'total_remaining': ft + bm + pc}


@with_db_retry()
def use_message(db, user_id):
    """
    Consume one credit in priority: free_trial → bonus → purchased.
    Returns (can_send: bool, remaining: int).
    Each find_one_and_update is an atomic single-document operation.
    """
    try:
        for field in ('free_trial_messages', 'bonus_messages', 'purchased_credits'):
            result = db.users.find_one_and_update(
                {'user_id': user_id, field: {'$gt': 0}},
                {'$inc': {field: -1}},
                return_document=True,
                projection={'free_trial_messages': 1, 'bonus_messages': 1, 'purchased_credits': 1},
            )
            if result:
                remaining = (
                    (result.get('free_trial_messages') or 0)
                    + (result.get('bonus_messages') or 0)
                    + (result.get('purchased_credits') or 0)
                )
                return (True, remaining)
        return (False, 0)
    except Exception as e:
        logger.error(f'[DB] use_message error: {e}')
        return (False, 0)


@with_db_retry()
def get_user_points(db, user_id):
    doc = db.users.find_one({'user_id': user_id}, {'points': 1})
    return doc.get('points', 0) if doc else 0


@with_db_retry()
def update_preferred_name(db, user_id, name):
    try:
        db.users.update_one({'user_id': user_id}, {'$set': {'preferred_name': name}})
        return True
    except Exception as e:
        logger.error(f'[DB] update_preferred_name error: {e}')
        return False


# ── Chat history ──────────────────────────────────────────────────────────────
@with_db_retry()
def save_message(db, user_id, role, content):
    try:
        db.chat_messages.insert_one({
            'user_id': user_id,
            'role': role,
            'content': content,
            'created_at': datetime.now(),
        })
        return True
    except Exception as e:
        logger.error(f'[DB] save_message error: {e}')
        return False


@with_db_retry()
def get_chat_history(db, user_id, limit=20):
    docs = list(
        db.chat_messages.find({'user_id': user_id})
        .sort('created_at', DESCENDING)
        .limit(limit)
    )
    docs.reverse()
    return [{'role': d['role'], 'content': d['content']} for d in docs]


@with_db_retry()
def get_message_count(db, user_id):
    return db.chat_messages.count_documents({'user_id': user_id})


# ── Conversation summaries ────────────────────────────────────────────────────
@with_db_retry()
def save_conversation_summary(db, user_id, summary, mood=None,
                               relationship_level=None, active_roleplay=None,
                               last_topic=None, message_count=0):
    try:
        db.conversation_summaries.update_one(
            {'user_id': user_id},
            {
                '$set': {
                    'user_id': user_id,
                    'summary': summary,
                    'mood': mood,
                    'relationship_level': relationship_level,
                    'active_roleplay': active_roleplay,
                    'last_topic': last_topic,
                    'message_count': message_count,
                    'updated_at': datetime.now(),
                },
                '$setOnInsert': {'created_at': datetime.now()},
            },
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f'[DB] save_conversation_summary error: {e}')
        return False


@with_db_retry()
def get_conversation_summary(db, user_id):
    doc = db.conversation_summaries.find_one({'user_id': user_id})
    if not doc:
        return None
    return {
        'summary': doc.get('summary'),
        'mood': doc.get('mood'),
        'relationship_level': doc.get('relationship_level'),
        'active_roleplay': doc.get('active_roleplay'),
        'last_topic': doc.get('last_topic'),
        'message_count': doc.get('message_count', 0),
    }


@with_db_retry()
def clear_conversation_summary(db, user_id):
    try:
        db.conversation_summaries.delete_one({'user_id': user_id})
        return True
    except Exception as e:
        logger.error(f'[DB] clear_conversation_summary error: {e}')
        return False


# ── User stats ────────────────────────────────────────────────────────────────
@with_db_retry()
def get_user_stats(db, user_id):
    doc = db.users.find_one({'user_id': user_id})
    if not doc:
        return None
    msg_count = db.chat_messages.count_documents({'user_id': user_id, 'role': 'user'})
    return {
        'user_id': doc['user_id'],
        'preferred_name': doc.get('preferred_name'),
        'first_name': doc.get('first_name'),
        'points': doc.get('points', 0),
        'referral_count': doc.get('referral_count', 0),
        'message_count': msg_count,
        'daily_messages_used': doc.get('daily_messages_used', 0),
        'bonus_messages': doc.get('bonus_messages', 0),
        'purchased_credits': doc.get('purchased_credits', 0),
        'free_trial_messages': doc.get('free_trial_messages', 0),
        'created_at': doc.get('created_at'),
        'last_active': doc.get('last_active'),
        'is_blocked': doc.get('is_blocked', False),
    }


@with_db_retry()
def get_all_users(db):
    docs = list(db.users.find({}).sort('last_active', DESCENDING))
    result = []
    for u in docs:
        msg_count = db.chat_messages.count_documents({'user_id': u['user_id']})
        result.append({
            'user_id': u['user_id'],
            'username': u.get('username'),
            'first_name': u.get('first_name'),
            'preferred_name': u.get('preferred_name'),
            'daily_messages_used': u.get('daily_messages_used', 0),
            'bonus_messages': u.get('bonus_messages', 0),
            'referral_count': u.get('referral_count', 0),
            'created_at': u.get('created_at'),
            'last_active': u.get('last_active'),
            'is_blocked': u.get('is_blocked', False),
            'custom_daily_limit': u.get('custom_daily_limit'),
            'purchased_credits': u.get('purchased_credits', 0),
            'message_count': msg_count,
            'free_trial_messages': u.get('free_trial_messages', FREE_TRIAL_LIMIT),
        })
    return result


@with_db_retry()
def get_user_chat_history(db, user_id, limit=100):
    docs = list(
        db.chat_messages.find({'user_id': user_id})
        .sort('created_at', DESCENDING)
        .limit(limit)
    )
    docs.reverse()
    return [{'role': d['role'], 'content': d['content'], 'created_at': d.get('created_at')} for d in docs]


@with_db_retry()
def get_chats_by_date_range(db, start_date, end_date):
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)

    docs = list(
        db.chat_messages.find({'created_at': {'$gte': start_date, '$lt': end_date}})
        .sort([('user_id', ASCENDING), ('created_at', ASCENDING)])
    )
    user_cache = {}
    result = []
    for m in docs:
        uid = m['user_id']
        if uid not in user_cache:
            u = db.users.find_one({'user_id': uid}, {'first_name': 1, 'preferred_name': 1, 'username': 1})
            user_cache[uid] = u or {}
        u = user_cache[uid]
        result.append({
            'user_id': uid,
            'user_name': u.get('preferred_name') or u.get('first_name') or 'Unknown',
            'username': u.get('username') or 'N/A',
            'role': 'Keerthana' if m['role'] == 'assistant' else 'User',
            'content': m['content'],
            'timestamp': m.get('created_at'),
        })
    return result


@with_db_retry()
def get_dashboard_stats(db):
    total_users = db.users.count_documents({})
    total_messages = db.chat_messages.count_documents({})
    cutoff = datetime.now() - timedelta(hours=24)
    active_today = db.users.count_documents({'last_active': {'$gt': cutoff}})

    rev_pipeline = [
        {'$match': {'status': 'SUCCESS'}},
        {'$group': {'_id': None, 'total': {'$sum': '$amount_paise'}}},
    ]
    rev = list(db.payment_orders.aggregate(rev_pipeline))
    total_revenue_paise = rev[0]['total'] if rev else 0

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    messages_today = db.chat_messages.count_documents({
        'role': 'assistant',
        'created_at': {'$gte': today_start},
    })
    return {
        'total_users': total_users,
        'total_messages': total_messages,
        'active_today': active_today,
        'total_revenue': total_revenue_paise // 100,
        'messages_today': messages_today,
    }


# ── Block / Limit ─────────────────────────────────────────────────────────────
@with_db_retry()
def is_user_blocked(db, user_id):
    doc = db.users.find_one({'user_id': user_id}, {'is_blocked': 1})
    return bool(doc.get('is_blocked')) if doc else False


@with_db_retry()
def block_user(db, user_id):
    try:
        db.users.update_one({'user_id': user_id}, {'$set': {'is_blocked': True}})
        return True
    except Exception as e:
        logger.error(f'[DB] block_user error: {e}')
        return False


@with_db_retry()
def unblock_user(db, user_id):
    try:
        db.users.update_one({'user_id': user_id}, {'$set': {'is_blocked': False}})
        return True
    except Exception as e:
        logger.error(f'[DB] unblock_user error: {e}')
        return False


@with_db_retry()
def set_user_daily_limit(db, user_id, limit):
    try:
        db.users.update_one({'user_id': user_id}, {'$set': {'custom_daily_limit': limit}})
        return True
    except Exception as e:
        logger.error(f'[DB] set_user_daily_limit error: {e}')
        return False


@with_db_retry()
def get_user_daily_limit(db, user_id):
    doc = db.users.find_one({'user_id': user_id}, {'custom_daily_limit': 1})
    return doc.get('custom_daily_limit') if doc else None


# ── Referral stats ────────────────────────────────────────────────────────────
@with_db_retry()
def get_total_referral_stats(db):
    total = db.referrals.count_documents({})
    pipeline = [
        {'$group': {'_id': '$referrer_id', 'count': {'$sum': 1}}},
        {'$sort': {'count': DESCENDING}},
        {'$limit': 10},
        {'$lookup': {
            'from': 'users',
            'localField': '_id',
            'foreignField': 'user_id',
            'as': 'user',
        }},
        {'$unwind': {'path': '$user', 'preserveNullAndEmptyArrays': True}},
        {'$project': {
            'count': 1,
            'name': {'$ifNull': ['$user.preferred_name', '$user.first_name', 'Unknown']},
        }},
    ]
    top = list(db.referrals.aggregate(pipeline))
    return {
        'total_referrals': total,
        'top_referrers': [{'name': r.get('name', 'Unknown'), 'count': r['count']} for r in top],
    }


# ── Memories ──────────────────────────────────────────────────────────────────
@with_db_retry()
def save_user_memory(db, user_id, memory_type, memory_key, memory_value, confidence=1.0):
    try:
        db.user_memories.update_one(
            {'user_id': user_id, 'memory_type': memory_type, 'memory_key': memory_key},
            {
                '$set': {
                    'memory_value': memory_value,
                    'confidence': confidence,
                    'updated_at': datetime.now(),
                },
                '$setOnInsert': {
                    'user_id': user_id,
                    'memory_type': memory_type,
                    'memory_key': memory_key,
                    'created_at': datetime.now(),
                },
            },
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f'[DB] save_user_memory error: {e}')
        return False


@with_db_retry()
def get_user_memories(db, user_id, memory_type=None, limit=50):
    query = {'user_id': user_id}
    if memory_type:
        query['memory_type'] = memory_type
    docs = list(
        db.user_memories.find(query)
        .sort('updated_at', DESCENDING)
        .limit(limit)
    )
    return [{
        'memory_type': d['memory_type'],
        'memory_key': d['memory_key'],
        'memory_value': d['memory_value'],
        'confidence': d.get('confidence', 1.0),
        'updated_at': d.get('updated_at'),
    } for d in docs]


@with_db_retry()
def delete_user_memory(db, user_id, memory_type, memory_key):
    try:
        db.user_memories.delete_one({
            'user_id': user_id,
            'memory_type': memory_type,
            'memory_key': memory_key,
        })
        return True
    except Exception as e:
        logger.error(f'[DB] delete_user_memory error: {e}')
        return False


# ── Payment orders ────────────────────────────────────────────────────────────
@with_db_retry()
def create_payment_order(db, user_id, order_id, txn_ref, pack_id, amount_paise, credits):
    try:
        now = datetime.now()
        db.payment_orders.insert_one({
            'order_id': order_id,
            'user_id': user_id,
            'txn_ref': txn_ref,
            'pack_id': pack_id,
            'amount_paise': amount_paise,
            'credits': credits,
            'status': 'PENDING',
            'verified_by': None,
            'paytm_txn_id': None,
            'utr': None,
            'created_at': now,
            'updated_at': now,
        })
        return True
    except DuplicateKeyError:
        logger.warning(f'[DB] Payment order already exists: {order_id}')
        return False
    except Exception as e:
        logger.error(f'[DB] create_payment_order error: {e}')
        return False


@with_db_retry()
def get_payment_order(db, order_id):
    pipeline = [
        {'$match': {'order_id': order_id}},
        {'$lookup': {
            'from': 'users',
            'localField': 'user_id',
            'foreignField': 'user_id',
            'as': 'user',
        }},
        {'$unwind': {'path': '$user', 'preserveNullAndEmptyArrays': True}},
    ]
    docs = list(db.payment_orders.aggregate(pipeline))
    if not docs:
        return None
    o = docs[0]
    u = o.get('user') or {}
    return {
        'order_id': o['order_id'],
        'user_id': o['user_id'],
        'txn_ref': o.get('txn_ref'),
        'pack_id': o.get('pack_id'),
        'amount_paise': o.get('amount_paise'),
        'credits': o.get('credits'),
        'status': o.get('status'),
        'paytm_txn_id': o.get('paytm_txn_id'),
        'utr': o.get('utr'),
        'created_at': o.get('created_at'),
        'first_name': u.get('first_name'),
        'username': u.get('username'),
    }


@with_db_retry()
def update_payment_order_status(db, order_id, status, verified_by=None):
    try:
        update = {'$set': {'status': status, 'updated_at': datetime.now()}}
        if verified_by:
            update['$set']['verified_by'] = verified_by
        db.payment_orders.update_one({'order_id': order_id}, update)
        return True
    except Exception as e:
        logger.error(f'[DB] update_payment_order_status error: {e}')
        return False


@with_db_retry()
def add_purchased_credits(db, user_id, credits):
    try:
        db.users.update_one({'user_id': user_id}, {'$inc': {'purchased_credits': credits}})
        return True
    except Exception as e:
        logger.error(f'[DB] add_purchased_credits error: {e}')
        return False


@with_db_retry()
def get_purchased_credits(db, user_id):
    doc = db.users.find_one({'user_id': user_id}, {'purchased_credits': 1})
    return doc.get('purchased_credits', 0) if doc else 0


@with_db_retry()
def use_purchased_credit(db, user_id):
    result = db.users.find_one_and_update(
        {'user_id': user_id, 'purchased_credits': {'$gt': 0}},
        {'$inc': {'purchased_credits': -1}},
        return_document=True,
        projection={'purchased_credits': 1},
    )
    return result.get('purchased_credits', 0) if result else 0


@with_db_retry()
def get_pending_payment_orders(db):
    pipeline = [
        {'$match': {'status': 'PENDING'}},
        {'$sort': {'created_at': DESCENDING}},
        {'$lookup': {
            'from': 'users',
            'localField': 'user_id',
            'foreignField': 'user_id',
            'as': 'user',
        }},
        {'$unwind': {'path': '$user', 'preserveNullAndEmptyArrays': True}},
    ]
    docs = list(db.payment_orders.aggregate(pipeline))
    result = []
    for o in docs:
        u = o.get('user') or {}
        result.append({
            'order_id': o['order_id'],
            'user_id': o['user_id'],
            'pack_id': o.get('pack_id'),
            'credits': o.get('credits'),
            'amount_paise': o.get('amount_paise'),
            'created_at': o.get('created_at'),
            'first_name': u.get('first_name', 'Unknown'),
            'username': u.get('username', ''),
        })
    return result


@with_db_retry()
def expire_old_payment_orders(db):
    cutoff = datetime.now() - timedelta(hours=24)
    try:
        db.payment_orders.update_many(
            {'status': 'PENDING', 'created_at': {'$lt': cutoff}},
            {'$set': {'status': 'EXPIRED', 'updated_at': datetime.now()}},
        )
        return True
    except Exception as e:
        logger.error(f'[DB] expire_old_payment_orders error: {e}')
        return False


@with_db_retry()
def get_user_payment_orders(db, user_id, limit=10):
    docs = list(
        db.payment_orders.find({'user_id': user_id})
        .sort('created_at', DESCENDING)
        .limit(limit)
    )
    return [{
        'order_id': d['order_id'],
        'pack_id': d.get('pack_id'),
        'credits': d.get('credits'),
        'amount_paise': d.get('amount_paise'),
        'status': d.get('status'),
        'created_at': d.get('created_at'),
    } for d in docs]


# ── Paytm credentials ─────────────────────────────────────────────────────────
@with_db_retry()
def save_paytm_credentials(db, mid, upi_id, merchant_key=None):
    try:
        update = {
            '$set': {
                'mid': mid,
                'upi_id': upi_id,
                'status': 'Active',
                'updated_at': datetime.now(),
            },
            '$setOnInsert': {'created_at': datetime.now()},
        }
        if merchant_key:
            update['$set']['merchant_key'] = merchant_key
        db.paytm_tokens.update_one({'mid': mid}, update, upsert=True)
        return True
    except Exception as e:
        logger.error(f'[DB] save_paytm_credentials error: {e}')
        return False


@with_db_retry()
def get_paytm_credentials(db):
    doc = db.paytm_tokens.find_one({'status': 'Active'}, sort=[('updated_at', DESCENDING)])
    if not doc:
        return None
    return {
        'mid': doc.get('mid'),
        'upi_id': doc.get('upi_id'),
        'merchant_key': doc.get('merchant_key'),
        'status': doc.get('status'),
    }


@with_db_retry()
def update_payment_order_utr(db, order_id, paytm_txn_id=None, utr=None, status=None):
    try:
        update_set = {'updated_at': datetime.now()}
        if paytm_txn_id:
            update_set['paytm_txn_id'] = paytm_txn_id
        if utr:
            update_set['utr'] = utr
        if status:
            update_set['status'] = status
        db.payment_orders.update_one({'order_id': order_id}, {'$set': update_set})
        return True
    except Exception as e:
        logger.error(f'[DB] update_payment_order_utr error: {e}')
        return False


@with_db_retry()
def log_payment_report(db, order_id, user_token, status, transaction_id, utr,
                        amount, payment_app='Paytm', verified_by=None):
    try:
        db.payment_reports.insert_one({
            'order_id': order_id,
            'user_token': user_token,
            'status': status,
            'transaction_id': transaction_id,
            'utr': utr,
            'amount': amount,
            'payment_app': payment_app,
            'verified_by': verified_by,
            'created_at': datetime.now(),
        })
        return True
    except Exception as e:
        logger.error(f'[DB] log_payment_report error: {e}')
        return False


@with_db_retry()
def atomic_credit_payment(db, order_id, paytm_txn_id, utr, credits_to_add, user_id):
    """
    Atomically mark the order SUCCESS (only if not already SUCCESS) then credit the user.
    Returns True if credits were added, False if already credited.
    """
    try:
        result = db.payment_orders.find_one_and_update(
            {'order_id': order_id, 'status': {'$ne': 'SUCCESS'}},
            {'$set': {
                'status': 'SUCCESS',
                'paytm_txn_id': paytm_txn_id,
                'utr': utr,
                'updated_at': datetime.now(),
            }},
            return_document=True,
        )
        if result is None:
            logger.info(f'[ATOMIC] Order {order_id} already SUCCESS — skipping double-credit')
            return False

        db.users.update_one(
            {'user_id': user_id},
            {'$inc': {'purchased_credits': credits_to_add}},
        )
        logger.info(f'[ATOMIC] Credited {credits_to_add} to user {user_id} for order {order_id}')
        return True
    except Exception as e:
        logger.error(f'[ATOMIC] Error: {e}')
        return False


# ── Admin helper functions ────────────────────────────────────────────────────
@with_db_retry()
def get_user_info(db, user_id):
    """Full user profile for admin /userinfo command."""
    doc = db.users.find_one({'user_id': user_id})
    if not doc:
        return None
    total_msgs = db.chat_messages.count_documents({'user_id': user_id})
    return {
        'user_id': doc['user_id'],
        'username': doc.get('username'),
        'first_name': doc.get('first_name'),
        'preferred_name': doc.get('preferred_name'),
        'free_trial': doc.get('free_trial_messages', 0) or 0,
        'bonus': doc.get('bonus_messages', 0) or 0,
        'purchased': doc.get('purchased_credits', 0) or 0,
        'referrals': doc.get('referral_count', 0) or 0,
        'is_blocked': doc.get('is_blocked', False),
        'custom_limit': doc.get('custom_daily_limit'),
        'daily_used': doc.get('daily_messages_used', 0) or 0,
        'last_reset': doc.get('last_reset_date'),
        'created_at': doc.get('created_at'),
        'last_active': doc.get('last_active'),
        'gender': doc.get('confirmed_gender'),
        'suffix': doc.get('suffix_preference', 'da'),
        'total_msgs': total_msgs,
    }


@with_db_retry()
def give_trial_messages(db, user_id, amount):
    """Give extra free trial messages to a user (admin gift)."""
    try:
        db.users.update_one({'user_id': user_id}, {'$inc': {'free_trial_messages': amount}})
        return True
    except Exception as e:
        logger.error(f'[DB] give_trial_messages error: {e}')
        return False


@with_db_retry()
def get_active_user_ids(db):
    """All non-blocked user IDs for /broadcast."""
    docs = list(
        db.users.find({'is_blocked': False}, {'user_id': 1})
        .sort('last_active', DESCENDING)
    )
    return [d['user_id'] for d in docs]
