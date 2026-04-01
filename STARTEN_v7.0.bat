@echo off
title LYL SchmuckBot v7.0
color 0B
echo ============================================
echo   LYL SchmuckBot v7.0 - Starter
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] Prüfe Python Installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Python nicht gefunden!
    echo Bitte Python 3.10+ installieren: https://python.org
    pause
    exit /b 1
)

echo [2/3] Installiere/Update Abhängigkeiten...
pip install undetected-chromedriver selenium selenium-stealth requests --quiet --upgrade
if errorlevel 1 (
    echo WARNUNG: Einige Pakete konnten nicht installiert werden
)

echo [3/3] Starte SchmuckBot v7.0...
echo.
python LYL_SchmuckBot_v7.0.py

if errorlevel 1 (
    echo.
    echo FEHLER beim Starten! Prüfe ob alle Abhängigkeiten installiert sind.
    echo Versuche: pip install undetected-chromedriver selenium requests
    pause
)
