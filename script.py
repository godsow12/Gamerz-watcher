import os, re, json
import urllib.request, urllib.parse
from playwright.sync_api import sync_playwright

EMAIL = os.environ["GAMERZ_EMAIL"]
PASSWORD = os.environ["GAMERZ_PASSWORD"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STATE_FILE = "state.json"

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    urllib.request.urlopen(url, data=data)

def load_last_count():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f).get("last_count", 0)
    return 0

def save_last_count(count):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_count": count}, f)

def dismiss_popup(page):
    for _ in range(4):
        try:
            age_btn = page.get_by_text("I'm 18 or Older", exact=True)
            if age_btn.count() > 0 and age_btn.first.is_visible():
                age_btn.first.click(timeout=3000)
                page.wait_for_timeout(800)
                continue
            overlay = page.locator("div.fixed.inset-0")
            if overlay.count() == 0 or not overlay.first.is_visible():
                return
            candidates = overlay.first.locator(
                "button:has-text('Continue'), button:has-text('Got it'), "
                "button:has-text('I Understand'), button:has-text('Enter'), "
                "button:has-text('Accept'), button:has-text('Agree'), "
                "[aria-label='Close'], [aria-label='close']"
            )
            if candidates.count() > 0:
                candidates.first.click(timeout=3000)
                page.wait_for_timeout(800)
            else:
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
        except Exception:
            page.wait_for_timeout(500)

def dump_debug(page, label):
    try:
        page.screenshot(path=f"debug_{label}.png", full_page=True)
    except Exception:
        pass

def get_job_count(page):
    """Wait for real job-count text to render, not a loading skeleton.
    Retries for up to ~10 seconds before giving up and returning what it has."""
    for attempt in range(10):
        content = page.content()
        match = re.search(r"(\d+)\s+Jobs open", content)
        if match:
            return int(match.group(1))
        page.wait_for_timeout(1000)
    return 0  # genuinely never found it after waiting

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto("https://gamerz360.com/login", timeout=30000)
            page.wait_for_timeout(2000)
            dump_debug(page, "01_after_goto")

            dismiss_popup(page)
            dump_debug(page, "02_after_popup_dismiss")

            page.get_by_placeholder("you@example.com").fill(EMAIL, timeout=15000)
            page.get_by_placeholder("Your password").fill(PASSWORD, timeout=15000)
            dump_debug(page, "03_after_fill")

            page.get_by_text("Login & Play").click(timeout=15000)
            page.wait_for_url(lambda url: "/login" not in url, timeout=20000)
            page.wait_for_timeout(2000)
            dump_debug(page, "04_after_login")

            page.goto("https://gamerz360.com/tasker?tab=queue", timeout=30000)
            dismiss_popup(page)

            current_count = get_job_count(page)
            dump_debug(page, "05_tasks_page")

            last_count = load_last_count()
            print(f"Last: {last_count}, Current: {current_count}")

            if current_count > 0 and current_count != last_count:
                send_telegram(f"🎮 Gamers360: {current_count} job(s) open now! Go check the Job Board.")

            save_last_count(current_count)
        except Exception as e:
            dump_debug(page, "99_failure")
            print(f"Error: {e}")
            raise
        finally:
            browser.close()

if __name__ == "__main__":
    main()
