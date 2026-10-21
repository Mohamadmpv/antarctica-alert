import asyncio
import os
import json
import requests
import re
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

WIND_THRESHOLD = 50  # آستانه هشدار طوفان

# --- ایستگاه‌های قطب جنوب ---
ANTARCTICA_STATIONS = [
    {"name": "Vostok (روسیه)", "lat": -78.4645, "lon": 106.8317, "coord": "۷۸°۲۷′ جنوبی، ۱۰۶°۵۰′ شرقی"},
    {"name": "Amundsen-Scott (آمریکا)", "lat": -90.0, "lon": 0.0, "coord": "۹۰° جنوبی"},
    {"name": "Novolazarevskaya (روسیه)", "lat": -70.7667, "lon": 11.8333, "coord": "۷۰°۴۶′ جنوبی، ۱۱°۵۰′ شرقی"},
    {"name": "Maitri (هند)", "lat": -70.7500, "lon": 11.7167, "coord": "۷۰°۴۵′ جنوبی، ۱۱°۴۳′ شرقی"},
    {"name": "Zhongshan (چین)", "lat": -69.3667, "lon": 76.3667, "coord": "۶۹°۲۲′ جنوبی، ۷۶°۲۲′ شرقی"},
    {"name": "Esperanza (آرژانتین)", "lat": -63.4000, "lon": -56.9833, "coord": "۶۳°۲۴′ جنوبی، ۵۶°۵۹′ غربی"},
]

# --- لیست معرفی ایستگاه‌ها (برای چرخش روزانه) ---
STATION_PROFILES = [
    {"name": "Vostok (روسیه)", "desc": "ایستگاه وستوک در ارتفاع ۳,۴۸۸ متری از سطح دریا قرار دارد و سردترین دمای ثبت‌شده روی زمین (منفی ۸۹.۲ درجه سانتی‌گراد) در این ایستگاه ثبت شده است. این ایستگاه به دلیل کشف هسته یخی که اطلاعات ۴۲۰,۰۰۰ ساله اقلیم زمین را در خود دارد، بسیار مشهور است."},
    {"name": "Amundsen-Scott (آمریکا)", "desc": "این ایستگاه دقیقاً در قطب جنوب جغرافیایی (۹۰ درجه جنوبی) قرار دارد. به دلیل موقعیت خاص خود، شش ماه از سال را در روشنایی کامل و شش ماه را در تاریکی مطلق سپری می‌کند. تحقیقات اصلی آن شامل نجوم، فیزیک جو و یخ‌شناسی است."},
    {"name": "Maitri (هند)", "desc": "ایستگاه میتری هند در منطقه ای با شرایط جوی نسبتاً ملایم‌تر قرار دارد و به عنوان پایگاهی برای تحقیقات زمین‌شناسی، یخ‌شناسی و مطالعه لایه ازن استفاده می‌شود. این ایستگاه در سال ۱۹۸۹ تأسیس شد."},
    {"name": "Zhongshan (چین)", "desc": "ایستگاه ژونگشان چین در خلیج پریدز واقع شده و به عنوان یک مرکز تحقیقاتی چندمنظوره فعالیت می‌کند. این ایستگاه در سال ۱۹۸۹ تأسیس شد و به مطالعه اقلیم، زیست‌شناسی دریایی و یخ‌شناسی می‌پردازد."},
    {"name": "Esperanza (آرژانتین)", "desc": "ایستگاه اسپرانزا آرژانتین یکی از معدود ایستگاه‌هایی است که در آن خانواده‌ها (با کودکان) نیز زندگی می‌کنند. این ایستگاه در سال ۱۹۵۲ تأسیس شد و به عنوان یک پایگاه دائمی آرژانتین در جنوبگان شناخته می‌شود."},
]

def get_gist_file(filename):
    url = "https://api.github.com/gists/" + str(GIST_ID)
    headers = {"Authorization": "token " + str(GH_PAT)}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        content = r.json()["files"].get(filename, {}).get("content", "")
        return content
    except Exception as e:
        print(f"Gist read error ({filename}):", e)
        return ""

def save_gist_file(filename, content):
    url = "https://api.github.com/gists/" + str(GIST_ID)
    headers = {"Authorization": "token " + str(GH_PAT)}
    data = {"files": {filename: {"content": content}}}
    try:
        r = requests.patch(url, headers=headers, json=data, timeout=30)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"Gist write error ({filename}):", e)
        return False

def get_gist_users(filename):
    content = get_gist_file(filename)
    try:
        return json.loads(content) if content else {}
    except Exception:
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

def get_kp_index():
    try:
        r = requests.get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json", timeout=30)
        r.raise_for_status()
        data = r.json()
        if len(data) > 1:
            return data[-1][1]
    except Exception as e:
        print("Kp NOAA error:", e)
    return None

def get_earthquakes():
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {"format": "geojson", "minlatitude": -90, "maxlatitude": -60, "minmagnitude": 4.0, "starttime": (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d"), "orderby": "time"}
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        return [{"mag": f["properties"]["mag"], "place": f["properties"]["place"]} for f in data["features"][:3]]
    except Exception as e:
        print("USGS error:", e)
        return []

def get_latest_paper():
    """دریافت مقاله جدید با چکیده از OpenAlex (اولویت) و CrossRef"""
    # تلاش اول: OpenAlex
    try:
        url = "https://api.openalex.org/works"
        params = {"filter": "title_and_abstract.search:Antarctica,from_publication_date:2026-01-01", "per-page": 1, "sort": "publication_date:desc"}
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data["results"]:
            item = data["results"][0]
            title = item.get("title", "بدون عنوان")
            doi = item.get("doi", "").replace("https://doi.org/", "")
            abstract = item.get("abstract_inverted_index", {})
            if abstract:
                words = {}
                for word, positions in abstract.items():
                    for pos in positions:
                        words[pos] = word
                abstract_text = " ".join(words[i] for i in sorted(words.keys()))
                if len(abstract_text) > 400:
                    abstract_text = abstract_text[:400] + "..."
            else:
                abstract_text = "چکیده در دسترس نیست."
            
            authors = item.get("authorships", [])
            first_author = authors[0]["author"]["display_name"] if authors else "نامشخص"
            
            return {"title": title, "link": f"https://doi.org/{doi}", "abstract": abstract_text, "author": first_author}
    except Exception as e:
        print("OpenAlex error:", e)
    
    # تلاش دوم: CrossRef
    try:
        url = "https://api.crossref.org/works"
        params = {"query": "Antarctica", "filter": "from-pub-date:2026-01-01,type:journal-article", "rows": 1, "sort": "published", "order": "desc"}
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data["message"]["items"]:
            item = data["message"]["items"][0]
            title = item.get("title", ["بدون عنوان"])[0]
            doi = item.get("DOI", "")
            abstract = item.get("abstract", "")
            if abstract:
                abstract = re.sub(r'<[^>]+>', '', abstract)
                abstract = ' '.join(abstract.split())
                if len(abstract) > 400:
                    abstract = abstract[:400] + "..."
            else:
                abstract = "چکیده در دسترس نیست."
            authors = item.get("author", [])
            first_author = authors[0].get("family", "نامشخص") if authors else "نامشخص"
            return {"title": title, "link": f"https://doi.org/{doi}", "abstract": abstract, "author": first_author}
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
        msg += f"   🗺️ مختصات: {st['coord']}\n"
        msg += f"   🗺️ [مشاهده روی نقشه](https://www.google.com/maps/search/?api=1&query={st['lat']},{st['lon']})\n"
        if wind and wind > WIND_THRESHOLD:
            alerts.append({"station": st["name"], "wind": wind, "temp": temp})
    
    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg, alerts

def build_scientific_message():
    msg = "🔬 **داده‌های علمی زنده** 🔬\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    
    kp = get_kp_index()
    if kp:
        msg += f"🌌 **شفق قطبی (شاخص Kp):** {kp}\n"
    else:
        msg += "🌌 **شفق قطبی:** داده در دسترس نیست\n"

    quakes = get_earthquakes()
    if quakes:
        msg += "\n🌍 **زمین‌لرزه‌های اخیر (M4+):**\n"
        for q in quakes:
            msg += f"   • M{q['mag']} - {q['place']}\n"
    else:
        msg += "\n🌍 **زمین‌لرزه‌ها:** داده در دسترس نیست\n"

    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg

def build_paper_message():
    paper = get_latest_paper()
    if not paper:
        return None
    msg = "📄 **مقاله علمی روز (جنوبگان)** 📄\n\n"
    msg += f"🔹 **{paper['title']}**\n\n"
    msg += f"👤 **نویسنده اول:** {paper['author']}\n\n"
    msg += f"📝 **چکیده:**\n{paper['abstract']}\n\n"
    msg += f"🔗 {paper['link']}\n"
    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg

def build_station_activity_message():
    """فعالیت‌های ایستگاه‌های قطب جنوب از اخبار رسمی"""
    msg = "🏗️ **فعالیت‌های ایستگاه‌های جنوبگان** 🏗️\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    
    activities = [
        {
            "title": "ایستگاه Casey (استرالیا): آغاز تابستان با فرود C-17",
            "text": "فصل تابستان در ایستگاه کیسی با فرود یک هواپیمای C-17 و رهاسازی ۱۸ چتر حاوی مواد غذایی، دارو و نامه‌ها آغاز شد. محموله‌های تازه شامل میوه و مرکبات نیز به ایستگاه رسید.",
            "link": "https://www.antarctica.gov.au/news/stations/casey/2026/16-october/"
        },
        {
            "title": "ایستگاه Mawson (استرالیا): زندگی روزمره و پژوهش",
            "text": "خدمه ایستگاه ماوسون در حال انجام وظایف روزانه مانند کمک در آشپزخانه، نگهداری از باغ سبزی هیدروپونیک و شرکت در تحقیقات مربوط به اثرات انزوا بر سلامت انسان هستند. آنها همچنین به دانشمندانی که از راه دور پروژه‌ها را مدیریت می‌کنند، کمک می‌کنند.",
            "link": "https://www.antarctica.gov.au/news/stations/mawson/2026/24-april/"
        }
    ]
    
    for act in activities:
        msg += f"🔹 **{act['title']}**\n   {act['text']}\n   🔗 {act['link']}\n\n"
    
    msg += "━━━━━━━━━━━━━━━\n"
    return msg

def build_station_profile_message():
    """معرفی روزانه یک ایستگاه (چرخشی)"""
    # انتخاب ایستگاه بر اساس روز ماه (چرخش خودکار)
    day_of_month = datetime.now().day
    profile = STATION_PROFILES[day_of_month % len(STATION_PROFILES)]
    
    msg = "🏛️ **معرفی ایستگاه جنوبگان** 🏛️\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    msg += f"📍 **{profile['name']}**\n\n"
    msg += f"{profile['desc']}\n"
    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg

async def send_telegram(msg, image_bytes=None):
    users = get_gist_users("antarctica_telegram_users.json")
    if not users:
        return
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
    if not users:
        return
    if not ANTARCTICA_BALE_TOKEN:
        return
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
    
    # ۱. پیام آب‌وهوا (همیشه)
    weather_msg, alerts = build_weather_message()
    image_bytes = get_webcam_image()
    await send_telegram(weather_msg, image_bytes)
    send_bale(weather_msg, image_bytes)
    print("Weather sent.")

    # ۲. هشدار فوری طوفان (جداگانه، اگر باد > ۵۰)
    if alerts:
        alert_msg = "🚨 **هشدار فوری طوفان در قطب جنوب** 🚨\n\n"
        alert_msg += "📅 " + now_jalali() + "\n"
        alert_msg += "━━━━━━━━━━━━━━━\n\n"
        for a in alerts:
            alert_msg += f"⚠️ **{a['station']}**\n   💨 باد: {a['wind']} km/h\n   🌡️ دما: {a['temp']}°C\n\n"
        alert_msg += "━━━━━━━━━━━━━━━\n"
        await send_telegram(alert_msg)
        send_bale(alert_msg)
        print("Storm alert sent.")

    # ۳. داده‌های علمی (شفق و زلزله)
    sci_msg = build_scientific_message()
    await send_telegram(sci_msg)
    send_bale(sci_msg)
    print("Scientific data sent.")

    # ۴. مقاله علمی روز
    paper_msg = build_paper_message()
    if paper_msg:
        await send_telegram(paper_msg)
        send_bale(paper_msg)
        print("Paper sent.")

    # ۵. فعالیت‌های ایستگاه‌ها (هر ۱۲ ساعت)
    activity_msg = build_station_activity_message()
    await send_telegram(activity_msg)
    send_bale(activity_msg)
    print("Station activities sent.")

    # ۶. معرفی ایستگاه (هر روز یک ایستگاه)
    profile_msg = build_station_profile_message()
    await send_telegram(profile_msg)
    send_bale(profile_msg)
    print("Station profile sent.")

    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())