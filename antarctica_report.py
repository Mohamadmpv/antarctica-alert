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

# --- ایستگاه‌های قطب جنوب ---
ANTARCTICA_STATIONS = [
    {"name": "Vostok (روسیه)", "temp": "-45°C تا -55°C", "coord": "۷۸°۲۷′ جنوبی، ۱۰۶°۵۰′ شرقی"},
    {"name": "Amundsen-Scott (آمریکا)", "temp": "-44°C تا -46°C", "coord": "۹۰° جنوبی"},
    {"name": "Novolazarevskaya (روسیه)", "temp": "-14°C تا -22°C", "coord": "۷۰°۴۶′ جنوبی، ۱۱°۵۰′ شرقی"},
    {"name": "Maitri (هند)", "temp": "-13°C تا -32°C", "coord": "۷۰°۴۵′ جنوبی، ۱۱°۴۳′ شرقی"},
    {"name": "Zhongshan (چین)", "temp": "-12°C تا -18°C", "coord": "۶۹°۲۲′ جنوبی، ۷۶°۲۲′ شرقی"},
    {"name": "Esperanza (آرژانتین)", "temp": "4°C تا 8°C", "coord": "۶۳°۲۴′ جنوبی، ۵۶°۵۹′ غربی"},
]

# --- اخبار طوفان (لینک مستقیم به خبر) ---
ANTARCTICA_STORM_NEWS = [
    {
        "title": "طوفان شدید در نزدیکی پایگاه بلغارستان",
        "text": "طوفانی با سرعت باد بیش از ۱۵۰ کیلومتر بر ساعت، پایگاه بلغارستان و کشتی تحقیقاتی آن را در نزدیکی جزیره لیوینگستون مسدود کرد.",
        "link": "https://bnrnews.bg/de/post/425938/starker-sturm-blockierte-bulgarische-basis-und-forschungsschiff-in-der-antarktis"
    },
    {
        "title": "طوفان ۱۳۰ کیلومتری و جداشدن یخبرگ ۵۰۰ متری",
        "text": "در ژانویه ۲۰۲۶، طوفانی با سرعت ۱۳۰ کیلومتر بر ساعت باعث جدا شدن یخبرگی به طول ۵۰۰ متر از سکوی یخی اکستروم شد که حامل ۷ کانتینر و ۹۵۰۰ لیتر گازوئیل بود.",
        "link": "https://es.gizmodo.com/la-antartida-perdio-un-iceberg-de-500-metros-en-una-tormenta-encima-llevaba-siete-contenedores-y-miles-de-litros-de-combustible-2000265124"
    }
]

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
    now_tehran = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3, minutes=30)
    msg = "🧊 **گزارش جنوبگان** 🧊\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    
    # ۱. آب‌وهوا (همیشه)
    msg += "🌡️ **دمای ایستگاه‌های تحقیقاتی:**\n\n"
    for st in ANTARCTICA_STATIONS:
        msg += f"📍 **{st['name']}**\n"
        msg += f"   🌡️ دما: {st['temp']}\n"
        msg += f"   🗺️ مختصات: {st['coord']}\n"
        msg += "   ➖➖➖➖➖➖\n"
    
    # ۲. اخبار طوفان (هر ۱ ساعت اجرا می‌شود و اگر خبری باشد)
    if ANTARCTICA_STORM_NEWS:
        msg += "\n━━━━━━━━━━━━━━━\n\n"
        msg += "🌀 **اخبار طوفان‌های قطب جنوب:**\n\n"
        for news in ANTARCTICA_STORM_NEWS:
            msg += f"🔹 **{news['title']}**\n"
            msg += f"   {news['text']}\n"
            msg += f"   🔗 {news['link']}\n\n"

    # ۳. اخبار پژوهشی (هر ۶ ساعت)
    if ANTARCTICA_RESEARCH_NEWS:
        msg += "\n━━━━━━━━━━━━━━━\n\n"
        msg += "📰 **اخبار پژوهشی جدید:**\n\n"
        for news in ANTARCTICA_RESEARCH_NEWS:
            msg += f"🔹 **{news['title']}**\n"
            msg += f"   {news['text']}\n"
            msg += f"   🔗 {news['link']}\n\n"

    # ۴. اخبار عمومی (هر ۱۲ ساعت)
    if ANTARCTICA_GENERAL_NEWS:
        msg += "\n━━━━━━━━━━━━━━━\n\n"
        msg += "🐾 **اخبار عمومی جنوبگان:**\n\n"
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