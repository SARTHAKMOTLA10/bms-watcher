# BookMyShow Show Watcher

Checks a specific theatre's page every 15 minutes to see if a specific movie
has showtimes listed for a specific date tab (e.g. next Monday or Friday).
Sends you a Telegram message the moment it finds them.

## One-time setup (~10-15 min)

### 1. Create a Telegram bot
1. Open Telegram, search for **@BotFather**, start a chat.
2. Send `/newbot`, follow the prompts (give it any name/username).
3. BotFather gives you a **bot token** — looks like `123456789:ABCdefGhIJKlmNoPQRstuVwxyZ`. Save it.
4. Send your new bot **any message** first (e.g. "hi") so it can message you back.

### 2. Get your Telegram chat ID
1. Visit this URL in your browser (replace `<TOKEN>` with your bot token):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
2. After sending your bot a message in step above, refresh this URL.
3. Look for `"chat":{"id":123456789,...}` in the response — that number is your **chat ID**.

### 3. Create the GitHub repo
1. Create a new **public or private** repo on GitHub (e.g. `bms-watcher`).
2. Upload all files from this project into it (check_shows.py, requirements.txt,
   state.json, README.md, and the `.github/workflows/watch.yml` file — keep the
   folder structure intact).

### 4. Add secrets (Settings → Secrets and variables → Actions → Secrets tab)
- `TELEGRAM_BOT_TOKEN` = your bot token from step 1
- `TELEGRAM_CHAT_ID` = your chat ID from step 2

### 5. Add variables (same page → Variables tab)
- `THEATRE_URL` = the exact BookMyShow theatre page URL (the one showing date
  tabs and movie listings — like the INOX Pacific Mall page)
- `MOVIE_NAME` = the exact movie name as it appears on the page, e.g.
  `Spider-Man: Brand New Day`
- `TARGET_DAY_NUM` = the day-of-month number shown on the date tab you want,
  e.g. `04` for the Tuesday the 4th, or `01` for Saturday the 1st
- `TARGET_DAY_LABEL` = (optional, just for readability in the alert message)
  e.g. `TUE` or `FRI`

### 6. Test it manually
1. Go to the **Actions** tab in your repo.
2. Click on "BookMyShow Show Watcher" workflow → **Run workflow** button
   (this is the `workflow_dispatch` trigger — lets you run it on demand
   instead of waiting for the schedule).
3. Watch the run. If it fails or doesn't find the movie, download the
   **debug-output** artifact from the run summary — it contains a screenshot
   and full page text dump so we can see exactly what the script saw and fix
   the selectors.

### 7. Let it run
Once a manual test succeeds, the schedule takes over automatically — it
checks every 15 minutes, 24/7, regardless of whether your laptop is on.
The moment it detects showtimes for your movie on your target date, you'll
get a Telegram message with a link to book.

## Changing target date/movie later
Just update the `THEATRE_URL`, `MOVIE_NAME`, `TARGET_DAY_NUM`, and
`TARGET_DAY_LABEL` variables in the repo settings — no code changes needed.
Also reset `state.json` back to `{"found": false}` if you're starting a fresh
watch (e.g. new week), so it doesn't think it already notified you.

## Important honest caveat
This script's selectors were written based on the general structure of
BookMyShow's page (as seen in a screenshot) but could not be tested live
against the real site during development (network restrictions in the
building sandbox). The **first manual run** (step 6) is the real test —
if it doesn't find the movie or date tab correctly, share the debug
screenshot/text artifact and the selectors can be adjusted.
