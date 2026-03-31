"""
Schmuck_TRACKER v0.0.7
======================
- Cloudflare-Bypass via undetected-chromedriver (primaer)
- Fallback: selenium + webdriver-manager
- Schreibt in 2 Google Sheets via Apps Script Web Apps
- GUI: tkinter (Status, Preisanzeige, Log, Countdown)
- Auto-Update alle 15 Min (konfigurierbar)
- Autostart: Windows Startup-Ordner

Benoetigt (einmalig installieren):
  pip install undetected-chromedriver selenium webdriver-manager requests
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import requests
import os
import sys
import json
import re
import subprocess
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# KONFIGURATION  (wird aus config.json geladen, diese Werte sind die Defaults)
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "webapp_sheet1": "https://script.google.com/macros/s/AKfycbzlZS1rYFqOwwYkDp2N6W0xJwsyPsWF8Kx1ebXa0CqlEOKZ/exec",
    "webapp_sheet2": "https://script.google.com/macros/s/AKfycbyZBP0wVP6MEMmQz2jZimAu2GcJHQvXgMbj6V7JGoURbQrtEjn5C_9osPXBnTPAUZjn/exec",
    "interval_minuten": 15
}

LYL_URL = "https://www.lyl.gg/wiki/entry/47-marktsystem"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
STARTUP_NAME = "Schmuck_TRACKER"


# ---------------------------------------------------------------------------
# HILFS-FUNKTIONEN
# ---------------------------------------------------------------------------

def lade_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # Fehlende Keys mit Defaults ergaenzen
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def speichere_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def autostart_einrichten(aktivieren: bool):
    """Legt Verknuepfung im Windows-Autostart-Ordner an / entfernt sie."""
    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"
    )
    lnk_path = os.path.join(startup_dir, f"{STARTUP_NAME}.bat")

    if aktivieren:
        python_exe = sys.executable
        script_path = os.path.abspath(__file__)
        bat = f'@echo off\nstart "" "{python_exe}" "{script_path}" --autostart\n'
        try:
            with open(lnk_path, "w") as f:
                f.write(bat)
            return True, lnk_path
        except Exception as e:
            return False, str(e)
    else:
        try:
            if os.path.exists(lnk_path):
                os.remove(lnk_path)
            return True, ""
        except Exception as e:
            return False, str(e)


# ---------------------------------------------------------------------------
# SCRAPER
# ---------------------------------------------------------------------------

def _parse_html(html: str):
    """Sucht Schmuck-Zeile in HTML. Gibt (min, preis, max) oder None zurueck."""
    # Methode 1: Regex-Tabellen-Parser
    pattern = re.compile(
        r'<td[^>]*>\s*Schmuck\s*</td>\s*'
        r'<td[^>]*>(.*?)</td>\s*'
        r'<td[^>]*>(.*?)</td>\s*'
        r'<td[^>]*>(.*?)</td>',
        re.IGNORECASE | re.DOTALL
    )
    m = pattern.search(html)
    if m:
        def bereinige(s):
            # HTML-Tags entfernen, Whitespace normalisieren
            s = re.sub(r'<[^>]+>', '', s)
            s = re.sub(r'\s+', ' ', s).strip()
            return s
        return bereinige(m.group(1)), bereinige(m.group(2)), bereinige(m.group(3))

    # Methode 2: Positions-basierte Suche (Fallback)
    idx = html.lower().find("schmuck")
    if idx == -1:
        return None
    snippet = html[max(0, idx - 50): idx + 600]
    zahlen = re.findall(r'\b\d{3,6}(?:[.,]\d+)?\b', snippet)
    zahlen = [z for z in zahlen if float(z.replace(".", "").replace(",", ".")) > 100]
    if len(zahlen) >= 3:
        return zahlen[0], zahlen[1], zahlen[2]

    return None


def scrape_mit_requests(log_fn=None):
    """Schnelle Methode via requests. Funktioniert wenn Cloudflare offen ist."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        r = requests.get(LYL_URL, headers=headers, timeout=20)
        if r.status_code == 200:
            return _parse_html(r.text)
        if log_fn:
            log_fn(f"Requests: HTTP {r.status_code} (Cloudflare?)")
    except Exception as e:
        if log_fn:
            log_fn(f"Requests Fehler: {e}")
    return None


def scrape_mit_uc(log_fn=None):
    """Cloudflare-Bypass via undetected-chromedriver + direkte Selenium-Tabellen-Lesung."""
    try:
        import undetected_chromedriver as uc
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        if log_fn:
            log_fn("Starte Chrome (undetected-chromedriver)...")

        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,800")

        driver = uc.Chrome(options=options)
        try:
            driver.get(LYL_URL)
            wait = WebDriverWait(driver, 25)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            time.sleep(2)  # JS nachladen lassen

            rows = driver.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 4 and cells[0].text.strip() == "Schmuck":
                    min_p = cells[1].text.strip()
                    preis = cells[2].text.strip()
                    max_p = cells[3].text.strip()
                    return min_p, preis, max_p

            if log_fn:
                log_fn("UC: Tabelle geladen, Schmuck-Zeile nicht gefunden.")
        finally:
            driver.quit()

    except ImportError:
        if log_fn:
            log_fn("undetected-chromedriver nicht installiert. Versuche Selenium...")
        return scrape_mit_selenium_wdm(log_fn)
    except Exception as e:
        if log_fn:
            log_fn(f"UC Fehler: {str(e)[:120]}")
        return scrape_mit_selenium_wdm(log_fn)

    return None


def scrape_mit_selenium_wdm(log_fn=None):
    """Fallback: normales Selenium + webdriver-manager (auto ChromeDriver)."""
    try:
        from selenium import webdriver as wd
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager

        if log_fn:
            log_fn("Starte Chrome (webdriver-manager)...")

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        service = Service(ChromeDriverManager().install())
        driver = wd.Chrome(service=service, options=options)
        try:
            driver.get(LYL_URL)
            wait = WebDriverWait(driver, 25)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            time.sleep(2)

            rows = driver.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 4 and cells[0].text.strip() == "Schmuck":
                    return cells[1].text.strip(), cells[2].text.strip(), cells[3].text.strip()

            if log_fn:
                log_fn("WDM: Tabelle geladen, Schmuck-Zeile nicht gefunden.")
        finally:
            driver.quit()

    except ImportError as e:
        if log_fn:
            log_fn(f"Selenium/WDM nicht installiert: {e}")
    except Exception as e:
        if log_fn:
            log_fn(f"Selenium WDM Fehler: {str(e)[:120]}")

    return None


def hole_preise(log_fn=None):
    """Versucht requests, dann undetected-chromedriver, dann selenium+wdm."""
    if log_fn:
        log_fn("Versuch 1: requests...")
    result = scrape_mit_requests(log_fn)
    if result:
        return result

    if log_fn:
        log_fn("Versuch 2: undetected-chromedriver (Cloudflare Bypass)...")
    result = scrape_mit_uc(log_fn)
    if result:
        return result

    return None


# ---------------------------------------------------------------------------
# SHEETS UPDATE
# ---------------------------------------------------------------------------

def update_sheets(min_p, preis, max_p, cfg, log_fn=None):
    """Sendet Werte an beide Apps Script Web Apps."""
    params = {"min": min_p, "preis": preis, "max": max_p}
    erfolge = 0

    urls = [
        ("Sheet 1", cfg.get("webapp_sheet1", "")),
        ("Sheet 2", cfg.get("webapp_sheet2", "")),
    ]

    for name, url in urls:
        if not url or "HIER" in url or len(url) < 30:
            if log_fn:
                log_fn(f"{name}: URL nicht konfiguriert, uebersprungen.")
            continue
        try:
            r = requests.get(url, params=params, timeout=30, allow_redirects=True)
            antwort = r.text.strip()
            if antwort == "OK" or r.status_code == 200:
                if log_fn:
                    log_fn(f"{name}: ✅ Aktualisiert (HTTP {r.status_code})")
                erfolge += 1
            else:
                if log_fn:
                    log_fn(f"{name}: ⚠️ Antwort: {antwort[:80]}")
        except Exception as e:
            if log_fn:
                log_fn(f"{name}: ❌ Fehler: {e}")

    return erfolge


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class SchmuckTrackerApp:
    def __init__(self, root: tk.Tk, autostart_modus: bool = False):
        self.root = root
        self.root.title("Schmuck_TRACKER v0.0.7")
        self.root.geometry("520x520")
        self.root.resizable(False, False)

        self.cfg = lade_config()
        self.running = False
        self._auto_thread = None

        self._baue_gui()
        self.log("Schmuck_TRACKER v0.0.7 gestartet.")
        self.log(f"Interval: {self.cfg['interval_minuten']} Min.")

        if autostart_modus:
            self.root.after(1500, self.toggle_auto)

    # -----------------------------------------------------------------------
    # GUI Aufbau
    # -----------------------------------------------------------------------
    def _baue_gui(self):
        # --- Titel ---
        tk.Label(
            self.root, text="LYL.GG  Schmuck Tracker",
            font=("Arial", 17, "bold"), fg="#1a237e"
        ).pack(pady=(12, 4))

        # --- Status ---
        self.status_var = tk.StringVar(value="🟡  Bereit")
        tk.Label(self.root, textvariable=self.status_var, font=("Arial", 12)).pack()

        # --- Preisanzeige ---
        pf = tk.Frame(self.root)
        pf.pack(pady=8)
        for col, txt in enumerate(["MIN", "PREIS", "MAX"]):
            tk.Label(pf, text=txt, font=("Arial", 10, "bold"), width=14).grid(row=0, column=col, padx=6)
        self.v_min   = tk.StringVar(value="—")
        self.v_preis = tk.StringVar(value="—")
        self.v_max   = tk.StringVar(value="—")
        for col, var in enumerate([self.v_min, self.v_preis, self.v_max]):
            tk.Label(pf, textvariable=var, font=("Arial", 13, "bold"),
                     fg="#1565c0", width=14).grid(row=1, column=col, padx=6)

        # --- Buttons ---
        bf = tk.Frame(self.root)
        bf.pack(pady=6)
        tk.Button(
            bf, text="  JETZT SCANNEN  ", command=self.scan_einmal,
            bg="#43a047", fg="white", font=("Arial", 11, "bold"), relief="flat", padx=8
        ).grid(row=0, column=0, padx=6)

        self.auto_btn = tk.Button(
            bf, text="  AUTO-START  ", command=self.toggle_auto,
            bg="#1e88e5", fg="white", font=("Arial", 11, "bold"), relief="flat", padx=8
        )
        self.auto_btn.grid(row=0, column=1, padx=6)

        tk.Button(
            bf, text="  ⚙ Einstellungen  ", command=self.oeffne_einstellungen,
            bg="#546e7a", fg="white", font=("Arial", 11, "bold"), relief="flat", padx=8
        ).grid(row=0, column=2, padx=6)

        # --- Countdown ---
        self.countdown_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.countdown_var,
                 font=("Arial", 10), fg="#757575").pack(pady=2)

        # --- Log ---
        tk.Label(self.root, text="Log:", font=("Arial", 9, "bold"),
                 anchor="w").pack(anchor="w", padx=12)
        self.log_box = scrolledtext.ScrolledText(
            self.root, height=12, width=64, state="disabled",
            font=("Consolas", 9), bg="#f5f5f5"
        )
        self.log_box.pack(padx=12, pady=4)

        # --- Autostart Checkbox ---
        self.autostart_var = tk.BooleanVar()
        self._aktualisiere_autostart_checkbox()
        tk.Checkbutton(
            self.root, text="Windows-Autostart (startet automatisch beim PC-Start)",
            variable=self.autostart_var, command=self._toggle_autostart,
            font=("Arial", 9)
        ).pack(pady=4)

    # -----------------------------------------------------------------------
    # Log
    # -----------------------------------------------------------------------
    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        zeile = f"[{ts}]  {msg}\n"
        self.log_box.config(state="normal")
        self.log_box.insert("end", zeile)
        self.log_box.see("end")
        self.log_box.config(state="disabled")
        print(zeile, end="")

    def set_status(self, text: str):
        self.status_var.set(text)

    # -----------------------------------------------------------------------
    # Scan
    # -----------------------------------------------------------------------
    def _do_scan(self):
        self.set_status("🔄  Scanne lyl.gg...")
        self.log("─" * 40)
        self.log("Starte Scan...")

        result = hole_preise(log_fn=self.log)

        if result is None:
            self.set_status("❌  Preise nicht gefunden")
            self.log("FEHLER: Konnte Preise nicht lesen.")
            return False

        min_p, preis, max_p = result
        self.v_min.set(min_p)
        self.v_preis.set(preis)
        self.v_max.set(max_p)
        self.log(f"Gefunden:  Min={min_p}  |  Preis={preis}  |  Max={max_p}")

        self.cfg = lade_config()
        erfolge = update_sheets(min_p, preis, max_p, self.cfg, log_fn=self.log)
        jetzt = datetime.now().strftime("%H:%M")

        if erfolge > 0:
            self.set_status(f"✅  Aktualisiert um {jetzt}")
        else:
            self.set_status(f"⚠️  Preise OK, Sheets Fehler – URLs pruefen!")

        return erfolge > 0

    def scan_einmal(self):
        """Einzelner Scan im Hintergrund-Thread."""
        if not self.running:
            threading.Thread(target=self._do_scan, daemon=True).start()
        else:
            self.log("Auto-Modus aktiv – naechster Scan laeuft automatisch.")

    def toggle_auto(self):
        """Startet / Stoppt den Auto-Modus."""
        if self.running:
            self.running = False
            self.auto_btn.config(text="  AUTO-START  ", bg="#1e88e5")
            self.countdown_var.set("")
            self.log("Auto-Modus gestoppt.")
        else:
            self.running = True
            self.auto_btn.config(text="  ■ STOPP  ", bg="#e53935")
            interval = self.cfg.get("interval_minuten", 15)
            self.log(f"Auto-Modus gestartet (alle {interval} Min).")
            self._auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
            self._auto_thread.start()

    def _auto_loop(self):
        """Hintergrund-Schleife fuer automatische Updates."""
        while self.running:
            self.root.after(0, lambda: None)  # GUI lebendig halten
            self._do_scan()
            if not self.running:
                break
            interval_sek = self.cfg.get("interval_minuten", 15) * 60
            for verbleibend in range(interval_sek, 0, -1):
                if not self.running:
                    break
                m, s = divmod(verbleibend, 60)
                self.countdown_var.set(f"Naechstes Update in:  {m:02d}:{s:02d}")
                time.sleep(1)
        self.countdown_var.set("")

    # -----------------------------------------------------------------------
    # Einstellungen
    # -----------------------------------------------------------------------
    def oeffne_einstellungen(self):
        win = tk.Toplevel(self.root)
        win.title("Einstellungen")
        win.geometry("560x280")
        win.resizable(False, False)
        win.grab_set()

        self.cfg = lade_config()

        def lbl(text, row):
            tk.Label(win, text=text, font=("Arial", 9, "bold"), anchor="w").grid(
                row=row, column=0, sticky="w", padx=12, pady=4)

        lbl("Sheet 1 URL (A1–E1):", 0)
        e1 = tk.Entry(win, width=60, font=("Consolas", 8))
        e1.insert(0, self.cfg.get("webapp_sheet1", ""))
        e1.grid(row=1, column=0, padx=12, pady=2, sticky="ew")

        lbl("Sheet 2 URL (Test Neustart C4–E4):", 2)
        e2 = tk.Entry(win, width=60, font=("Consolas", 8))
        e2.insert(0, self.cfg.get("webapp_sheet2", ""))
        e2.grid(row=3, column=0, padx=12, pady=2, sticky="ew")

        lbl("Update-Interval (Minuten):", 4)
        e3 = tk.Entry(win, width=10, font=("Arial", 10))
        e3.insert(0, str(self.cfg.get("interval_minuten", 15)))
        e3.grid(row=5, column=0, padx=12, pady=2, sticky="w")

        def speichern():
            self.cfg["webapp_sheet1"] = e1.get().strip()
            self.cfg["webapp_sheet2"] = e2.get().strip()
            try:
                self.cfg["interval_minuten"] = int(e3.get().strip())
            except ValueError:
                pass
            speichere_config(self.cfg)
            self.log("Einstellungen gespeichert.")
            win.destroy()

        tk.Button(win, text="Speichern", command=speichern,
                  bg="#43a047", fg="white", font=("Arial", 10, "bold"),
                  relief="flat", padx=12, pady=4).grid(
            row=6, column=0, pady=12, padx=12, sticky="w")

    # -----------------------------------------------------------------------
    # Autostart
    # -----------------------------------------------------------------------
    def _aktualisiere_autostart_checkbox(self):
        startup_dir = os.path.join(
            os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"
        )
        lnk = os.path.join(startup_dir, f"{STARTUP_NAME}.bat")
        self.autostart_var = tk.BooleanVar(value=os.path.exists(lnk))

    def _toggle_autostart(self):
        aktivieren = self.autostart_var.get()
        ok, info = autostart_einrichten(aktivieren)
        if ok:
            status = "aktiviert" if aktivieren else "deaktiviert"
            self.log(f"Autostart {status}.")
            if aktivieren and info:
                self.log(f"  → {info}")
        else:
            self.log(f"Autostart Fehler: {info}")
            messagebox.showerror("Autostart Fehler", info)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    autostart_modus = "--autostart" in sys.argv

    root = tk.Tk()
    app = SchmuckTrackerApp(root, autostart_modus=autostart_modus)

    # Fenster minimieren wenn Autostart
    if autostart_modus:
        root.iconify()

    root.mainloop()


if __name__ == "__main__":
    main()
