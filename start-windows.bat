@echo off
setlocal
cd /d "%~dp0"
rem Komutlari mevcut klasorde aramayi kapat; Python yalnizca PATH'te aranir ve tam yoluyla calistirilir.
set "NoDefaultCurrentDirectoryInExePath=1"
set "PYEXE="
for /f "delims=" %%i in ('where $PATH:pyw.exe 2^>nul') do if not defined PYEXE set "PYEXE=%%i"
if defined PYEXE (
    start "" "%PYEXE%" -3 "%~dp0main.py"
    exit /b
)
for /f "delims=" %%i in ('where $PATH:pythonw.exe 2^>nul') do if not defined PYEXE set "PYEXE=%%i"
if defined PYEXE (
    start "" "%PYEXE%" "%~dp0main.py"
    exit /b
)
echo Python bulunamadi. https://www.python.org/downloads/ adresinden Python 3.10+ kurun
echo (kurulumda "Add python.exe to PATH" secenegini isaretleyin) ve tekrar deneyin.
pause
