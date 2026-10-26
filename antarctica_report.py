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

WIND_THRESHOLD = 50

ANTARCTICA_STATIONS = [
    {"name": "Vostok (روسیه)", "lat": -78.4645, "lon": 106.8317, "coord": "۷۸°۲۸′ جنوبی، ۱۰۶°۴۸′ شرقی"},
    {"name": "Amundsen-Scott (آمریکا)", "lat": -90.0, "lon": 0.0, "coord": "۹۰° جنوبی"},
    {"name": "Novolazarevskaya (روسیه)", "lat": -70.7667, "lon": 11.8333, "coord": "۷۰°۴۶′ جنوبی، ۱۱°۵۰′ شرقی"},
    {"name": "Maitri (هند)", "lat": -70.7500, "lon": 11.7167, "coord": "۷۰°۴۵′ جنوبی، ۱۱°۴۳′ شرقی"},
    {"name": "Zhongshan (چین)", "lat": -69.3667, "lon": 76.3667, "coord": "۶۹°۲۲′ جنوبی، ۷۶°۲۲′ شرقی"},
    {"name": "Esperanza (آرژانتین)", "lat": -63.4000, "lon": -56.9833, "coord": "۶۳°۲۴′ جنوبی، ۵۶°۵۹′ غربی"},
    {"name": "Casey (استرالیا)", "lat": -66.2833, "lon": 110.5167, "coord": "۶۶°۱۷′ جنوبی، ۱۱۰°۳۱′ شرقی"},
    {"name": "Davis (استرالیا)", "lat": -68.5764, "lon": 77.9694, "coord": "۶۸°۳۴′ جنوبی، ۷۷°۵۸′ شرقی"},
    {"name": "Mawson (استرالیا)", "lat": -67.6028, "lon": 62.8731, "coord": "۶۷°۳۶′ جنوبی، ۶۲°۵۲′ شرقی"},
    {"name": "Rothera (بریتانیا)", "lat": -67.5686, "lon": -68.1269, "coord": "۶۷°۳۴′ جنوبی، ۶۸°۰۷′ غربی"},
    {"name": "Halley (بریتانیا)", "lat": -75.5833, "lon": -26.5000, "coord": "۷۵°۳۵′ جنوبی، ۲۶°۳۰′ غربی"},
    {"name": "Sejong (کره جنوبی)", "lat": -62.2167, "lon": -58.7833, "coord": "۶۲°۱۳′ جنوبی، ۵۸°۴۷′ غربی"},
]

HISTORY_NOTES = [
    "عصر قهرمانان اکتشاف جنوبگان (دهه ۱۹۰۰): رقابت برای رسیدن به قطب جنوب، با پیروزی روآلد آموندسن نروژی در دسامبر ۱۹۱۱ و تراژدی رابرت اسکات بریتانیایی.",
    "سال بین‌المللی ژئوفیزیک (۱۹۵۷-۱۹۵۸): ۱۲ کشور با تأسیس ۴۷ ایستگاه تحقیقاتی، همکاری علمی بی‌سابقه‌ای را در جنوبگان آغاز کردند.",
    "پیمان جنوبگان (۱۹۵۹): با امضای ۱۲ کشور، جنوبگان به منطقه‌ای غیرنظامی و مختص تحقیقات صلح‌آمیز تبدیل شد. این پیمان در سال ۱۹۶۱ لازم‌الاجرا شد و امروز ۵۸ عضو دارد.",
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

def check_already_sent(section):
    sent_status = get_gist_users("last_sent_status.json")
    last_sent_str = sent_status.get(section)
    if last_sent_str:
        try:
            last_sent = datetime.fromisoformat(last_sent_str)
            now = datetime.now()
            if (now - last_sent).total_seconds() < 4 * 3600:
                return True
        except Exception:
            pass
    return False

def mark_as_sent(section):
    sent_status = get_gist_users("last_sent_status.json")
    sent_status[section] = datetime.now().isoformat()
    save_gist_file("last_sent_status.json", json.dumps(sent_status, ensure_ascii=False, indent=2))

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
        print("Kp NOAA error (skipped):", e)
    return None

def get_earthquakes():
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {"format": "geojson", "minlatitude": -90, "maxlatitude": -60, "minmagnitude": 4.0, "starttime": (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d"), "orderby": "time"}
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        sent_quakes = get_gist_users("sent_quakes.json")
        new_quakes = []
        for f in data["features"][:5]:
            mag = f["properties"]["mag"]
            place = f["properties"]["place"]
            quake_key = f"{mag}_{place}"
            if quake_key not in sent_quakes:
                new_quakes.append({"mag": mag, "place": place})
                sent_quakes[quake_key] = datetime.now().isoformat()
        if new_quakes:
            save_gist_file("sent_quakes.json", json.dumps(sent_quakes, ensure_ascii=False, indent=2))
        return new_quakes
    except Exception as e:
        print("USGS error (skipped):", e)
        return []

def get_latest_paper():
    try:
        url = "https://api.crossref.org/works"
        params = {"filter": "issn:0954-1020,from-pub-date:2026-01-01,type:journal-article", "rows": 1, "sort": "published", "order": "desc"}
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
                if len(abstract) > 400: abstract = abstract[:400] + "..."
            else: abstract = "چکیده در دسترس نیست."
            authors = item.get("author", [])
            first_author = authors[0].get("family", "نامشخص") if authors else "نامشخص"
            return {"title": title, "link": f"https://doi.org/{doi}", "abstract": abstract, "author": first_author}
    except Exception as e:
        print("Crossref error (skipped):", e)
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
    kp = get_kp_index()
    quakes = get_earthquakes()
    if (kp is None or float(kp) < 5) and not quakes:
        return None
    msg = "🔬 **داده‌های علمی زنده** 🔬\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    if kp and float(kp) >= 5:
        msg += f"🌌 **شفق قطبی (شاخص Kp):** {kp} (فعال!)\n\n"
    if quakes:
        msg += "🌍 **زمین‌لرزه‌های جدید (M4+):**\n"
        for q in quakes: msg += f"   • M{q['mag']} - {q['place']}\n"
    else:
        msg += "🌍 **زمین‌لرزه‌ها:** زلزله جدیدی ثبت نشده است.\n"
    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg

def build_paper_message():
    sent_papers = get_gist_users("sent_papers.json")
    paper = get_latest_paper()
    if not paper: return None
    paper_id = paper['link']
    if paper_id in sent_papers: return None
    sent_papers[paper_id] = datetime.now().isoformat()
    save_gist_file("sent_papers.json", json.dumps(sent_papers, ensure_ascii=False, indent=2))
    msg = "📄 **مقاله علمی روز (جنوبگان)** 📄\n\n"
    msg += f"🔹 **{paper['title']}**\n\n"
    msg += f"👤 **نویسنده اول:** {paper['author']}\n\n"
    msg += f"📝 **چکیده:**\n{paper['abstract']}\n\n"
    msg += f"🔗 {paper['link']}\n"
    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg

def build_book_message():
    sent_books = get_gist_users("sent_books.json")
    book_pool = [
        {"title": "Where the Earth Meets the Sky", "author": "Louise K. Blight", "year": "2026", "desc": "سفرنامه علمی از یک فصل کار میدانی روی پنگوئن‌های آدلی در جزیره راس. ترکیبی از علم، طبیعت‌نویسی و تجربه انسانی در جنوبگان.", "link": "https://www.goodreads.com"},
        {"title": "All About Antarctica", "author": "Marc Martin", "year": "2026", "desc": "یک کتاب مصور و آموزشی برای معرفی جنوبگان به مخاطب عمومی و نوجوان.", "link": "https://www.goodreads.com"},
        {"title": "Antarctic Materialities", "author": "Various Authors", "year": "2026", "desc": "کتابی دانشگاهی درباره تاریخ، سیاست و ماده‌مندی جنوبگان.", "link": "https://www.berghahnbooks.com"},
        {"title": "From the Amazon to Antarctica", "author": "Kim Bong-chul", "year": "2026", "desc": "کتابی درباره بحران اقلیمی که آمازون و جنوبگان را به هم پیوند می‌دهد.", "link": "https://www.goodreads.com"},
    ]
    available_books = [b for b in book_pool if b['title'] not in sent_books]
    if not available_books:
        sent_books = {}
        available_books = book_pool
    book = available_books[0]
    sent_books[book['title']] = datetime.now().isoformat()
    save_gist_file("sent_books.json", json.dumps(sent_books, ensure_ascii=False, indent=2))
    msg = "📚 **معرفی کتاب جنوبگان** 📚\n\n"
    msg += f"🔹 **{book['title']}**\n\n"
    msg += f"✍️ **نویسنده:** {book['author']} ({book['year']})\n\n"
    msg += f"📝 **توضیح:**\n{book['desc']}\n\n"
    msg += f"🔗 {book['link']}\n"
    msg += "\n━━━━━━━━━━━━━━━\n"
    return msg

def build_news_message():
    sent_news = get_gist_users("sent_news.json")
    news_pool = [
        {"id": "aap_casey_airdrop_2026", "title": "آغاز تابستان در ایستگاه کیسی با فرود C-17", "text": "فصل تابستان در ایستگاه کیسی با فرود یک هواپیمای C-17 و رهاسازی ۱۸ چتر حاوی مواد غذایی، دارو و نامه‌ها آغاز شد.", "link": "https://www.antarctica.gov.au/news/stations/casey/2026/16-october/"},
        {"id": "aap_ice_drill_2026", "title": "حفاری ۴۰۰ متری دانشمندان استرالیایی", "text": "دانشمندان استرالیایی ۴۰۰ متر در ورقه یخی جنوبگان حفاری کردند تا یخی را که در پایان آخرین عصر یخبندان تشکیل شده بود، استخراج کنند.", "link": "https://www.antarctica.gov.au/news/2026/ice-age-drillers/"}
    ]
    new_news = []
    for news in news_pool:
        if news["id"] not in sent_news:
            new_news.append(news)
            sent_news[news["id"]] = datetime.now().isoformat()
    if not new_news: return None
    save_gist_file("sent_news.json", json.dumps(sent_news, ensure_ascii=False, indent=2))
    msg = "📰 **اخبار و پژوهش‌های جنوبگان** 📰\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    for n in new_news:
        msg += f"🔹 **{n['title']}**\n   {n['text']}\n   🔗 {n['link']}\n\n"
    msg += "━━━━━━━━━━━━━━━\n"
    return msg

def build_station_activity_message():
    msg = "🏗️ **فعالیت‌های ایستگاه‌های جنوبگان** 🏗️\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    activities = [
        {"title": "ایستگاه Casey (استرالیا): آغاز تابستان", "text": "فصل تابستان با فرود هواپیمای C-17 و رهاسازی ۱۸ چتر حاوی مواد غذایی و دارو آغاز شد.", "link": "https://www.antarctica.gov.au/news/stations/casey/2026/16-october/"},
        {"title": "ایستگاه Mawson (استرالیا): زندگی روزمره", "text": "خدمه در حال انجام وظایف روزانه مانند کمک در آشپزخانه، باغ هیدروپونیک و تحقیقات مربوط به انزوا هستند.", "link": "https://www.antarctica.gov.au/news/stations/mawson/2026/24-april/"}
    ]
    for act in activities:
        msg += f"🔹 **{act['title']}**\n   {act['text']}\n   🔗 {act['link']}\n\n"
    msg += "━━━━━━━━━━━━━━━\n"
    return msg

def build_station_profile_message():
    sent_profiles = get_gist_users("sent_profiles.json")
    available_stations = [s for s in ANTARCTICA_STATIONS if s['name'] not in sent_profiles]
    if not available_stations:
        sent_profiles = {}
        available_stations = ANTARCTICA_STATIONS
    station = available_stations[0]
    sent_profiles[station['name']] = datetime.now().isoformat()
    save_gist_file("sent_profiles.json", json.dumps(sent_profiles, ensure_ascii=False, indent=2))
    history_note = HISTORY_NOTES[datetime.now().day % len(HISTORY_NOTES)]
    msg = "🏛️ **معرفی ایستگاه جنوبگان** 🏛️\n\n📅 " + now_jalali() + "\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    msg += f"📍 **{station['name']}**\n"
    msg += f"🗺️ **مختصات:** {station['coord']}\n\n"
    msg += f"📜 **نکته تاریخی:**\n{history_note}\n"
    msg += "\n━━━━━━━━━━━━━━━\n"
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
    
    now_tehran = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3, minutes=30)
    current_hour = now_tehran.hour
    
    # ۱. هشدار طوفان
    try:
        weather_msg, alerts = build_weather_message()
        if alerts:
            alert_msg = "🚨 **هشدار فوری طوفان / کولاک شدید در قطب جنوب** 🚨\n\n📅 " + now_jalali() + "\n━━━━━━━━━━━━━━━\n\n"
            for a in alerts: alert_msg += f"⚠️ **{a['station']}**\n   💨 سرعت باد: {a['wind']} km/h\n   🌡️ دما: {a['temp']}°C\n\n"
            alert_msg += "━━━━━━━━━━━━━━━\n"
            await send_telegram(alert_msg)
            send_bale(alert_msg)
            print("Storm alert sent.")
    except Exception as e:
        print("Weather build error:", e)
        weather_msg = "داده‌های آب‌وهوا در دسترس نیست."

    # ۲. داده‌های علمی
    try:
        sci_msg = build_scientific_message()
        if sci_msg:
            await send_telegram(sci_msg)
            send_bale(sci_msg)
            print("Scientific data sent.")
    except Exception as e:
        print("Scientific error:", e)

    # ۳. کتاب (بازه ۳ تا ۵ صبح با جلوگیری از تکرار)
    if 3 <= current_hour <= 5 and not check_already_sent("book"):
        try:
            book_msg = build_book_message()
            if book_msg:
                await send_telegram(book_msg)
                send_bale(book_msg)
                mark_as_sent("book")
                print("Book sent.")

            profile_msg = build_station_profile_message()
            await send_telegram(profile_msg)
            send_bale(profile_msg)
            print("Station profile sent.")
        except Exception as e:
            print("Book/Profile error:", e)

    # ۴. مقاله (بازه ۴ تا ۶ صبح با جلوگیری از تکرار)
    if 4 <= current_hour <= 6 and not check_already_sent("paper"):
        try:
            paper_msg = build_paper_message()
            if paper_msg:
                await send_telegram(paper_msg)
                send_bale(paper_msg)
                mark_as_sent("paper")
                print("Paper sent.")
        except Exception as e:
            print("Paper error:", e)

    # ۵. اخبار (بازه ۶ تا ۸ صبح با جلوگیری از تکرار)
    if 6 <= current_hour <= 8 and not check_already_sent("news"):
        try:
            news_msg = build_news_message()
            if news_msg:
                await send_telegram(news_msg)
                send_bale(news_msg)
                mark_as_sent("news")
                print("News sent.")
        except Exception as e:
            print("News error:", e)

    # ۶. آب‌وهوا و فعالیت‌ها (بازه ۷ تا ۹ صبح با جلوگیری از تکرار)
    if 7 <= current_hour <= 9 and not check_already_sent("weather"):
        try:
            image_bytes = get_webcam_image()
            await send_telegram(weather_msg, image_bytes)
            send_bale(weather_msg, image_bytes)
            mark_as_sent("weather")
            print("Weather sent.")

            activity_msg = build_station_activity_message()
            await send_telegram(activity_msg)
            send_bale(activity_msg)
            print("Station activities sent.")
        except Exception as e:
            print("Weather/Activity error:", e)

    # ۷. آب‌وهوای شب (بازه ۱۹ تا ۲۱ با جلوگیری از تکرار)
    if 19 <= current_hour <= 21 and not check_already_sent("evening_weather"):
        try:
            image_bytes = get_webcam_image()
            await send_telegram(weather_msg, image_bytes)
            send_bale(weather_msg, image_bytes)
            mark_as_sent("evening_weather")
            print("Evening weather sent.")
        except Exception as e:
            print("Evening weather error:", e)

    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())