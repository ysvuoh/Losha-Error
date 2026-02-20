import threading
import requests
from faker import Faker
from telebot import types
from storage.repositories.bans import is_banned
from storage.db import get_connection

from security.channel_guard import is_channel_subscribed, send_channel_prompt
fake = Faker()

def register_fake(bot):

    @bot.message_handler(
        func=lambda message: message.text
        and (message.text.lower().startswith('.fake')
             or message.text.lower().startswith('/fake'))
    )
    

    
    def respond_to_fake(message):

        def worker():
            try:
                # 🌍 Country code (default US)
                try:
                    country = message.text.split(" ", 1)[1].strip().upper()
                except:
                    country = "US"

                r = requests.get(
                    f"https://randomuser.me/api/?nat={country}",
                    timeout=10
                ).json()

                result = r["results"][0]

                name = f"{result['name']['title']} {result['name']['first']} {result['name']['last']}"
                street = f"{result['location']['street']['number']} {result['location']['street']['name']}"
                city = result["location"]["city"]
                state = result["location"]["state"]
                country_name = result["location"]["country"]
                postcode = result["location"]["postcode"]

                phone = fake.phone_number()
                email = fake.email()

                text = f"""
<b>📍 Fake Address ({country_name})</b>

<b>👤 Full Name:</b> <code>{name}</code>
<b>🏙 City:</b> <code>{city}</code>
<b>🗺 State:</b> <code>{state}</code>
<b>📮 Postal Code:</b> <code>{postcode}</code>
<b>🏠 Street:</b> <code>{street}</code>
<b>📞 Phone:</b> <code>{phone}</code>
<b>📧 Email:</b> <code>{email}</code>
"""

                bot.reply_to(
                    message,
                    text,
                    parse_mode="HTML"
                )

            except Exception as e:
                bot.reply_to(
                    message,
                    "❌ Country code not found or service unavailable."
                )
                print("FAKE ERROR:", e)

        threading.Thread(target=worker).start()