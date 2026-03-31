import tkinter as tk
from tkinter import ttk
import time
import re
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
WEBAPP1 = "https://script.google.com/macros/s/AKfycbyU7aO9-YqUbulvESSkWc3/exec"
status_text = "🟢 Bereit"

root = tk.Tk()
root.title("LYL SchmuckBot v6.0")
root.geometry("350x200")

label = ttk.Label(root, text="LYL.GG Schmuck Tracker")
label.pack(pady=10)

status_label = ttk.Label(root, text=status_text)
status_label.pack(pady=5)

def scan_schmuck():
    global status_text
    status_text = "🔄 Scanne lyl.gg..."
    status_label.config(text=status_text)
    root.update()
    
    options = uc.ChromeOptions()
    options.add_argument('--headless')
    driver
