# Captura una ventana por titulo SIN robarle el foco al usuario (PrintWindow).
param([string]$Titulo, [string]$Salida)
Add-Type -AssemblyName System.Drawing
Add-Type -Namespace F -Name W -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
[DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
[DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
public struct RECT { public int Left, Top, Right, Bottom; }
public delegate bool EnumProc(IntPtr h, IntPtr p);
'@
$encontrada = [IntPtr]::Zero
$cb = [F.W+EnumProc]{
    param([IntPtr]$h, [IntPtr]$p)
    if ([F.W]::IsWindowVisible($h)) {
        $len = [F.W]::GetWindowTextLength($h)
        if ($len -gt 0) {
            $sb = New-Object System.Text.StringBuilder ($len + 1)
            [void][F.W]::GetWindowText($h, $sb, $sb.Capacity)
            if ($sb.ToString() -like "*$Titulo*") { $script:encontrada = $h; return $false }
        }
    }
    return $true
}
[void][F.W]::EnumWindows($cb, [IntPtr]::Zero)
if ($encontrada -eq [IntPtr]::Zero) { Write-Output "NO ENCONTRADA: $Titulo"; exit 1 }
$r = New-Object F.W+RECT
[void][F.W]::GetWindowRect($encontrada, [ref]$r)
$w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$dc = $g.GetHdc()
[void][F.W]::PrintWindow($encontrada, $dc, 2)
$g.ReleaseHdc($dc); $g.Dispose()
$bmp.Save($Salida, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output "$Salida  ${w}x${h}"
