async def main():
    print("=" * 60 + "\nگزارش جنوبگان - " + now_jalali() + "\n" + "=" * 60)
    
    now_tehran = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3, minutes=30)
    current_hour = now_tehran.hour
    is_even_day = (now_tehran.day % 2 == 0)
    
    # ۱. هشدار طوفان (همیشه بررسی می‌شود)
    weather_msg, alerts = build_weather_message()
    if alerts:
        alert_msg = "🚨 **هشدار فوری طوفان / کولاک شدید در قطب جنوب** 🚨\n\n📅 " + now_jalali() + "\n━━━━━━━━━━━━━━━\n\n"
        for a in alerts: alert_msg += f"⚠️ **{a['station']}**\n   💨 سرعت باد: {a['wind']} km/h\n   🌡️ دما: {a['temp']}°C\n\n"
        alert_msg += "━━━━━━━━━━━━━━━\n"
        await send_telegram(alert_msg)
        send_bale(alert_msg)
        print("Storm alert sent.")
    else:
        print("No storm alerts (wind < 50).")

    # ۲. داده‌های علمی (فقط اگر خبری باشد: Kp >= 5 یا زلزله)
    sci_msg = build_scientific_message()
    if sci_msg:
        await send_telegram(sci_msg)
        send_bale(sci_msg)
        print("Scientific data sent (activity detected).")
    else:
        print("No scientific activity (Kp < 5 and no earthquakes).")

    # ۳. آب‌وهوا، فعالیت‌ها و اخبار (ساعت ۶ و ۱۸ تهران)
    if current_hour in [6, 18]:
        image_bytes = get_webcam_image()
        await send_telegram(weather_msg, image_bytes)
        send_bale(weather_msg, image_bytes)
        print("Weather sent.")

        activity_msg = build_station_activity_message()
        await send_telegram(activity_msg)
        send_bale(activity_msg)
        print("Station activities sent.")

        news_msg = build_news_message()
        if news_msg:
            await send_telegram(news_msg)
            send_bale(news_msg)
            print("News sent.")
        else:
            print("No new news.")
    else:
        print("Not 6 or 18 Tehran, skipping weather/activities/news.")

    # ۴. مقاله علمی (روزهای فرد، ساعت ۶ صبح تهران)
    if current_hour == 6 and not is_even_day:
        paper_msg = build_paper_message()
        if paper_msg:
            await send_telegram(paper_msg)
            send_bale(paper_msg)
            print("Paper sent.")
        else:
            print("No new paper.")
    else:
        print("Not odd day at 6 AM, skipping paper.")

    # ۵. کتاب و معرفی ایستگاه (روزهای زوج، ساعت ۶ صبح تهران)
    if current_hour == 6 and is_even_day:
        book_msg = build_book_message()
        if book_msg:
            await send_telegram(book_msg)
            send_bale(book_msg)
            print("Book sent.")
        else:
            print("No new book.")

        profile_msg = build_station_profile_message()
        await send_telegram(profile_msg)
        send_bale(profile_msg)
        print("Station profile sent.")
    else:
        print("Not even day at 6 AM, skipping book/profile.")

    print("Done.")