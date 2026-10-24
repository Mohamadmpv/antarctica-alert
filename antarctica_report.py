async def main():
    print("=" * 60 + "\nگزارش جنوبگان - " + now_jalali() + "\n" + "=" * 60)
    
    # زمان فعلی تهران
    now_tehran = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3, minutes=30)
    current_hour = now_tehran.hour
    current_minute = now_tehran.minute
    
    # ۱. هشدار طوفان (هر ساعت بررسی می‌شود)
    weather_msg, alerts = build_weather_message()
    if alerts:
        alert_msg = "🚨 **هشدار فوری طوفان / کولاک شدید در قطب جنوب** 🚨\n\n📅 " + now_jalali() + "\n━━━━━━━━━━━━━━━\n\n"
        for a in alerts: alert_msg += f"⚠️ **{a['station']}**\n   💨 سرعت باد: {a['wind']} km/h\n   🌡️ دما: {a['temp']}°C\n\n"
        alert_msg += "━━━━━━━━━━━━━━━\n"
        await send_telegram(alert_msg)
        send_bale(alert_msg)
        print("Storm alert sent.")

    # ۲. داده‌های علمی (هر ساعت بررسی می‌شود)
    sci_msg = build_scientific_message()
    if sci_msg:
        await send_telegram(sci_msg)
        send_bale(sci_msg)
        print("Scientific data sent.")

    # ۳. آب‌وهوا + فعالیت‌ها (ساعت ۱۱ صبح و ۱۱ شب تهران)
    if (current_hour == 11 and 0 <= current_minute < 30) or (current_hour == 23 and 0 <= current_minute < 30):
        image_bytes = get_webcam_image()
        await send_telegram(weather_msg, image_bytes)
        send_bale(weather_msg, image_bytes)
        print("Weather sent.")

        activity_msg = build_station_activity_message()
        await send_telegram(activity_msg)
        send_bale(activity_msg)
        print("Station activities sent.")

    # ۴. اخبار (ساعت ۱۰:۳۰ صبح و ۱۰:۳۰ شب تهران)
    if (current_hour == 10 and 30 <= current_minute < 60) or (current_hour == 22 and 30 <= current_minute < 60):
        news_msg = build_news_message()
        if news_msg:
            await send_telegram(news_msg)
            send_bale(news_msg)
            print("News sent.")

    # ۵. مقاله علمی (ساعت ۸:۰۰ صبح تهران)
    if current_hour == 8 and 0 <= current_minute < 30:
        paper_msg = build_paper_message()
        if paper_msg:
            await send_telegram(paper_msg)
            send_bale(paper_msg)
            print("Paper sent.")

    # ۶. کتاب + معرفی ایستگاه (ساعت ۷:۰۰ صبح تهران)
    if current_hour == 7 and 0 <= current_minute < 30:
        book_msg = build_book_message()
        if book_msg:
            await send_telegram(book_msg)
            send_bale(book_msg)
            print("Book sent.")

        profile_msg = build_station_profile_message()
        await send_telegram(profile_msg)
        send_bale(profile_msg)
        print("Station profile sent.")

    print("Done.")