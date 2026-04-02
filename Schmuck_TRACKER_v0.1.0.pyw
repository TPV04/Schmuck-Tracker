"""
Schmuck_TRACKER v0.1.0
======================
- Eingebaute Markt-Tabelle (alle Items, sortierbar, suchbar)
- Kein Google Sheets mehr noetig
- API-Backend: direkt via LYL Markt-API
- Profit-Rechner
- Haeuser-Inventar (Popup)

Benoetigt (einmalig installieren):
  pip install requests
"""

import tkinter as tk
from tkinter import messagebox
import tkinter.ttk as ttk
import threading
import time
import requests
import os
import sys
import json
import re
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

# ---------------------------------------------------------------------------
# KONFIGURATION
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "interval_minuten": 15
}

LYL_API      = "https://www.lyl.gg/lyl-api/market.php"
CONFIG_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
HOUSES_JSON  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "houses.json")
STARTUP_NAME = "Schmuck_TRACKER"


# ---------------------------------------------------------------------------
# HILFS-FUNKTIONEN
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
# API-BACKEND
# ---------------------------------------------------------------------------

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, */*",
    "Referer": "https://www.lyl.gg/",
    "X-Requested-With": "XMLHttpRequest"
}


def hole_markt(log_fn=None):
    """Holt alle Marktdaten via LYL API. Gibt Liste zurueck."""
    try:
        r = requests.get(LYL_API, headers=API_HEADERS, timeout=15)
        data = r.json()
        return data.get("market", [])
    except Exception as e:
        if log_fn:
            log_fn(f"API Fehler: {e}")
    return []


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
        self.root.title("Schmuck_TRACKER v0.1.0")
        self.root.geometry("720x840")
        self.root.minsize(600, 600)
        self.root.resizable(True, True)
        self.root.configure(bg=BG)

        self.cfg             = lade_config()
        self.running         = False
        self._auto_thread    = None
        self._preis_aktuell  = 0
        self._markt_daten    = []   # Cache aller API-Items
        self._sort_col       = "name"
        self._sort_rev       = False

        self._baue_ttk_style()
        self._baue_gui()

        self.log("Schmuck_TRACKER v0.1.0 gestartet.")
        self.log(f"Interval: {self.cfg['interval_minuten']} Min. | Sheets-Anbindung entfernt.")

        if autostart_modus:
            self.root.after(1500, self.toggle_auto)

    # -----------------------------------------------------------------------
    # TTK Style (Dark)
    # -----------------------------------------------------------------------
    def _baue_ttk_style(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview",
                         background=BG3,
                         foreground=TEXT,
                         fieldbackground=BG3,
                         rowheight=23,
                         font=('Segoe UI', 9),
                         borderwidth=0)
        style.configure("Treeview.Heading",
                         background=BG2,
                         foreground=GOLD,
                         font=('Segoe UI', 9, 'bold'),
                         relief='flat',
                         padding=(6, 4))
        style.map("Treeview",
                   background=[('selected', '#2a1e00')],
                   foreground=[('selected', GOLD2)])
        style.map("Treeview.Heading",
                   background=[('active', GRAY2),
                                ('pressed', GRAY)])
        style.configure("Vertical.TScrollbar",
                         background=GRAY, troughcolor=BG2,
                         arrowcolor=TEXT3, borderwidth=0)

    # -----------------------------------------------------------------------
    # GUI Aufbau
    # -----------------------------------------------------------------------
    def _baue_gui(self):

        # ── HEADER ──────────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=BG2)
        header.pack(fill='x')

        ring_cv = tk.Canvas(header, width=60, height=60, bg=BG2,
                            highlightthickness=0)
        ring_cv.pack(side='left', padx=(16, 10), pady=12)
        self._draw_ring(ring_cv, 60, BG2)

        info = tk.Frame(header, bg=BG2)
        info.pack(side='left', pady=12)

        title_cv = tk.Canvas(info, bg=BG2, highlightthickness=0,
                             height=28, width=360)
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
        self._dot_cv = dot_cv

        self.status_var = tk.StringVar(value="Bereit")
        self.status_lbl = tk.Label(status_row, textvariable=self.status_var,
                                   font=('Segoe UI', 11), fg=GREEN, bg=BG2)
        self.status_lbl.pack(side='left')

        self.update_time_var = tk.StringVar(value="")
        tk.Label(header, textvariable=self.update_time_var,
                 font=('Segoe UI', 8), fg=TEXT3, bg=BG2).pack(
            side='right', padx=16)

        # Separator
        tk.Frame(self.root, bg=GRAY, height=1).pack(fill='x')

        # ── PREISKARTEN (Schmuck) ────────────────────────────────────────────
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

        # PREIS
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
        tk.Label(max_inner, text="Hoechstkurs", font=('Segoe UI', 8),
                 fg=TEXT3, bg=BG3).pack()

        # ── BUTTONS ─────────────────────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(fill='x', padx=14, pady=(0, 10))

        tk.Button(
            btn_frame, text="\u27f3  JETZT SCANNEN", command=self.scan_einmal,
            bg=GOLD, fg='#000000', font=('Segoe UI', 11, 'bold'),
            relief='flat', pady=9, cursor='hand2',
            activebackground=GOLD2, activeforeground='#000000'
        ).pack(side='left', expand=True, fill='x', padx=(0, 5))

        self.auto_btn = tk.Button(
            btn_frame, text="\u25b6  AUTO-START", command=self.toggle_auto,
            bg=BLUE, fg=TEXT, font=('Segoe UI', 11, 'bold'),
            relief='flat', pady=9, cursor='hand2',
            activebackground=BLUE2, activeforeground=TEXT
        )
        self.auto_btn.pack(side='left', expand=True, fill='x', padx=5)

        tk.Button(
            btn_frame, text="\U0001f3e0  HAEUSER", command=self.oeffne_haeuser,
            bg='#1a2a1a', fg='#4CAF50', font=('Segoe UI', 11, 'bold'),
            relief='flat', pady=9, cursor='hand2',
            activebackground='#2a3a2a', activeforeground=TEXT
        ).pack(side='left', expand=True, fill='x', padx=5)

        tk.Button(
            btn_frame, text="\u2699  SETTINGS", command=self.oeffne_einstellungen,
            bg=GRAY, fg='#aaaaaa', font=('Segoe UI', 11, 'bold'),
            relief='flat', pady=9, cursor='hand2',
            activebackground=GRAY2, activeforeground=TEXT
        ).pack(side='left', expand=True, fill='x', padx=(5, 0))

        # Separator
        tk.Frame(self.root, bg=GRAY, height=1).pack(fill='x', padx=14)

        # ── PROFIT RECHNER ───────────────────────────────────────────────────
        profit_outer = tk.Frame(self.root, bg=BG)
        profit_outer.pack(fill='x', padx=14, pady=10)

        self._section_title(profit_outer, "PROFIT RECHNER")

        row = tk.Frame(profit_outer, bg=BG)
        row.pack(fill='x')

        grp1 = tk.Frame(row, bg=BG)
        grp1.pack(side='left', expand=True, fill='x', padx=(0, 6))
        tk.Label(grp1, text="EINKAUFSPREIS (\u20ac)", font=('Segoe UI', 8),
                 fg=TEXT3, bg=BG, anchor='w').pack(fill='x')
        self.buy_var = tk.StringVar(value="10500")
        tk.Entry(grp1, textvariable=self.buy_var,
                 bg=BG3, fg=TEXT, insertbackground=GOLD,
                 relief='flat', highlightthickness=1,
                 highlightbackground=GRAY, highlightcolor=GOLD,
                 font=('Segoe UI', 12)).pack(fill='x', ipady=7)

        grp2 = tk.Frame(row, bg=BG)
        grp2.pack(side='left', expand=True, fill='x', padx=6)
        tk.Label(grp2, text="ANZAHL STUECK", font=('Segoe UI', 8),
                 fg=TEXT3, bg=BG, anchor='w').pack(fill='x')
        self.qty_var = tk.StringVar(value="1")
        tk.Entry(grp2, textvariable=self.qty_var,
                 bg=BG3, fg=TEXT, insertbackground=GOLD,
                 relief='flat', highlightthickness=1,
                 highlightbackground=GRAY, highlightcolor=GOLD,
                 font=('Segoe UI', 12)).pack(fill='x', ipady=7)

        result_box = tk.Frame(row, bg=BG_GOLD, padx=14, pady=6)
        result_box.pack(side='left', padx=(6, 0))
        tk.Label(result_box, text="PROFIT", font=('Segoe UI', 8),
                 fg=TEXT3, bg=BG_GOLD).pack()
        self.profit_val_var = tk.StringVar(value="+0\u20ac")
        self.lbl_profit_val = tk.Label(result_box,
                                       textvariable=self.profit_val_var,
                                       font=('Segoe UI', 16, 'bold'),
                                       fg=GREEN, bg=BG_GOLD, width=9)
        self.lbl_profit_val.pack()
        self.profit_pct_var = tk.StringVar(value="\u25b2 0,0%")
        tk.Label(result_box, textvariable=self.profit_pct_var,
                 font=('Segoe UI', 9), fg=TEXT3, bg=BG_GOLD).pack()

        self.buy_var.trace_add('write', lambda *_: self._calc_profit())
        self.qty_var.trace_add('write', lambda *_: self._calc_profit())

        # Separator
        tk.Frame(self.root, bg=GRAY, height=1).pack(fill='x', padx=14, pady=4)

        # ── MARKT TABELLE ─────────────────────────────────────────────────────
        markt_outer = tk.Frame(self.root, bg=BG)
        markt_outer.pack(fill='both', expand=True, padx=14, pady=(4, 0))

        # Titel + Suchfeld in einer Zeile
        top_row = tk.Frame(markt_outer, bg=BG)
        top_row.pack(fill='x', pady=(0, 6))

        tk.Label(top_row, text="MARKT", font=('Segoe UI', 8, 'bold'),
                 fg=TEXT3, bg=BG).pack(side='left')
        tk.Frame(top_row, bg=GRAY, height=1).pack(
            side='left', fill='x', expand=True, padx=(8, 16), pady=5)

        # Item-Zaehler
        self.item_count_var = tk.StringVar(value="")
        tk.Label(top_row, textvariable=self.item_count_var,
                 font=('Segoe UI', 8), fg=TEXT3, bg=BG).pack(side='right', padx=(0, 8))

        # Suchfeld
        tk.Label(top_row, text="\U0001f50d", fg=TEXT3, bg=BG,
                 font=('Segoe UI', 10)).pack(side='right')
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *_: self._filter_tabelle())
        tk.Entry(top_row, textvariable=self.search_var, width=18,
                 bg=BG3, fg=TEXT, insertbackground=GOLD,
                 relief='flat', highlightthickness=1,
                 highlightbackground=GRAY, highlightcolor=GOLD,
                 font=('Segoe UI', 9)).pack(side='right', ipady=3)

        # Treeview-Bereich
        tree_frame = tk.Frame(markt_outer, bg=BG)
        tree_frame.pack(fill='both', expand=True)

        cols = ("name", "min", "preis", "max", "diff")
        self.tree = ttk.Treeview(tree_frame, columns=cols,
                                  show='headings', selectmode='browse')

        col_cfg = [
            ("name",  "Name",     240, 'w'),
            ("min",   "Min \u20ac",  105, 'e'),
            ("preis", "Preis \u20ac",115, 'e'),
            ("max",   "Max \u20ac",  105, 'e'),
            ("diff",  "Diff %",    90, 'e'),
        ]

        for cid, hdr, width, anchor in col_cfg:
            self.tree.heading(cid, text=hdr,
                               command=lambda c=cid: self._sort_by(c))
            self.tree.column(cid, width=width, minwidth=60,
                              anchor=anchor, stretch=(cid == "name"))

        # Zeilenfarben
        self.tree.tag_configure('schmuck',  background='#2a1e00', foreground=GOLD2)
        self.tree.tag_configure('positive', background='#0d1a0d', foreground='#81c784')
        self.tree.tag_configure('negative', background='#1a0d0d', foreground='#e57373')
        self.tree.tag_configure('neutral',  background=BG3,       foreground=TEXT)
        self.tree.tag_configure('alt',      background='#181818', foreground=TEXT2)

        vsb = ttk.Scrollbar(tree_frame, orient='vertical',
                             command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self.tree.bind('<MouseWheel>',
                        lambda e: self.tree.yview_scroll(
                            int(-1 * (e.delta / 120)), 'units'))

        # Sortier-Pfeil im Heading
        self._sort_pfeil = {}

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
    # Ring-Icon
    # -----------------------------------------------------------------------
    def _draw_ring(self, canvas, size=60, bg=BG2):
        cx = size / 2
        bw, bh = size * 0.72, size * 0.22
        bx, by = cx - bw / 2, size * 0.62
        canvas.create_oval(bx, by, bx + bw, by + bh,
                           fill=GOLD, outline='#8B6914', width=1)
        m = size * 0.07
        canvas.create_oval(bx + m, by + m * 0.6,
                           bx + bw - m, by + bh - m * 0.6,
                           fill=bg, outline='')
        canvas.create_oval(bx, by - bh * 0.35, bx + bw, by + bh * 0.65,
                           fill=GOLD, outline='#8B6914', width=1)
        canvas.create_oval(bx + m, by - bh * 0.15,
                           bx + bw - m, by + bh * 0.45,
                           fill=bg, outline='')
        gem_bottom = size * 0.52
        band_top   = by + bh * 0.1
        for dx in [-0.26, 0.0, 0.26]:
            x = cx + dx * size
            canvas.create_line(x, gem_bottom, x, band_top,
                               fill=GOLD, width=2)
        gw, gh = size * 0.30, size * 0.36
        canvas.create_polygon(
            cx,             size * 0.10,
            cx + gw / 2,   size * 0.10 + gh * 0.33,
            cx + gw * 0.38, size * 0.10 + gh,
            cx - gw * 0.38, size * 0.10 + gh,
            cx - gw / 2,   size * 0.10 + gh * 0.33,
            fill='#4fc3f7', outline='#87CEEB', smooth=True
        )
        canvas.create_polygon(
            cx,             size * 0.13,
            cx + gw * 0.22, size * 0.13 + gh * 0.28,
            cx,             size * 0.13 + gh * 0.46,
            cx - gw * 0.14, size * 0.13 + gh * 0.28,
            fill='white', outline='', stipple='gray25'
        )

    # -----------------------------------------------------------------------
    # Abschnittstitel
    # -----------------------------------------------------------------------
    def _section_title(self, parent, text):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill='x', pady=(0, 6))
        tk.Label(f, text=text, font=('Segoe UI', 8, 'bold'),
                 fg=TEXT3, bg=BG).pack(side='left')
        tk.Frame(f, bg=GRAY, height=1).pack(
            side='left', fill='x', expand=True, padx=(8, 0), pady=5)

    # -----------------------------------------------------------------------
    # Markt-Tabelle
    # -----------------------------------------------------------------------
    def _update_markt_tabelle(self, markt_daten):
        """Speichert neue Daten und baut Tabelle neu auf."""
        self._markt_daten = markt_daten
        self._filter_tabelle()

    def _filter_tabelle(self):
        suche = self.search_var.get().lower().strip()
        for item in self.tree.get_children():
            self.tree.delete(item)

        daten = list(self._markt_daten)
        if not daten:
            self.item_count_var.set("")
            return

        # Filter
        if suche:
            daten = [d for d in daten if suche in d.get("name", "").lower()]

        # Sortierung
        col = self._sort_col
        rev = self._sort_rev
        try:
            if col == "name":
                daten.sort(key=lambda x: x.get("name", "").lower(), reverse=rev)
            elif col == "min":
                daten.sort(key=lambda x: float(x.get("min", 0)), reverse=rev)
            elif col == "preis":
                daten.sort(key=lambda x: float(x.get("price", 0)), reverse=rev)
            elif col == "max":
                daten.sort(key=lambda x: float(x.get("max", 0)), reverse=rev)
            elif col == "diff":
                daten.sort(key=lambda x: float(x.get("diff", 0)), reverse=rev)
        except Exception:
            pass

        self.item_count_var.set(f"{len(daten)} Items")

        for i, item in enumerate(daten):
            name  = item.get("name", "")
            min_p = int(float(item.get("min",   0)))
            preis = int(float(item.get("price", 0)))
            max_p = int(float(item.get("max",   0)))
            diff  = float(item.get("diff", 0))

            def fmt(n): return f"{n:,}".replace(',', '.')

            vals = (name, fmt(min_p), fmt(preis), fmt(max_p), f"{diff:+.1f}%")

            if name.lower() == "schmuck":
                tag = 'schmuck'
            elif diff >= 1.0:
                tag = 'positive'
            elif diff <= -1.0:
                tag = 'negative'
            elif i % 2 == 0:
                tag = 'neutral'
            else:
                tag = 'alt'

            self.tree.insert('', 'end', values=vals, tags=(tag,))

        # Schmuck anspringen wenn kein Suchtext
        if not suche:
            for iid in self.tree.get_children():
                if self.tree.item(iid, 'values')[0].lower() == 'schmuck':
                    self.tree.see(iid)
                    break

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = True if col != "name" else False
        # Heading-Pfeil aktualisieren
        pfeil = " \u25bc" if self._sort_rev else " \u25b2"
        labels = {"name": "Name", "min": "Min \u20ac",
                  "preis": "Preis \u20ac", "max": "Max \u20ac", "diff": "Diff %"}
        for c, lbl in labels.items():
            self.tree.heading(c, text=(lbl + pfeil) if c == col else lbl)
        self._filter_tabelle()

    # -----------------------------------------------------------------------
    # Profit-Rechner
    # -----------------------------------------------------------------------
    def _fmt_preis(self, raw: str) -> str:
        m = re.match(r'^(\d+)', raw.strip())
        if m:
            num = int(m.group(1))
            return f"{num:,}\u20ac".replace(',', '.')
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
                    f"{sign}{int(round(profit)):,}\u20ac".replace(',', '.'))
                self.profit_pct_var.set(
                    f"{'▲' if pct >= 0 else '▼'} {'+' if pct >= 0 else ''}{pct:.1f}%")
                self.lbl_profit_val.config(fg=GREEN if profit >= 0 else RED)
        except (ValueError, ZeroDivisionError):
            pass

    # -----------------------------------------------------------------------
    # Log (nur Konsole, kein Fenster)
    # -----------------------------------------------------------------------
    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            print(f"[{ts}]  {msg}")
        except Exception:
            pass

    def set_status(self, text: str):
        if '\u2705' in text or 'Aktualisiert' in text:
            color = GREEN
        elif '\u274c' in text or 'Fehler' in text:
            color = RED
        elif '\U0001f504' in text or 'Scanne' in text:
            color = GOLD
        else:
            color = TEXT2
        self.status_var.set(text)
        self.status_lbl.config(fg=color)

    # -----------------------------------------------------------------------
    # Scan
    # -----------------------------------------------------------------------
    def _do_scan(self):
        self.set_status("\U0001f504  Scanne lyl.gg...")
        self.log("Starte Scan...")

        markt = hole_markt(log_fn=self.log)

        if not markt:
            self.set_status("\u274c  Marktdaten nicht gefunden")
            self.log("FEHLER: API-Abfrage fehlgeschlagen.")
            return False

        # Tabelle im GUI-Thread aktualisieren
        self.root.after(0, lambda: self._update_markt_tabelle(markt))

        # Schmuck-Preiskarten
        for item in markt:
            if item.get("name", "").lower() == "schmuck":
                min_p = str(int(float(item["min"])))
                preis = f"{int(float(item['price']))}\u20ac ({item['diff']:+.1f}%)"
                max_p = str(int(float(item["max"])))

                self.v_min.set(self._fmt_preis(min_p))
                self.v_preis.set(self._fmt_preis(preis))
                self.v_max.set(self._fmt_preis(max_p))

                diff_val = float(item.get("diff", 0))
                arrow = "\u25b2" if diff_val >= 0 else "\u25bc"
                col   = GREEN    if diff_val >= 0 else RED
                self.v_change.set(f"{arrow} {diff_val:+.1f}%")

                # Preis fuer Profit-Rechner
                try:
                    self._preis_aktuell = float(item["price"])
                    self.root.after(0, self._calc_profit)
                except (ValueError, KeyError):
                    pass

                self.log(f"Schmuck: Min={min_p}\u20ac | Preis={preis} | Max={max_p}\u20ac")
                break

        jetzt = datetime.now().strftime("%H:%M")
        self.update_time_var.set(f"Stand: {jetzt}  \u2022  {len(markt)} Items")
        self.set_status(f"\u2705  Aktualisiert um {jetzt}")
        return True

    def scan_einmal(self):
        if not self.running:
            threading.Thread(target=self._do_scan, daemon=True).start()
        else:
            self.log("Auto-Modus aktiv — naechster Scan laeuft automatisch.")

    def toggle_auto(self):
        if self.running:
            self.running = False
            self.auto_btn.config(text="\u25b6  AUTO-START", bg=BLUE)
            self.countdown_var.set("")
            self.log("Auto-Modus gestoppt.")
        else:
            self.running = True
            self.auto_btn.config(text="\u25a0  STOPP", bg='#c62828')
            interval = self.cfg.get("interval_minuten", 15)
            self.log(f"Auto-Modus gestartet (alle {interval} Min).")
            self._auto_thread = threading.Thread(
                target=self._auto_loop, daemon=True)
            self._auto_thread.start()

    def _auto_loop(self):
        while self.running:
            self._do_scan()
            if not self.running:
                break
            interval_sek = self.cfg.get("interval_minuten", 15) * 60
            for verbleibend in range(interval_sek, 0, -1):
                if not self.running:
                    break
                m, s = divmod(verbleibend, 60)
                self.countdown_var.set(
                    f"Naechstes Update in:  {m:02d}:{s:02d}")
                time.sleep(1)
        self.countdown_var.set("")

    # -----------------------------------------------------------------------
    # Haeuser Fenster (neues Modul)
    # -----------------------------------------------------------------------
    def oeffne_haeuser(self):
        from haeuser_fenster import HaeuserFenster
        HaeuserFenster(self.root, markt_daten=self._markt_daten)

    # -----------------------------------------------------------------------
    # Einstellungen
    # -----------------------------------------------------------------------
    def oeffne_einstellungen(self):
        win = tk.Toplevel(self.root)
        win.title("Einstellungen")
        win.geometry("340x160")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.grab_set()

        self.cfg = lade_config()

        tk.Label(win, text="Update-Interval (Minuten):",
                 font=('Segoe UI', 10, 'bold'), fg=TEXT2, bg=BG,
                 anchor='w').pack(padx=20, pady=(20, 4), anchor='w')

        e = tk.Entry(win, width=10, font=('Segoe UI', 12),
                     bg=BG3, fg=TEXT, insertbackground=GOLD,
                     relief='flat', highlightthickness=1,
                     highlightbackground=GRAY, highlightcolor=GOLD)
        e.insert(0, str(self.cfg.get("interval_minuten", 15)))
        e.pack(padx=20, pady=4, anchor='w', ipady=6)

        def speichern():
            try:
                self.cfg["interval_minuten"] = int(e.get().strip())
            except ValueError:
                pass
            speichere_config(self.cfg)
            self.log("Einstellungen gespeichert.")
            win.destroy()

        tk.Button(win, text="  Speichern  ", command=speichern,
                  bg=GOLD, fg='#000', font=('Segoe UI', 10, 'bold'),
                  relief='flat', padx=12, pady=6, cursor='hand2',
                  activebackground=GOLD2, activeforeground='#000'
                  ).pack(padx=20, pady=14, anchor='w')

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
            self.log(f"Autostart {'aktiviert' if aktivieren else 'deaktiviert'}.")
            if aktivieren and info:
                self.log(f"  \u2192 {info}")
        else:
            self.log(f"Autostart Fehler: {info}")
            messagebox.showerror("Autostart Fehler", info)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    autostart_modus = "--autostart" in sys.argv
    root = tk.Tk()
    app  = SchmuckTrackerApp(root, autostart_modus=autostart_modus)
    if autostart_modus:
        root.iconify()
    root.mainloop()


if __name__ == "__main__":
    main()
