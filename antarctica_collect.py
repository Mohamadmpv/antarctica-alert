import os
import json
import requests

ANTARCTICA_TELEGRAM_TOKEN = os.getenv("ANTARCTICA_TELEGRAM_TOKEN")
ANTARCTICA_BALE_TOKEN = os.getenv("ANTARCTICA_BALE_TOKEN")
GIST_ID = os.getenv("GIST_ID")
GH_PAT = os.getenv("GH_PAT")

def get_gist_file(filename):
    url = "https://api.github.com/gists/" + GIST_ID
    headers = {"Authorization": "token " + GH_PAT}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()["files"].get(filename, {}).get("content", "")
    except Exception:
        return ""

def save_gist_file(filename, content):
    url = "https://api.github.com/gists/" + GIST_ID
    headers = {"Authorization": "token " + GH_PAT}
    data = {"files": {filename: {"content": content}}}
    try:
        r = requests.patch(url, headers=headers, json=data, timeout=30)
        r.raise_for_status()
        return True
    except Exception:
        return False

def get_offset(filename):
    content = get_gist_file(filename)
    try:
        return int(content.strip()) if content else 0
    except Exception:
        return 0

def save_offset(filename, offset):
    return save_gist_file(filename, str(offset))

def collect_telegram():
    print("Collecting Telegram users for Antarctica...")
    users = json.loads(get_gist_file("antarctica_telegram_users.json") or "{}")
    offset = get_offset("antarctica_offset_telegram.txt")
    url = f"https://api.telegram.org/bot{ANTARCTICA_TELEGRAM_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": offset, "timeout": 10}, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("Telegram error:", e)
        return
    if not data.get("ok"): return
    updates = data.get("result", [])
    new_count = 0
    last_id = offset
    for u in updates:
        last_id = u.get("update_id", last_id)
        msg = u.get("message")
        if not msg: continue
        chat_id = str(msg["chat"]["id"])
        name = msg["chat"].get("first_name", "Unknown")
        if chat_id not in users:
            users[chat_id] = name
            new_count += 1
            print("NEW Telegram:", chat_id, name)
    if new_count > 0:
        save_gist_file("antarctica_telegram_users.json", json.dumps(users, ensure_ascii=False, indent=2))
    if last_id > 0:
        save_offset("antarctica_offset_telegram.txt", last_id + 1)
    print("Total Telegram users:", len(users))

def collect_bale():
    print("Collecting Bale users for Antarctica...")
    users = json.loads(get_gist_file("antarctica_bale_users.json") or "{}")
    offset = get_offset("antarctica_offset_bale.txt")
    url = f"https://tapi.bale.ai/bot{ANTARCTICA_BALE_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": offset, "timeout": 10}, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("Bale error:", e)
        return
    if not data.get("ok"): return
    updates = data.get("result", [])
    new_count = 0
    last_id = offset
    for u in updates:
        last_id = u.get("update_id", last_id)
        msg = u.get("message")
        if not msg: continue
        chat_id = str(msg["chat"]["id"])
        name = msg["chat"].get("first_name", "Unknown")
        if chat_id not in users:
            users[chat_id] = name
            new_count += 1
            print("NEW Bale:", chat_id, name)
    if new_count > 0:
        save_gist_file("antarctica_bale_users.json", json.dumps(users, ensure_ascii=False, indent=2))
    if last_id > 0:
        save_offset("antarctica_offset_bale.txt", last_id + 1)
    print("Total Bale users:", len(users))

if __name__ == "__main__":
    collect_telegram()
    collect_bale()