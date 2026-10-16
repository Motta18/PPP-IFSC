# run.ps1 - Atalho para rodar o Streamlit no ambiente virtual correto (.venv314)
# Uso: .\run.ps1
# Para liberar a execução deste script (uma vez por sessão): Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

Write-Host "Iniciando Streamlit com o ambiente .venv314..." -ForegroundColor Cyan
& "$PSScriptRoot\.venv314\Scripts\python.exe" -m streamlit run "$PSScriptRoot\app.py"
