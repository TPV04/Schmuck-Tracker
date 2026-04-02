"""
Haeuser-Fenster Modul fuer Schmuck_TRACKER
4 Tabs: Uebersicht | Inventar | Buchungen | Mitglieder
"""
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox, simpledialog
import os, json, threading, subprocess, uuid
from datetime import datetime

BASE              = os.path.dirname(os.path.abspath(__file__))
HOUSES_JSON       = os.path.join(BASE, "houses.json")
HOUSE_NAMES_JSON  = os.path.join(BASE, "house_names.json")
TRANSACTIONS_JSON = os.path.join(BASE, "transactions.json")
MEMBERS_JSON      = os.path.join(BASE, "members.json")
PYTHON_EXE        = r"C:\Users\Tony\AppData\Local\Programs\Python\Python312\python.exe"
UPDATER_PY        = os.path.join(BASE, "haeuser_updater.py")

BG       = '#141414'
BG2      = '#1a1a1a'
BG3      = '#1e1e1e'
BG_GOLD  = '#1e1b0a'
GOLD     = '#D4A017'
GOLD2    = '#FFD700'
BLUE     = '#1565c0'
GREEN    = '#4CAF50'
RED      = '#f44336'
ORANGE   = '#FF9800'
GRAY     = '#2a2a2a'
GRAY2    = '#3a3a3a'
TEXT     = '#ffffff'
TEXT2    = '#999999'
TEXT3    = '#555555'

DEFAULT_MEMBERS = ["Tony Baron", "Nonen Tonen", "Dima Korsakow", "Wilhelm Maybach"]


def lade_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def speichere_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fmt(n):
    try:
        return f"{int(n):,}".replace(',', '.')
    except Exception:
        return str(n)


class HaeuserFenster:
    def __init__(self, parent, markt_daten=None):
        self.parent      = parent
        self.markt_daten = markt_daten or []
        self.price_map   = {
            it.get("name", "").lower(): it.get("price", 0)
            for it in self.markt_daten
        }

        self.houses_data  = lade_json(HOUSES_JSON, {"haeuser": []})
        self.house_names  = lade_json(HOUSE_NAMES_JSON, {})
        self.transactions = lade_json(TRANSACTIONS_JSON, [])
        self.members      = lade_json(MEMBERS_JSON, list(DEFAULT_MEMBERS))

        self.win = tk.Toplevel(parent)
        self.win.title("\U0001f3e0 Haeuser Management")
        self.win.configure(bg=BG)
        self.win.geometry("980x700")
        self.win.minsize(800, 500)
        self.win.resizable(True, True)

        self._buch_sort_col = "timestamp"
        self._buch_sort_rev = True
        self.datum_von      = None   # datetime oder None
        self.datum_bis      = None   # datetime oder None
        self.aktiver_preset = "Gesamt"
        self._preset_buttons = {}
        self._auto_job      = None   # after-Job fuer Auto-Aktualisierung

        self._setup_style()
        self._baue_ui()

        # Auto-Aktualisierung starten
        self._starte_auto_update()
        self.win.protocol("WM_DELETE_WINDOW", self._beim_schliessen)

    # ------------------------------------------------------------------
    def _setup_style(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure("H.Treeview", background=BG3, foreground=TEXT,
                    fieldbackground=BG3, rowheight=24, font=('Segoe UI', 9))
        s.configure("H.Treeview.Heading", background=BG2, foreground=GOLD,
                    font=('Segoe UI', 9, 'bold'), relief='flat', padding=(6, 4))
        s.map("H.Treeview",
              background=[('selected', '#2a1e00')],
              foreground=[('selected', GOLD2)])
        s.map("H.Treeview.Heading", background=[('active', GRAY2)])
        s.configure("H.TNotebook",     background=BG2, borderwidth=0)
        s.configure("H.TNotebook.Tab", background=GRAY, foreground=TEXT2,
                    font=('Segoe UI', 10, 'bold'), padding=(16, 8))
        s.map("H.TNotebook.Tab",
              background=[('selected', BG3)],
              foreground=[('selected', GOLD)])
        s.configure("H.Vertical.TScrollbar",
                    background=GRAY, troughcolor=BG2, arrowcolor=TEXT3)

    # ------------------------------------------------------------------
    def _baue_ui(self):
        hdr = tk.Frame(self.win, bg=BG2, pady=10)
        hdr.pack(fill='x')
        tk.Label(hdr, text="\U0001f3e0  HAEUSER MANAGEMENT",
                 font=('Segoe UI', 14, 'bold'), fg=GOLD, bg=BG2).pack(
            side='left', padx=16)
        self.status_var = tk.StringVar(value="")
        tk.Label(hdr, textvariable=self.status_var, font=('Segoe UI', 9),
                 fg=GREEN, bg=BG2).pack(side='right', padx=16)
        tk.Button(hdr, text="\U0001f504  UCP Aktualisieren",
                  command=self._aktualisieren,
                  bg=GOLD, fg='#000', font=('Segoe UI', 9, 'bold'),
                  relief='flat', padx=12, pady=4, cursor='hand2').pack(
            side='right', padx=8)

        nb = ttk.Notebook(self.win, style="H.TNotebook")
        nb.pack(fill='both', expand=True, padx=8, pady=8)

        self.t_uebersicht  = tk.Frame(nb, bg=BG)
        self.t_inventar    = tk.Frame(nb, bg=BG)
        self.t_buchungen   = tk.Frame(nb, bg=BG)
        self.t_mitglieder  = tk.Frame(nb, bg=BG)

        nb.add(self.t_uebersicht, text="  \U0001f4ca  UEBERSICHT  ")
        nb.add(self.t_inventar,   text="  \U0001f3e0  INVENTAR  ")
        nb.add(self.t_buchungen,  text="  \U0001f4dd  BUCHUNGEN  ")
        nb.add(self.t_mitglieder, text="  \U0001f465  MITGLIEDER  ")

        self._baue_uebersicht()
        self._baue_inventar()
        self._baue_buchungen()
        self._baue_mitglieder()

    # ==================================================================
    # AKTUALISIEREN (UCP Scraping + Auto-Diff)
    # ==================================================================
    def _aktualisieren(self):
        self.status_var.set("\u23f3 Lade UCP-Daten ...")

        def _run():
            try:
                # Snapshot der alten Daten
                alte = {
                    h.get("ort", f"h{i}"): {
                        it["name"].lower(): it["menge"]
                        for it in h.get("items", [])
                    }
                    for i, h in enumerate(self.houses_data.get("haeuser", []))
                }

                proc = subprocess.run(
                    [PYTHON_EXE, UPDATER_PY],
                    capture_output=True, text=True, timeout=180,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                # Fehlermeldung aus stdout/stderr lesen
                ausgabe = (proc.stdout or "") + (proc.stderr or "")
                zeilen = ausgabe.splitlines()
                fehler_zeilen  = [l for l in zeilen if l.startswith("FEHLER:")]
                status_zeilen  = [l for l in zeilen if l.startswith("STATUS:")]

                # Detail-Fehler (FEHLER_DETAIL) separat loggen
                detail_zeilen = [l for l in zeilen if l.startswith("FEHLER_DETAIL:")]

                # Letzten STATUS live anzeigen wenn kein Fehler
                if status_zeilen and not fehler_zeilen and "LOGIN_REQUIRED" not in zeilen:
                    if not any(l.startswith("OK:") for l in zeilen):
                        letzter = status_zeilen[-1].replace("STATUS: ", "")
                        self.win.after(0, lambda m=letzter:
                                       self.status_var.set(f"\u23f3 {m}"))

                # Login erforderlich → Chrome sichtbar oeffnen
                if "LOGIN_REQUIRED" in zeilen:
                    self.win.after(0, self._zeige_login_dialog)
                    return

                if fehler_zeilen:
                    msg = fehler_zeilen[0].replace("FEHLER: ", "")
                    self.win.after(0, lambda m=msg:
                                   self.status_var.set(f"\u274c {m}"))
                    return

                # Kein OK und kein FEHLER → rohe Ausgabe anzeigen
                if not any(l.startswith("OK:") for l in zeilen):
                    detail = ausgabe.strip()[:120] if ausgabe.strip() else "Keine Ausgabe vom Updater."
                    self.win.after(0, lambda m=detail:
                                   self.status_var.set(f"\u274c {m}"))
                    return

                neu_data  = lade_json(HOUSES_JSON, {"haeuser": []})
                auto_buch = []
                log_buch  = []   # Buchungen aus echten UCP-Logs
                now = datetime.now().isoformat()

                # Bekannte Log-IDs laden (Duplikate vermeiden)
                bekannte_log_ids = {
                    b.get("log_key", "") for b in self.transactions
                    if b.get("log_key")
                }

                for i, haus in enumerate(neu_data.get("haeuser", [])):
                    ort       = haus.get("ort", f"h{i}")
                    alt_items = alte.get(ort, {})
                    haus_name = self.house_names.get(str(i), ort)

                    # ── A) Echte LOG-Eintraege vom UCP verarbeiten ──────────
                    for log in haus.get("logs", []):
                        player = log.get("player", "").strip()
                        item   = log.get("item",   "").strip()
                        menge  = log.get("menge",  0)
                        ts_raw = log.get("ts",     "")
                        action = log.get("action", "").lower()

                        if not player or not item or menge <= 0:
                            continue

                        # Aktion bestimmen (JS setzt bereits "eingelagert"/"entnommen")
                        if action == "entnommen" or action.startswith("-"):
                            typ = "entnommen"
                        else:
                            typ = "eingelagert"

                        # Eindeutiger Key fuer Duplikat-Pruefung
                        log_key = f"{haus_name}|{ts_raw}|{player}|{item}|{menge}|{typ}"
                        if log_key in bekannte_log_ids:
                            continue

                        # Timestamp parsen — LYL Format: "02.04.26, 12:16"
                        ts_iso = now
                        for ts_fmt in [
                            "%d.%m.%y, %H:%M",   # LYL: "02.04.26, 12:16"
                            "%d.%m.%Y %H:%M:%S",
                            "%d.%m.%Y %H:%M",
                            "%Y-%m-%d %H:%M:%S",
                            "%Y-%m-%dT%H:%M"
                        ]:
                            try:
                                ts_iso = datetime.strptime(ts_raw, ts_fmt).isoformat()
                                break
                            except ValueError:
                                pass

                        log_buch.append({
                            "id":        str(uuid.uuid4())[:8],
                            "timestamp": ts_iso,
                            "person":    player,
                            "haus_idx":  i,
                            "haus_name": haus_name,
                            "item":      item,
                            "menge":     menge,
                            "typ":       typ,
                            "notiz":     f"UCP-Log ({ts_raw})",
                            "log_key":   log_key
                        })

                    # ── B) Inventar-Diff als Fallback (wenn keine Logs) ─────
                    if not haus.get("logs"):
                        for it in haus.get("items", []):
                            name  = it["name"]
                            neu_m = it["menge"]
                            alt_m = alt_items.get(name.lower(), 0)
                            diff  = neu_m - alt_m
                            if diff != 0:
                                auto_buch.append({
                                    "id":        str(uuid.uuid4())[:8],
                                    "timestamp": now,
                                    "person":    "[Automatisch]",
                                    "haus_idx":  i,
                                    "haus_name": haus_name,
                                    "item":      name,
                                    "menge":     abs(diff),
                                    "typ":       "eingelagert" if diff > 0 else "entnommen",
                                    "notiz":     "Auto-Diff UCP"
                                })
                        neu_keys = {it["name"].lower() for it in haus.get("items", [])}
                        for k, m in alt_items.items():
                            if k not in neu_keys and m > 0:
                                auto_buch.append({
                                    "id":        str(uuid.uuid4())[:8],
                                    "timestamp": now,
                                    "person":    "[Automatisch]",
                                    "haus_idx":  i,
                                    "haus_name": haus_name,
                                    "item":      k.capitalize(),
                                    "menge":     m,
                                    "typ":       "entnommen",
                                    "notiz":     "Auto-Diff UCP"
                                })

                # Alle neuen Buchungen vorne einfuegen
                alle_neu = log_buch + auto_buch
                if alle_neu:
                    self.transactions = alle_neu + self.transactions
                    speichere_json(TRANSACTIONS_JSON, self.transactions)

                self.houses_data = neu_data
                self.win.after(0, self._refresh_all)
                ts  = datetime.now().strftime("%H:%M")
                msg = f"\u2705 {ts}"
                if log_buch:
                    msg += f"  ({len(log_buch)} Log-Buchungen)"
                elif auto_buch:
                    msg += f"  ({len(auto_buch)} Auto-Buchungen)"
                self.win.after(0, lambda m=msg: self.status_var.set(m))

            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                # Vollstaendigen Traceback in error.log schreiben
                log_path = os.path.join(BASE, "error.log")
                try:
                    with open(log_path, "a", encoding="utf-8") as lf:
                        lf.write(f"\n=== {datetime.now()} ===\n{tb}\n")
                except Exception:
                    pass
                # Kurzinfo im Status + Hinweis auf Logdatei
                zeile = tb.strip().splitlines()[-1] if tb.strip() else str(e)
                self.win.after(0, lambda z=zeile:
                               self.status_var.set(f"\u274c {z}  \u2192 error.log"))

        threading.Thread(target=_run, daemon=True).start()

    def _refresh_all(self):
        self._refresh_uebersicht()
        self._refresh_inventar()
        self._refresh_buchungen()
        self._refresh_mitglieder()

    def _starte_auto_update(self):
        """Liest Interval aus config.json und plant naechste Aktualisierung."""
        if self._auto_job:
            try:
                self.win.after_cancel(self._auto_job)
            except Exception:
                pass
        try:
            cfg_path = os.path.join(BASE, "config.json")
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            minuten = int(cfg.get("interval_minuten", 15))
        except Exception:
            minuten = 15
        ms = minuten * 60 * 1000
        self._auto_job = self.win.after(ms, self._auto_aktualisieren)

    def _auto_aktualisieren(self):
        """Wird vom Timer aufgerufen — aktualisiert still im Hintergrund."""
        self._aktualisieren()
        self._starte_auto_update()   # naechsten Tick planen

    def _beim_schliessen(self):
        """Timer stoppen wenn Fenster geschlossen wird."""
        if self._auto_job:
            try:
                self.win.after_cancel(self._auto_job)
            except Exception:
                pass
        self.win.destroy()

    def _zeige_login_dialog(self):
        """Zeigt Login-Hinweis und oeffnet Chrome sichtbar."""
        self.status_var.set("\u26a0\ufe0f Nicht eingeloggt auf ucp.lyl.gg")

        # Tony-Chrome (Default-Profil) sichtbar starten fuer Login
        import subprocess
        try:
            subprocess.Popen([
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "--remote-debugging-port=9222",
                "--remote-allow-origins=*",
                f"--user-data-dir={os.path.join(os.environ.get('LOCALAPPDATA',''), 'Google', 'Chrome', 'User Data')}",
                "--profile-directory=Default",
                "--no-first-run",
                "--no-default-browser-check",
                "https://ucp.lyl.gg/houses"
            ])
        except Exception:
            pass

        dlg = tk.Toplevel(self.win)
        dlg.title("Login erforderlich")
        dlg.configure(bg=BG)
        dlg.geometry("420x220")
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="\u26a0\ufe0f  LOGIN ERFORDERLICH",
                 font=('Segoe UI', 13, 'bold'), fg=ORANGE, bg=BG).pack(pady=(20, 8))
        tk.Label(dlg, text="Chrome wurde geoeffnet.\nBitte auf ucp.lyl.gg einloggen\nund danach hier auf OK klicken.",
                 font=('Segoe UI', 10), fg=TEXT, bg=BG, justify='center').pack(pady=8)

        def ok():
            dlg.destroy()
            self._aktualisieren()

        tk.Button(dlg, text="\u2705  Eingeloggt \u2014 Jetzt aktualisieren",
                  command=ok,
                  bg=GOLD, fg='#000', font=('Segoe UI', 10, 'bold'),
                  relief='flat', padx=16, pady=8, cursor='hand2').pack(pady=12)
        tk.Button(dlg, text="Abbrechen", command=dlg.destroy,
                  bg=GRAY, fg=TEXT2, font=('Segoe UI', 9),
                  relief='flat', padx=10, pady=4, cursor='hand2').pack()

    def get_name(self, idx, haus):
        return self.house_names.get(str(idx), haus.get("ort", f"Haus {idx+1}"))

    # ==================================================================
    # TAB 1 – UEBERSICHT
    # ==================================================================
    def _baue_uebersicht(self):
        f = self.t_uebersicht

        self.stats_frame = tk.Frame(f, bg=BG)
        self.stats_frame.pack(fill='x', padx=12, pady=10)

        sep_row = tk.Frame(f, bg=BG)
        sep_row.pack(fill='x', padx=12, pady=(0, 4))
        tk.Label(sep_row, text="PRO HAUS", font=('Segoe UI', 8, 'bold'),
                 fg=TEXT3, bg=BG).pack(side='left')
        tk.Frame(sep_row, bg=GRAY, height=1).pack(
            side='left', fill='x', expand=True, padx=(8, 0), pady=5)

        tbl_f = tk.Frame(f, bg=BG)
        tbl_f.pack(fill='both', expand=True, padx=12, pady=(0, 8))

        cols = ("haus", "auslast", "schmuck", "gold", "eisen", "diamant", "sonstiges", "frei")
        self.tree_uebersicht = ttk.Treeview(tbl_f, columns=cols,
                                             show='headings', selectmode='browse',
                                             style="H.Treeview")
        col_cfgs = [
            ("haus",       "Haus",            200, 'w'),
            ("auslast",    "Auslast.",         115, 'e'),
            ("schmuck",    "\U0001f4a0 Schmuck",  90, 'e'),
            ("gold",       "\U0001f947 Gold",     90, 'e'),
            ("eisen",      "\U0001f529 Eisen",    90, 'e'),
            ("diamant",    "\U0001f48e Diamant",  90, 'e'),
            ("sonstiges",  "Sonstiges",          85, 'e'),
            ("frei",       "Frei",               80, 'e'),
        ]
        for cid, hdr, w, anchor in col_cfgs:
            self.tree_uebersicht.heading(cid, text=hdr)
            self.tree_uebersicht.column(cid, width=w, anchor=anchor,
                                         minwidth=40, stretch=(cid == "haus"))
        self.tree_uebersicht.tag_configure('voll',      foreground=RED)
        self.tree_uebersicht.tag_configure('warn',      foreground=ORANGE)
        self.tree_uebersicht.tag_configure('ok',        foreground=TEXT)
        self.tree_uebersicht.tag_configure('alt_ok',    foreground=TEXT,  background='#181818')
        self.tree_uebersicht.tag_configure('alt_warn',  foreground=ORANGE, background='#181818')
        self.tree_uebersicht.tag_configure('alt_voll',  foreground=RED,   background='#181818')

        vsb = ttk.Scrollbar(tbl_f, orient='vertical',
                             command=self.tree_uebersicht.yview,
                             style="H.Vertical.TScrollbar")
        self.tree_uebersicht.configure(yscrollcommand=vsb.set)
        self.tree_uebersicht.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self._refresh_uebersicht()

    def _refresh_uebersicht(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()

        haeuser = self.houses_data.get("haeuser", [])

        # Aggregieren
        totals = {}
        gesamt_wert = 0
        for haus in haeuser:
            for it in haus.get("items", []):
                k = it["name"].lower()
                totals[k] = totals.get(k, 0) + it["menge"]
                gesamt_wert += self.price_map.get(k, 0) * it["menge"]

        def total_kw(keywords):
            return sum(v for k, v in totals.items()
                       if any(kw in k for kw in keywords))

        schmuck = total_kw(["schmuck"])
        gold    = total_kw(["goldbarren", "gold"])
        eisen   = total_kw(["eisenbarren", "eisen"])
        diamant = total_kw(["diamant"])

        cards = [
            ("\U0001f4a0 SCHMUCK",  schmuck, self.price_map.get("schmuck",   0), GOLD2,    '#2a1e00'),
            ("\U0001f947 GOLD",     gold,    self.price_map.get("goldbarren", self.price_map.get("gold", 0)), '#FFD700', '#1e1a00'),
            ("\U0001f529 EISEN",    eisen,   self.price_map.get("eisenbarren", self.price_map.get("eisen", 0)), '#90A4AE', '#151820'),
            ("\U0001f48e DIAMANT",  diamant, self.price_map.get("diamant",   self.price_map.get("diamanten", 0)), '#4fc3f7', '#0d1a20'),
        ]
        for label, menge, preis, farbe, bg_c in cards:
            wert = menge * preis
            c = tk.Frame(self.stats_frame, bg=bg_c, padx=14, pady=10)
            c.pack(side='left', expand=True, fill='both', padx=(0, 6))
            tk.Label(c, text=label, font=('Segoe UI', 8, 'bold'),
                     fg=TEXT2, bg=bg_c).pack(anchor='w')
            tk.Label(c, text=f"{fmt(menge)} Stk",
                     font=('Segoe UI', 15, 'bold'), fg=farbe, bg=bg_c).pack(anchor='w')
            if wert > 0:
                tk.Label(c, text=f"{fmt(wert)}\u20ac",
                         font=('Segoe UI', 9), fg=TEXT2, bg=bg_c).pack(anchor='w')

        gc = tk.Frame(self.stats_frame, bg='#1a1a0d', padx=14, pady=10)
        gc.pack(side='left', expand=True, fill='both')
        tk.Label(gc, text="\U0001f4b0 GESAMT", font=('Segoe UI', 8, 'bold'),
                 fg=TEXT2, bg='#1a1a0d').pack(anchor='w')
        tk.Label(gc, text=f"{fmt(gesamt_wert)}\u20ac",
                 font=('Segoe UI', 14, 'bold'), fg=GOLD2, bg='#1a1a0d').pack(anchor='w')
        tk.Label(gc, text=f"{len(haeuser)} Haeuser",
                 font=('Segoe UI', 9), fg=TEXT2, bg='#1a1a0d').pack(anchor='w')

        # Tabelle
        for row in self.tree_uebersicht.get_children():
            self.tree_uebersicht.delete(row)

        for i, haus in enumerate(haeuser):
            name    = self.get_name(i, haus)
            kap     = haus.get("kapazitaet", 1) or 1
            belegt  = haus.get("belegt", 0)
            pct     = min(100, int(belegt / kap * 100))
            frei    = kap - belegt

            d = {it["name"].lower(): it["menge"] for it in haus.get("items", [])}
            sc = sum(v for k, v in d.items() if "schmuck"  in k)
            go = sum(v for k, v in d.items() if "gold"     in k)
            ei = sum(v for k, v in d.items() if "eisen"    in k)
            di = sum(v for k, v in d.items() if "diamant"  in k)
            so = sum(v for k, v in d.items()
                     if not any(kw in k for kw in ["schmuck","gold","eisen","diamant"]))

            def v(n): return fmt(n) if n > 0 else "\u2014"

            if pct >= 90:
                base = 'voll'
            elif pct >= 70:
                base = 'warn'
            else:
                base = 'ok'
            tag = ('alt_' + base) if i % 2 == 1 else base

            # Auslastung: freie Plaetze als Zahl + Prozent
            bar = f"{fmt(frei)} frei  ({pct}%)"
            self.tree_uebersicht.insert('', 'end', tags=(tag,),
                values=(name, bar,
                        v(sc), v(go), v(ei), v(di), v(so), fmt(frei)))

    # ==================================================================
    # TAB 2 – INVENTAR
    # ==================================================================
    def _baue_inventar(self):
        f = self.t_inventar

        top = tk.Frame(f, bg=BG2, pady=6)
        top.pack(fill='x')
        tk.Label(top, text="Haus:", fg=TEXT2, bg=BG2,
                 font=('Segoe UI', 9)).pack(side='left', padx=(12, 4))
        self.inv_haus_var = tk.StringVar(value="Alle Haeuser")
        self.inv_combo = ttk.Combobox(top, textvariable=self.inv_haus_var,
                                       state='readonly', width=30, font=('Segoe UI', 9))
        self.inv_combo.pack(side='left')
        self.inv_combo.bind('<<ComboboxSelected>>',
                             lambda e: self._refresh_inventar())

        cf = tk.Frame(f, bg=BG)
        cf.pack(fill='both', expand=True, padx=8, pady=6)
        self.inv_canvas = tk.Canvas(cf, bg=BG, highlightthickness=0)
        vsb = tk.Scrollbar(cf, orient='vertical', command=self.inv_canvas.yview)
        self.inv_sf = tk.Frame(self.inv_canvas, bg=BG)
        self.inv_sf.bind('<Configure>',
                          lambda e: self.inv_canvas.configure(
                              scrollregion=self.inv_canvas.bbox('all')))
        self.inv_canvas.create_window((0, 0), window=self.inv_sf, anchor='nw')
        self.inv_canvas.configure(yscrollcommand=vsb.set)
        self.inv_canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.inv_canvas.bind('<MouseWheel>',
                              lambda e: self.inv_canvas.yview_scroll(
                                  int(-1 * (e.delta / 120)), 'units'))
        self._refresh_inventar()

    def _refresh_inventar(self):
        haeuser = self.houses_data.get("haeuser", [])
        namen   = ["Alle Haeuser"] + [
            self.get_name(i, h) for i, h in enumerate(haeuser)
            if h.get("items") or h.get("belegt", 0) > 0
        ]
        self.inv_combo['values'] = namen
        if self.inv_haus_var.get() not in namen:
            self.inv_haus_var.set("Alle Haeuser")

        for w in self.inv_sf.winfo_children():
            w.destroy()

        gesamt = 0
        sel    = self.inv_haus_var.get()

        for idx, haus in enumerate(haeuser):
            if not haus.get("items") and haus.get("belegt", 0) == 0:
                continue
            name = self.get_name(idx, haus)
            if sel != "Alle Haeuser" and name != sel:
                continue

            kap    = haus.get("kapazitaet", 1) or 1
            belegt = haus.get("belegt", 0)
            pct    = min(100, int(belegt / kap * 100))
            farbe  = RED if pct >= 90 else ORANGE if pct >= 70 else GREEN

            card = tk.Frame(self.inv_sf, bg=BG3, pady=6, padx=10)
            card.pack(fill='x', pady=(0, 6))

            tr = tk.Frame(card, bg=BG3)
            tr.pack(fill='x')
            tk.Label(tr, text=f"\U0001f4cd {name}",
                     font=('Segoe UI', 11, 'bold'), fg=GOLD, bg=BG3).pack(side='left')

            def mk_rename(i, n):
                return lambda: self._umbenennen(i, n, self._refresh_inventar)
            tk.Button(tr, text="\u270f\ufe0f", font=('Segoe UI', 9),
                      bg=BG3, fg=TEXT3, relief='flat', cursor='hand2',
                      command=mk_rename(idx, name)).pack(side='left', padx=(6, 0))

            tk.Label(card,
                     text=f"Kapazitaet: {fmt(belegt)} / {fmt(kap)}  ({pct}%)   Frei: {fmt(kap-belegt)}",
                     font=('Segoe UI', 8), fg=farbe, bg=BG3).pack(anchor='w')

            bar_bg = tk.Frame(card, bg=GRAY, height=5)
            bar_bg.pack(fill='x', pady=(2, 6))
            bar_bg.update_idletasks()
            bw = bar_bg.winfo_width()
            if bw > 10:
                tk.Frame(bar_bg, bg=farbe, height=5,
                          width=max(2, int(bw * pct / 100))).place(x=0, y=0)

            items = haus.get("items", [])
            if not items:
                tk.Label(card, text="  (leer)", fg=TEXT3, bg=BG3,
                         font=('Segoe UI', 9)).pack(anchor='w')
                continue

            hr = tk.Frame(card, bg=BG2)
            hr.pack(fill='x', pady=(0, 2))
            for txt, w, a in [("Item", 24, 'w'), ("Menge", 10, 'e'),
                               ("Preis/Stk", 12, 'e'), ("Gesamtwert", 14, 'e')]:
                tk.Label(hr, text=txt, font=('Segoe UI', 8, 'bold'),
                         fg=TEXT3, bg=BG2, width=w, anchor=a).pack(side='left')

            hw = 0
            for it in items:
                p    = self.price_map.get(it["name"].lower(), 0)
                wert = p * it["menge"]
                hw  += wert
                r    = tk.Frame(card, bg=BG3)
                r.pack(fill='x')
                tk.Label(r, text=f"  {it['name']}", fg=TEXT, bg=BG3,
                         font=('Segoe UI', 9), anchor='w', width=24).pack(side='left')
                tk.Label(r, text=f"{fmt(it['menge'])}x", fg=TEXT2, bg=BG3,
                         font=('Segoe UI', 9), width=10, anchor='e').pack(side='left')
                tk.Label(r, text=f"{fmt(p)}\u20ac" if p else "\u2014",
                         fg=TEXT3, bg=BG3, font=('Segoe UI', 9),
                         width=12, anchor='e').pack(side='left')
                tk.Label(r, text=f"{fmt(wert)}\u20ac" if wert else "\u2014",
                         fg=GREEN if wert > 0 else TEXT3, bg=BG3,
                         font=('Segoe UI', 9, 'bold'), width=14, anchor='e').pack(side='left')

            gesamt += hw
            tk.Frame(card, bg=GRAY, height=1).pack(fill='x', pady=(4, 2))
            tk.Label(card, text=f"Hauswert: {fmt(hw)}\u20ac",
                     fg=GOLD, bg=BG3, font=('Segoe UI', 10, 'bold')).pack(anchor='e')

        tf = tk.Frame(self.inv_sf, bg=BG2, pady=10, padx=14)
        tf.pack(fill='x', pady=(8, 0))
        tk.Label(tf, text="GESAMTWERT:", fg=TEXT2, bg=BG2,
                 font=('Segoe UI', 9, 'bold')).pack(side='left')
        tk.Label(tf, text=f"{fmt(gesamt)}\u20ac", fg=GOLD2, bg=BG2,
                 font=('Segoe UI', 14, 'bold')).pack(side='right')

    def _umbenennen(self, idx, aktueller_name, refresh_fn):
        rw = tk.Toplevel(self.win)
        rw.title("Haus umbenennen")
        rw.configure(bg=BG)
        rw.geometry("380x140")
        rw.resizable(False, False)
        tk.Label(rw, text="Neuer Name:", fg=TEXT2, bg=BG,
                 font=('Segoe UI', 10)).pack(pady=(16, 4))
        var = tk.StringVar(value=aktueller_name)
        e   = tk.Entry(rw, textvariable=var, bg=BG3, fg=TEXT,
                       insertbackground=GOLD, relief='flat',
                       highlightthickness=1, highlightbackground=GRAY,
                       font=('Segoe UI', 12), width=32)
        e.pack(ipady=6, padx=16)
        e.focus_set()
        e.select_range(0, 'end')

        def ok():
            self.house_names[str(idx)] = var.get().strip()
            speichere_json(HOUSE_NAMES_JSON, self.house_names)
            rw.destroy()
            refresh_fn()

        tk.Button(rw, text="\u2705  Speichern", command=ok,
                  bg=GOLD, fg='#000', font=('Segoe UI', 10, 'bold'),
                  relief='flat', pady=6, cursor='hand2').pack(pady=10)
        rw.bind('<Return>', lambda _: ok())

    # ==================================================================
    # DATUM-FILTER HILFSMETHODEN
    # ==================================================================
    def _filter_nach_datum(self, data):
        """Filtert eine Liste von Buchungen nach datum_von / datum_bis."""
        if not self.datum_von and not self.datum_bis:
            return data
        result = []
        for b in data:
            ts = b.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts)
            except Exception:
                result.append(b)
                continue
            if self.datum_von and dt < self.datum_von:
                continue
            if self.datum_bis and dt > self.datum_bis:
                continue
            result.append(b)
        return result

    def _setze_preset(self, preset):
        """Setzt datum_von / datum_bis anhand des Preset-Namens."""
        from datetime import timedelta
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        now   = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)

        if preset == "Heute":
            self.datum_von = today
            self.datum_bis = now
        elif preset == "Gestern":
            self.datum_von = today - timedelta(days=1)
            self.datum_bis = today - timedelta(seconds=1)
        elif preset == "Diese Woche":
            self.datum_von = today - timedelta(days=today.weekday())
            self.datum_bis = now
        elif preset == "Letzte Woche":
            mo = today - timedelta(days=today.weekday() + 7)
            so = mo + timedelta(days=6, hours=23, minutes=59, seconds=59)
            self.datum_von = mo
            self.datum_bis = so
        elif preset == "Dieser Monat":
            self.datum_von = today.replace(day=1)
            self.datum_bis = now
        elif preset == "Letzter Monat":
            first_this = today.replace(day=1)
            last_prev  = first_this - timedelta(days=1)
            self.datum_von = last_prev.replace(day=1)
            self.datum_bis = last_prev.replace(hour=23, minute=59, second=59)
        else:  # Gesamt
            self.datum_von = None
            self.datum_bis = None

        self.aktiver_preset = preset
        # Von/Bis-Felder aktualisieren
        if hasattr(self, 'datum_von_var'):
            self.datum_von_var.set(
                self.datum_von.strftime("%d.%m.%Y") if self.datum_von else "")
            self.datum_bis_var.set(
                self.datum_bis.strftime("%d.%m.%Y") if self.datum_bis else "")
        self._update_preset_buttons()
        self._refresh_buchungen()
        self._refresh_mitglieder()

    def _update_preset_buttons(self):
        for name, btn in self._preset_buttons.items():
            if name == self.aktiver_preset:
                btn.configure(bg=GOLD, fg='#000')
            else:
                btn.configure(bg=GRAY2, fg=TEXT2)

    def _wende_datum_filter_an(self):
        """Liest Von/Bis-Felder und wendet den Filter manuell an."""
        von_str = self.datum_von_var.get().strip()
        bis_str = self.datum_bis_var.get().strip()

        def parse_d(s, eod=False):
            for fmt in ["%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(s, fmt)
                    if eod:
                        return dt.replace(hour=23, minute=59, second=59)
                    return dt
                except ValueError:
                    pass
            return None

        if von_str:
            p = parse_d(von_str)
            if p is None:
                messagebox.showwarning("Datum-Fehler",
                    f"Ungueltiges Von-Datum: {von_str}\nFormat: TT.MM.JJJJ",
                    parent=self.win)
                return
            self.datum_von = p
        else:
            self.datum_von = None

        if bis_str:
            p = parse_d(bis_str, eod=True)
            if p is None:
                messagebox.showwarning("Datum-Fehler",
                    f"Ungueltiges Bis-Datum: {bis_str}\nFormat: TT.MM.JJJJ",
                    parent=self.win)
                return
            self.datum_bis = p
        else:
            self.datum_bis = None

        self.aktiver_preset = "Manuell"
        self._update_preset_buttons()
        self._refresh_buchungen()
        self._refresh_mitglieder()

    def _zeitraum_label_text(self):
        """Gibt einen lesbaren Text fuer den aktiven Zeitraum zurueck."""
        if self.aktiver_preset not in ("Gesamt", "Manuell"):
            return self.aktiver_preset
        if self.datum_von or self.datum_bis:
            von = self.datum_von.strftime("%d.%m.%Y") if self.datum_von else "\u2014"
            bis = self.datum_bis.strftime("%d.%m.%Y") if self.datum_bis else "\u2014"
            return f"{von} \u2013 {bis}"
        return "Gesamter Zeitraum"

    # ==================================================================
    # TAB 3 – BUCHUNGEN
    # ==================================================================
    def _baue_buchungen(self):
        f = self.t_buchungen

        # ── Zeitraum-Filter-Zeile ──────────────────────────────────────
        zr = tk.Frame(f, bg=BG2, pady=6)
        zr.pack(fill='x')

        presets = ["Heute", "Gestern", "Diese Woche", "Letzte Woche",
                   "Dieser Monat", "Letzter Monat", "Gesamt"]
        self._preset_buttons = {}
        for p in presets:
            aktiv = (p == self.aktiver_preset)
            btn = tk.Button(zr, text=p,
                            command=lambda x=p: self._setze_preset(x),
                            bg=GOLD if aktiv else GRAY2,
                            fg='#000' if aktiv else TEXT2,
                            font=('Segoe UI', 8, 'bold'),
                            relief='flat', padx=7, pady=3, cursor='hand2')
            btn.pack(side='left', padx=(8 if p == "Heute" else 2, 0))
            self._preset_buttons[p] = btn

        tk.Label(zr, text="Von:", fg=TEXT2, bg=BG2,
                 font=('Segoe UI', 8)).pack(side='left', padx=(12, 3))
        self.datum_von_var = tk.StringVar()
        tk.Entry(zr, textvariable=self.datum_von_var, width=10,
                 bg=GRAY2, fg=TEXT, insertbackground=TEXT,
                 font=('Segoe UI', 8), relief='flat').pack(side='left')

        tk.Label(zr, text="Bis:", fg=TEXT2, bg=BG2,
                 font=('Segoe UI', 8)).pack(side='left', padx=(8, 3))
        self.datum_bis_var = tk.StringVar()
        tk.Entry(zr, textvariable=self.datum_bis_var, width=10,
                 bg=GRAY2, fg=TEXT, insertbackground=TEXT,
                 font=('Segoe UI', 8), relief='flat').pack(side='left')

        tk.Button(zr, text="Anwenden", command=self._wende_datum_filter_an,
                  bg=BLUE, fg=TEXT, font=('Segoe UI', 8, 'bold'),
                  relief='flat', padx=8, pady=3, cursor='hand2').pack(
            side='left', padx=(6, 0))

        # ── Person / Haus / Item Filter ────────────────────────────────
        fr = tk.Frame(f, bg=BG2, pady=7)
        fr.pack(fill='x')

        def lbl(txt):
            tk.Label(fr, text=txt, fg=TEXT2, bg=BG2,
                     font=('Segoe UI', 9)).pack(side='left', padx=(10, 3))

        lbl("Person:")
        self.bf_person = tk.StringVar(value="Alle")
        self.cb_person = ttk.Combobox(fr, textvariable=self.bf_person,
                                       state='readonly', width=15, font=('Segoe UI', 9))
        self.cb_person.pack(side='left', padx=(0, 6))
        self.cb_person.bind('<<ComboboxSelected>>', lambda e: self._refresh_buchungen())

        lbl("Haus:")
        self.bf_haus = tk.StringVar(value="Alle")
        self.cb_haus = ttk.Combobox(fr, textvariable=self.bf_haus,
                                     state='readonly', width=20, font=('Segoe UI', 9))
        self.cb_haus.pack(side='left', padx=(0, 6))
        self.cb_haus.bind('<<ComboboxSelected>>', lambda e: self._refresh_buchungen())

        lbl("Item:")
        self.bf_item = tk.StringVar(value="Alle")
        self.cb_item = ttk.Combobox(fr, textvariable=self.bf_item,
                                     state='readonly', width=13, font=('Segoe UI', 9))
        self.cb_item.pack(side='left', padx=(0, 8))
        self.cb_item.bind('<<ComboboxSelected>>', lambda e: self._refresh_buchungen())

        tk.Button(fr, text="\u00d7 Reset", command=self._reset_filter,
                  bg=GRAY, fg=TEXT2, font=('Segoe UI', 9),
                  relief='flat', padx=8, pady=2, cursor='hand2').pack(side='left')

        self.buch_count_var = tk.StringVar(value="")
        tk.Label(fr, textvariable=self.buch_count_var,
                 fg=TEXT3, bg=BG2, font=('Segoe UI', 8)).pack(side='left', padx=8)

        tk.Button(fr, text="  \u2795  Neue Buchung  ",
                  command=self._neue_buchung,
                  bg=GOLD, fg='#000', font=('Segoe UI', 9, 'bold'),
                  relief='flat', padx=12, pady=4, cursor='hand2').pack(
            side='right', padx=12)

        tbl_f = tk.Frame(f, bg=BG)
        tbl_f.pack(fill='both', expand=True, padx=8, pady=6)

        cols = ("datum", "zeit", "person", "haus", "item", "menge", "typ", "notiz")
        self.tree_b = ttk.Treeview(tbl_f, columns=cols,
                                    show='headings', selectmode='browse',
                                    style="H.Treeview")
        col_cfgs = [
            ("datum",  "Datum",    88, 'w'),
            ("zeit",   "Uhrzeit",  60, 'w'),
            ("person", "Person",  130, 'w'),
            ("haus",   "Haus",    170, 'w'),
            ("item",   "Item",     95, 'w'),
            ("menge",  "Menge",    75, 'e'),
            ("typ",    "Typ",      95, 'w'),
            ("notiz",  "Notiz",   130, 'w'),
        ]
        for cid, hdr, w, anchor in col_cfgs:
            self.tree_b.heading(cid, text=hdr,
                                 command=lambda c=cid: self._sort_b(c))
            self.tree_b.column(cid, width=w, anchor=anchor,
                                minwidth=40, stretch=(cid == "haus"))

        self.tree_b.tag_configure('ein',  foreground=GREEN)
        self.tree_b.tag_configure('aus',  foreground=RED)
        self.tree_b.tag_configure('auto', foreground=TEXT3)
        self.tree_b.tag_configure('ein2', foreground=GREEN, background='#181818')
        self.tree_b.tag_configure('aus2', foreground=RED,   background='#181818')

        vsb = ttk.Scrollbar(tbl_f, orient='vertical', command=self.tree_b.yview,
                             style="H.Vertical.TScrollbar")
        self.tree_b.configure(yscrollcommand=vsb.set)
        self.tree_b.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree_b.bind('<MouseWheel>',
                          lambda e: self.tree_b.yview_scroll(
                              int(-1 * (e.delta / 120)), 'units'))
        self.tree_b.bind('<Delete>',    lambda e: self._loesche_buchung())
        self.tree_b.bind('<Button-3>',  self._buchung_menu)

        self._refresh_buchungen()

    def _reset_filter(self):
        self.bf_person.set("Alle")
        self.bf_haus.set("Alle")
        self.bf_item.set("Alle")
        self._setze_preset("Gesamt")   # setzt auch datum_von/bis zurueck

    def _refresh_buchungen(self):
        all_p = ["Alle"] + sorted(set(b.get("person","") for b in self.transactions))
        all_h = ["Alle"] + sorted(set(b.get("haus_name","") for b in self.transactions))
        all_i = ["Alle"] + sorted(set(b.get("item","") for b in self.transactions))

        self.cb_person['values'] = all_p
        self.cb_haus['values']   = all_h
        self.cb_item['values']   = all_i
        for var, lst in [(self.bf_person, all_p),
                          (self.bf_haus,   all_h),
                          (self.bf_item,   all_i)]:
            if var.get() not in lst:
                var.set("Alle")

        data = list(self.transactions)
        if self.bf_person.get() != "Alle":
            data = [b for b in data if b.get("person") == self.bf_person.get()]
        if self.bf_haus.get() != "Alle":
            data = [b for b in data if b.get("haus_name") == self.bf_haus.get()]
        if self.bf_item.get() != "Alle":
            data = [b for b in data if b.get("item") == self.bf_item.get()]

        # Datum-Filter anwenden
        data = self._filter_nach_datum(data)

        try:
            data.sort(key=lambda x: x.get(self._buch_sort_col, ""),
                      reverse=self._buch_sort_rev)
        except Exception:
            pass

        self.buch_count_var.set(f"{len(data)} Eintraege")

        for row in self.tree_b.get_children():
            self.tree_b.delete(row)

        for i, b in enumerate(data):
            ts = b.get("timestamp", "")
            try:
                dt    = datetime.fromisoformat(ts)
                datum = dt.strftime("%d.%m.%Y")
                zeit  = dt.strftime("%H:%M")
            except Exception:
                datum = ts[:10] if ts else "\u2014"
                zeit  = ts[11:16] if len(ts) > 15 else "\u2014"

            typ    = b.get("typ", "")
            person = b.get("person", "")
            menge  = b.get("menge", 0)
            ms     = f"+{fmt(menge)}" if typ == "eingelagert" else f"-{fmt(menge)}"
            typ_lbl = "\U0001f4e5 Eingelagert" if typ == "eingelagert" else "\U0001f4e4 Entnommen"

            if person == "[Automatisch]":
                tag = 'auto'
            elif i % 2 == 0:
                tag = 'ein' if typ == "eingelagert" else 'aus'
            else:
                tag = 'ein2' if typ == "eingelagert" else 'aus2'

            self.tree_b.insert('', 'end', iid=b.get("id", f"_{i}"),
                                values=(datum, zeit, person, b.get("haus_name",""),
                                        b.get("item",""), ms, typ_lbl, b.get("notiz","")),
                                tags=(tag,))

    def _sort_b(self, col):
        mapping = {"datum": "timestamp", "zeit": "timestamp",
                   "person": "person", "haus": "haus_name",
                   "item": "item", "menge": "menge",
                   "typ": "typ", "notiz": "notiz"}
        rc = mapping.get(col, col)
        if self._buch_sort_col == rc:
            self._buch_sort_rev = not self._buch_sort_rev
        else:
            self._buch_sort_col = rc
            self._buch_sort_rev = True
        self._refresh_buchungen()

    def _neue_buchung(self):
        dlg = tk.Toplevel(self.win)
        dlg.title("Neue Buchung")
        dlg.configure(bg=BG)
        dlg.geometry("420x390")
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="\U0001f4dd  NEUE BUCHUNG",
                 font=('Segoe UI', 12, 'bold'), fg=GOLD, bg=BG).pack(pady=(16, 10))

        form = tk.Frame(dlg, bg=BG)
        form.pack(fill='x', padx=24)

        def row_lbl(t):
            tk.Label(form, text=t, font=('Segoe UI', 9), fg=TEXT2,
                     bg=BG, anchor='w').pack(fill='x', pady=(8, 2))

        def mk_combo(vals, default=""):
            v = tk.StringVar(value=default)
            ttk.Combobox(form, textvariable=v, values=vals,
                          font=('Segoe UI', 10), width=36).pack(fill='x', ipady=3)
            return v

        def mk_entry(default=""):
            v = tk.StringVar(value=default)
            tk.Entry(form, textvariable=v, bg=BG3, fg=TEXT,
                     insertbackground=GOLD, relief='flat',
                     highlightthickness=1, highlightbackground=GRAY,
                     highlightcolor=GOLD, font=('Segoe UI', 10)).pack(fill='x', ipady=5)
            return v

        row_lbl("Person:")
        p_var = mk_combo(self.members, self.members[0] if self.members else "")

        row_lbl("Haus:")
        h_namen = [self.get_name(i, h)
                   for i, h in enumerate(self.houses_data.get("haeuser", []))]
        h_var = mk_combo(h_namen, h_namen[0] if h_namen else "")

        row_lbl("Item:")
        known = sorted(set(
            [it.get("name", "") for it in self.markt_daten] +
            [it["name"] for h in self.houses_data.get("haeuser", [])
             for it in h.get("items", [])]
        ))
        i_var = mk_combo(known, "Schmuck")

        row_lbl("Menge:")
        m_var = mk_entry("1")

        row_lbl("Typ:")
        typ_row = tk.Frame(form, bg=BG)
        typ_row.pack(fill='x')
        t_var = tk.StringVar(value="eingelagert")
        for lbl_txt, val, fg in [("\U0001f4e5 Eingelagert", "eingelagert", GREEN),
                                  ("\U0001f4e4 Entnommen",   "entnommen",   RED)]:
            tk.Radiobutton(typ_row, text=lbl_txt, variable=t_var, value=val,
                           fg=fg, bg=BG, selectcolor=BG3,
                           activebackground=BG, font=('Segoe UI', 9),
                           cursor='hand2').pack(side='left', padx=(0, 14))

        row_lbl("Notiz (optional):")
        n_var = mk_entry("")

        def speichern():
            try:
                menge = int(m_var.get().replace('.', '').replace(',', ''))
            except ValueError:
                menge = 0
            if menge <= 0:
                return

            haus_name = h_var.get()
            haus_idx  = 0
            for ii, hh in enumerate(self.houses_data.get("haeuser", [])):
                if self.get_name(ii, hh) == haus_name:
                    haus_idx = ii
                    break

            buch = {
                "id":        str(uuid.uuid4())[:8],
                "timestamp": datetime.now().isoformat(),
                "person":    p_var.get(),
                "haus_idx":  haus_idx,
                "haus_name": haus_name,
                "item":      i_var.get(),
                "menge":     menge,
                "typ":       t_var.get(),
                "notiz":     n_var.get()
            }
            self.transactions.insert(0, buch)
            speichere_json(TRANSACTIONS_JSON, self.transactions)
            self._refresh_buchungen()
            self._refresh_mitglieder()
            dlg.destroy()

        tk.Button(form, text="   \u2705  Speichern   ", command=speichern,
                  bg=GOLD, fg='#000', font=('Segoe UI', 10, 'bold'),
                  relief='flat', pady=8, cursor='hand2').pack(pady=12)
        dlg.bind('<Return>', lambda _: speichern())

    def _loesche_buchung(self):
        sel = self.tree_b.selection()
        if not sel:
            return
        iid = sel[0]
        if messagebox.askyesno("Buchung loeschen",
                                "Diesen Eintrag wirklich loeschen?",
                                parent=self.win):
            self.transactions = [b for b in self.transactions
                                  if b.get("id") != iid]
            speichere_json(TRANSACTIONS_JSON, self.transactions)
            self._refresh_buchungen()
            self._refresh_mitglieder()

    def _buchung_menu(self, event):
        iid = self.tree_b.identify_row(event.y)
        if not iid:
            return
        self.tree_b.selection_set(iid)
        buch = next((b for b in self.transactions
                     if b.get("id") == iid), None)

        menu = tk.Menu(self.win, tearoff=0, bg=BG2, fg=TEXT,
                       activebackground=GOLD, activeforeground='#000')

        if buch and buch.get("person") == "[Automatisch]":
            pm = tk.Menu(menu, tearoff=0, bg=BG2, fg=TEXT,
                         activebackground=GOLD, activeforeground='#000')
            for member in self.members:
                def assign(m=member, bk=buch):
                    bk["person"] = m
                    speichere_json(TRANSACTIONS_JSON, self.transactions)
                    self._refresh_buchungen()
                    self._refresh_mitglieder()
                pm.add_command(label=member, command=assign)
            menu.add_cascade(label="\U0001f464  Person zuweisen \u25b6", menu=pm)
            menu.add_separator()

        menu.add_command(label="\U0001f5d1\ufe0f  Loeschen",
                          command=self._loesche_buchung)
        menu.tk_popup(event.x_root, event.y_root)

    # ==================================================================
    # TAB 4 – MITGLIEDER
    # ==================================================================
    def _baue_mitglieder(self):
        f = self.t_mitglieder

        br = tk.Frame(f, bg=BG2, pady=8)
        br.pack(fill='x')
        tk.Button(br, text="  \u2795  Mitglied hinzufuegen  ",
                  command=self._add_member,
                  bg=BLUE, fg=TEXT, font=('Segoe UI', 9, 'bold'),
                  relief='flat', padx=10, pady=4, cursor='hand2').pack(
            side='left', padx=12)
        tk.Button(br, text="\U0001f5d1\ufe0f  Entfernen",
                  command=self._remove_member,
                  bg=GRAY, fg=TEXT2, font=('Segoe UI', 9, 'bold'),
                  relief='flat', padx=10, pady=4, cursor='hand2').pack(
            side='left', padx=4)
        self.zeitraum_lbl = tk.Label(br, text="\U0001f4c5  Zeitraum: Gesamter Zeitraum",
                                      font=('Segoe UI', 9), fg=GOLD, bg=BG2)
        self.zeitraum_lbl.pack(side='right', padx=16)

        tbl_f = tk.Frame(f, bg=BG)
        tbl_f.pack(fill='both', expand=True, padx=8, pady=6)

        cols = ("person", "gold", "eisen", "diamant", "s_ein", "s_aus", "sonstiges", "n")
        self.tree_m = ttk.Treeview(tbl_f, columns=cols,
                                    show='headings', selectmode='browse',
                                    style="H.Treeview")
        col_cfgs = [
            ("person",    "Mitglied",           155, 'w'),
            ("gold",      "\U0001f947 Gold (ein)",  110, 'e'),
            ("eisen",     "\U0001f529 Eisen (ein)", 110, 'e'),
            ("diamant",   "\U0001f48e Diamant (ein)",110,'e'),
            ("s_ein",     "\U0001f4a0 Schmuck (ein)",110,'e'),
            ("s_aus",     "\U0001f4a0 Schmuck (aus)",110,'e'),
            ("sonstiges", "Sonstiges (ein)",    110, 'e'),
            ("n",         "Buchungen",            80, 'e'),
        ]
        for cid, hdr, w, anchor in col_cfgs:
            self.tree_m.heading(cid, text=hdr)
            self.tree_m.column(cid, width=w, anchor=anchor,
                                minwidth=50, stretch=(cid == "person"))

        self.tree_m.tag_configure('member', background='#1a1a0d', foreground=TEXT)
        self.tree_m.tag_configure('guest',  background=BG3,       foreground=TEXT2)
        self.tree_m.tag_configure('alt_m',  background='#181810', foreground=TEXT)

        vsb = ttk.Scrollbar(tbl_f, orient='vertical', command=self.tree_m.yview,
                             style="H.Vertical.TScrollbar")
        self.tree_m.configure(yscrollcommand=vsb.set)
        self.tree_m.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        tk.Label(f, text="Statistiken basieren auf Buchungen (Tab BUCHUNGEN)  \u2014  "
                         "Auto-Buchungen werden nicht gezaehlt",
                 font=('Segoe UI', 8), fg=TEXT3, bg=BG).pack(pady=(0, 6))

        self._refresh_mitglieder()

    def _refresh_mitglieder(self):
        for row in self.tree_m.get_children():
            self.tree_m.delete(row)

        # Zeitraum-Label aktualisieren
        if hasattr(self, 'zeitraum_lbl'):
            self.zeitraum_lbl.configure(
                text=f"\U0001f4c5  Zeitraum: {self._zeitraum_label_text()}")

        stats  = {}
        counts = {}

        buchungen = self._filter_nach_datum(self.transactions)
        for b in buchungen:
            p = b.get("person", "")
            if p == "[Automatisch]":
                continue
            item  = b.get("item", "").lower()
            menge = b.get("menge", 0)
            typ   = b.get("typ", "eingelagert")

            if p not in stats:
                stats[p]  = {}
                counts[p] = 0
            counts[p] += 1

            if item not in stats[p]:
                stats[p][item] = {"ein": 0, "aus": 0}
            stats[p][item]["ein" if typ == "eingelagert" else "aus"] += menge

        alle = list(self.members)
        for p in stats:
            if p not in alle:
                alle.append(p)

        for i, person in enumerate(alle):
            ps = stats.get(person, {})

            def s_ein(kws):
                return sum(ps[k]["ein"] for k in ps
                           if any(kw in k for kw in kws))

            def s_aus(kws):
                return sum(ps[k]["aus"] for k in ps
                           if any(kw in k for kw in kws))

            gold    = s_ein(["gold"])
            eisen   = s_ein(["eisen"])
            diamant = s_ein(["diamant"])
            sc_ein  = s_ein(["schmuck"])
            sc_aus  = s_aus(["schmuck"])
            sonst   = sum(ps[k]["ein"] for k in ps
                          if not any(kw in k for kw in
                                     ["gold","eisen","diamant","schmuck"]))

            def v(n): return fmt(n) if n > 0 else "\u2014"

            in_members = person in self.members
            tag = ('member' if i % 2 == 0 else 'alt_m') if in_members else 'guest'

            self.tree_m.insert('', 'end', tags=(tag,),
                                values=(person, v(gold), v(eisen), v(diamant),
                                        v(sc_ein), v(sc_aus), v(sonst),
                                        counts.get(person, 0)))

    def _add_member(self):
        name = simpledialog.askstring("Mitglied hinzufuegen", "Name des Spielers:",
                                       parent=self.win)
        if name and name.strip() and name.strip() not in self.members:
            self.members.append(name.strip())
            speichere_json(MEMBERS_JSON, self.members)
            self._refresh_mitglieder()

    def _remove_member(self):
        sel = self.tree_m.selection()
        if not sel:
            return
        name = self.tree_m.item(sel[0], 'values')[0]
        if name in self.members:
            if messagebox.askyesno("Entfernen",
                                    f"'{name}' aus der Mitgliederliste entfernen?\n"
                                    f"Buchungen bleiben erhalten.",
                                    parent=self.win):
                self.members.remove(name)
                speichere_json(MEMBERS_JSON, self.members)
                self._refresh_mitglieder()
