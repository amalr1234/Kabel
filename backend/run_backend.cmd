@echo off
setlocal
cd /d "%~dp0"
set API_KEY_OK=0
if not "%GEMINI_API_KEY%"=="" set API_KEY_OK=1

echo.
echo SOLVIA backend startup
echo DEMO_MODE=%DEMO_MODE%
echo GEMINI_API_KEY_set=%API_KEY_OK%
echo CHROMA_PERSIST_DIRECTORY=%CHROMA_PERSIST_DIRECTORY%
echo DATABASE_URL=%DATABASE_URL%
echo.

if "%API_KEY_OK%"=="0" (
    echo WARNING: GEMINI_API_KEY is not set.
    echo The backend will use demo-mode fallback for generation.
    echo Set GEMINI_API_KEY to enable real Gemini generation.
    echo.
)

set PYTHONUNBUFFERED=1
.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
