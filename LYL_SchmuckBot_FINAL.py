"""
LYL SchmuckBot FINAL - Vollstaendig & Funktionierend
- Cloudflare Bypass via undetected-chromedriver
- Zwei Google Sheets werden aktualisiert
- GUI mit Tkinter + Auto-Update alle 5 Min
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import requests
from datetime import datetime
import json
import os

# -- KONFIGURATION ----------------------------------------------------------
# Sheet 1 (z.B. A1-E1):
WEBAPP_SHEET1 = "https://script.google.com/macros/s/AKfycbzlZS1rYFqOwwYkDp2N6W0xJwsyPsWF8Kx1ebXa0CqlEOKZ/exec"

# Sheet 2 (Test Neustart C4-E4) - aus config.json:
WEBAPP_SHEET2 = "https://script.google.com/macros/s/AKfycbyZBP0wVP6MEMmQz2jZimAu2GcJHQvXgMbj6V7JGoURbQrtEjn5C_9osPXBnTPAUZjn/exec"

UPDATE_INTERVAL = 300  # 5 Minuten in Sekunden
LYL_URL = "https://www.lyl.gg/wiki/entry/47-marktsystem"
# ---------------------------------------------------------------------------


class SchmuckBot:
    def __init__(self, root):
        self.root = root
        self.root.title("LYL SchmuckBot FINAL")
        self.root.geometry("500x450")
        self.root.resizable(False, False)

        self.running = False
        self.auto_thread = None

        self._build_gui()
        self.log("Programm gestartet. Klicke SCAN oder AUTO-START.")

    def _build_gui(self):
        # Titel
        title = tk.Label(self.root, text="LYL.GG Schmuck Tracker", font=("Arial", 16, "bold"))
        title.pack(pady=10)

        # Status
        self.status_var = tk.StringVar(value="🟡 Bereit")
        status_lbl = tk.Label(self.root, textvariable=self.status_var, font=("Arial", 12))
        status_lbl.pack()

        # Preis-Anzeige
        frame = tk.Frame(self.root)
        frame.pack(pady=8)
        for col, text in enumerate(["MIN", "PREIS", "MAX"]):
            tk.Label(frame, text=text, font=("Arial", 10, "bold"), width=12).grid(row=0, column=col, padx=4)
        self.val_min = tk.StringVar(value="-")
        self.val_preis = tk.StringVar(value="-")
        self.val_max = tk.StringVar(value="-")
        for col, var in enumerate([self.val_min, self.val_preis, self.val_max]):
            tk.Label(frame, textvariable=var, font=("Arial", 12), fg="blue", width=12).grid(row=1, column=col, padx=4)

        # Buttons
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="SCAN JETZT", command=self.scan_once,
                  bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), width=14).grid(row=0, column=0, padx=6)
        self.auto_btn = tk.Button(btn_frame, text="AUTO-START", command=self.toggle_auto,
                                  bg="#2196F3", fg="white", font=("Arial", 11, "bold"), width=14)
        self.auto_btn.grid(row=0, column=1, padx=6)

        # Countdown
        self.countdown_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.countdown_var, font=("Arial", 10), fg="gray").pack()

        # Log-Fenster
        tk.Label(self.root, text="Log:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10)
        self.log_box = scrolledtext.ScrolledText(self.root, height=10, width=60, state="disabled",
                                                  font=("Consolas", 9))
        self.log_box.pack(padx=10, pady=4)

    def log(self, msg):
        """Schreibt eine Nachricht ins Log-Fenster."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full = f"[{timestamp}] {msg}\n"
        self.log_box.config(state="normal")
        self.log_box.insert("end", full)
        self.log_box.see("end")
        self.log_box.config(state="disabled")
        print(full, end="")

    def set_status(self, text):
        self.status_var.set(text)

    # -----------------------------------------------------------------------
    # SCRAPING
    # -----------------------------------------------------------------------
    def get_schmuck_preise(self):
        """Holt Schmuck-Preise von lyl.gg via requests (kein Selenium noetig wenn Cloudflare offen)."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "de-DE,de;q=0.9",
        }
        try:
            r = requests.get(LYL_URL, headers=headers, timeout=20)
            if r.status_code != 200:
                self.log(f"HTTP Fehler: {r.status_code}")
                return None
            return self._parse_preise(r.text)
        except Exception as e:
            self.log(f"Requests Fehler: {e}")
            return None

    def get_schmuck_preise_selenium(self):
        """Fallback: Selenium + undetected-chromedriver fuer Cloudflare."""
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            self.log("Starte Chrome (Cloudflare Bypass)...")
            options = uc.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            driver = uc.Chrome(options=options)
            driver.get(LYL_URL)

            # Warte auf Tabelle
            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            time.sleep(2)

            html = driver.page_source
            driver.quit()
            return self._parse_preise(html)
        except ImportError:
            self.log("undetected-chromedriver nicht installiert.")
            return None
        except Exception as e:
            self.log(f"Selenium Fehler: {e}")
            return None

    def _parse_preise(self, html):
        """Sucht Schmuck-Zeile in HTML und extrahiert Min/Preis/Max."""
        import re

        # Suche nach der Schmuck-Zeile im HTML
        idx = html.lower().find("schmuck")
        if idx == -1:
            self.log("'Schmuck' nicht im HTML gefunden.")
            return None

        # Extrahiere Zahlen in der Naehe
        snippet = html[idx:idx + 500]
        zahlen = re.findall(r"[\d]+(?:[.,]\d+)*", snippet)
        # Filtere auf realistische Preis-Zahlen (> 100)
        zahlen_gefiltert = [z.replace(",", ".") for z in zahlen
                            if float(z.replace(",", ".").replace(".", "", z.replace(",", ".").count(".")-1)
                                     if z.replace(",", ".").count(".") > 1
                                     else z.replace(",", ".")) > 100]

        if len(zahlen_gefiltert) >= 3:
            return zahlen_gefiltert[0], zahlen_gefiltert[1], zahlen_gefiltert[2]

        # Breitere Suche
        alle_zahlen = re.findall(r"\b\d{4,6}\b", html[max(0, idx-100):idx + 800])
        if len(alle_zahlen) >= 3:
            return alle_zahlen[0], alle_zahlen[1], alle_zahlen[2]

        self.log(f"Parsing fehlgeschlagen. Gefundene Zahlen: {zahlen[:10]}")
        return None

    # -----------------------------------------------------------------------
    # SHEETS UPDATE
    # -----------------------------------------------------------------------
    def update_sheets(self, min_p, preis, max_p):
        """Sendet Werte an beide Apps Script Web Apps."""
        params = {"min": min_p, "preis": preis, "max": max_p}
        erfolge = 0

        for i, url in enumerate([WEBAPP_SHEET1, WEBAPP_SHEET2], 1):
            if not url or "HIER" in url:
                self.log(f"Sheet {i}: URL nicht konfiguriert, uebersprungen.")
                continue
            try:
                r = requests.get(url, params=params, timeout=30, allow_redirects=True)
                if r.text.strip() == "OK" or r.status_code == 200:
                    self.log(f"Sheet {i}: ✅ Aktualisiert ({r.status_code})")
                    erfolge += 1
                else:
                    self.log(f"Sheet {i}: ⚠️ Antwort: {r.text[:80]}")
            except Exception as e:
                self.log(f"Sheet {i}: ❌ Fehler: {e}")

        return erfolge

    # -----------------------------------------------------------------------
    # SCAN LOGIK
    # -----------------------------------------------------------------------
    def do_scan(self):
        """Hauptlogik: Holen + Sheets updaten."""
        self.set_status("🔄 Scanne lyl.gg...")
        self.log("Starte Scan...")

        # Erst requests versuchen (schneller)
        result = self.get_schmuck_preise()

        # Falls Cloudflare blockt -> Selenium
        if result is None:
            self.log("Requests fehlgeschlagen, versuche Selenium...")
            result = self.get_schmuck_preise_selenium()

        if result is None:
            self.set_status("❌ Keine Preise gefunden")
            self.log("FEHLER: Preise konnten nicht gelesen werden.")
            return False

        min_p, preis, max_p = result
        self.val_min.set(min_p)
        self.val_preis.set(preis)
        self.val_max.set(max_p)
        self.log(f"Gefunden: Min={min_p} | Preis={preis} | Max={max_p}")

        # Sheets updaten
        erfolge = self.update_sheets(min_p, preis, max_p)
        now = datetime.now().strftime("%H:%M")

        if erfolge > 0:
            self.set_status(f"✅ Aktualisiert um {now}")
        else:
            self.set_status(f"⚠️ Preise gefunden, Sheets Fehler")

        return True

    def scan_once(self):
        """Einzelner Scan im eigenen Thread."""
        threading.Thread(target=self.do_scan, daemon=True).start()

    def toggle_auto(self):
        """Startet / Stoppt den Auto-Modus."""
        if self.running:
            self.running = False
            self.auto_btn.config(text="AUTO-START", bg="#2196F3")
            self.countdown_var.set("")
            self.log("Auto-Modus gestoppt.")
        else:
            self.running = True
            self.auto_btn.config(text="STOPP", bg="#f44336")
            self.log(f"Auto-Modus gestartet (alle {UPDATE_INTERVAL//60} Min).")
            self.auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
            self.auto_thread.start()

    def _auto_loop(self):
        """Laeuft im Hintergrund und aktualisiert regelmaessig."""
        while self.running:
            self.do_scan()
            # Countdown anzeigen
            for verbleibend in range(UPDATE_INTERVAL, 0, -1):
                if not self.running:
                    break
                min_v = verbleibend // 60
                sek_v = verbleibend % 60
                self.countdown_var.set(f"Naechstes Update in: {min_v:02d}:{sek_v:02d}")
                time.sleep(1)
        self.countdown_var.set("")


def main():
    root = tk.Tk()
    app = SchmuckBot(root)
    root.mainloop()


if __name__ == "__main__":
    main()
