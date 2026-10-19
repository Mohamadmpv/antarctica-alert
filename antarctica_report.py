import asyncio
import os
import requests
from dotenv import load_dotenv

load_dotenv()

from telegram import Bot as TelegramBot
from jalali import now_jalali

# --- توکن‌های مخصوص ربات‌های جنوبگان ---
ANTARCTICA_TELEGRAM_TOKEN = os.getenv("ANTARCTICA_TELEGRAM_TOKEN")
ANTARCTICA_BALE_TOKEN = os.getenv("ANTARCTICA_BALE_TOKEN")
GIST_ID = os.getenv("GIST_ID")
GH_PAT = os.getenv("GH_PAT")

# --- ایستگاه‌های قطب جنوب (فقط آب‌وهوا) ---
ANTARCTICA_STATIONS = [
    {"name": "Vostok (روسیه)", "temp": "-45°C تا -55°C", "coord": "۷۸°۲۷′ جنوبی، ۱۰۶°۵۰′ شرقی"},
    {"name": "Amundsen-Scott (آمریکا)", "temp": "-44°C تا -46°C", "coord": "۹۰° جنوبی"},
    {"name": "Novolazarevskaya (روسیه)", "temp": "-14°C تا -22°C", "coord": "۷۰°۴۶′ جنوبی، ۱۱°۵۰′ شرقی"},
    {"name": "Maitri (هند)", "temp": "-13°C تا -32°C", "coord": "۷۰°۴۵′ جنوبی، ۱۱°۴۳′ شرقی"},
    {"name": "Zhongshan (چین)", "temp": "-12°C تا -18°C", "coord": "۶۹°۲۲′ جنوبی، ۷۶°۲۲′ شرقی"},
    {"name": "Esperanza (آرژانتین)", "temp": "4°C تا 8°C", "coord": "۶۳°۲۴′ جنوبی، ۵۶°۵۹′ غربی"},
]

def get_gist_users(filename):
    url = "https://api.github.com/gists/" + str(GIST_ID)
    headers = {"Authorization": "token " + str(GH_PAT)}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        content = r.json()["files"].get(filename, {}).get("content", "")
        return json.loads(content) if content else {}
    except Exception as e:
        print("Gist error:", e)
        return {}

def build_message():
    msg = "🧊 **گزارش آب‌وهوای جنوبگان** 🧊\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    
    msg += "🌡️ **دمای ایستگاه‌های تحقیقاتی (امروز):**\n\n"
    for st in ANTARCTICA_STATIONS:
        msg += f"📍 **{st['name']}**\n"
        msg += f"   🌡️ دما: {st['temp']}\n"
        msg += f"   🗺️ مختصات: {st['coord']}\n"
        msg += "   ➖➖➖➖➖➖\n"
        
    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg

async def send_telegram(msg):
    users = get_gist_users("antarctica_telegram_users.json")
    if not users: 
        print("No Telegram users found.")
        return
    bot = TelegramBot(token=ANTARCTICA_TELEGRAM_TOKEN)
    print("Telegram recipients:", len(users))
    for cid in users.keys():
        try:
            await bot.send_message(chat_id=cid, text=msg)
            print("  TG Sent:", cid)
        except Exception as e:
            print("  TG Failed:", cid, e)

def send_bale(msg):
    users = get_gist_users("antarctica_bale_users.json")
    if not users: 
        print("No Bale users found.")
        return
    print("Bale recipients:", len(users))
    if not ANTARCTICA_BALE_TOKEN: 
        print("  Bale Failed: Token is None")
        return
    for cid in users.keys():
        url = f"https://tapi.bale.ai/bot{ANTARCTICA_BALE_TOKEN}/sendMessage"
        try:
            r = requests.post(url, json={"chat_id": cid, "text": msg, "parse_mode": "Markdown"}, timeout=30)
            r.raise_for_status()
            print("  Bale Sent:", cid)
        except Exception as e:
            print("  Bale Failed:", cid, e)

async def main():
    print("=" * 60 + "\nگزارش آب‌وهوای جنوبگان - " + now_jalali() + "\n" + "=" * 60)
    msg = build_message()
    await send_telegram(msg)
    send_bale(msg)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())