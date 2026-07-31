"""
BookMyShow show-availability watcher.

Checks a specific theatre's page for a specific movie, on a specific date tab.
If showtimes are now listed (and weren't before), sends a Telegram notification.

State is stored in state.json (committed back to the repo by the GitHub Action)
so the script remembers whether it already found/alerted, and doesn't spam you
on every run.
"""

import os
import sys
import json
import re
import requests
from playwright.sync_api import sync_playwright

# ---------- CONFIG (comes from environment variables set in GitHub Actions) ----------
THEATRE_URL = os.environ["THEATRE_URL"]          # e.g. the buytickets URL for INOX Pacific Mall
MOVIE_NAME = os.environ["MOVIE_NAME"]            # e.g. "Spider-Man: Brand New Day"
TARGET_DAY_NUM = os.environ["TARGET_DAY_NUM"]    # e.g. "01"  (the day-of-month shown on the date tab)
TARGET_DAY_LABEL = os.environ.get("TARGET_DAY_LABEL", "")  # optional e.g. "SAT" for extra matching safety

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state.json"


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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )

        print(f"Opening {THEATRE_URL}")
        # NOTE: THEATRE_URL is expected to already contain the target date
        # baked into the URL path (BookMyShow's buytickets URLs end in a
        # YYYYMMDD date segment, e.g. .../buytickets/IPMJ/20260804).
        # This means the page should load directly showing that date's
        # listings, with no need to click a date tab. As a safety net, we
        # still attempt to click a matching date-tab element if one is
        # found and clickable, but we don't fail if it isn't.
        page.goto(THEATRE_URL, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)  # let JS render

        # ---- Step 1 (best-effort safety net): try clicking a date tab too ----
        try:
            candidates = page.locator(f"text='{TARGET_DAY_NUM}'")
            count = candidates.count()
            print(f"Found {count} elements with text '{TARGET_DAY_NUM}' (best-effort click attempt)")
            if count > 0:
                try:
                    candidates.first.click(timeout=3000)
                    print("Clicked a date-tab candidate as extra safety net.")
                except Exception as e:
                    print(f"Could not click date tab (not necessarily a problem, URL date should already apply): {e}")
        except Exception as e:
            print("Date tab click step skipped:", e)

        page.wait_for_timeout(3000)  # let showtimes re-render if anything changed

        # ---- Step 2: find the movie's section and check for showtime elements ----
        page_text = page.inner_text("body")

        # Save full text for debugging (uploaded as a GitHub Actions artifact)
        with open("debug_page_text.txt", "w", encoding="utf-8") as f:
            f.write(page_text)

        page.screenshot(path="debug_screenshot.png", full_page=True)

        movie_found_in_text = MOVIE_NAME.lower() in page_text.lower()
        print(f"Movie name appears in page text: {movie_found_in_text}")

        shows_available = False

        if movie_found_in_text:
            # Try to isolate the block of text right after the movie name and
            # look for time-like patterns (e.g. "07:50 AM", "11:20 PM") near it.
            idx = page_text.lower().find(MOVIE_NAME.lower())
            # Look at a window of text after the movie name (next ~800 characters,
            # roughly covers that movie's showtime rows before the next movie title)
            window = page_text[idx: idx + 800]
            time_pattern = re.compile(r"\b\d{1,2}:\d{2}\s?(AM|PM)\b", re.IGNORECASE)
            matches = time_pattern.findall(window)
            print(f"Time-like matches found near movie name: {len(matches)}")
            if matches:
                shows_available = True

        browser.close()

    # ---- Step 3: compare to previous state, notify if newly available ----
    already_notified = state.get("found", False)

    if shows_available and not already_notified:
        msg = (
            f"🎬 Tickets are now LIVE!\n\n"
            f"Movie: {MOVIE_NAME}\n"
            f"Date tab: {TARGET_DAY_LABEL} {TARGET_DAY_NUM}\n"
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
        # If it previously said "found" but now doesn't (e.g. date rolled over),
        # you could reset state here manually between runs/weeks.

    print("Done.")


if __name__ == "__main__":
    main()
