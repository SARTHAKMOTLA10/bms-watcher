"""
BookMyShow show-availability watcher.

Logic (discovered empirically):
- BookMyShow's buytickets URL ends in a date segment (YYYYMMDD), e.g.
  .../buytickets/IPMJ/20260807
- If that date's bookings are NOT yet released, BookMyShow silently
  redirects you back to TODAY's date page instead.
- If that date's bookings ARE released, it stays on the requested date
  and shows the listings.

So the most reliable signal is simply: after loading THEATRE_URL, check
whether the resulting page URL still contains our requested date, or
whether it got redirected back to today. If it stayed put, tickets are
live -> notify. If it got redirected, they're not live yet -> do nothing.

As a secondary confirmation (belt-and-suspenders), we also check that the
target movie name appears somewhere in the page text.

State is stored in state.json (committed back to the repo by the GitHub
Action) so the script remembers whether it already alerted, and doesn't
spam you on every run.
"""

import os
import re
import json
import requests
from playwright.sync_api import sync_playwright

# ---------- CONFIG (from environment variables set in GitHub Actions) ----------
THEATRE_URL = os.environ["THEATRE_URL"]          # full buytickets URL including target YYYYMMDD date
MOVIE_NAME = os.environ["MOVIE_NAME"]            # e.g. "Spider-Man: Brand New Day"
TARGET_DAY_LABEL = os.environ.get("TARGET_DAY_LABEL", "")  # optional, just for the alert message

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state.json"


def extract_date_segment(url: str):
    """Pull the trailing 8-digit YYYYMMDD date out of a BookMyShow buytickets URL."""
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
        page.wait_for_timeout(4000)  # let JS render / redirect settle

        final_url = page.url
        final_date = extract_date_segment(final_url)
        print(f"Final URL after load: {final_url}")
        print(f"Final date segment: {final_date}")

        date_stayed_on_target = (requested_date is not None and final_date == requested_date)
        print(f"Date stayed on target (main signal): {date_stayed_on_target}")

        # ---- Secondary confirmation: is the movie name present on the page? ----
        page_text = page.inner_text("body")
        with open("debug_page_text.txt", "w", encoding="utf-8") as f:
            f.write(page_text)
        page.screenshot(path="debug_screenshot.png", full_page=True)

        movie_found_in_text = MOVIE_NAME.lower() in page_text.lower()
        print(f"Movie name appears in page text (now REQUIRED): {movie_found_in_text}")

        # ---- Detect Cloudflare / bot-detection block pages explicitly ----
        # If we're blocked, the block page renders at the SAME url we requested
        # (no redirect happens), which would otherwise look identical to a
        # genuine "date is live" signal. We must catch this explicitly or
        # every block will look like a false positive.
        block_indicators = [
            "sorry, you have been blocked",
            "cloudflare ray id",
            "attention required",
            "unable to access bookmyshow.com",
            "performance & security by cloudflare",
        ]
        lower_text = page_text.lower()
        was_blocked = any(indicator in lower_text for indicator in block_indicators)
        print(f"Blocked by Cloudflare/bot-detection: {was_blocked}")

        browser.close()

    if was_blocked:
        print("Request was blocked by the site's security layer — result is INCONCLUSIVE, "
              "not treated as available. No alert will be sent this run.")
        shows_available = False
    else:
        # Require BOTH signals: the date didn't redirect back to today, AND
        # the target movie's name actually appears on the rendered page.
        shows_available = date_stayed_on_target and movie_found_in_text

    # ---- Compare to previous state, notify if newly available ----
    already_notified = state.get("found", False)

    if shows_available and not already_notified:
        msg = (
            f"🎬 Tickets are now LIVE!\n\n"
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
        print("No shows found yet for target date/movie (page redirected back to today, "
              "or movie name not found).")

    print("Done.")


if __name__ == "__main__":
    main()
