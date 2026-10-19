import jdatetime
from datetime import datetime


def _add_period(hour_str):
    """
    اضافه کردن صبح/عصر/شب به ساعت 24 ساعته.
    """
    try:
        h, m = hour_str.split(":")
        h = int(h)
        if 0 <= h < 5:
            period = "بامداد"
        elif 5 <= h < 12:
            period = "صبح"
        elif 12 <= h < 17:
            period = "بعدازظهر"
        elif 17 <= h < 20:
            period = "عصر"
        else:
            period = "شب"
        return hour_str + " " + period
    except Exception:
        return hour_str


def to_jalali(iso_time_str):
    """
    تبدیل زمان ISO به شمسی.
    ورودی: 2026-10-07T21:00
    خروجی: 1405/07/15 - 21:00 شب
    """
    try:
        if "T" in iso_time_str:
            date_part, time_part = iso_time_str.split("T")
            hour_min = time_part[:5]
        else:
            date_part = iso_time_str
            hour_min = "00:00"

        y, m, d = date_part.split("-")
        g_date = jdatetime.date.fromgregorian(
            year=int(y), month=int(m), day=int(d)
        )
        date_str = g_date.strftime("%Y/%m/%d")
        time_str = _add_period(hour_min)
        return date_str + " - " + time_str
    except Exception:
        return iso_time_str


def now_jalali():
    """زمان فعلی به شمسی"""
    now = datetime.now()
    g_date = jdatetime.date.fromgregorian(
        year=now.year, month=now.month, day=now.day
    )
    time_str = _add_period(now.strftime("%H:%M"))
    return g_date.strftime("%Y/%m/%d") + " ساعت " + time_str