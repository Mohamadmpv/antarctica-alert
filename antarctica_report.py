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

# --- ایستگاه‌های قطب جنوب با مختصات دقیق ---
ANTARCTICA_STATIONS = [
    {"name": "Vostok (روسیه)", "lat": -78.4645, "lon": 106.8317, "coord": "۷۸°۲۷′ جنوبی، ۱۰۶°۵۰′ شرقی"},
    {"name": "Amundsen-Scott (آمریکا)", "lat": -90.0, "lon": 0.0, "coord": "۹۰° جنوبی"},
    {"name": "Novolazarevskaya (روسیه)", "lat": -70.7667, "lon": 11.8333, "coord": "۷۰°۴۶′ جنوبی، ۱۱°۵۰′ شرقی"},
    {"name": "Maitri (هند)", "lat": -70.7500, "lon": 11.7167, "coord": "۷۰°۴۵′ جنوبی، ۱۱°۴۳′ شرقی"},
    {"name": "Zhongshan (چین)", "lat": -69.3667, "lon": 76.3667, "coord": "۶۹°۲۲′ جنوبی، ۷۶°۲۲′ شرقی"},
    {"name": "Esperanza (آرژانتین)", "lat": -63.4000, "lon": -56.9833, "coord": "۶۳°۲۴′ جنوبی، ۵۶°۵۹′ غربی"},
]

WIND_THRESHOLD = 50

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

def get_kp_index():
    try:
        r = requests.get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json", timeout=30)
        r.raise_for_status()
        data = r.json()
        if len(data) > 1: return data[-1][1]
        return None
    except Exception as e:
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
        return []

def get_latest_paper():
    url = "https://api.crossref.org/works"
    params = {"query": "Antarctica", "filter": "from-pub-date:2026-01-01,type:journal-article", "rows": 1, "sort": "published", "order": "desc"}
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data["message"]["items"]:
            item = data["message"]["items"][0]
            title = item.get("title", ["بدون عنوان"])[0]
            doi = item.get("DOI", "")
            abstract = item.get("abstract", "چکیده در دسترس نیست.")
            abstract = abstract.replace("<jats:p>", "").replace("</jats:p>", "").replace("<jats:title>", "").replace("</jats:title>", "")[:300] + "..."
            return {"title": title, "link": f"https://doi.org/{doi}", "abstract": abstract}
        return None
    except Exception as e:
        return None

def get_webcam_image():
    image_url = "https://gmd-int.cmdl.noaa.gov/obop/spo/latest.jpg"
    try:
        r = requests.get(image_url, timeout=30)
        if r.status_code == 200 and r.headers.get('content-type', '').startswith('image'): return r.content
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
        if wind and wind > WIND_THRESHOLD: alerts.append({"station": st["name"], "wind": wind})
    
    if alerts:
        msg += "\n🚨 **هشدار طوفان!**\n"
        for a in alerts: msg += f"⚠️ **{a['station']}**: {a['wind']} km/h\n"
    
    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg

def build_scientific_message():
    msg = "🔬 **داده‌های علمی زنده** 🔬\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    
    kp = get_kp_index()
    if kp: msg += f"🌌 **شفق قطبی (شاخص Kp):** {kp}\n"
    else: msg += "🌌 **شفق قطبی:** داده در دسترس نیست\n"

    quakes = get_earthquakes()
    if quakes:
        msg += "\n🌍 **زمین‌لرزه‌های اخیر (M4+):**\n"
        for q in quakes: msg += f"   • M{q['mag']} - {q['place']}\n"
    else:
        msg += "\n🌍 **زمین‌لرزه‌ها:** داده در دسترس نیست\n"

    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg

def build_paper_message():
    paper = get_latest_paper()
    if not paper: return None
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
            if image_bytes: await bot.send_photo(chat_id=cid, photo=InputFile(BytesIO(image_bytes), filename="south_pole.jpg"), caption=msg)
            else: await bot.send_message(chat_id=cid, text=msg)
        except Exception as e: print("  TG Failed:", cid, e)

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
        except Exception as e: print("  Bale Failed:", cid, e)

async def main():
    print("=" * 60 + "\nگزارش جنوبگان - " + now_jalali() + "\n" + "=" * 60)
    
    weather_msg = build_weather_message()
    image_bytes = get_webcam_image()
    await send_telegram(weather_msg, image_bytes)
    send_bale(weather_msg, image_bytes)
    print("Weather sent.")

    sci_msg = build_scientific_message()
    await send_telegram(sci_msg)
    send_bale(sci_msg)
    print("Scientific data sent.")

    paper_msg = build_paper_message()
    if paper_msg:
        await send_telegram(paper_msg)
        send_bale(paper_msg)
        print("Paper sent.")

    news_msg = build_news_message()
    await send_telegram(news_msg)
    send_bale(news_msg)
    print("News sent.")

    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())