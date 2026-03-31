"""
LYL Markt Relay – läuft still im Hintergrund
Holt alle 15 Min Marktdaten und schickt sie an Google Sheets
"""
import time, requests, json, logging, os
from datetime import datetime

WEBHOOK = "https://script.google.com/macros/s/AKfycbxwKmbLcuQe1gSXqTmSwRW1Lg3QFKygwS-yJdBn63dUxaZmJP8FdFhgRvyjHaMauXY2/exec"
API_URL = "https://www.lyl.gg/lyl-api/market.php"
INTERVAL = 15 * 60  # 15 Minuten

LOG_FILE = os.path.join(os.path.dirname(__file__), "relay.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%d.%m.%Y %H:%M:%S"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, */*",
    "Referer": "https://www.lyl.gg/",
    "X-Requested-With": "XMLHttpRequest"
}

def hole_marktdaten():
    """Versucht Marktdaten zu holen – erst requests, dann Selenium."""
    # Versuch 1: direkt
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=15)
        data = r.json()
        if "market" in data:
            logging.info(f"✅ Direkt: {len(data['market'])} Items")
            return data
    except Exception:
        pass

    # Versuch 2: Selenium
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        opts = webdriver.ChromeOptions()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--log-level=3")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        driver.get(API_URL)
        time.sleep(4)
        text = driver.find_element("tag name", "body").text
        driver.quit()
        data = json.loads(text)
        if "market" in data:
            logging.info(f"✅ Selenium: {len(data['market'])} Items")
            return data
    except Exception as e:
        logging.error(f"❌ Selenium Fehler: {e}")

    return None

def sende_an_sheets(data):
    """Schickt Marktdaten an Google Sheets Webhook."""
    try:
        # Google Apps Script leitet POST weiter – Session mit allow_redirects nötig
        session = requests.Session()
        r = session.post(
            WEBHOOK,
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            },
            allow_redirects=True,
            timeout=30
        )
        text = r.text.strip()
        if not text:
            logging.error(f"❌ Sheets: Leere Antwort (Status {r.status_code})")
            return False
        result = json.loads(text)
        if result.get("status") == "ok":
            logging.info("✅ Sheets aktualisiert")
            return True
        else:
            logging.error(f"❌ Sheets Fehler: {result}")
    except Exception as e:
        logging.error(f"❌ Webhook Fehler: {e}")
    return False

def main():
    logging.info("🚀 LYL Relay gestartet")
    while True:
        logging.info("--- Scan Start ---")
        data = hole_marktdaten()
        if data:
            sende_an_sheets(data)
        else:
            logging.error("❌ Keine Daten erhalten")
        logging.info(f"💤 Nächster Scan in {INTERVAL//60} Minuten")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
