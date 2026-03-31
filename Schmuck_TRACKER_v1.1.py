# Schmuck Tracker v1.1 - Cloudflare Bypass
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import requests
from datetime import datetime
import json
import os
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

class SchmuckTracker:
    def __init__(self
