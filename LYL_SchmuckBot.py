import tkinter as tk
from tkinter import ttk
import requests
import re
import threading
from datetime import datetime

WEBAPP1 = "https://script.google.com/macros/s/AKfycbyU7aO9-YqUbulvESSkWc3-3WuDfSPQjrWi6w9l0jDu06QRIWV2AU6thhuVDGR99kTexec"
WEBAPP2 = "https://script.google.com/macros/s/AKfycbzlZS1rYFqOwwYkDp2N6W0xJwsyPsWF8Kx1ebXa0CqlEOKZexec"

root = tk.Tk()
root.title("LYL SchmuckBot")
root.geometry("400x250")

status = tk.StringVar(value="🟢 Bereit")
minp = tk.StringVar(value="---")
preis = tk.StringVar(value="---")
maxp = tk.StringVar(value="---")

ttk.Label(root, text="LYL SchmuckBot v7.0", font=("Arial", 14, "bold")).pack(pady=10)
ttk.Label(root, textvariable=status, font=("Arial", 11)).pack(pady=5)

frame = ttk.Frame(root)
frame.pack(pady=10)
ttk.Label(frame, text="Min").grid(row=0, column=0, padx=10)
ttk.Label(frame, textvariable=minp, font=("Arial", 16, "bold")).grid(row=1, column=0)
ttk.Label(frame, text="Preis").grid(row=0, column=1, padx=10)
ttk.Label(frame, textvariable=preis, font=("Arial", 16, "bold")).grid(row=1, column=1)
ttk.Label(frame, text="Max").grid(row=0, column=2, padx=10)
ttk.Label(frame, textvariable=maxp, font=("Arial", 16, "bold")).grid(row=1, column=2)

def scan():
    global status, minp, preis, maxp
    try:
        status.set("🔄 Lade lyl.gg...")
        root.update()
        
        url = "https://www.lyl.gg/wiki/entry/47-marktsystem"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=15)
        
        html = r.text
        idx = html.find("Schmuck")
        if idx == -1:
            status.set("❌ Schmuck nicht gefunden")
            return
        
        zahlen = re.findall(r'[\d,]+', html[idx:idx+500])
        if len(zahlen) >= 3:
            minp.set(zahlen[0])
            preis.set(zahlen[1])
            maxp.set(zahlen[2])
            
            params = {'min': zahlen[0], 'preis': zahlen[1], 'max': zahlen[2]}
            requests.get(WEBAPP1, params=params)
            requests.get(WEBAPP2, params=params)
            
            status.set("✅ Erfolg!")
        else:
            status.set("❌ Preise unlesbar")
    except Exception as e:
        status.set(f"❌ Fehler: {str(e)[:30]}")

ttk.Button(root, text="🔍 SCAN", command=lambda: threading.Thread(target=scan, daemon=True).start()).pack(pady=20)
ttk.Button(root, text="❌ Schließen", command=root.quit).pack(pady=5)

root.mainloop()
