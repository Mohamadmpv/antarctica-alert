import time
import subprocess
from datetime import datetime, timezone, timedelta

def get_tehran_time():
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3, minutes=30)

last_run_hour = -1

print("🚀 سیستم ردیاب جنوبگان روشن شد (حالت کامپیوتر شخصی).")
print("منتظر ساعت‌های مقرر (۳، ۴، ۶، ۷، ۱۸، ۱۹) می‌مانم...")

while True:
    now = get_tehran_time()
    
    # دقیقاً راس هر ساعت اجرا کن
    if now.minute == 0 and last_run_hour != now.hour:
        print(f"\n⏰ ساعت {now.strftime('%H:%M')} تهران - اجرا...")
        try:
            subprocess.run(["python", "antarctica_report.py"], check=True)
        except Exception as e:
            print("خطا:", e)
        last_run_hour = now.hour

    elif now.minute != 0:
        last_run_hour = -1

    time.sleep(10)