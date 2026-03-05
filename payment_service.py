import os
import qrcode
import io
import random
import string
import json
import requests
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta

try:
    import PaytmChecksum
    PAYTM_CHECKSUM_AVAILABLE = True
except ImportError:
    PAYTM_CHECKSUM_AVAILABLE = False

logger = logging.getLogger(__name__)

PRICING_PACKS = {
    'starter': {
        'name': 'Starter Pack',
        'price_paise': 5000,
        'price_display': '₹50',
        'credits': 200,
        'emoji': '🌟'
    },
    'value': {
        'name': 'Value Pack',
        'price_paise': 10000,
        'price_display': '₹100',
        'credits': 500,
        'emoji': '💎'
    },
    'pro': {
        'name': 'Pro Pack',
        'price_paise': 20000,
        'price_display': '₹200',
        'credits': 1200,
        'emoji': '👑'
    }
}

SUBSCRIPTION_PLANS = {
    'monthly_lite': {
        'name': 'Monthly Lite',
        'price_paise': 19900,
        'price_display': '₹199',
        'messages_limit': 1000,
        'duration_days': 30,
        'emoji': '🌙',
        'plan_type': 'subscription',
        'description': '1000 messages / 30 days',
    },
    'monthly_pro': {
        'name': 'Monthly Pro',
        'price_paise': 39900,
        'price_display': '₹399',
        'messages_limit': 3000,
        'duration_days': 30,
        'emoji': '👑',
        'plan_type': 'subscription',
        'description': '3000 messages / 30 days',
    },
}

# Combined lookup for any plan type
ALL_PLANS = {**PRICING_PACKS, **SUBSCRIPTION_PLANS}

PAYTM_STATUS_API_V3 = "https://securegw.paytm.in/v3/order/status"
PAYTM_STATUS_API_LEGACY = "https://securegw.paytm.in/order/status"

class PaymentService:
    def __init__(self, db_module):
        self.db = db_module
        self._credentials_cache = None
        self._cache_time = None
        self._cache_duration = 300

    def _get_cached_credentials(self) -> Optional[Dict]:
        """Get Paytm credentials from environment secrets with caching"""
        now = datetime.now()
        if self._credentials_cache and self._cache_time:
            if (now - self._cache_time).seconds < self._cache_duration:
                return self._credentials_cache
        
        mid = os.environ.get('PAYTM_MERCHANT_ID')
        merchant_key = os.environ.get('PAYTM_MERCHANT_KEY')
        upi_id = os.environ.get('PAYTM_UPI_ID')

        # Warn if only one of the pair is set — both are required for v3 API
        if mid and not merchant_key:
            logger.warning("[PAYTM] PAYTM_MERCHANT_ID set but PAYTM_MERCHANT_KEY missing — auto-verification will fall back to legacy API or manual")
        if merchant_key and not mid:
            logger.warning("[PAYTM] PAYTM_MERCHANT_KEY set but PAYTM_MERCHANT_ID missing — auto-verification disabled")

        if mid and upi_id:
            creds = {
                'mid': mid,
                'upi_id': upi_id,
                'merchant_key': merchant_key
            }
            self._credentials_cache = creds
            self._cache_time = now
            return creds

        return None

    def generate_transaction_id(self, length: int = 10) -> str:
        """Generate unique alphanumeric transaction ID"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    def generate_upi_link(self, upi_id: str, amount_paise: int, txn_ref: str, pack_name: str) -> str:
        """Generate UPI payment link with transaction reference"""
        amount_rupees = f"{(amount_paise / 100):.2f}"
        timestamp = str(datetime.now().timestamp()).split('.')[-1][:6]
        transaction_note = f"KEERTHANA{timestamp}"
        
        upi_link = (
            f"upi://pay"
            f"?pa={upi_id}"
            f"&am={amount_rupees}"
            f"&pn=Keerthana Bot"
            f"&tn={transaction_note}"
            f"&tr={txn_ref}"
        )
        return upi_link

    def generate_qr_code_bytes(self, upi_link: str) -> bytes:
        """Generate QR code image bytes from UPI link"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(upi_link)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer.getvalue()

    def create_payment_order(self, user_id: int, pack_id: str, plan_override: dict = None) -> Tuple[str, bytes, str, dict]:
        """Create a new payment order with QR code"""
        pack = plan_override or PRICING_PACKS.get(pack_id)
        if not pack:
            raise ValueError(f"Invalid pack_id: {pack_id}")
        
        creds = self._get_cached_credentials()
        if creds and creds.get('upi_id'):
            upi_id = creds['upi_id']
        else:
            upi_id = self.db.get_bot_setting('paytm_upi_id') or 'keerthanabot@paytm'
        
        order_id = self.generate_transaction_id()
        txn_ref = self.generate_transaction_id()
        
        upi_link = self.generate_upi_link(
            upi_id=upi_id,
            amount_paise=pack['price_paise'],
            txn_ref=txn_ref,
            pack_name=pack_id
        )
        
        qr_bytes = self.generate_qr_code_bytes(upi_link)
        
        self.db.create_payment_order(
            user_id=user_id,
            order_id=order_id,
            txn_ref=txn_ref,
            pack_id=pack_id,
            amount_paise=pack['price_paise'],
            credits=pack['credits']
        )
        
        return order_id, qr_bytes, upi_link, pack

    def _check_paytm_v3_api(self, order: dict, creds: dict) -> Dict:
        """Call Paytm v3 API with checksum (requires merchant_key)"""
        merchant_key = creds.get('merchant_key')
        if not merchant_key:
            return {'success': False, 'status': 'NO_KEY', 'message': 'Merchant key not configured'}
        
        if not PAYTM_CHECKSUM_AVAILABLE:
            return {'success': False, 'status': 'NO_LIBRARY', 'message': 'Paytm library not available'}
        
        try:
            body = {
                "mid": creds['mid'],
                "orderId": order['txn_ref']
            }
            
            checksum = PaytmChecksum.generateSignature(json.dumps(body), merchant_key)
            
            paytm_params = {
                "body": body,
                "head": {
                    "signature": checksum
                }
            }
            
            logger.info(f"[PAYTM-V3] Checking status for order {order['order_id']}")
            
            response = requests.post(
                PAYTM_STATUS_API_V3,
                json=paytm_params,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"[PAYTM-V3] API returned status {response.status_code}")
                return {'success': False, 'status': 'API_ERROR', 'message': 'Paytm API error'}
            
            data = response.json()
            logger.info(f"[PAYTM-V3] Response: {json.dumps(data)}")
            
            result_body = data.get('body', {})
            result_info = result_body.get('resultInfo', {})
            
            result_code = result_info.get('resultCode')
            result_status = result_info.get('resultStatus')
            result_msg = result_info.get('resultMsg', '')
            
            if result_code == '330' or 'checksum' in result_msg.lower():
                logger.error(f"[PAYTM-V3] Checksum error: {result_msg}")
                return {'success': False, 'status': 'CHECKSUM_ERROR', 'message': 'API configuration error'}
            
            if result_code == '501' or 'invalid orderId' in result_msg.lower():
                logger.info(f"[PAYTM-V3] No record for order: {result_msg}")
                return {
                    'success': True,
                    'api_version': 'v3',
                    'status': None,
                    'result_code': result_code,
                    'result_msg': 'No record found'
                }
            
            return {
                'success': True,
                'api_version': 'v3',
                'status': result_status,
                'result_code': result_code,
                'result_msg': result_msg,
                'txn_id': result_body.get('txnId'),
                'bank_txn_id': result_body.get('bankTxnId'),
                'txn_amount': result_body.get('txnAmount')
            }
            
        except Exception as e:
            logger.error(f"[PAYTM-V3] Error: {e}")
            return {'success': False, 'status': 'ERROR', 'message': str(e)}

    def _check_paytm_legacy_api(self, order: dict, creds: dict) -> Dict:
        """Call Paytm legacy API (no checksum - may not work for all accounts)"""
        try:
            payload = {
                "MID": creds['mid'],
                "ORDERID": order['txn_ref']
            }
            
            logger.info(f"[PAYTM-LEGACY] Checking status for order {order['order_id']}")
            
            response = requests.post(
                PAYTM_STATUS_API_LEGACY,
                data={"JsonData": json.dumps(payload)},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"[PAYTM-LEGACY] API returned status {response.status_code}")
                return {'success': False, 'status': 'API_ERROR', 'message': 'Paytm API error'}
            
            data = response.json()
            logger.info(f"[PAYTM-LEGACY] Response: {json.dumps(data)}")
            
            return {
                'success': True,
                'api_version': 'legacy',
                'status': data.get('STATUS'),
                'result_code': data.get('RESPCODE'),
                'result_msg': data.get('RESPMSG'),
                'txn_id': data.get('TXNID'),
                'bank_txn_id': data.get('BANKTXNID'),
                'txn_amount': data.get('TXNAMOUNT')
            }
            
        except Exception as e:
            logger.error(f"[PAYTM-LEGACY] Error: {e}")
            return {'success': False, 'status': 'ERROR', 'message': str(e)}

    def check_paytm_payment_status(self, order_id: str) -> Dict:
        """
        Check payment status via Paytm API.
        Tries v3 API with checksum first, falls back to legacy API.
        """
        order = self.db.get_payment_order(order_id)
        if not order:
            return {'success': False, 'status': 'NOT_FOUND', 'message': 'Order not found'}
        
        if order['status'] == 'SUCCESS':
            return {
                'success': True,
                'status': 'ALREADY_VERIFIED',
                'message': f"Already verified. {order['credits']} credits were added.",
                'credits': order['credits']
            }
        
        creds = self._get_cached_credentials()
        if not creds or not creds.get('mid'):
            logger.info(f"[PAYTM] No MID configured, falling back to manual verification")
            return {'success': False, 'status': 'NO_CREDENTIALS', 'message': 'Paytm credentials not configured'}
        
        api_result = None
        if creds.get('merchant_key') and PAYTM_CHECKSUM_AVAILABLE:
            api_result = self._check_paytm_v3_api(order, creds)
            if api_result.get('status') == 'CHECKSUM_ERROR':
                logger.error(f"[PAYTM] v3 API checksum error - check merchant_key configuration")
                return {
                    'success': False,
                    'status': 'CONFIG_ERROR',
                    'message': 'Payment API configuration error. Please contact support.'
                }
            if not api_result.get('success') or api_result.get('status') in ['NO_KEY', 'NO_LIBRARY', 'ERROR']:
                logger.info(f"[PAYTM] v3 API failed, trying legacy API")
                api_result = self._check_paytm_legacy_api(order, creds)
        else:
            api_result = self._check_paytm_legacy_api(order, creds)
        
        if not api_result.get('success'):
            return api_result
        
        paytm_status = api_result.get('status')
        paytm_txn_id = api_result.get('txn_id')
        bank_txn_id = api_result.get('bank_txn_id')
        txn_amount = api_result.get('txn_amount')
        resp_msg = api_result.get('result_msg', '')
        
        if paytm_status == 'TXN_SUCCESS':
            expected_amount = f"{order['amount_paise'] / 100:.2f}"
            if txn_amount and str(txn_amount) != expected_amount:
                logger.error(f"[PAYTM] Amount mismatch: expected {expected_amount}, got {txn_amount}")
                return {'success': False, 'status': 'AMOUNT_MISMATCH', 'message': 'Payment amount mismatch'}
            
            credited = self._atomic_credit(order, paytm_txn_id, bank_txn_id)
            
            if credited:
                return {
                    'success': True,
                    'status': 'TXN_SUCCESS',
                    'message': f"✅ Payment verified! {order['credits']} credits added",
                    'credits': order['credits'],
                    'utr': bank_txn_id,
                    'txn_id': paytm_txn_id
                }
            else:
                return {
                    'success': True,
                    'status': 'ALREADY_VERIFIED',
                    'message': f"Already verified. {order['credits']} credits were added.",
                    'credits': order['credits']
                }
        
        elif paytm_status == 'TXN_FAILURE':
            self.db.update_payment_order_utr(
                order_id=order_id,
                status='TXN_FAILURE'
            )
            return {
                'success': False,
                'status': 'TXN_FAILURE',
                'message': f'❌ Payment failed: {resp_msg}'
            }
        
        elif paytm_status == 'PENDING':
            return {
                'success': False,
                'status': 'PENDING',
                'message': '⏳ Payment is processing. Please wait and try again.'
            }
        
        elif 'No record found' in str(resp_msg) or paytm_status is None:
            return {
                'success': False,
                'status': 'NO_RECORD',
                'message': '⏳ Payment not received yet. Auto-verify works best with Paytm app.'
            }
        
        else:
            return {
                'success': False,
                'status': paytm_status or 'UNKNOWN',
                'message': f'Payment status: {resp_msg or "Unknown"}. Please wait or contact support.'
            }

    def _atomic_credit(self, order: dict, paytm_txn_id: str, bank_txn_id: str) -> bool:
        """
        Atomically credit user - returns True if credits were added, False if already credited.
        Uses database-level conditional UPDATE to prevent duplicate credits.
        """
        credited = self.db.atomic_credit_payment(
            order_id=order['order_id'],
            paytm_txn_id=paytm_txn_id,
            utr=bank_txn_id,
            credits_to_add=order['credits'],
            user_id=order['user_id']
        )
        
        if credited:
            self.db.log_payment_report(
                order_id=order['order_id'],
                user_token=order.get('user_token', ''),
                status='TXN_SUCCESS',
                transaction_id=paytm_txn_id,
                utr=bank_txn_id,
                amount=order['amount_paise']
            )
        
        return credited

    def verify_payment_auto(self, order_id: str) -> Dict:
        """Try automatic verification via Paytm API, fall back to pending if not configured"""
        order = self.db.get_payment_order(order_id)
        
        if not order:
            return {'success': False, 'status': 'NOT_FOUND', 'message': 'Order not found'}
        
        if order['status'] == 'SUCCESS':
            return {
                'success': True,
                'status': 'ALREADY_VERIFIED',
                'message': f"✅ Already verified! {order['credits']} credits were added",
                'order': order
            }
        
        expires_at = order['created_at'] + timedelta(minutes=30)
        if datetime.now() > expires_at:
            self.db.update_payment_order_status(order_id, 'EXPIRED')
            return {
                'success': False,
                'status': 'EXPIRED',
                'message': '❌ Payment window expired (30 minutes). Please create a new order.'
            }
        
        api_result = self.check_paytm_payment_status(order_id)
        
        if api_result['status'] == 'TXN_SUCCESS':
            return api_result
        elif api_result['status'] == 'ALREADY_VERIFIED':
            return api_result
        elif api_result['status'] == 'TXN_FAILURE':
            return api_result
        elif api_result['status'] == 'PENDING':
            return api_result
        elif api_result['status'] == 'NO_RECORD':
            return api_result
        elif api_result['status'] == 'CONFIG_ERROR':
            self.db.update_payment_order_status(order_id, 'PENDING_VERIFICATION')
            return {
                'success': True,
                'status': 'PENDING_VERIFICATION',
                'message': '⏳ Auto-verification unavailable. Payment submitted for admin verification.',
                'order': order
            }
        elif api_result['status'] in ['NO_CREDENTIALS', 'NO_KEY', 'NO_LIBRARY', 'API_ERROR', 'TIMEOUT', 'ERROR']:
            self.db.update_payment_order_status(order_id, 'PENDING_VERIFICATION')
            return {
                'success': True,
                'status': 'PENDING_VERIFICATION',
                'message': '⏳ Payment submitted for verification. Admin will verify shortly.',
                'order': order
            }
        else:
            self.db.update_payment_order_status(order_id, 'PENDING_VERIFICATION')
            return {
                'success': True,
                'status': 'PENDING_VERIFICATION',
                'message': '⏳ Payment marked for admin verification.',
                'order': order
            }

    def verify_payment_manual(self, order_id: str, admin_user_id: int) -> Dict:
        """Admin manually verifies a payment and credits the user"""
        order = self.db.get_payment_order(order_id)
        
        if not order:
            return {
                'success': False,
                'status': 'NOT_FOUND',
                'message': 'Order not found'
            }
        
        if order['status'] == 'SUCCESS':
            return {
                'success': False,
                'status': 'ALREADY_VERIFIED',
                'message': 'Payment already verified'
            }
        
        if order['status'] == 'EXPIRED':
            return {
                'success': False,
                'status': 'EXPIRED',
                'message': 'Order has expired'
            }
        
        self.db.update_payment_order_status(order_id, 'SUCCESS', verified_by=admin_user_id)
        self.db.add_purchased_credits(order['user_id'], order['credits'])
        
        self.db.log_payment_report(
            order_id=order_id,
            user_token=order.get('user_token', ''),
            status='MANUAL_VERIFIED',
            transaction_id=None,
            utr=None,
            amount=order['amount_paise'],
            verified_by=admin_user_id
        )
        
        return {
            'success': True,
            'status': 'SUCCESS',
            'message': f"✅ Payment verified! {order['credits']} credits added to user {order['user_id']}",
            'order': order,
            'credits': order['credits']
        }

    def user_confirm_payment(self, order_id: str) -> Dict:
        """Called when user clicks 'I've Paid' - tries auto-verify first"""
        return self.verify_payment_auto(order_id)

    def get_pending_orders(self) -> list:
        return self.db.get_pending_payment_orders()

    def expire_old_orders(self):
        self.db.expire_old_payment_orders()

    def get_user_orders(self, user_id: int) -> list:
        return self.db.get_user_payment_orders(user_id)

    def create_subscription_order(self, user_id: int, plan_id: str, plan_override: dict = None) -> tuple:
        """Create a payment order for a subscription plan."""
        import database as db_module
        plan = plan_override or SUBSCRIPTION_PLANS.get(plan_id)
        if not plan:
            raise ValueError(f"Unknown subscription plan: {plan_id}")

        order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        txn_ref = f"SUB{user_id}{order_id}"

        creds = self._get_cached_credentials()
        upi_id = creds['upi_id'] if creds else os.environ.get('PAYTM_UPI_ID', '')

        if not upi_id:
            raise ValueError("No UPI ID configured")

        upi_link = self.generate_upi_link(upi_id, plan['price_paise'], txn_ref, plan['name'])
        qr_bytes = self.generate_qr_code_bytes(upi_link)

        self.db.create_payment_order(
            user_id=user_id,
            order_id=order_id,
            txn_ref=txn_ref,
            pack_id=plan_id,
            amount_paise=plan['price_paise'],
            credits=plan['messages_limit'],
        )

        logger.info(f"[SUB_ORDER] Created subscription order {order_id} for user {user_id} plan {plan_id}")
        return (order_id, qr_bytes, upi_link, plan)

    def complete_subscription_payment(self, order_id: str, paytm_txn_id: str = '', utr: str = '', admin_user_id: int = None) -> dict:
        """Called after payment verified for a subscription. Creates the subscription record."""
        try:
            order = self.db.get_payment_order(order_id)
            if not order:
                return {'success': False, 'message': 'Order not found'}

            plan_id = order.get('pack_id', '')
            plan = SUBSCRIPTION_PLANS.get(plan_id)
            if not plan:
                return {'success': False, 'message': f'Not a subscription plan: {plan_id}'}

            user_id = order['user_id']
            messages_limit = plan['messages_limit']

            # Atomic mark order as SUCCESS
            credited = self.db.atomic_credit_payment(
                order_id, paytm_txn_id, utr, messages_limit, user_id
            )
            if not credited:
                return {'success': False, 'message': 'Already processed'}

            # Create subscription record
            self.db.create_subscription(user_id, plan_id, messages_limit, order_id)

            verified_by = f"admin:{admin_user_id}" if admin_user_id else "auto"
            self.db.log_payment_report(order_id, str(user_id), 'SUCCESS', paytm_txn_id, utr, plan['price_paise'], verified_by=verified_by)

            logger.info(f"[SUB_COMPLETE] Subscription {plan_id} created for user {user_id}")
            return {
                'success': True,
                'plan': plan,
                'messages_limit': messages_limit,
                'user_id': user_id,
            }
        except Exception as e:
            logger.error(f"[SUB_COMPLETE] Error: {e}")
            return {'success': False, 'message': str(e)}

