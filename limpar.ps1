# limpar.ps1 - Lista e remove somente arquivos temporários e duplicados conhecidos.
# O ambiente .venv314, os dados de entrada, os resultados finais, o código,
# a configuração e o README não são removidos por este script.

$venvAntigo = Join-Path $PSScriptRoot ".venv"
$venvFuncional = Join-Path $PSScriptRoot ".venv314"
$diretorioResultados = Join-Path $PSScriptRoot "data\results_output"
$scriptInspecao = Join-Path $PSScriptRoot "inspect_project.py"

# Calcula o tamanho de um arquivo ou de uma pasta usando apenas os itens encontrados.
function Get-TamanhoBytes {
    param([string]$Caminho)

    if (-not (Test-Path -LiteralPath $Caminho)) {
        return [long]0
    }

    $item = Get-Item -LiteralPath $Caminho -Force
    if ($item.PSIsContainer) {
        $medicao = Get-ChildItem -LiteralPath $Caminho -File -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum
        if ($null -eq $medicao.Sum) {
            return [long]0
        }
        return [long]$medicao.Sum
    }

    return [long]$item.Length
}

# Procura pastas __pycache__ sem entrar nos ambientes virtuais.
function Find-PycacheDirectories {
    param([string]$Diretorio)

    $encontradas = @()
    $filhos = Get-ChildItem -LiteralPath $Diretorio -Directory -Force -ErrorAction SilentlyContinue
    foreach ($filho in $filhos) {
        # Não segue links de diretório, evitando sair da pasta do projeto.
        if ($filho.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            continue
        }
        if (
            $filho.FullName -ieq $venvAntigo -or
            $filho.FullName -ieq $venvFuncional
        ) {
            continue
        }
        if ($filho.Name -eq "__pycache__") {
            $encontradas += $filho.FullName
            continue
        }
        $encontradas += Find-PycacheDirectories -Diretorio $filho.FullName
    }
    return $encontradas
}

Write-Host "================================================================"
Write-Host "LIMPEZA SEGURA DO PROJETO"
Write-Host "Este script identifica itens específicos e pede confirmação"
Write-Host "antes de removê-los. O ambiente .venv314 será preservado."
Write-Host "================================================================"
Write-Host ""

# Monta a lista de alvos permitidos, sem incluir dados ou resultados finais.
$itens = @(
    [PSCustomObject]@{
        Caminho = $venvAntigo
        Tipo = "Pasta"
    }
)

$zipsDuplicados = @()
if (Test-Path -LiteralPath $diretorioResultados -PathType Container) {
    $zipsDuplicados = Get-ChildItem `
        -LiteralPath $diretorioResultados `
        -File `
        -Filter "*_LIB_20261014*.zip" `
        -Force `
        -ErrorAction SilentlyContinue
    foreach ($zip in $zipsDuplicados) {
        $itens += [PSCustomObject]@{
            Caminho = $zip.FullName
            Tipo = "Arquivo"
        }
    }
}

$itens += [PSCustomObject]@{
    Caminho = $scriptInspecao
    Tipo = "Arquivo"
}

$pastasPycache = @(Find-PycacheDirectories -Diretorio $PSScriptRoot)
foreach ($pastaPycache in $pastasPycache) {
    $itens += [PSCustomObject]@{
        Caminho = $pastaPycache
        Tipo = "Pasta"
    }
}

# Exibe todos os alvos existentes e inexistentes e estima o espaço a liberar.
$totalEstimado = [long]0
Write-Host "Itens que podem ser removidos:"
foreach ($item in $itens) {
    $existe = Test-Path -LiteralPath $item.Caminho
    if ($existe) {
        $tamanho = Get-TamanhoBytes -Caminho $item.Caminho
        $status = "existe"
        $totalEstimado += $tamanho
    }
    else {
        $tamanho = [long]0
        $status = "não existe"
    }
    $tamanhoMB = $tamanho / 1MB
    Write-Host ("  Caminho: {0}" -f $item.Caminho)
    Write-Host ("  Tamanho: {0:N2} MB | Status: {1}" -f $tamanhoMB, $status)
}

if ($zipsDuplicados.Count -eq 0) {
    Write-Host "  Nenhum ZIP correspondente a *_LIB_20261014*.zip foi encontrado."
}
if ($pastasPycache.Count -eq 0) {
    Write-Host "  Nenhuma pasta __pycache__ elegível foi encontrada."
}
Write-Host ""
Write-Host ("Espaço estimado a liberar: {0:N2} MB" -f ($totalEstimado / 1MB))
Write-Host ""

# Solicita confirmação explícita antes de executar qualquer remoção.
$confirmacao = Read-Host "Deseja continuar? (S/N)"
if ($confirmacao -notmatch "^[sS]$") {
    Write-Host "Limpeza cancelada. Nenhum item foi removido." -ForegroundColor Yellow
    return
}

# Remove cada alvo isoladamente; uma falha não impede as demais tentativas.
$totalLiberado = [long]0
foreach ($item in $itens) {
    if (-not (Test-Path -LiteralPath $item.Caminho)) {
        continue
    }

    $tamanhoAntes = Get-TamanhoBytes -Caminho $item.Caminho
    try {
        Remove-Item -LiteralPath $item.Caminho -Recurse -Force -ErrorAction Stop
        if (-not (Test-Path -LiteralPath $item.Caminho)) {
            $totalLiberado += $tamanhoAntes
            Write-Host ("Removido com sucesso: {0}" -f $item.Caminho) -ForegroundColor Green
        }
        else {
            $tamanhoDepois = Get-TamanhoBytes -Caminho $item.Caminho
            $totalLiberado += [Math]::Max([long]0, $tamanhoAntes - $tamanhoDepois)
            Write-Host ("Remoção parcial: {0} ainda existe." -f $item.Caminho) -ForegroundColor Yellow
        }
    }
    catch {
        $tamanhoDepois = Get-TamanhoBytes -Caminho $item.Caminho
        $totalLiberado += [Math]::Max([long]0, $tamanhoAntes - $tamanhoDepois)
        Write-Host ("Erro ao remover {0}: {1}" -f $item.Caminho, $_.Exception.Message) -ForegroundColor Red
    }
}

# Resume o espaço efetivamente liberado após as tentativas.
Write-Host ""
Write-Host ("Espaço efetivamente liberado: {0:N2} MB" -f ($totalLiberado / 1MB))
Write-Host "Limpeza concluída."
