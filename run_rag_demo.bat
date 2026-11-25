@echo off
title Position-Aware RAG Demo Server
echo ========================================================
echo    Starting Position-Aware RAG Interactive Dashboard
echo    Max Upload Size: 1,000 MB (Word, PDF, TXT, MD)
echo ========================================================
echo.
cd /d "%~dp0"
python -m streamlit run app.py
pause
