# atualizar.ps1 — Atualiza o dashboard automaticamente e publica no GitHub
Set-Location "C:\Users\info\REPORTCLAUDE"

$logFile  = "C:\Users\info\REPORTCLAUDE\atualizar.log"
$lockFile = "C:\Users\info\REPORTCLAUDE\.atualizando"
$agora    = Get-Date -Format "dd/MM/yyyy HH:mm:ss"

# Evita execuções sobrepostas (mas ignora lock zumbi com mais de 30 min)
if (Test-Path $lockFile) {
    $lockAge = (Get-Date) - (Get-Item $lockFile).CreationTime
    if ($lockAge.TotalMinutes -lt 30) {
        Add-Content $logFile "[$agora] Já em execução, pulando."
        exit 0
    }
    Add-Content $logFile "[$agora] Lock zumbi detectado ($([int]$lockAge.TotalMinutes) min), removendo e continuando."
    Remove-Item $lockFile -Force
}

New-Item $lockFile -ItemType File -Force | Out-Null

try {
    Add-Content $logFile "[$agora] Iniciando atualização..."

    # Gera o dashboard (Meta Ads + Rezdy)
    $output = & python gerar_dashboard.py 2>&1
    Add-Content $logFile ($output | Out-String)

    if ($LASTEXITCODE -ne 0) {
        Add-Content $logFile "[$agora] ERRO ao gerar dashboard (exit $LASTEXITCODE). Abortando."
        exit 1
    }

    # Commit e push somente se index.html foi modificado
    $changed = git status --porcelain index.html
    if ($changed) {
        $now = Get-Date -Format "dd/MM/yyyy HH:mm"
        git add index.html | Out-Null
        git commit -m "Auto-update: $now" | Out-Null
        git push origin main 2>&1 | Out-Null
        $fim = Get-Date -Format "dd/MM/yyyy HH:mm:ss"
        Add-Content $logFile "[$fim] Publicado com sucesso."
    } else {
        Add-Content $logFile "[$agora] Sem alterações, nada a publicar."
    }
}
finally {
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
}
