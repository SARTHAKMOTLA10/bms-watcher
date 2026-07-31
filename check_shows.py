"""
BookMyShow show-availability watcher — OLD VERSION (date-redirect signal only).

NOTE: This version does NOT check for Cloudflare/bot-detection block pages,
and does NOT require the movie name to be found. It relies solely on
whether the URL's date segment stays put after loading (vs redirecting
back to today). We now know this can produce FALSE POSITIVES when
Cloudflare blocks the request, because the block page renders at the same
URL without redirecting - which looks identical to "date is live" to this
version of the script.

Kept only for testing/comparison purposes.
"""

import os
import re
import json
import requests
from playwright.sync_api import sync_playwright

THEATRE_URL = os.environ["THEATRE_URL"]
MOVIE_NAME = os.environ["MOVIE_NAME"]
TARGET_DAY_LABEL = os.environ.get("TARGET_DAY_LABEL", "")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state.json"


def extract_date_segment(url: str):
    match = re.search(r"(\d{8})(?:[/?#]|$)", url)
    return match.group(1) if match else None


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
        print("Telegram response:", r.status_code, r.text[:200])
    except Exception as e:
        print("Failed to send Telegram message:", e)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"found": False}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def main():
    state = load_state()

    requested_date = extract_date_segment(THEATRE_URL)
    print(f"Requested date segment: {requested_date}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )

        print(f"Opening {THEATRE_URL}")
        page.goto(THEATRE_URL, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        final_url = page.url
        final_date = extract_date_segment(final_url)
        print(f"Final URL after load: {final_url}")
        print(f"Final date segment: {final_date}")

        date_stayed_on_target = (requested_date is not None and final_date == requested_date)
        print(f"Date stayed on target (main signal): {date_stayed_on_target}")

        page_text = page.inner_text("body")
        with open("debug_page_text.txt", "w", encoding="utf-8") as f:
            f.write(page_text)
        page.screenshot(path="debug_screenshot.png", full_page=True)

        movie_found_in_text = MOVIE_NAME.lower() in page_text.lower()
        print(f"Movie name appears in page text (informational only, not required): {movie_found_in_text}")

        browser.close()

    # OLD LOGIC: relies solely on the date signal - known to false-positive on Cloudflare blocks.
    shows_available = date_stayed_on_target

    already_notified = state.get("found", False)

    if shows_available and not already_notified:
        msg = (
            f"🎬 Tickets are now LIVE! (OLD SCRIPT - unverified, may be false positive)\n\n"
            f"Movie: {MOVIE_NAME}\n"
            f"Date: {TARGET_DAY_LABEL} ({requested_date})\n"
            f"Book now: {THEATRE_URL}"
        )
        print("New shows detected — sending Telegram alert.")
        send_telegram(msg)
        state["found"] = True
        save_state(state)
    elif shows_available and already_notified:
        print("Shows available, but already notified previously — skipping duplicate alert.")
    else:
        print("No shows found yet for target date/movie.")

    print("Done.")


if __name__ == "__main__":
    main()
