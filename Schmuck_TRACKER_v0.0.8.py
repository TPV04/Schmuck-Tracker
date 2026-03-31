"""
Schmuck_TRACKER v0.0.8
======================
- UI-Redesign: LYL-Launcher Dark Theme (Gold/Schwarz)
- Gold Ring-Icon (Canvas)
- Profit-Rechner integriert
- Backend identisch mit v0.0.7

Benoetigt (einmalig installieren):
  pip install undetected-chromedriver selenium webdriver-manager requests
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import time
import requests
import os
import sys
import json
import re
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# KONFIGURATION
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
# HILFS-FUNKTIONEN  (identisch mit v0.0.7)
# ---------------------------------------------------------------------------

def lade_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
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
# SCRAPER  (identisch mit v0.0.7)
# ---------------------------------------------------------------------------

def _parse_html(html: str):
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
            s = re.sub(r'<[^>]+>', '', s)
            s = re.sub(r'\s+', ' ', s).strip()
            return s
        return bereinige(m.group(1)), bereinige(m.group(2)), bereinige(m.group(3))

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
            time.sleep(2)

            rows = driver.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 4 and cells[0].text.strip() == "Schmuck":
                    return cells[1].text.strip(), cells[2].text.strip(), cells[3].text.strip()

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
    if log_fn:
        log_fn("Versuch 1: requests...")
    result = scrape_mit_requests(log_fn)
    if result:
        return result

    if log_fn:
        log_fn("Versuch 2: undetected-chromedriver (Cloudflare Bypass)...")
    return scrape_mit_uc(log_fn)


# ---------------------------------------------------------------------------
# SHEETS UPDATE  (identisch mit v0.0.7)
# ---------------------------------------------------------------------------

def update_sheets(min_p, preis, max_p, cfg, log_fn=None):
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
            if r.text.strip() == "OK" or r.status_code == 200:
                if log_fn:
                    log_fn(f"{name}: \u2705 Aktualisiert (HTTP {r.status_code})")
                erfolge += 1
            else:
                if log_fn:
                    log_fn(f"{name}: \u26a0\ufe0f Antwort: {r.text.strip()[:80]}")
        except Exception as e:
            if log_fn:
                log_fn(f"{name}: \u274c Fehler: {e}")

    return erfolge


# ---------------------------------------------------------------------------
# FARBEN
# ---------------------------------------------------------------------------
BG       = '#141414'
BG2      = '#1a1a1a'
BG3      = '#1e1e1e'
BG_GOLD  = '#1e1b0a'
GOLD     = '#D4A017'
GOLD2    = '#FFD700'
BLUE     = '#1565c0'
BLUE2    = '#1976d2'
GREEN    = '#4CAF50'
RED      = '#f44336'
ORANGE   = '#FF9800'
GRAY     = '#2a2a2a'
GRAY2    = '#3a3a3a'
TEXT     = '#ffffff'
TEXT2    = '#999999'
TEXT3    = '#555555'
TEXT4    = '#444444'


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class SchmuckTrackerApp:
    def __init__(self, root: tk.Tk, autostart_modus: bool = False):
        self.root = root
        self.root.title("Schmuck_TRACKER v0.0.8")
        self.root.geometry("520x640")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self.cfg = lade_config()
        self.running = False
        self._auto_thread = None
        self._preis_aktuell = 0

        self._baue_gui()
        self.log("Schmuck_TRACKER v0.0.8 gestartet.")
        self.log(f"Interval: {self.cfg['interval_minuten']} Min.")

        if autostart_modus:
            self.root.after(1500, self.toggle_auto)

    # -----------------------------------------------------------------------
    # GUI Aufbau
    # -----------------------------------------------------------------------
    def _baue_gui(self):

        # ── HEADER ──────────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=BG2)
        header.pack(fill='x')

        # Ring-Icon
        ring_cv = tk.Canvas(header, width=60, height=60, bg=BG2,
                            highlightthickness=0)
        ring_cv.pack(side='left', padx=(16, 10), pady=12)
        self._draw_ring(ring_cv, 60, BG2)

        # Titel + Status
        info = tk.Frame(header, bg=BG2)
        info.pack(side='left', pady=12)

        # Titel als Canvas für exaktes zweifarbiges "LYL.GG Schmuck Tracker"
        title_cv = tk.Canvas(info, bg=BG2, highlightthickness=0,
                             height=28, width=340)
        title_cv.pack(anchor='w')
        font_title = ('Segoe UI', 16, 'bold')
        title_cv.create_text(0, 14, text="LYL.", font=font_title,
                             fill=GOLD, anchor='w')
        title_cv.create_text(38, 14, text="GG Schmuck Tracker",
                             font=font_title, fill=TEXT, anchor='w')

        status_row = tk.Frame(info, bg=BG2)
        status_row.pack(anchor='w', pady=(3, 0))
        dot_cv = tk.Canvas(status_row, width=10, height=10, bg=BG2,
                           highlightthickness=0)
        dot_cv.pack(side='left', padx=(0, 5))
        dot_cv.create_oval(1, 1, 9, 9, fill=GREEN, outline='')
        self.status_var = tk.StringVar(value="Bereit")
        self.status_lbl = tk.Label(status_row, textvariable=self.status_var,
                                   font=('Segoe UI', 11), fg=GREEN, bg=BG2)
        self.status_lbl.pack(side='left')

        # Separator
        tk.Frame(self.root, bg=GRAY, height=1).pack(fill='x')

        # ── PREISKARTEN ─────────────────────────────────────────────────────
        prices_frame = tk.Frame(self.root, bg=BG)
        prices_frame.pack(fill='x', padx=14, pady=12)

        # MIN
        min_border = tk.Frame(prices_frame, bg=GRAY, padx=1, pady=1)
        min_border.pack(side='left', expand=True, fill='both', padx=(0, 4))
        min_inner = tk.Frame(min_border, bg=BG3, padx=10, pady=8)
        min_inner.pack(fill='both', expand=True)
        tk.Label(min_inner, text="MIN", font=('Segoe UI', 8, 'bold'),
                 fg=TEXT2, bg=BG3).pack()
        self.v_min = tk.StringVar(value="—")
        tk.Label(min_inner, textvariable=self.v_min,
                 font=('Segoe UI', 17, 'bold'), fg=GOLD, bg=BG3).pack()
        tk.Label(min_inner, text="Tiefstkurs", font=('Segoe UI', 8),
                 fg=TEXT3, bg=BG3).pack()

        # PREIS (hervorgehoben)
        preis_border = tk.Frame(prices_frame, bg=GOLD, padx=1, pady=1)
        preis_border.pack(side='left', expand=True, fill='both', padx=4)
        preis_inner = tk.Frame(preis_border, bg=BG_GOLD, padx=10, pady=8)
        preis_inner.pack(fill='both', expand=True)
        tk.Label(preis_inner, text="PREIS", font=('Segoe UI', 8, 'bold'),
                 fg=TEXT2, bg=BG_GOLD).pack()
        self.v_preis = tk.StringVar(value="—")
        tk.Label(preis_inner, textvariable=self.v_preis,
                 font=('Segoe UI', 19, 'bold'), fg=GOLD2, bg=BG_GOLD).pack()
        self.v_change = tk.StringVar(value="")
        tk.Label(preis_inner, textvariable=self.v_change,
                 font=('Segoe UI', 9), fg=GREEN, bg=BG_GOLD).pack()

        # MAX
        max_border = tk.Frame(prices_frame, bg=GRAY, padx=1, pady=1)
        max_border.pack(side='left', expand=True, fill='both', padx=(4, 0))
        max_inner = tk.Frame(max_border, bg=BG3, padx=10, pady=8)
        max_inner.pack(fill='both', expand=True)
        tk.Label(max_inner, text="MAX", font=('Segoe UI', 8, 'bold'),
                 fg=TEXT2, bg=BG3).pack()
        self.v_max = tk.StringVar(value="—")
        tk.Label(max_inner, textvariable=self.v_max,
                 font=('Segoe UI', 17, 'bold'), fg=GOLD, bg=BG3).pack()
        tk.Label(max_inner, text="Höchstkurs", font=('Segoe UI', 8),
                 fg=TEXT3, bg=BG3).pack()

        # ── BUTTONS ─────────────────────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(fill='x', padx=14, pady=(0, 10))

        tk.Button(
            btn_frame, text="⟳  JETZT SCANNEN", command=self.scan_einmal,
            bg=GOLD, fg='#000000', font=('Segoe UI', 11, 'bold'),
            relief='flat', pady=9, cursor='hand2',
            activebackground=GOLD2, activeforeground='#000000'
        ).pack(side='left', expand=True, fill='x', padx=(0, 5))

        self.auto_btn = tk.Button(
            btn_frame, text="▶  AUTO-START", command=self.toggle_auto,
            bg=BLUE, fg=TEXT, font=('Segoe UI', 11, 'bold'),
            relief='flat', pady=9, cursor='hand2',
            activebackground=BLUE2, activeforeground=TEXT
        )
        self.auto_btn.pack(side='left', expand=True, fill='x', padx=5)

        tk.Button(
            btn_frame, text="⚙  SETTINGS", command=self.oeffne_einstellungen,
            bg=GRAY, fg='#aaaaaa', font=('Segoe UI', 11, 'bold'),
            relief='flat', pady=9, cursor='hand2',
            activebackground=GRAY2, activeforeground=TEXT
        ).pack(side='left', expand=True, fill='x', padx=(5, 0))

        # Separator
        tk.Frame(self.root, bg=GRAY, height=1).pack(fill='x', padx=14)

        # ── PROFIT RECHNER ───────────────────────────────────────────────────
        profit_outer = tk.Frame(self.root, bg=BG)
        profit_outer.pack(fill='x', padx=14, pady=10)

        # Abschnittstitel
        self._section_title(profit_outer, "PROFIT RECHNER")

        row = tk.Frame(profit_outer, bg=BG)
        row.pack(fill='x')

        # Einkaufspreis
        grp1 = tk.Frame(row, bg=BG)
        grp1.pack(side='left', expand=True, fill='x', padx=(0, 6))
        tk.Label(grp1, text="EINKAUFSPREIS (€)", font=('Segoe UI', 8),
                 fg=TEXT3, bg=BG, anchor='w').pack(fill='x')
        self.buy_var = tk.StringVar(value="10500")
        tk.Entry(grp1, textvariable=self.buy_var,
                 bg=BG3, fg=TEXT, insertbackground=GOLD,
                 relief='flat', highlightthickness=1,
                 highlightbackground=GRAY, highlightcolor=GOLD,
                 font=('Segoe UI', 12)
                 ).pack(fill='x', ipady=7)

        # Anzahl
        grp2 = tk.Frame(row, bg=BG)
        grp2.pack(side='left', expand=True, fill='x', padx=6)
        tk.Label(grp2, text="ANZAHL STÜCK", font=('Segoe UI', 8),
                 fg=TEXT3, bg=BG, anchor='w').pack(fill='x')
        self.qty_var = tk.StringVar(value="1")
        tk.Entry(grp2, textvariable=self.qty_var,
                 bg=BG3, fg=TEXT, insertbackground=GOLD,
                 relief='flat', highlightthickness=1,
                 highlightbackground=GRAY, highlightcolor=GOLD,
                 font=('Segoe UI', 12)
                 ).pack(fill='x', ipady=7)

        # Ergebnis-Box
        result_box = tk.Frame(row, bg=BG_GOLD, padx=14, pady=6)
        result_box.pack(side='left', padx=(6, 0))
        tk.Label(result_box, text="PROFIT", font=('Segoe UI', 8),
                 fg=TEXT3, bg=BG_GOLD).pack()
        self.profit_val_var = tk.StringVar(value="+0€")
        self.lbl_profit_val = tk.Label(result_box, textvariable=self.profit_val_var,
                                       font=('Segoe UI', 16, 'bold'),
                                       fg=GREEN, bg=BG_GOLD, width=9)
        self.lbl_profit_val.pack()
        self.profit_pct_var = tk.StringVar(value="▲ 0,0%")
        tk.Label(result_box, textvariable=self.profit_pct_var,
                 font=('Segoe UI', 9), fg=TEXT3, bg=BG_GOLD).pack()

        self.buy_var.trace_add('write', lambda *_: self._calc_profit())
        self.qty_var.trace_add('write', lambda *_: self._calc_profit())

        # Separator
        tk.Frame(self.root, bg=GRAY, height=1).pack(fill='x', padx=14, pady=4)

        # ── LOG ──────────────────────────────────────────────────────────────
        log_outer = tk.Frame(self.root, bg=BG)
        log_outer.pack(fill='x', padx=14, pady=(4, 4))

        self._section_title(log_outer, "LOG")

        self.log_box = scrolledtext.ScrolledText(
            log_outer, height=6, state='disabled',
            font=('Consolas', 9), bg='#0d0d0d', fg=TEXT3,
            insertbackground=GOLD, relief='flat',
            highlightthickness=1, highlightbackground='#1e1e1e'
        )
        self.log_box.pack(fill='x')
        self.log_box.tag_config('ok',   foreground=GREEN)
        self.log_box.tag_config('warn', foreground=ORANGE)
        self.log_box.tag_config('err',  foreground=RED)

        # ── FOOTER ───────────────────────────────────────────────────────────
        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill='x', padx=14, pady=6)

        self.countdown_var = tk.StringVar(value="")
        tk.Label(footer, textvariable=self.countdown_var,
                 font=('Segoe UI', 10), fg=TEXT4, bg=BG).pack(side='left')

        self.autostart_var = tk.BooleanVar()
        self._aktualisiere_autostart_checkbox()
        tk.Checkbutton(
            footer, text="Windows-Autostart",
            variable=self.autostart_var, command=self._toggle_autostart,
            font=('Segoe UI', 9), fg=TEXT4, bg=BG,
            selectcolor=BG3, activebackground=BG, activeforeground='#666'
        ).pack(side='right')

    # -----------------------------------------------------------------------
    # Ring-Icon zeichnen
    # -----------------------------------------------------------------------
    def _draw_ring(self, canvas, size=60, bg=BG2):
        cx = size / 2

        # Band unten
        bw, bh = size * 0.72, size * 0.22
        bx, by = cx - bw / 2, size * 0.62
        canvas.create_oval(bx, by, bx + bw, by + bh,
                           fill=GOLD, outline='#8B6914', width=1)
        m = size * 0.07
        canvas.create_oval(bx + m, by + m * 0.6,
                           bx + bw - m, by + bh - m * 0.6,
                           fill=bg, outline='')

        # Band-Oberkante
        canvas.create_oval(bx, by - bh * 0.35, bx + bw, by + bh * 0.65,
                           fill=GOLD, outline='#8B6914', width=1)
        canvas.create_oval(bx + m, by - bh * 0.15,
                           bx + bw - m, by + bh * 0.45,
                           fill=bg, outline='')

        # Zinken
        gem_bottom = size * 0.52
        band_top   = by + bh * 0.1
        for dx in [-0.26, 0.0, 0.26]:
            x = cx + dx * size
            canvas.create_line(x, gem_bottom, x, band_top,
                               fill=GOLD, width=2)

        # Edelstein (Polygon)
        gw, gh = size * 0.30, size * 0.36
        canvas.create_polygon(
            cx,            size * 0.10,
            cx + gw / 2,   size * 0.10 + gh * 0.33,
            cx + gw * 0.38, size * 0.10 + gh,
            cx - gw * 0.38, size * 0.10 + gh,
            cx - gw / 2,   size * 0.10 + gh * 0.33,
            fill='#4fc3f7', outline='#87CEEB', smooth=True
        )
        # Highlight
        canvas.create_polygon(
            cx,            size * 0.13,
            cx + gw * 0.22, size * 0.13 + gh * 0.28,
            cx,            size * 0.13 + gh * 0.46,
            cx - gw * 0.14, size * 0.13 + gh * 0.28,
            fill='white', outline='', stipple='gray25'
        )

    # -----------------------------------------------------------------------
    # Abschnittstitel Hilfsmethode
    # -----------------------------------------------------------------------
    def _section_title(self, parent, text):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill='x', pady=(0, 6))
        tk.Label(f, text=text, font=('Segoe UI', 8, 'bold'),
                 fg=TEXT3, bg=BG).pack(side='left')
        tk.Frame(f, bg=GRAY, height=1).pack(
            side='left', fill='x', expand=True, padx=(8, 0), pady=5)

    # -----------------------------------------------------------------------
    # Profit-Rechner
    # -----------------------------------------------------------------------
    def _fmt_preis(self, raw: str) -> str:
        """Formatiert '10500€' → '10.500€', lässt Prozentteil weg."""
        m = re.match(r'^(\d+)', raw.strip())
        if m:
            num = int(m.group(1))
            return f"{num:,}€".replace(',', '.')
        return raw

    def _calc_profit(self):
        try:
            buy = float(self.buy_var.get().replace(',', '.'))
            qty = float(self.qty_var.get().replace(',', '.'))
            if self._preis_aktuell > 0 and buy > 0 and qty > 0:
                profit = (self._preis_aktuell - buy) * qty
                pct    = (self._preis_aktuell - buy) / buy * 100
                sign   = '+' if profit >= 0 else ''
                self.profit_val_var.set(
                    f"{sign}{int(round(profit)):,}€".replace(',', '.'))
                self.profit_pct_var.set(
                    f"{'▲' if pct >= 0 else '▼'} {'+' if pct >= 0 else ''}{pct:.1f}%")
                self.lbl_profit_val.config(fg=GREEN if profit >= 0 else RED)
        except (ValueError, ZeroDivisionError):
            pass

    # -----------------------------------------------------------------------
    # Log
    # -----------------------------------------------------------------------
    def log(self, msg: str):
        ts   = datetime.now().strftime("%H:%M:%S")
        zeile = f"[{ts}]  {msg}\n"
        self.log_box.config(state='normal')

        # Farbe bestimmen
        if any(c in msg for c in ['✅', 'OK', 'Aktualisiert', 'Gefunden']):
            tag = 'ok'
        elif any(c in msg for c in ['⚠️', 'Antwort', 'Fallback', 'Fehler', '❌', 'Warnung']):
            tag = 'warn' if '⚠' in msg else 'err'
        else:
            tag = ''

        if tag:
            self.log_box.insert('end', zeile, tag)
        else:
            self.log_box.insert('end', zeile)

        self.log_box.see('end')
        self.log_box.config(state='disabled')
        print(zeile, end='')

    def set_status(self, text: str):
        # Farbe je nach Status
        if '✅' in text or 'Aktualisiert' in text:
            color = GREEN
        elif '❌' in text or 'Fehler' in text:
            color = RED
        elif '🔄' in text or 'Scanne' in text:
            color = GOLD
        else:
            color = TEXT2
        self.status_var.set(text)
        self.status_lbl.config(fg=color)

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
        self.v_min.set(self._fmt_preis(min_p))
        self.v_preis.set(self._fmt_preis(preis))
        self.v_max.set(self._fmt_preis(max_p))

        # Prozent-Anzeige aus preis extrahieren
        pct_match = re.search(r'([+-]?\d+[.,]\d+)\s*%', preis)
        if pct_match:
            self.v_change.set(f"▲ +{pct_match.group(1).replace(',', '.')}%")
        else:
            self.v_change.set("")

        # Aktuellem Preis (Zahl) für Profit-Rechner speichern
        preis_zahl = re.search(r'\d[\d.,]*', preis)
        if preis_zahl:
            try:
                raw = preis_zahl.group(0)
                if ',' in raw:
                    raw = raw.replace('.', '').replace(',', '.')
                else:
                    raw = raw.replace('.', '')
                self._preis_aktuell = float(raw)
                self.root.after(0, self._calc_profit)
            except ValueError:
                pass

        self.log(f"Gefunden:  Min={min_p}  |  Preis={preis}  |  Max={max_p}")

        self.cfg = lade_config()
        erfolge = update_sheets(min_p, preis, max_p, self.cfg, log_fn=self.log)
        jetzt   = datetime.now().strftime("%H:%M")

        if erfolge > 0:
            self.set_status(f"✅  Aktualisiert um {jetzt}")
        else:
            self.set_status("⚠️  Preise OK — Sheets-URLs prüfen!")

        return erfolge > 0

    def scan_einmal(self):
        if not self.running:
            threading.Thread(target=self._do_scan, daemon=True).start()
        else:
            self.log("Auto-Modus aktiv — nächster Scan läuft automatisch.")

    def toggle_auto(self):
        if self.running:
            self.running = False
            self.auto_btn.config(text="▶  AUTO-START", bg=BLUE)
            self.countdown_var.set("")
            self.log("Auto-Modus gestoppt.")
        else:
            self.running = True
            self.auto_btn.config(text="■  STOPP", bg='#c62828')
            interval = self.cfg.get("interval_minuten", 15)
            self.log(f"Auto-Modus gestartet (alle {interval} Min).")
            self._auto_thread = threading.Thread(
                target=self._auto_loop, daemon=True)
            self._auto_thread.start()

    def _auto_loop(self):
        while self.running:
            self.root.after(0, lambda: None)
            self._do_scan()
            if not self.running:
                break
            interval_sek = self.cfg.get("interval_minuten", 15) * 60
            for verbleibend in range(interval_sek, 0, -1):
                if not self.running:
                    break
                m, s = divmod(verbleibend, 60)
                self.countdown_var.set(
                    f"Nächstes Update in:  {m:02d}:{s:02d}")
                time.sleep(1)
        self.countdown_var.set("")

    # -----------------------------------------------------------------------
    # Einstellungen
    # -----------------------------------------------------------------------
    def oeffne_einstellungen(self):
        win = tk.Toplevel(self.root)
        win.title("Einstellungen")
        win.geometry("560x300")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.grab_set()

        self.cfg = lade_config()

        def lbl(text, row):
            tk.Label(win, text=text, font=('Segoe UI', 9, 'bold'),
                     fg=TEXT2, bg=BG, anchor='w').grid(
                row=row, column=0, sticky='w', padx=14, pady=(10, 2))

        def entry(row, val):
            e = tk.Entry(win, width=62, font=('Consolas', 8),
                         bg=BG3, fg=TEXT, insertbackground=GOLD,
                         relief='flat', highlightthickness=1,
                         highlightbackground=GRAY, highlightcolor=GOLD)
            e.insert(0, val)
            e.grid(row=row, column=0, padx=14, pady=2, sticky='ew')
            return e

        lbl("Sheet 1 URL (A1–E1):", 0)
        e1 = entry(1, self.cfg.get("webapp_sheet1", ""))

        lbl("Sheet 2 URL (Test Neustart C4–E4):", 2)
        e2 = entry(3, self.cfg.get("webapp_sheet2", ""))

        lbl("Update-Interval (Minuten):", 4)
        e3 = tk.Entry(win, width=10, font=('Segoe UI', 10),
                      bg=BG3, fg=TEXT, insertbackground=GOLD,
                      relief='flat', highlightthickness=1,
                      highlightbackground=GRAY, highlightcolor=GOLD)
        e3.insert(0, str(self.cfg.get("interval_minuten", 15)))
        e3.grid(row=5, column=0, padx=14, pady=2, sticky='w')

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

        tk.Button(win, text="  Speichern  ", command=speichern,
                  bg=GOLD, fg='#000', font=('Segoe UI', 10, 'bold'),
                  relief='flat', padx=12, pady=6, cursor='hand2',
                  activebackground=GOLD2, activeforeground='#000'
                  ).grid(row=6, column=0, pady=14, padx=14, sticky='w')

    # -----------------------------------------------------------------------
    # Autostart
    # -----------------------------------------------------------------------
    def _aktualisiere_autostart_checkbox(self):
        startup_dir = os.path.join(
            os.environ.get("APPDATA", ""),
            r"Microsoft\Windows\Start Menu\Programs\Startup"
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
    if autostart_modus:
        root.iconify()
    root.mainloop()


if __name__ == "__main__":
    main()
