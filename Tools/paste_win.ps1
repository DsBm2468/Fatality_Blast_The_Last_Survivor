<#
  paste_win.ps1 - pega texto T3D en el lienzo de un editor de Blueprint.

  La API de Python de UE no puede crear nodos ni conexiones (UEdGraphPin no es
  un UObject), y tampoco expone el portapapeles ni el comando Pegar. La unica
  via es la de verdad: poner el texto en el portapapeles de Windows, dar el
  foco al lienzo del grafo y mandar Ctrl+V.

  Dos cosas que costaron un intento cada una:
   - el editor de Blueprint abre en VENTANA PROPIA, titulada con el nombre del
     asset; mandar Ctrl+V a la ventana principal no pega nada;
   - Windows bloquea el robo de foco desde un proceso que no esta en primer
     plano: SetForegroundWindow devuelve true y no hace nada. Hay que enganchar
     la cola de entrada al hilo que tiene el foco (AttachThreadInput).

  Este script NO verifica nada: quien lo llama (Tools/paste_bp.py) cuenta los
  nodos del grafo destino por T3D antes y despues.
#>
param(
    [string]$File = "",
    [Parameter(Mandatory=$true)][string]$WindowTitle,
    [double]$FracX = 0.55,
    [double]$FracY = 0.55,
    [switch]$Click,
    [switch]$SoloClic
)

$ErrorActionPreference = 'Stop'
if (-not $SoloClic -and -not (Test-Path $File)) { Write-Error "no existe $File"; exit 2 }

Add-Type -Namespace W -Name U -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
[DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, UIntPtr e);
[DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, UIntPtr e);
[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
[DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
[DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool f);
[DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
[DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
public delegate bool EnumProc(IntPtr h, IntPtr p);
[StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
'@

$KEYEVENTF_KEYUP = 0x0002

function Get-Title([IntPtr]$h) {
    $len = [W.U]::GetWindowTextLength($h)
    if ($len -le 0) { return "" }
    $sb = New-Object System.Text.StringBuilder ($len + 1)
    [void][W.U]::GetWindowText($h, $sb, $sb.Capacity)
    return $sb.ToString()
}

function Get-VentanasUnreal {
    $proc = Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $proc) { return @() }
    $lista = New-Object System.Collections.ArrayList
    $cb = [W.U+EnumProc]{
        param([IntPtr]$h, [IntPtr]$p)
        $pid2 = 0
        [void][W.U]::GetWindowThreadProcessId($h, [ref]$pid2)
        if ($pid2 -eq $proc.Id -and [W.U]::IsWindowVisible($h)) {
            $t = Get-Title $h
            if ($t -ne "") { [void]$lista.Add([pscustomobject]@{ H = $h; T = $t }) }
        }
        return $true
    }
    [void][W.U]::EnumWindows($cb, [IntPtr]::Zero)
    return $lista
}

function Set-Foreground([IntPtr]$h) {
    $hiloActual = [W.U]::GetCurrentThreadId()
    $pidFg = 0
    $hiloFg = [W.U]::GetWindowThreadProcessId([W.U]::GetForegroundWindow(), [ref]$pidFg)
    $eng = $false
    if ($hiloFg -ne $hiloActual) { $eng = [W.U]::AttachThreadInput($hiloActual, $hiloFg, $true) }
    [void][W.U]::ShowWindow($h, 3)          # SW_MAXIMIZE
    [void][W.U]::BringWindowToTop($h)
    [void][W.U]::SetForegroundWindow($h)
    if ($eng) { [void][W.U]::AttachThreadInput($hiloActual, $hiloFg, $false) }
}

# --- 1. localizar la ventana del editor de Blueprint -----------------------
$ventanas = Get-VentanasUnreal
if ($ventanas.Count -eq 0) { Write-Error "el editor de Unreal no esta abierto"; exit 4 }
Write-Output ("VENTANAS: " + (($ventanas | ForEach-Object { "'" + $_.T + "'" }) -join ", "))

$destino = $ventanas | Where-Object { $_.T -eq $WindowTitle } | Select-Object -First 1
if (-not $destino) {
    $destino = $ventanas | Where-Object { $_.T -like "*$WindowTitle*" } | Select-Object -First 1
}
if (-not $destino) {
    Write-Error "no hay ninguna ventana de Unreal titulada '$WindowTitle'"
    exit 6
}
Write-Output "DESTINO: '$($destino.T)'"

# --- 2. portapapeles -------------------------------------------------------
if (-not $SoloClic) {
$texto = Get-Content -Raw -Encoding UTF8 $File
Set-Clipboard -Value $texto
Start-Sleep -Milliseconds 300
$comp = Get-Clipboard -Raw
if ($null -eq $comp -or $comp.Length -lt ($texto.Length / 2)) {
    Write-Error "el portapapeles no acepto el texto"; exit 3
}
Write-Output "PORTAPAPELES: $($texto.Length) caracteres"
}

# --- 3. foco ---------------------------------------------------------------
$ok = $false
for ($i = 0; $i -lt 8; $i++) {
    Set-Foreground $destino.H
    Start-Sleep -Milliseconds 450
    if ([W.U]::GetForegroundWindow() -eq $destino.H) { $ok = $true; break }
}
if (-not $ok) {
    Write-Error "no se pudo poner en primer plano '$($destino.T)' (esta en '$(Get-Title ([W.U]::GetForegroundWindow()))')"
    exit 5
}
Write-Output "FOCO OK"

# --- 4. clic en el lienzo --------------------------------------------------
$r = New-Object W.U+RECT
[void][W.U]::GetWindowRect($destino.H, [ref]$r)
$cx = [int]($r.Left + ($r.Right  - $r.Left) * $FracX)
$cy = [int]($r.Top  + ($r.Bottom - $r.Top ) * $FracY)
# El raton se coloca SIEMPRE sobre el lienzo: Slate pega donde esta el cursor.
# El clic, en cambio, es opcional: puede caer encima de un nodo ya existente o
# levantar un tooltip que se lleva el foco, y el panel del grafo suele tener ya
# el foco de teclado al abrir la ventana.
[void][W.U]::SetCursorPos($cx, $cy)
Start-Sleep -Milliseconds 250
if ($Click) {
    [W.U]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)   # LEFTDOWN
    Start-Sleep -Milliseconds 70
    [W.U]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)   # LEFTUP
    Start-Sleep -Milliseconds 400
}
Write-Output "CURSOR EN: $cx,$cy  (ventana $($r.Left),$($r.Top)-$($r.Right),$($r.Bottom))  clic=$Click"

# Si algo se llevo el foco (un tooltip, un popup), se reintenta una vez.
if ([W.U]::GetForegroundWindow() -ne $destino.H) {
    Write-Output "AVISO: el foco se fue tras mover/clicar; se reintenta"
    Set-Foreground $destino.H
    Start-Sleep -Milliseconds 500
    [void][W.U]::SetCursorPos($cx, $cy)
    Start-Sleep -Milliseconds 200
}
if ([W.U]::GetForegroundWindow() -ne $destino.H) {
    Write-Error "no se pudo devolver el foco a la ventana destino"; exit 7
}

# --- 5. Ctrl+V -------------------------------------------------------------
if ($SoloClic) { Write-Output "SOLO CLIC: no se pega"; exit 0 }
[W.U]::keybd_event(0x11, 0, 0, [UIntPtr]::Zero)        # CTRL down
Start-Sleep -Milliseconds 80
[W.U]::keybd_event(0x56, 0, 0, [UIntPtr]::Zero)        # V down
Start-Sleep -Milliseconds 90
[W.U]::keybd_event(0x56, 0, $KEYEVENTF_KEYUP, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 70
[W.U]::keybd_event(0x11, 0, $KEYEVENTF_KEYUP, [UIntPtr]::Zero)
Write-Output "CTRL+V ENVIADO"
Start-Sleep -Milliseconds 2000

# --- 6. modal? -------------------------------------------------------------
$fgFinal = Get-Title ([W.U]::GetForegroundWindow())
Write-Output "VENTANA TRAS PEGAR: '$fgFinal'"
if ([W.U]::GetForegroundWindow() -ne $destino.H) {
    Write-Output "AVISO: hay una ventana por encima tras pegar -> '$fgFinal' (posible modal)"
}
exit 0
