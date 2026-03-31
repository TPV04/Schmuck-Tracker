import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
print("=== CLOUDFLARE BYPASS TEST ===")
print("Öffnet Chrome (sichtbar)...")

driver = uc.Chrome(headless=False, use_subprocess=True)
driver.get("https://www.lyl.gg/wiki/entry/47-marktsystem")

print("1. Warte 10s auf Challenge...")
input("2. Cloudflare-Seite OK? Enter...")

# Suche Schmuck
rows = driver.find_elements(By.TAG_NAME, "tr")
print(f"Gefunden: {len(rows)} Zeilen")

for i, row in enumerate(rows):
    cells = row.find_elements(By.TAG_NAME, "td")
    if len(cells) >= 4 and "Schmuck" in cells[0].text:
        print(f"🎯 SCHMUCK: {cells[1].text} | {cells[2].text} | {cells[3].text}")
        break

input("Enter zum Schließen...")
driver.quit()
print("✅ TEST ENDE")

