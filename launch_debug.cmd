@echo off
rem Launch the GitHub Copilot app with the WebView2 inspector enabled on port 9222.
rem Close the running app first (the app is single-instance, so a second launch
rem just forwards to the existing window and no inspector is exposed).
setlocal
set WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222
start "" "%LOCALAPPDATA%\Programs\GitHub Copilot\github.exe"
echo.
echo Started with remote debugging.
echo   Inspector UI : http://127.0.0.1:9222
echo   Target list  : http://127.0.0.1:9222/json
echo Close this window when done; the app keeps running.
endlocal
