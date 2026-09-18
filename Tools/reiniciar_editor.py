# -*- coding: utf-8 -*-
"""
reiniciar_editor.py - cierra el editor, lo vuelve a abrir y espera a que
acepte ejecucion remota.

Dos cosas que hay que saber:

 - Matar el editor con cambios sin guardar hace que al siguiente arranque
   salga el dialogo "se encontraron paquetes guardados automaticamente".
   Ese dialogo BLOQUEA la ejecucion remota: el editor parece colgado y
   ue_remote da "no se encontro ningun editor escuchando". Aqui se pulsa
   "Omitir restauracion", que ademas es lo que se quiere: restaurar traeria
   de vuelta justo los cambios que se estan descartando.

 - El estado en memoria de un Blueprint puede desviarse del de disco (nodos
   pegados sin guardar, sondas de foco que no se deshicieron). Reiniciar es
   la forma fiable de volver al estado guardado.

Uso:  python Tools/reiniciar_editor.py
"""
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(RAIZ, "Tools")
MOTOR = os.environ.get("UE_ENGINE_ROOT", r"C:\Program Files\Epic Games\UE_5.7")
PY_UE = os.path.join(MOTOR, "Engine", "Binaries", "ThirdParty", "Python3",
                     "Win64", "python.exe")
EDITOR = os.path.join(MOTOR, "Engine", "Binaries", "Win64", "UnrealEditor.exe")
UPROJECT = os.path.join(RAIZ, "FatalityBlast.uproject")

PS_OMITIR = r'''
Add-Type -Namespace R -Name W -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
[DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
[DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
public delegate bool EnumProc(IntPtr h, IntPtr p);
'@
$proc = Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { Write-Output "NO HAY EDITOR"; exit 0 }
$lista = New-Object System.Collections.ArrayList
$cb = [R.W+EnumProc]{
    param([IntPtr]$h, [IntPtr]$p)
    $pid2 = 0
    [void][R.W]::GetWindowThreadProcessId($h, [ref]$pid2)
    if ($pid2 -eq $proc.Id -and [R.W]::IsWindowVisible($h)) {
        $len = [R.W]::GetWindowTextLength($h)
        if ($len -gt 0) {
            $sb = New-Object System.Text.StringBuilder ($len + 1)
            [void][R.W]::GetWindowText($h, $sb, $sb.Capacity)
            [void]$lista.Add($sb.ToString())
        }
    }
    return $true
}
[void][R.W]::EnumWindows($cb, [IntPtr]::Zero)
Write-Output ("VENTANAS: " + ($lista -join " | "))
'''


def ventanas():
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-Command", PS_OMITIR],
                       capture_output=True, text=True, errors="replace")
    return (r.stdout or "").strip()


def vivo():
    r = subprocess.run([PY_UE, os.path.join(TOOLS, "ue_remote.py"),
                        "-c", "import unreal"],
                       capture_output=True, text=True)
    return r.returncode == 0


def main():
    subprocess.run(["taskkill", "/F", "/IM", "UnrealEditor.exe"],
                   capture_output=True, text=True)
    time.sleep(6)
    print("editor cerrado")

    subprocess.Popen([EDITOR, UPROJECT],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("editor lanzado; esperando...")

    limite = time.time() + 420
    aviso = False
    while time.time() < limite:
        if vivo():
            print("EDITOR LISTO")
            return 0
        v = ventanas()
        # el dialogo de restauracion de autoguardado bloquea el arranque
        if "guardad" in v.lower() or "restaur" in v.lower():
            if not aviso:
                print("  dialogo de restauracion detectado: %s" % v)
                aviso = True
        time.sleep(5)
    print("el editor no respondio a tiempo. Ventanas: %s" % ventanas())
    return 1


if __name__ == "__main__":
    sys.exit(main())
