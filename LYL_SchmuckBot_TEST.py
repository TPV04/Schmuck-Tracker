import tkinter as tk
from tkinter import ttk
import threading

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def main():
    root = tk.Tk()
    root.title("LYL SchmuckBot TEST")
    root.geometry("340x190")

    status = tk.StringVar(value="🟢 Bereit")

    label = ttk.Label(root, text="LYL SchmuckBot TEST", font=("Arial", 12))
    label.pack(pady=10)

    status_label = ttk.Label(root, textvariable=status, font=("Arial", 10))
    status_label.pack(pady=5)

    def scan_worker():
        driver = None
        try:
            status.set("🔄 Starte Browser…")
            root.update()

            options = uc.ChromeOptions()
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")

            driver = uc.Chrome(options=options)

            status.set("🔄 Öffne lyl.gg Marktsystem…")
            root.update()

            url = "https://www.lyl.gg/wiki/entry/47-marktsystem"
            driver.get(url)

            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            html = driver.page_source
            with open("lyl_debug.html", "w", encoding="utf-8") as f:
                f.write(html)

            status.set("✅ Seite geladen, lyl_debug.html gespeichert")
        except Exception as e:
            status.set(f"❌ Fehler: {type(e).__name__}")
        finally:
            try:
                if driver is not None:
                    driver.quit()
            except:
                pass

    def scan_click():
        status.set("🔄 Starte TEST-Scan…")
        root.update()
        t = threading.Thread(target=scan_worker, daemon=True)
        t.start()

    scan_button = ttk.Button(root, text="SCAN (Browser-Test)", command=scan_click)
    scan_button.pack(pady=10)

    close_button = ttk.Button(root, text="Schließen", command=root.destroy)
    close_button.pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    main()