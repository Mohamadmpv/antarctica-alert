import asyncio
import os
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from io import BytesIO

load_dotenv()

from telegram import Bot as TelegramBot, InputFile
from jalali import now_jalali

ANTARCTICA_TELEGRAM_TOKEN = os.getenv("ANTARCTICA_TELEGRAM_TOKEN")
ANTARCTICA_BALE_TOKEN = os.getenv("ANTARCTICA_BALE_TOKEN")
GIST_ID = os.getenv("GIST_ID")
GH_PAT = os.getenv("GH_PAT")

# --- ایستگاه‌های قطب جنوب با مختصات دقیق (برای دریافت دمای زنده) ---
ANTARCTICA_STATIONS = [
    {"name": "Vostok (روسیه)", "lat": -78.4645, "lon": 106.8317},
    {"name": "Amundsen-Scott (آمریکا)", "lat": -90.0, "lon": 0.0},
    {"name": "Novolazarevskaya (روسیه)", "lat": -70.7667, "lon": 11.8333},
    {"name": "Maitri (هند)", "lat": -70.7500, "lon": 11.7167},
    {"name": "Zhongshan (چین)", "lat": -69.3667, "lon": 76.3667},
    {"name": "Esperanza (آرژانتین)", "lat": -63.4000, "lon": -56.9833},
]

WIND_THRESHOLD = 50  # km/h

# --- اخبار پژوهشی (لینک مستقیم به مقاله یا خبر) ---
ANTARCTICA_RESEARCH_NEWS = [
    {
        "title": "سوراخ لایه اوزون در سال ۲۰۲۶ بزرگ‌تر شد",
        "text": "سوراخ لایه اوزون بر فراز قطب جنوب در سپتامبر ۲۰۲۶ به حدود ۲۷.۴ میلیون کیلومتر مربع رسید و به بزرگ‌ترین اندازه خود در حدود ۲۰ سال گذشته نزدیک شد.",
        "link": "https://www.khabaronline.ir/news/2279751/%D8%B3%D9%88%D8%B1%D8%A7%D8%AE-%D9%84%D8%A7%DB%8C%D9%87-%D8%A7%D9%88%D8%B2%D9%88%D9%86-%D8%A7%D9%85%D8%B3%D8%A7%D9%84-%D8%A8%D8%B2%D8%B1%DA%AF-%D8%AA%D8%B1-%D8%B4%D8%AF-%D9%86%D8%B4%D8%A7%D9%86%D9%87-%D9%87%D8%A7%DB%8C%D8%B4-%D8%A7%D8%B2-%D9%85%D8%A7%D9%87-%D9%87%D8%A7-%D9%82%D8%A8%D9%84"
    },
    {
        "title": "کاهش بی‌سابقه یخ‌های دریایی (NSIDC/NASA)",
        "text": "حداکثر وسعت یخ‌های دریایی در سال ۲۰۲۶ به حدود ۱۷.۵۹ میلیون کیلومتر مربع رسید که سومین رکورد پایین‌ترین میزان از سال ۱۹۷۸ است.",
        "link": "https://nsidc.org/sea-ice-today"
    },
    {
        "title": "جایزه نوبل فیزیک ۲۰۲۶ برای رصدخانه یخی IceCube",
        "text": "پروفسور فرانسیس هالزن به دلیل ساخت رصدخانه نوترینو IceCube در عمق یخ‌های قطب جنوب موفق به دریافت جایزه نوبل فیزیک شد.",
        "link": "https://icecube.wisc.edu/"
    },
    {
        "title": "افزایش موقت یخ‌های دریایی قطب جنوب با گرم شدن اقیانوس‌های گرمسیری مرتبط است (Nature)",
        "text": "تحقیق جدیدی در Nature نشان می‌دهد که افزایش موقت یخ‌های دریایی قطب جنوب با گرم شدن اقیانوس‌های گرمسیری مرتبط است، اما این موضوع نشان‌دهنده معکوس شدن روند بلندمدت ذوب یخ‌ها نیست.",
        "link": "https://doi.org/10.1038/s41586-026-10912-x"
    }
]

# --- اخبار عمومی (حیات وحش و رویدادها) ---
ANTARCTICA_GENERAL_NEWS = [
    {
        "title": "عضویت کشورهای جدید در SCAR",
        "text": "در سی و نهمین نشست دبیران SCAR در اسلو، امارات متحده عربی و کاستاریکا به عنوان اعضای جدید به این کمیته پیوستند و تعداد اعضا به ۴۸ کشور رسید.",
        "link": "https://scar.org/scar-news/scar-delegates-meeting-2026"
    },
    {
        "title": "مشاهده نادر پنگوئن آدلی در عمق خشکی",
        "text": "در ژانویه ۲۰۲۶، یک پنگوئن آدلی در ایستگاه تحقیقاتی ترول در سرزمین ملکه مود، در فاصله ۲۰۰ کیلومتری از دریای باز مشاهده شد. این مشاهده بسیار نادر است.",
        "link": "https://polarresearch.net/index.php/polar"
    }
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

def get_weather_data(lat, lon):
    """دریافت دما و باد زنده از Open-Meteo"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,wind_speed_10m",
        "timezone": "UTC",
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Open-Meteo error for {lat},{lon}:", e)
        return None

def get_webcam_image():
    """دریافت تصویر زنده از دوربین NOAA"""
    image_url = "https://gmd-int.cmdl.noaa.gov/obop/spo/latest.jpg"
    try:
        r = requests.get(image_url, timeout=30)
        if r.status_code == 200 and r.headers.get('content-type', '').startswith('image'):
            return r.content
        return None
    except Exception:
        return None

def build_message():
    msg = "🧊 **گزارش جنوبگان** 🧊\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    
    # ۱. دمای ایستگاه‌ها (زنده از Open-Meteo)
    alerts = []
    msg += "🌡️ **دمای ایستگاه‌های تحقیقاتی (لحظه‌ای):**\n\n"
    for st in ANTARCTICA_STATIONS:
        data = get_weather_data(st["lat"], st["lon"])
        if not data or "current" not in data:
            msg += f"📍 **{st['name']}**: داده در دسترس نیست\n\n"
            continue
        
        current = data["current"]
        temp = current.get("temperature_2m")
        wind = current.get("wind_speed_10m")
        
        msg += f"📍 **{st['name']}**\n"
        msg += f"   🌡️ دما: {temp}°C\n"
        msg += f"   💨 باد: {wind} km/h\n"
        msg += "   ➖➖➖➖➖➖\n"
        
        if wind and wind > WIND_THRESHOLD:
            alerts.append({"station": st["name"], "wind": wind, "temp": temp})

    # ۲. هشدار طوفان
    if alerts:
        msg += "\n🚨 **هشدار طوفان در قطب جنوب!** 🚨\n\n"
        for a in alerts:
            msg += f"⚠️ **{a['station']}**: باد با سرعت {a['wind']} km/h\n"
        msg += "\n━━━━━━━━━━━━━━━\n"
    else:
        msg += "\n✅ **وضعیت طوفان: عادی** (باد کمتر از ۵۰ km/h)\n"
        msg += "\n━━━━━━━━━━━━━━━\n"

    # ۳. اخبار پژوهشی
    if ANTARCTICA_RESEARCH_NEWS:
        msg += "\n📰 **اخبار پژوهشی جدید:**\n\n"
        for news in ANTARCTICA_RESEARCH_NEWS:
            msg += f"🔹 **{news['title']}**\n"
            msg += f"   {news['text']}\n"
            msg += f"   🔗 {news['link']}\n\n"

    # ۴. اخبار عمومی (حیات وحش و رویدادها)
    if ANTARCTICA_GENERAL_NEWS:
        msg += "\n🐾 **اخبار عمومی جنوبگان:**\n\n"
        for news in ANTARCTICA_GENERAL_NEWS:
            msg += f"🔹 **{news['title']}**\n"
            msg += f"   {news['text']}\n"
            msg += f"   🔗 {news['link']}\n\n"
        
    msg += "━━━━━━━━━━━━━━━\n"
    return msg

async def send_telegram(msg, image_bytes=None):
    users = get_gist_users("antarctica_telegram_users.json")
    if not users: 
        print("No Telegram users found.")
        return
    bot = TelegramBot(token=ANTARCTICA_TELEGRAM_TOKEN)
    print("Telegram recipients:", len(users))
    for cid in users.keys():
        try:
            if image_bytes:
                await bot.send_photo(chat_id=cid, photo=InputFile(BytesIO(image_bytes), filename="south_pole.jpg"), caption=msg)
            else:
                await bot.send_message(chat_id=cid, text=msg)
            print("  TG Sent:", cid)
        except Exception as e:
            print("  TG Failed:", cid, e)

def send_bale(msg, image_bytes=None):
    users = get_gist_users("antarctica_bale_users.json")
    if not users: 
        print("No Bale users found.")
        return
    print("Bale recipients:", len(users))
    if not ANTARCTICA_BALE_TOKEN: 
        print("  Bale Failed: Token is None")
        return
    
    bale_msg = msg
    if image_bytes:
        bale_msg += "\n📷 [مشاهده تصویر زنده](https://gmd-int.cmdl.noaa.gov/obop/spo/livecamera.html)"
    
    for cid in users.keys():
        url = f"https://tapi.bale.ai/bot{ANTARCTICA_BALE_TOKEN}/sendMessage"
        try:
            r = requests.post(url, json={"chat_id": cid, "text": bale_msg, "parse_mode": "Markdown"}, timeout=30)
            r.raise_for_status()
            print("  Bale Sent:", cid)
        except Exception as e:
            print("  Bale Failed:", cid, e)

async def main():
    print("=" * 60 + "\nگزارش جنوبگان - " + now_jalali() + "\n" + "=" * 60)
    msg = build_message()
    
    print("Fetching webcam image...")
    image_bytes = get_webcam_image()
    if image_bytes:
        print("Image fetched successfully.")
    else:
        print("Failed to fetch image.")

    await send_telegram(msg, image_bytes)
    send_bale(msg, image_bytes)
    
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())