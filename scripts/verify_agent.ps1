# Verifica el estado del print agent local y las impresoras
$base = 'http://127.0.0.1:34567'
function Try-Get($path) {
    try {
        $r = Invoke-RestMethod -Uri ($base + $path) -Method GET -TimeoutSec 5
        Write-Host "$path -> OK: $(ConvertTo-Json $r -Compress)"
    } catch {
        Write-Host "$path -> FAIL: $($_.Exception.Message)"
    }
}

Try-Get '/ping'
Try-Get '/info'
Try-Get '/print/raw'  # returns 400 normally (no body) but helps check endpoint
Try-Get '/print/html'
