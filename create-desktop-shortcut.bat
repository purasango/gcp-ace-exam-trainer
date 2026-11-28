@echo off
setlocal
rem Masaustune simgeli "GCP ACE Exam Trainer" kisayolu olusturur (bir kez calistirmaniz yeterli).
rem Yollar PowerShell'e ortam degiskeni olarak verilir; klasor adindaki bosluk ve tirnaklar sorun olmaz.
set "GCPACE_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=$env:GCPACE_DIR; $lnk=Join-Path ([Environment]::GetFolderPath('Desktop')) 'GCP ACE Exam Trainer.lnk'; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($lnk); $s.TargetPath=(Join-Path $d 'start-windows.bat'); $s.WorkingDirectory=$d; $s.IconLocation=(Join-Path $d 'examtrainer\assets\icon.ico'); $s.WindowStyle=7; $s.Description='GCP ACE Exam Trainer'; $s.Save()"
if errorlevel 1 (
    echo Kisayol olusturulamadi.
) else (
    echo Masaustune "GCP ACE Exam Trainer" kisayolu eklendi.
)
pause
