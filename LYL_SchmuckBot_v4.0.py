#!/usr/bin/env python3
"""
LYL.GG SchmuckBot v4.0 - Vollständiges System
Cloudflare Bypass | 2 Google Sheets | GUI | Autostart
Tony - 25.03.2026
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import re
from datetime import datetime
import requests
import os
import sys

# Selenium (Python 3.14 kompatibel)
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui
