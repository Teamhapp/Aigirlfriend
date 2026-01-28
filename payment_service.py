import qrcode
import io
import base64
import random
import string
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta

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

class PaymentService:
    def __init__(self, db_module):
        self.db = db_module

    def generate_transaction_id(self, length: int = 10) -> str:
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    def generate_upi_link(self, upi_id: str, amount_paise: int, txn_ref: str, pack_name: str) -> str:
        amount_rupees = f"{(amount_paise / 100):.2f}"
        timestamp = str(datetime.now().timestamp()).split('.')[-1][:6]
        transaction_note = f"Keerthana-{pack_name}-{timestamp}"
        
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

    def create_payment_order(self, user_id: int, pack_id: str) -> Tuple[str, bytes, str, dict]:
        if pack_id not in PRICING_PACKS:
            raise ValueError(f"Invalid pack_id: {pack_id}")
        
        pack = PRICING_PACKS[pack_id]
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

    def verify_payment_manual(self, order_id: str, admin_user_id: int) -> Dict:
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
        
        return {
            'success': True,
            'status': 'SUCCESS',
            'message': f"✅ Payment verified! {order['credits']} credits added",
            'order': order
        }

    def user_confirm_payment(self, order_id: str) -> Dict:
        order = self.db.get_payment_order(order_id)
        
        if not order:
            return {
                'success': False,
                'status': 'NOT_FOUND',
                'message': 'Order not found'
            }
        
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
        
        self.db.update_payment_order_status(order_id, 'PENDING_VERIFICATION')
        
        return {
            'success': True,
            'status': 'PENDING_VERIFICATION',
            'message': '⏳ Payment marked for verification. Admin will verify shortly and credits will be added.',
            'order': order
        }

    def get_pending_orders(self) -> list:
        return self.db.get_pending_payment_orders()

    def expire_old_orders(self):
        self.db.expire_old_payment_orders()

    def get_user_orders(self, user_id: int) -> list:
        return self.db.get_user_payment_orders(user_id)
