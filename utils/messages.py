import requests
import re
from config.settings import CHANNEL_ICON, TOOL_BY, OWNER_ICON, OWNER_ICO

# ================= CLEAN RESPONSE =================
def clean_response(response):
    """
    Cleans the response string from tuples, technical names, and extra characters.
    Example: "('Approved', 'Stripe_Auth_V1')" -> "Approved"
    """
    if not response:
        return "N/A"
    
    res_str = str(response)
    
    # Remove tuple formatting if present: ('Text', 'Gate') -> Text
    if res_str.startswith('(') and res_str.endswith(')'):
        try:
            # Extract the first part of the tuple
            parts = re.findall(r"'(.*?)'", res_str)
            if parts:
                res_str = parts[0]
        except:
            pass
    
    # Remove common technical suffixes or prefixes only if they are the entire response
    technical_names = ["Stripe_Auth_V1", "Stripe_Charge_V1", "Braintree_Auth_V1", "Shopify_Charge_V1", "Paypal_Donation_V1"]
    if res_str in technical_names:
        return "N/A"
    
    # Remove amounts like $1.00, 1.00$, 1.00 USD, etc.
    res_str = re.sub(r'\$?\d+(\.\d+)?\s?(USD|EUR|GBP|\$)?', '', res_str, flags=re.IGNORECASE)
    
    # Clean up extra characters
    res_str = res_str.strip(" ,()[]'\"")
    
    return res_str if res_str else "N/A"

# ================= USER NAME =================
def get_user_name(user):
    if user.username:
        return f"@{user.username}"
    elif user.first_name:
        return user.first_name
    else:
        return str(user.id)


def format_checked_by(user):
    if user.username:
        return f"@{user.username}"
    elif user.first_name:
        return user.first_name
    else:
        return f"User ID: {user.id}"


# ================= BIN DATA =================
def dato(zh):
    try:
        # Use a more reliable BIN API or handle errors gracefully
        api_url = requests.get(
            f"https://bins.antipublic.cc/bins/{zh[:6]}",
            timeout=5
        ).json()

        return {
            "brand": api_url.get("brand", "N/A"),
            "type": api_url.get("type", "N/A"),
            "level": api_url.get("level", "N/A"),
            "bank": api_url.get("bank", "N/A"),
            "country": api_url.get("country_name", "N/A"),
            "flag": api_url.get("country_flag", "")
        }

    except Exception:
        return {
            "brand": "N/A",
            "type": "N/A",
            "level": "N/A",
            "bank": "N/A",
            "country": "N/A",
            "flag": ""
        }


# ================= APPROVED =================
def approved_message(cc, last, gate_name, execution_time, dato_func, checked_by_text="", func_name="", price=""):
    info = dato_func(cc[:6])
    cleaned_last = clean_response(last)
    header = f"#{gate_name}"
    if func_name:
        header += f" ({func_name})"
    
    
    return f"""<b>{header} [{CHANNEL_ICON}] 🌩
- - - - - - - - - - - - - - - - - - - - - -
[{CHANNEL_ICON}] 𝐂𝐚𝐫𝐝: <code>{cc}</code>
[{CHANNEL_ICON}] 𝐒𝐭𝐚𝐭𝐮𝐬: Approved ✅
[{CHANNEL_ICON}] 𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {cleaned_last}
- - - - - - - - - - - - - - - - - - - - - -
[{CHANNEL_ICON}] 𝐁𝐢𝐧: {info['brand']} - {info['type']} - {info['level']}
[{CHANNEL_ICON}] 𝐁𝐚𝐧𝐤: {info['bank']}
[{CHANNEL_ICON}] 𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {info['country']} {info['flag']}
- - - - - - - - - - - - - - - - - - - - - -
[{OWNER_ICO}] 𝐓𝐢𝐦𝐞: {execution_time:.2f}s
[{OWNER_ICO}] 𝐂𝐡𝐞𝐜𝐤𝐞𝐝 𝐛𝐲: {checked_by_text}
- - - - - - - - - - - - - - - - - - - - - -
[{OWNER_ICON}] 𝐃𝐞𝐯 𝐛𝐲: {TOOL_BY}
</b>"""


# ================= CHARGED =================
def charged_message(cc, last, gate_name, execution_time, dato_func, checked_by_text="", func_name="", price=""):
    info = dato_func(cc[:6])
    cleaned_last = clean_response(last)
    header = f"#{gate_name}"
    if func_name:
        header += f" ({func_name})"



    return f"""<b>{header} [{CHANNEL_ICON}] 🌩
- - - - - - - - - - - - - - - - - - - - - -
[{CHANNEL_ICON}] 𝐂𝐚𝐫𝐝: <code>{cc}</code>
[{CHANNEL_ICON}] 𝐒𝐭𝐚𝐭𝐮𝐬: Charged 🔥
[{CHANNEL_ICON}] 𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {cleaned_last}
- - - - - - - - - - - - - - - - - - - - - -
[{CHANNEL_ICON}] 𝐁𝐢ن: {info['brand']} - {info['type']} - {info['level']}
[{CHANNEL_ICON}] 𝐁𝐚𝐧𝐤: {info['bank']}
[{CHANNEL_ICON}] 𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {info['country']} {info['flag']}
- - - - - - - - - - - - - - - - - - - - - -
[{OWNER_ICO}] 𝐓𝐢𝐦𝐞: {execution_time:.2f}s
[{OWNER_ICO}] 𝐂𝐡𝐞𝐜𝐤𝐞𝐝 𝐛𝐲: {checked_by_text}
- - - - - - - - - - - - - - - - - - - - - -
[{OWNER_ICON}] 𝐃𝐞𝐯 𝐛𝐲: {TOOL_BY}
</b>"""


# ================= FUNDS =================
def insufficient_funds_message(cc, last, gate_name, execution_time, dato_func, checked_by_text="", func_name="", price=""):
    info = dato_func(cc[:6])
    cleaned_last = clean_response(last)
    header = f"#{gate_name}"
    if func_name:
        header += f" ({func_name})"



    return f"""<b>{header} [{CHANNEL_ICON}] 🌩
- - - - - - - - - - - - - - - - - - - - - -
[{CHANNEL_ICON}] 𝐂𝐚𝐫𝐝: <code>{cc}</code>
[{CHANNEL_ICON}] 𝐒𝐭𝐚𝐭𝐮𝐬: Insufficient Funds 💸
[{CHANNEL_ICON}] 𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {cleaned_last}
- - - - - - - - - - - - - - - - - - - - - -
[{CHANNEL_ICON}] 𝐁𝐢ن: {info['brand']} - {info['type']} - {info['level']}
[{CHANNEL_ICON}] 𝐁𝐚𝐧𝐤: {info['bank']}
[{CHANNEL_ICON}] 𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {info['country']} {info['flag']}
- - - - - - - - - - - - - - - - - - - - - -
[{OWNER_ICO}] 𝐓𝐢𝐦𝐞: {execution_time:.2f}s
[{OWNER_ICO}] 𝐂𝐡𝐞𝐜𝐤𝐞𝐝 𝐛𝐲: {checked_by_text}
- - - - - - - - - - - - - - - - - - - - - -
[{OWNER_ICON}] 𝐃𝐞𝐯 𝐛𝐲: {TOOL_BY}
</b>"""


# ================= DECLINED =================
def declined_message(cc, last, gate_name, execution_time, dato_func, checked_by_text="", func_name=""):
    info = dato_func(cc[:6])
    cleaned_last = clean_response(last)
    header = f"#{gate_name}"
    if func_name:
        header += f" ({func_name})"

    return f"""<b>{header} [{CHANNEL_ICON}] 🌩
- - - - - - - - - - - - - - - - - - - - - -
[{CHANNEL_ICON}] 𝐂𝐚𝐫𝐝: <code>{cc}</code>
[{CHANNEL_ICON}] 𝐒𝐭𝐚𝐭𝐮𝐬: Declined ❌
[{CHANNEL_ICON}] 𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {cleaned_last}
- - - - - - - - - - - - - - - - - - - - - -
[{CHANNEL_ICON}] 𝐁𝐢𝐧: {info['brand']} - {info['type']} - {info['level']}
[{CHANNEL_ICON}] 𝐁𝐚𝐧𝐤: {info['bank']}
[{CHANNEL_ICON}] 𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {info['country']} {info['flag']}
- - - - - - - - - - - - - - - - - - - - - -
[{OWNER_ICO}] 𝐓𝐢𝐦𝐞: {execution_time:.2f}s
[{OWNER_ICO}] 𝐂𝐡𝐞𝐜𝐤𝐞𝐝 𝐛𝐲: {checked_by_text}
- - - - - - - - - - - - - - - - - - - - - -
[{OWNER_ICON}] 𝐃𝐞𝐯 𝐛𝐲: {TOOL_BY}
</b>"""


# ================= HIT DETECTED =================
def hit_detected_message(name, status_type, execution_time, gateway, checked_by_text="", func_name="", price=""):
    status_map = {
        "approved": "Approved ✅",
        "charged": "Charged ⚡",
        "funds": "Funds 💸"
    }

    status_text = status_map.get(status_type.lower(), status_type)
    header = f"{gateway}"
    if func_name:
        header += f" ({func_name})"
    


    return f"""<b>
[{CHANNEL_ICON}] 𝗛𝗶𝘁 𝗗𝗲𝘁𝗲𝗰𝘁𝗲𝗱 🔥
- - - - - - - - - - - - - - - - - - - -
[{CHANNEL_ICON}] 𝐍𝐚𝐦𝐞: {name}
[{CHANNEL_ICON}] 𝐒𝐭𝐚𝐭𝐮𝐬: {status_text}
[{CHANNEL_ICON}] 𝐓𝐢𝐦𝐞: {execution_time:.2f}s
[{CHANNEL_ICON}] 𝐆𝐚𝐭𝐞𝐰𝐚𝐲: {header}
- - - - - - - - - - - - - - - - - - - -
[{CHANNEL_ICON}] 𝐓𝐨𝐨𝐥 𝐁𝐲: {TOOL_BY}
</b>"""
