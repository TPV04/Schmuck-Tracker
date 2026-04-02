"""
Haeuser Updater - liest ucp.lyl.gg/houses via Chrome CDP
Liest Inventar + LOG pro Haus
Speichert Ergebnis in houses.json
"""
import json, os, time, requests

HOUSES_JSON  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "houses.json")
UCP_URL      = "https://ucp.lyl.gg/houses"
CHROME_EXE   = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFIL_DIR   = r"C:\Users\Tony\AppData\Local\Google\Chrome\User Data"
PROFIL_NAME  = "Default"

# ---------------------------------------------------------------------------
# JavaScript: Inventar + Logs
# ---------------------------------------------------------------------------
JS_EXTRACT = """
(async function() {
  const result = { timestamp: new Date().toISOString(), haeuser: [] };

  // ── 1. Inventar aus dataTable ──────────────────────────────────────────
  const tables = document.querySelectorAll('table.dataTable');
  tables.forEach((table) => {
    let el = table, hausOrt = '', belegt = 0, kapazitaet = 0;
    for (let j = 0; j < 25; j++) {
      el = el.parentElement;
      if (!el) break;
      const match = el.textContent.match(
        /([A-Za-z\\u00e4\\u00f6\\u00fc\\u00c4\\u00d6\\u00dc\\s]+)\\s*\\((\\d+)\\s*\\/\\s*(\\d+)\\)/
      );
      if (match) {
        hausOrt    = match[1].trim();
        belegt     = parseInt(match[2]);
        kapazitaet = parseInt(match[3]);
        break;
      }
    }
    const items = [];
    table.querySelectorAll('tbody tr').forEach(row => {
      const cells = row.querySelectorAll('td');
      if (cells.length >= 3) {
        const name  = cells[1].textContent.trim();
        const menge = parseInt(cells[2].textContent.trim());
        if (name && !isNaN(menge) && menge > 0) items.push({ name, menge });
      }
    });
    if (hausOrt) result.haeuser.push({ ort: hausOrt, belegt, kapazitaet, items, logs: [] });
  });

  // ── 2. LOG-Buttons suchen ─────────────────────────────────────────────
  // Moeglicherweise mehrere Selektoren je nach UCP-Version
  const logBtns = Array.from(
    document.querySelectorAll('button, a, .v-btn, [class*="btn"]')
  ).filter(b => {
    const t = b.textContent.trim().toUpperCase();
    return t === 'LOG' || t === 'VERLAUF' || t === 'HISTORY' || t === 'PROTOKOLL';
  });

  for (let i = 0; i < logBtns.length && i < result.haeuser.length; i++) {
    try {
      logBtns[i].click();
      await new Promise(r => setTimeout(r, 1800));

      // Modal / Dialog suchen
      const modal = document.querySelector(
        '.v-dialog--active, .v-overlay--active .v-card, ' +
        '.modal.show, [role="dialog"], .dialog--active'
      );
      if (!modal) continue;

      const logEintraege = [];
      // Tabellenzeilen im Modal lesen
      // Format LYL UCP: Spalte0=Spieler | Spalte1=Items ("32 x Gold, -4 x Eisen") | Spalte2=Datum
      modal.querySelectorAll('tbody tr').forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 3) {
          const player   = cells[0].textContent.trim();
          const itemsStr = cells[1].textContent.trim();
          const ts       = cells[2].textContent.trim();

          // Mehrere Items pro Zeile moeglich, getrennt durch Komma
          itemsStr.split(',').forEach(part => {
            part = part.trim();
            // Matching: "-4 x Goldbrikett" oder "32 x Eisenbarren"
            const m = part.match(/^(-?\d+)\s*x\s*(.+)$/);
            if (m) {
              const menge  = parseInt(m[1]);
              const item   = m[2].trim();
              logEintraege.push({
                ts:     ts,
                player: player,
                action: menge >= 0 ? 'eingelagert' : 'entnommen',
                item:   item,
                menge:  Math.abs(menge),
                raw:    [player, itemsStr, ts]
              });
            }
          });
        }
      });

      if (result.haeuser[i]) {
        result.haeuser[i].logs = logEintraege;
      }

      // Modal schliessen
      const closeBtn = modal.querySelector(
        '.v-btn--icon[aria-label*="lose"], .close, button[aria-label*="lose"], ' +
        '.v-card__actions button:last-child, .modal-close'
      );
      if (closeBtn) {
        closeBtn.click();
      } else {
        // Fallback: ESC-Taste
        document.dispatchEvent(new KeyboardEvent('keydown', {
          key: 'Escape', keyCode: 27, bubbles: true
        }));
      }
      await new Promise(r => setTimeout(r, 600));

    } catch(e) {
      // Fehler beim LOG lesen – weiter mit naechstem Haus
    }
  }

  return JSON.stringify(result);
})()
"""

# ---------------------------------------------------------------------------
def starte_tracker_chrome():
    """Schliesst laufendes Chrome und startet Tony-Chrome mit Debug-Port."""
    import subprocess
    # Alle Chrome-Prozesse beenden
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                   capture_output=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    # Warten bis alle Prozesse wirklich weg sind
    for _ in range(10):
        time.sleep(1)
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
                           capture_output=True, text=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        if "chrome.exe" not in r.stdout:
            break

    # Tony-Chrome (Default-Profil) mit Debug-Port starten, off-screen
    subprocess.Popen([
        CHROME_EXE,
        "--remote-debugging-port=9222",
        "--remote-allow-origins=*",
        f"--user-data-dir={PROFIL_DIR}",
        f"--profile-directory={PROFIL_NAME}",
        "--window-position=-32000,-32000",
        "--window-size=1280,900",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-notifications",
        UCP_URL
    ], creationflags=subprocess.CREATE_NO_WINDOW)

    # Warten bis Port 9222 wirklich antwortet (max. 20 Sek)
    print("STATUS: Warte auf Chrome Debug-Port...")
    for _ in range(20):
        time.sleep(1)
        try:
            requests.get("http://localhost:9222/json", timeout=1)
            print("STATUS: Chrome bereit.")
            return
        except Exception:
            pass
    print("FEHLER: Chrome Port 9222 nicht erreichbar. Chrome konnte nicht gestartet werden.")


def _tabs_finden(tabs, suchbegriff):
    """Sucht sicher in einer Tab-Liste nach einem URL-Begriff."""
    if not isinstance(tabs, list):
        return None
    for tab in tabs:
        if not isinstance(tab, dict):
            continue
        url = tab.get("url") or ""
        if suchbegriff in url:
            return tab
    return None


def hole_via_cdp():
    """Verbindet sich mit laufendem Chrome via Remote Debugging."""
    try:
        # ── 1. Port 9222 pruefen ───────────────────────────────────────
        tabs = None
        try:
            r = requests.get("http://localhost:9222/json", timeout=3)
            tabs = r.json()
            if not isinstance(tabs, list):
                print(f"FEHLER: Chrome Port 9222 liefert unerwartete Antwort: {type(tabs).__name__}")
                return None
            print(f"STATUS: Chrome verbunden. {len(tabs)} Tabs gefunden.")
        except Exception as e:
            print(f"STATUS: Port 9222 nicht erreichbar ({e}). Chrome wird gestartet...")
            starte_tracker_chrome()
            try:
                r = requests.get("http://localhost:9222/json", timeout=3)
                tabs = r.json()
                if not isinstance(tabs, list):
                    print(f"FEHLER: Chrome antwortet aber liefert kein Tab-Array.")
                    return None
            except Exception as e2:
                print(f"FEHLER: Chrome Port 9222 nach Neustart nicht erreichbar: {e2}")
                return None

        # ── 2. UCP-Tab suchen ──────────────────────────────────────────
        houses_tab = _tabs_finden(tabs, "ucp.lyl.gg")

        if not houses_tab:
            print(f"STATUS: Kein UCP-Tab offen. Oeffne neuen Tab...")
            laufende_urls = [tab.get("url") or "" for tab in tabs if isinstance(tab, dict)]
            print(f"STATUS: Aktuelle Tabs: {[u for u in laufende_urls if u.startswith('http')][:5]}")
            try:
                requests.get(f"http://localhost:9222/json/new?{UCP_URL}", timeout=5)
            except Exception as e:
                print(f"FEHLER: Konnte keinen neuen Tab oeffnen: {e}")
                return None
            time.sleep(5)
            try:
                r2 = requests.get("http://localhost:9222/json", timeout=3)
                tabs2 = r2.json()
            except Exception as e:
                print(f"FEHLER: Tab-Liste nach UCP-Oeffnen nicht lesbar: {e}")
                return None
            houses_tab = _tabs_finden(tabs2, "ucp.lyl.gg")

        if not houses_tab:
            print(f"FEHLER: UCP-Tab nicht gefunden. Bist du auf ucp.lyl.gg eingeloggt?")
            return None

        ws_url = houses_tab.get("webSocketDebuggerUrl")
        if not ws_url:
            print(f"FEHLER: Tab hat keine WebSocket-URL. Tab-Info: {houses_tab.get('url','?')}")
            return None

        print(f"STATUS: UCP-Tab gefunden: {houses_tab.get('url','?')}")

        import websocket, threading
        result_holder = [None]
        error_holder  = [None]

        def run_ws():
            import traceback
            try:
                print("STATUS: WebSocket-Verbindung wird aufgebaut...")
                ws = websocket.create_connection(ws_url, timeout=90)
                print("STATUS: WebSocket verbunden.")

                print("STATUS: Page.enable wird gesendet...")
                ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
                r1 = ws.recv()
                print(f"STATUS: Page.enable Antwort: {str(r1)[:80]}")

                print("STATUS: Seite wird neu geladen...")
                ws.send(json.dumps({"id": 2, "method": "Page.reload",
                                     "params": {"ignoreCache": True}}))
                r2 = ws.recv()
                print(f"STATUS: Page.reload Antwort: {str(r2)[:80]}")

                print("STATUS: Warte auf Seiten-Load (max. 20s)...")
                ws.settimeout(20)
                deadline = time.time() + 20
                loaded = False
                while time.time() < deadline:
                    try:
                        raw = ws.recv()
                        msg = json.loads(raw) if raw else {}
                        if isinstance(msg, dict) and msg.get("method") == "Page.loadEventFired":
                            loaded = True
                            break
                    except Exception:
                        break
                print(f"STATUS: Seite geladen: {loaded}")
                ws.settimeout(90)
                time.sleep(1)

                print("STATUS: JS-Extraktion wird gestartet...")
                ws.send(json.dumps({
                    "id": 3,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression":    JS_EXTRACT,
                        "returnByValue": True,
                        "awaitPromise":  True
                    }
                }))
                print("STATUS: Warte auf JS-Antwort (kann 30-90s dauern)...")
                raw_resp = ws.recv()
                ws.close()
                print(f"STATUS: JS-Antwort erhalten ({len(raw_resp)} Zeichen).")

                resp = json.loads(raw_resp) if raw_resp else {}
                if not isinstance(resp, dict):
                    error_holder[0] = f"CDP-Antwort kein Dict: {type(resp).__name__}"
                    return

                result_obj = resp.get("result") or {}
                if not isinstance(result_obj, dict):
                    error_holder[0] = f"CDP result kein Dict: {type(result_obj).__name__}"
                    return

                exc_details = result_obj.get("exceptionDetails")
                if exc_details:
                    txt = exc_details.get("text","") if isinstance(exc_details, dict) else str(exc_details)
                    error_holder[0] = f"JS-Fehler auf Seite: {txt}"
                    return

                inner = result_obj.get("result") or {}
                val   = inner.get("value") if isinstance(inner, dict) else None
                print(f"STATUS: JS-Wert erhalten: {bool(val)} ({len(str(val)) if val else 0} Zeichen)")

                if not val:
                    error_holder[0] = "LOGIN_REQUIRED"
                    return

                data    = json.loads(val)
                haeuser = data.get("haeuser") if isinstance(data, dict) else None
                if not haeuser:
                    print(f"STATUS: Haeuser-Array leer oder fehlt. Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                    error_holder[0] = "LOGIN_REQUIRED"
                    return

                result_holder[0] = data
                log_count = sum(len(h.get("logs") or []) for h in haeuser if isinstance(h, dict))
                print(f"OK: {len(haeuser)} Haeuser | {log_count} Log-Eintraege")

            except websocket.WebSocketTimeoutException:
                error_holder[0] = "Timeout: Chrome hat nicht rechtzeitig geantwortet (>90s)."
            except Exception as e:
                tb = traceback.format_exc()
                error_holder[0] = f"WebSocket-Fehler: {e}"
                print(f"FEHLER: WebSocket-Fehler Detail:\n{tb}")

        t = threading.Thread(target=run_ws)
        t.start()
        t.join(timeout=120)

        if error_holder[0]:
            if error_holder[0] == "LOGIN_REQUIRED":
                print("LOGIN_REQUIRED")
            else:
                print(f"FEHLER: {error_holder[0]}")
            return None
        if result_holder[0] is None:
            print("FEHLER: Timeout — Chrome hat nach 120s nicht geantwortet.")
        return result_holder[0]

    except Exception as e:
        import traceback
        print(f"FEHLER: {e}")
        print(f"FEHLER_DETAIL: {traceback.format_exc()}")
        return None


def hole_via_selenium():
    """Fallback: Selenium mit Chrome-Profil."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument(f"--user-data-dir={PROFIL_DIR}")

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=opts
        )
        driver.get(UCP_URL)
        time.sleep(4)
        result = driver.execute_script(JS_EXTRACT)
        driver.quit()
        return json.loads(result) if result else None
    except Exception:
        return None


def update_haeuser():
    data = hole_via_cdp()
    if data:
        with open(HOUSES_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    print("FEHLER: Konnte keine Daten laden.")
    return None


if __name__ == "__main__":
    update_haeuser()
