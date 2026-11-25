import json
import os
import threading
import time

import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
CHAT_ID = os.getenv("CHAT_ID", "PUT_YOUR_CHAT_ID_HERE")

SITE_URL = "https://cfc.scenecinemas.com/"
CHECK_EVERY = 300  # كل 5 دقايق
STATE_FILE = "movies.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CinemaBot/1.0)"}
API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(text, chat_id=None):
    try:
        requests.post(
            f"{API}/sendMessage",
            data={"chat_id": chat_id or CHAT_ID, "text": text},
            timeout=20,
        )
    except requests.RequestException as e:
        print("Telegram send error:", e)


def fetch_movies():
    r = requests.get(SITE_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    movies = {}
    for a in soup.select('a[href*="/movie-details/"]'):
        href = a.get("href", "").strip()
        title = (a.get("title") or "").strip()
        if not href or not title:
            continue
        if href not in movies:
            movies[href] = title
    return movies


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_state(movies):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)


def monitor():
    known = load_state()
    first_run = known is None
    known = known or {}

    while True:
        try:
            current = fetch_movies()

            if first_run:
                save_state(current)
                known = current
                first_run = False
                send_message(f"البوت اشتغل ✅\nعدد الأفلام دلوقتي: {len(current)}")
            else:
                new_urls = [u for u in current if u not in known]
                for url in new_urls:
                    send_message(f"🎬 فيلم جديد نزل: {current[url]}\n{url}")
                if new_urls:
                    known.update({u: current[u] for u in new_urls})
                    save_state(known)
        except Exception as e:
            print("Check error:", e)

        time.sleep(CHECK_EVERY)


def listen_commands():
    offset = None
    while True:
        try:
            r = requests.get(
                f"{API}/getUpdates",
                params={"timeout": 30, "offset": offset},
                timeout=40,
            )
            for upd in r.json().get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                text = (msg.get("text") or "").strip().lower()
                chat_id = (msg.get("chat") or {}).get("id")
                if not chat_id:
                    continue

                if text.startswith("/count"):
                    movies = fetch_movies()
                    send_message(f"عدد الأفلام دلوقتي: {len(movies)}", chat_id)
                elif text.startswith("/list"):
                    movies = fetch_movies()
                    lines = [f"{i}. {t}" for i, t in enumerate(movies.values(), 1)]
                    send_message("\n".join(lines) or "مفيش أفلام", chat_id)
        except Exception as e:
            print("Listen error:", e)
            time.sleep(5)


if __name__ == "__main__":
    threading.Thread(target=listen_commands, daemon=True).start()
    monitor()
