# LYL SchmuckBot v7.0
# Haeuser + Schliessfach + Schmuck-Preis -> Google Sheets
# Cloudflare Bypass via undetected_chromedriver

import time, json, os, requests, threading, tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def lade_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

cfg          = lade_config()
WEBAPP_URL   = cfg.get("web_app_url", "")
INTERVAL_SEK = int(cfg.get("interval", 300))
HOUSES_URL   = "https://ucp.lyl.gg/houses"
LOCKER_URL   = "https://ucp.lyl.gg/locker"
MARKET_URL   = "https://ucp.lyl.gg/market"

# --- Driver ---
def erstelle_driver(headless=True):
    opts = uc.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--lang=de-DE")
    d = uc.Chrome(options=opts, use_subprocess=True)
    d.set_page_load_timeout(30)
    return d

def warte(driver, url, sel, t=20):
    driver.get(url)
    WebDriverWait(driver, t).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
    time.sleep(1.5)

# --- Scraper ---
HAEUSER_JS = """
let h=[];
document.querySelectorAll('.card').forEach(c=>{
  const te=c.querySelector('h2,h3,h4,.card-title,[class*="title"]');
  if(!te)return;
  const t=te.textContent.trim();
  const m=t.match(/^(.+?)\s*\((\d+)\s*\/\s*(\d+)\)(.*)/);
  if(!m)return;
  let items=[];
  c.querySelectorAll('tr').forEach(r=>{
    const cl=r.querySelectorAll('td');
    if(cl.length>=3){
      const n=cl[1]&&cl[1].textContent.trim();
      const a=cl[2]&&cl[2].textContent.trim();
      if(n&&a)items.push({name:n,amount:a});
    }
  });
  h.push({location:m[1].trim(),current:m[2],max:m[3],owner:m[4].trim(),items});
});
return h;
"""

LOCKER_JS = """
let l=[];
document.querySelectorAll('.card').forEach(c=>{
  const te=c.querySelector('h2,h3,h4,.card-title,[class*="title"]');
  if(!te)return;
  const t=te.textContent.trim();
  if(!t.toLowerCase().includes('schlie'))return;
  let items=[];
  c.querySelectorAll('tr').forEach(r=>{
    const cl=r.querySelectorAll('td');
    if(cl.length>=3){
      const n=cl[1]&&cl[1].textContent.trim();
      const a=cl[2]&&cl[2].textContent.trim();
      if(n&&a)items.push({name:n,amount:a});
    }
  });
  const m=t.match(/^(.+?)\s*\((\d+)\s*\/\s*(\d+)\)/);
  if(m)l.push({type:m[1].trim(),current:m[2],max:m[3],items});
  else l.push({type:t,current:'?',max:'?',items});
});
return l;
"""

MARKET_JS = """
let p=null;
document.querySelectorAll('.card').forEach(c=>{
  if(!c.textContent.includes('Apfel'))return;
  c.querySelectorAll('tr').forEach(r=>{
    const cl=r.querySelectorAll('td');
    if(cl.length>=3){
      const n=cl[1]&&cl[1].textContent.trim();
      if(n&&n.toLowerCase()==='schmuck'){
        const raw=cl[2]&&cl[2].textContent.trim();
        p=raw?raw.replace(/[^0-9]/g,''):null;
      }
    }
  });
});
return p;
"""

def scrape_haeuser(d):
    warte(d, HOUSES_URL, ".card")
    return d.execute_script(HAEUSER_JS)

def scrape_schliessfach(d):
    warte(d, LOCKER_URL, ".card")
    return d.execute_script(LOCKER_JS)

def scrape_schmuck_preis(d):
    warte(d, MARKET_URL, ".card")
    return d.execute_script(MARKET_JS)

# --- Sheets senden ---
def sende(payload):
    if not WEBAPP_URL:
        return False, "Keine WEBAPP_URL in config.json!"
    try:
        r = requests.post(WEBAPP_URL, json=payload, timeout=15)
        r.raise_for_status()
        return True, r.text
    except Exception as e:
        return False, str(e)

# --- Haupt-Scan ---
def scan(log=print):
    log("Starte Scan...")
    driver = None
    try:
        driver = erstelle_driver(headless=True)
        log("Browser gestartet (UC-Bypass aktiv)")

        log("Scanne Haeuser...")
        haeuser = scrape_haeuser(driver)
        log(f"  {len(haeuser)} Haeuser gefunden")

        log("Scanne Schliessfach...")
        faecher = scrape_schliessfach(driver)
        log(f"  {len(faecher)} Schliessfaecher gefunden")

        log("Scanne Schmuck-Preis...")
        preis = scrape_schmuck_preis(driver)
        log(f"  Schmuck-Preis: {preis} EUR")

        ts = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        payload = {
            "action":        "update_schmuck",
            "zeitstempel":   ts,
            "schmuck_preis": preis,
            "haeuser":       haeuser,
            "schliessfach":  faecher
        }

        log("Sende an Sheets...")
        ok, antwort = sende(payload)
        if ok:
            log(f"Sheets OK! ({ts}) -> {antwort}")
        else:
            log(f"Sheets-Fehler: {antwort}")
        return ok, payload

    except Exception as e:
        log(f"Fehler: {e}")
        return False, {}
    finally:
        if driver:
            try: driver.quit()
            except: pass

# --- GUI ---
class App:
    def __init__(self, root):
        self.root = root
        root.title("LYL SchmuckBot v7.0")
        root.geometry("560x430")
        root.configure(bg="#0d1117")
        self.laufend = False
        self._gui()
        self.log("SchmuckBot v7.0 bereit")
        self.log(f"Intervall: {INTERVAL_SEK}s | WebApp: {'OK' if WEBAPP_URL else 'FEHLT!'}")

    def _gui(self):
        tk.Label(self.root, text="LYL SchmuckBot v7.0", bg="#0d1117",
                 fg="#58a6ff", font=("Segoe UI",13,"bold")).pack(pady=10)
        self.status = tk.StringVar(value="Bereit")
        tk.Label(self.root, textvariable=self.status, bg="#0d1117",
                 fg="#8b949e", font=("Segoe UI",9)).pack()
        bf = tk.Frame(self.root, bg="#0d1117"); bf.pack(pady=8)
        self.b_start  = tk.Button(bf, text="Auto-Start",  bg="#1f6feb", fg="white",
                                   font=("Segoe UI",9,"bold"), bd=0, padx=10, pady=5,
                                   command=self.start_auto)
        self.b_start.grid(row=0,column=0,padx=5)
        tk.Button(bf, text="1x Scannen", bg="#238636", fg="white",
                  font=("Segoe UI",9,"bold"), bd=0, padx=10, pady=5,
                  command=self.einmal).grid(row=0,column=1,padx=5)
        self.b_stop = tk.Button(bf, text="Stop", bg="#b91c1c", fg="white",
                                 font=("Segoe UI",9,"bold"), bd=0, padx=10, pady=5,
                                 command=self.stopp, state="disabled")
        self.b_stop.grid(row=0,column=2,padx=5)
        self.box = scrolledtext.ScrolledText(self.root, height=15, width=68,
            bg="#161b22", fg="#c9d1d9", font=("Consolas",9), bd=0, state="disabled")
        self.box.pack(padx=10,pady=6,fill=tk.BOTH,expand=True)

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        def _d():
            self.box.config(state="normal")
            self.box.insert(tk.END, f"[{ts}] {msg}\n")
            self.box.see(tk.END)
            self.box.config(state="disabled")
        self.root.after(0, _d)

    def set_s(self, t): self.root.after(0, lambda: self.status.set(t))

    def einmal(self):
        def _r():
            self.set_s("Scanne...")
            scan(self.log)
            self.set_s("Bereit")
        threading.Thread(target=_r, daemon=True).start()

    def start_auto(self):
        if self.laufend: return
        self.laufend = True
        self.b_start.config(state="disabled")
        self.b_stop.config(state="normal")
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        self.set_s(f"Auto aktiv ({INTERVAL_SEK}s)")
        while self.laufend:
            scan(self.log)
            for _ in range(INTERVAL_SEK):
                if not self.laufend: break
                time.sleep(1)
        self.set_s("Gestoppt")

    def stopp(self):
        self.laufend = False
        self.b_start.config(state="normal")
        self.b_stop.config(state="disabled")
        self.log("Gestoppt.")

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
