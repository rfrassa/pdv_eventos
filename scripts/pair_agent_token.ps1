# Script para emparejar token con el print agent local (localhost:34567)
# Uso: .\pair_agent_token.ps1 -Token 'SECRET'
param(
    [Parameter(Mandatory=$true)]
    [string]$Token
)
$uri = 'http://127.0.0.1:34567/pair'
try {
    $resp = Invoke-RestMethod -Uri $uri -Method POST -Body @{ token = $Token } -ContentType 'application/x-www-form-urlencoded' -TimeoutSec 5
    Write-Host "Pair response: $(ConvertTo-Json $resp)"
} catch {
    Write-Error "Pair request failed: $($_.Exception.Message)"
}
