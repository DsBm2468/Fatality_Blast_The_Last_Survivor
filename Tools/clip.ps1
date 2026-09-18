# Carga un pegado de Tools/bp_paste/ en el portapapeles.
#
#   powershell -File Tools\clip.ps1 00
#
# Copia SOLO desde la primera linea "Begin Object" (la cabecera // se imprime
# en pantalla, no se copia: el editor de Blueprint no la entiende).

param([Parameter(Mandatory = $true)][string]$Numero)

$dir = Join-Path $PSScriptRoot "bp_paste"
$archivos = @(Get-ChildItem -Path $dir -Filter "$Numero*.txt" -ErrorAction SilentlyContinue)

if ($archivos.Count -eq 0) {
    Write-Host "No hay ningun pegado que empiece por '$Numero' en $dir" -ForegroundColor Red
    Write-Host "Disponibles:" -ForegroundColor Yellow
    Get-ChildItem -Path $dir -Filter "*.txt" | ForEach-Object { Write-Host "   $($_.Name)" }
    exit 1
}
if ($archivos.Count -gt 1) {
    Write-Host "'$Numero' es ambiguo:" -ForegroundColor Red
    $archivos | ForEach-Object { Write-Host "   $($_.Name)" }
    exit 1
}

$archivo = $archivos[0]
$lineas = Get-Content -Path $archivo.FullName -Encoding UTF8

# cabecera informativa
$lineas | Where-Object { $_ -like "//*" } | ForEach-Object {
    Write-Host ($_ -replace "^//\s?", "") -ForegroundColor Cyan
}

$inicio = 0
for ($i = 0; $i -lt $lineas.Count; $i++) {
    if ($lineas[$i] -like "Begin Object*") { $inicio = $i; break }
}
$cuerpo = $lineas[$inicio..($lineas.Count - 1)] -join "`r`n"

Set-Clipboard -Value $cuerpo

$nodos = ($lineas | Where-Object { $_ -like "Begin Object*" }).Count
Write-Host ""
Write-Host "En el portapapeles: $($archivo.Name)  ($nodos nodos, $($cuerpo.Length) caracteres)" -ForegroundColor Green
Write-Host "Ahora: abre el grafo de destino y pulsa Ctrl+V" -ForegroundColor Green
