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
    {"name": "Vostok (روسیه)", "lat": -78.4645, "lon": 106.8317},
    {"name": "Amundsen-Scott (آمریکا)", "lat": -90.0, "lon": 0.0},
    {"name": "Novolazarevskaya (روسیه)", "lat": -70.7667, "lon": 11.8333},
    {"name": "Maitri (هند)", "lat": -70.7500, "lon": 11.7167},
    {"name": "Zhongshan (چین)", "lat": -69.3667, "lon": 76.3667},
    {"name": "Esperanza (آرژانتین)", "lat": -63.4000, "lon": -56.9833},
]

WIND_THRESHOLD = 50

# --- اخبار پژوهشی و عمومی ---
ANTARCTICA_RESEARCH_NEWS = [
    {"title": "سوراخ لایه اوزون در سال ۲۰۲۶ بزرگ‌تر شد", "text": "سوراخ لایه اوزون بر فراز قطب جنوب در سپتامبر ۲۰۲۶ به حدود ۲۷.۴ میلیون کیلومتر مربع رسید.", "link": "https://www.khabaronline.ir/news/2279751"},
    {"title": "کاهش بی‌سابقه یخ‌های دریایی (NSIDC/NASA)", "text": "حداکثر وسعت یخ‌های دریایی در سال ۲۰۲۶ به حدود ۱۷.۵۹ میلیون کیلومتر مربع رسید.", "link": "https://nsidc.org/sea-ice-today"},
]

ANTARCTICA_GENERAL_NEWS = [
    {"title": "عضویت کشورهای جدید در SCAR", "text": "در سی و نهمین نشست دبیران SCAR در اسلو، امارات متحده عربی و کاستاریکا به این کمیته پیوستند.", "link": "https://scar.org/scar-news/scar-delegates-meeting-2026"},
    {"title": "مشاهده نادر پنگوئن آدلی در عمق خشکی", "text": "یک پنگوئن آدلی در فاصله ۲۰۰ کیلومتری از دریای باز در سرزمین ملکه مود مشاهده شد.", "link": "https://polarresearch.net/index.php/polar"},
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
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": lat, "longitude": lon, "current": "temperature_2m,wind_speed_10m", "timezone": "UTC"}
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Open-Meteo error: {e}")
        return None

def get_latest_paper():
    """دریافت جدیدترین مقاله از CrossRef با Abstract"""
    url = "https://api.crossref.org/works"
    params = {
        "query": "Antarctica",
        "filter": "from-pub-date:2026-01-01,type:journal-article",
        "rows": 1,
        "sort": "published",
        "order": "desc"
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data["message"]["items"]:
            item = data["message"]["items"][0]
            title = item.get("title", ["بدون عنوان"])[0]
            doi = item.get("DOI", "")
            abstract = item.get("abstract", "چکیده در دسترس نیست.")
            # تمیز کردن تگ‌های HTML از abstract
            abstract = abstract.replace("<jats:p>", "").replace("</jats:p>", "").replace("<jats:title>", "").replace("</jats:title>", "")[:300] + "..."
            return {"title": title, "link": f"https://doi.org/{doi}", "abstract": abstract}
        return None
    except Exception as e:
        print("CrossRef error:", e)
        return None

def get_webcam_image():
    image_url = "https://gmd-int.cmdl.noaa.gov/obop/spo/latest.jpg"
    try:
        r = requests.get(image_url, timeout=30)
        if r.status_code == 200 and r.headers.get('content-type', '').startswith('image'):
            return r.content
        return None
    except Exception:
        return None

def build_weather_message():
    msg = "🌡️ **دمای ایستگاه‌های جنوبگان** 🌡️\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    
    alerts = []
    for st in ANTARCTICA_STATIONS:
        data = get_weather_data(st["lat"], st["lon"])
        if not data or "current" not in data:
            msg += f"📍 **{st['name']}**: داده در دسترس نیست\n"
            continue
        c = data["current"]
        temp, wind = c.get("temperature_2m"), c.get("wind_speed_10m")
        msg += f"📍 **{st['name']}**: {temp}°C | باد: {wind} km/h\n"
        if wind and wind > WIND_THRESHOLD:
            alerts.append({"station": st["name"], "wind": wind})
    
    if alerts:
        msg += "\n🚨 **هشدار طوفان!**\n"
        for a in alerts: msg += f"⚠️ **{a['station']}**: {a['wind']} km/h\n"
    
    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg

def build_paper_message():
    paper = get_latest_paper()
    if not paper:
        return None
    
    msg = "📄 **مقاله علمی هفته (جنوبگان)** 📄\n\n"
    msg += f"🔹 **{paper['title']}**\n\n"
    msg += f"📝 **چکیده:**\n{paper['abstract']}\n\n"
    msg += f"🔗 {paper['link']}\n"
    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg

def build_news_message():
    msg = "📰 **اخبار و پژوهش‌های جنوبگان** 📰\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    
    msg += "🔬 **اخبار پژوهشی:**\n"
    for n in ANTARCTICA_RESEARCH_NEWS:
        msg += f"🔹 **{n['title']}**\n   {n['text']}\n   🔗 {n['link']}\n\n"

    msg += "🐾 **اخبار عمومی:**\n"
    for n in ANTARCTICA_GENERAL_NEWS:
        msg += f"🔹 **{n['title']}**\n   {n['text']}\n   🔗 {n['link']}\n\n"
        
    msg += "━━━━━━━━━━━━━━━\n"
    return msg

async def send_telegram(msg, image_bytes=None):
    users = get_gist_users("antarctica_telegram_users.json")
    if not users: return
    bot = TelegramBot(token=ANTARCTICA_TELEGRAM_TOKEN)
    for cid in users.keys():
        try:
            if image_bytes:
                await bot.send_photo(chat_id=cid, photo=InputFile(BytesIO(image_bytes), filename="south_pole.jpg"), caption=msg)
            else:
                await bot.send_message(chat_id=cid, text=msg)
        except Exception as e:
            print("  TG Failed:", cid, e)

def send_bale(msg, image_bytes=None):
    users = get_gist_users("antarctica_bale_users.json")
    if not users: return
    if not ANTARCTICA_BALE_TOKEN: return
    bale_msg = msg + ("\n📷 [مشاهده تصویر زنده](https://gmd-int.cmdl.noaa.gov/obop/spo/livecamera.html)" if image_bytes else "")
    for cid in users.keys():
        url = f"https://tapi.bale.ai/bot{ANTARCTICA_BALE_TOKEN}/sendMessage"
        try:
            r = requests.post(url, json={"chat_id": cid, "text": bale_msg, "parse_mode": "Markdown"}, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print("  Bale Failed:", cid, e)

async def main():
    print("=" * 60 + "\nگزارش جنوبگان - " + now_jalali() + "\n" + "=" * 60)
    
    # ۱. ارسال پیام آب‌وهوا (همیشه)
    weather_msg = build_weather_message()
    image_bytes = get_webcam_image()
    await send_telegram(weather_msg, image_bytes)
    send_bale(weather_msg, image_bytes)
    print("Weather sent.")

    # ۲. ارسال مقاله علمی (هر ۲ روز یک بار - بر اساس روز فرد/زوج)
    today = datetime.now().day
    if today % 2 == 0:  # فقط در روزهای زوج
        paper_msg = build_paper_message()
        if paper_msg:
            await send_telegram(paper_msg)
            send_bale(paper_msg)
            print("Paper sent.")

    # ۳. ارسال اخبار (هر ۱۲ ساعت - یعنی ۲ بار در روز)
    # برای سادگی، هر بار که این کد اجرا می‌شه، اخبار هم می‌ره. 
    # اگه می‌خوای فقط ۲ بار در روز باشه، باید در Workflow ساعت‌بندی کنیم.
    news_msg = build_news_message()
    await send_telegram(news_msg)
    send_bale(news_msg)
    print("News sent.")

    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())