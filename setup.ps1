# setup.ps1 - Configura o ambiente para execução do projeto (roda uma vez)
# Uso: .\setup.ps1
# Para liberar a execução deste script (uma vez por sessão): Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

Write-Host "Configurando ambiente do projeto PPP-IBGE..." -ForegroundColor Cyan

# Libera a execução de scripts apenas para este processo do PowerShell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# Verifica se o .venv314 existe
$venvPath = "$PSScriptRoot\.venv314\Scripts\Activate.ps1"
if (-not (Test-Path $venvPath)) {
    Write-Host "ERRO: Ambiente .venv314 nao encontrado em $venvPath" -ForegroundColor Red
    Write-Host "Crie o ambiente com: python -m venv .venv314" -ForegroundColor Yellow
    exit 1
}

Write-Host "Ambiente .venv314 encontrado. Ativando..." -ForegroundColor Green
& $venvPath

Write-Host "Ambiente ativo. Verificando Python..." -ForegroundColor Cyan
python --version

Write-Host "Ambiente pronto para uso!" -ForegroundColor Green
Write-Host "Para rodar o app: .\run.ps1" -ForegroundColor Yellow
