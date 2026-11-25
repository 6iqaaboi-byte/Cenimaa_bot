import json
import os

import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

SITE_URL = "https://cfc.scenecinemas.com/"
STATE_FILE = "movies.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CinemaBot/1.0)"}
API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(text, chat_id=None):
    try:
        r = requests.post(
            f"{API}/sendMessage",
            data={"chat_id": chat_id or CHAT_ID, "text": text},
            timeout=20,
        )
        print("Telegram:", r.status_code, r.text[:200], flush=True)
    except requests.RequestException as e:
        print("Telegram send error:", e)


def fetch_movies():
    print("Fetching site...", flush=True)
    r = requests.get(SITE_URL, headers=HEADERS, timeout=(10, 20))
    print("Site status:", r.status_code, flush=True)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    movies = {}
    for a in soup.select('a[href*="/movie-details/"]'):
        href = a.get("href", "").strip()
        title = (a.get("title") or "").strip()
        if href and title and href not in movies:
            movies[href] = title
    print("Movies found:", len(movies), flush=True)
    return movies


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_state(movies):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)


def handle_commands(movies):
    try:
        updates = requests.get(f"{API}/getUpdates", timeout=20).json().get("result", [])
    except Exception as e:
        print("Updates error:", e)
        return

    for upd in updates:
        msg = upd.get("message") or {}
        text = (msg.get("text") or "").strip().lower()
        chat_id = (msg.get("chat") or {}).get("id")
        if not chat_id:
            continue
        if text.startswith("/count"):
            send_message(f"عدد الأفلام دلوقتي: {len(movies)}", chat_id)
        elif text.startswith("/list"):
            lines = [f"{i}. {t}" for i, t in enumerate(movies.values(), 1)]
            send_message("\n".join(lines) or "مفيش أفلام", chat_id)

    if updates:
        requests.get(
            f"{API}/getUpdates",
            params={"offset": updates[-1]["update_id"] + 1},
            timeout=20,
        )


def main():
    current = fetch_movies()
    if not current:
        print("No movies found, skipping (maybe the site layout changed).")
        return

    known = load_state()

    if known is None:
        save_state(current)
        send_message(f"البوت اشتغل ✅\nعدد الأفلام دلوقتي: {len(current)}")
    else:
        new_urls = [u for u in current if u not in known]
        for url in new_urls:
            send_message(f"🎬 فيلم جديد نزل: {current[url]}\n{url}")
        if new_urls:
            known.update({u: current[u] for u in new_urls})
            save_state(known)

    print("Handling commands...", flush=True)
    handle_commands(current)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
