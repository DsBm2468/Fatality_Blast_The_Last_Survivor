# -*- coding: utf-8 -*-
"""
reemplazar_grafo.py - deja VACIO el EventGraph de un Blueprint.

Por que no basta con Ctrl+A + Supr: **Ctrl+A no llega al lienzo**. Se probo a
conciencia el 2026-09-11. Lo que pasa es que cada pulsacion necesita que el
panel del grafo tenga el foco de TECLADO, y eso solo lo da el clic de la misma
invocacion; pero el clic deselecciona, asi que Ctrl+A y Supr tienen que ir
juntos... y aun asi Ctrl+A no selecciona nada. Ctrl+V si funciona. No se ha
encontrado por que, y no merece mas tiempo: hay un camino que si es fiable.

El camino fiable:
  1. BlueprintEditorLibrary.remove_graph() borra el EventGraph entero (API).
  2. Unreal NO lo recrea solo, y UbergraphPages es protegida desde Python, asi
     que new_object() crea un EdGraph que el editor no ve. La unica forma es
     el boton "+" de la seccion GRAFICOS del panel "Mi blueprint", que crea
     "NewEventGraph" y lo deja en modo renombrar -> Enter acepta el nombre.
  3. rename_graph() lo devuelve a "EventGraph" (API).

Queda un grafo vacio, con su nombre de siempre, listo para un Ctrl+V.

Uso:
    python Tools/reemplazar_grafo.py /Game/ruta/BP_X
    ... --fx 0.1464 --fy 0.3992    (donde esta el "+" de GRAFICOS)
"""
import argparse
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(RAIZ, "Tools")
SAVED = os.path.join(RAIZ, "Saved")
PY_UE = os.environ.get(
    "UE_PYTHON",
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe",
)

# Posicion del "+" de la seccion GRAFICOS, en fraccion de la ventana del editor
# maximizada. Medidas en pantalla el 2026-09-11.
#
# La Y depende del TIPO de Blueprint: en uno de Actor, el panel "Mi blueprint"
# va debajo del de Componentes, y en uno de ActorComponent (que no tiene
# Viewport ni Componentes) va arriba del todo. Se prueban las dos y se
# comprueba el resultado.
FX_MAS = 0.1464
FY_CANDIDATAS = [0.3992, 0.1293]


def remoto(fuente):
    tmp = os.path.join(SAVED, "_tmp_reemplazar.py")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(fuente)
    r = subprocess.run([PY_UE, os.path.join(TOOLS, "ue_remote.py"), tmp],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print((r.stdout or "").rstrip())
    if r.returncode != 0:
        print((r.stderr or "").rstrip())
        raise SystemExit("fallo el paso remoto")
    return r.stdout


def ps(args):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", os.path.join(TOOLS, "paste_win.ps1")] + args,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("asset")
    ap.add_argument("--fx", type=float, default=FX_MAS)
    ap.add_argument("--fy", type=float, default=None)
    a = ap.parse_args()
    titulo = a.asset.rsplit("/", 1)[-1]

    print("=== VACIAR EventGraph de %s ===" % a.asset)

    remoto('''
import unreal
BEL, EAL = unreal.BlueprintEditorLibrary, unreal.EditorAssetLibrary
bp = EAL.load_asset(%r)
ss = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
g = BEL.find_event_graph(bp)
print("EventGraph actual:", g)
if g is not None:
    BEL.remove_graph(bp, g)
    BEL.compile_blueprint(bp)
    # GUARDAR es obligatorio. Sin esto el estado en memoria se desvia del de
    # disco y, al cerrar y reabrir el editor del asset, vuelve el grafo viejo
    # sin avisar: el pegado se queda buscando una pestana que ya no existe.
    EAL.save_loaded_asset(bp, only_if_is_dirty=False)
print("tras borrar:", BEL.find_event_graph(bp))
ss.close_all_editors_for_asset(bp)
ss.open_editor_for_assets([bp])
''' % a.asset)
    time.sleep(3.0)

    candidatas = [a.fy] if a.fy is not None else FY_CANDIDATAS
    for fy in candidatas:
        print("  pulsando el '+' de GRAFICOS en (%.4f, %.4f)" % (a.fx, fy))
        ps(["-WindowTitle", titulo, "-SoloClic", "-Click",
            "-FracX", str(a.fx), "-FracY", str(fy)])
        time.sleep(1.5)
        ps(["-WindowTitle", titulo, "-Enviar", "enter"])
        time.sleep(1.5)
        hay = remoto('''
import unreal
BEL, EAL = unreal.BlueprintEditorLibrary, unreal.EditorAssetLibrary
bp = EAL.load_asset(%r)
print("NUEVO:", BEL.find_graph(bp, "NewEventGraph") is not None)
''' % a.asset)
        if "NUEVO: True" in hay:
            break

    salida = remoto('''
import unreal
BEL, EAL = unreal.BlueprintEditorLibrary, unreal.EditorAssetLibrary
bp = EAL.load_asset(%r)
g = BEL.find_graph(bp, "NewEventGraph")
if g is not None:
    BEL.rename_graph(g, "EventGraph")
BEL.compile_blueprint(bp)
EAL.save_loaded_asset(bp, only_if_is_dirty=False)
eg = BEL.find_event_graph(bp)
print("EventGraph:", eg)
print("RESULTADO:", "OK" if eg is not None else "NO SE CREO")
''' % a.asset)

    ok = "RESULTADO: OK" in salida
    print("FALLOS: %d" % (0 if ok else 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
