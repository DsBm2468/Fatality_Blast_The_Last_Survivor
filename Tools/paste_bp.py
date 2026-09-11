# -*- coding: utf-8 -*-
"""
paste_bp.py - pega un fichero T3D en un grafo de Blueprint y VERIFICA que entro.

Por que existe: la API de Python de UE no puede crear logica de Blueprint
(UEdGraphPin no es un UObject) y tampoco expone el portapapeles ni el comando
Pegar. La unica via es la de verdad -- portapapeles + Ctrl+V en el lienzo --, y
eso hay que hacerlo desde fuera del editor.

Las tres trampas que costaron un intento cada una:

1. El editor de Blueprint abre en VENTANA PROPIA, titulada con el nombre del
   asset. Mandar Ctrl+V a la ventana principal no pega nada y no avisa.
2. Windows bloquea el robo de foco desde un proceso que no esta en primer
   plano. Se resuelve en paste_win.ps1 con AttachThreadInput.
3. **El pegado va a la PESTANA ACTIVA, no al EventGraph.** El editor recuerda
   la ultima pestana abierta en la propiedad LastEditedDocuments del propio
   Blueprint, que desde Python es protegida: no se puede leer ni escribir. Sin
   comprobarlo, el pegado entra entero en el grafo equivocado -- y como el
   contador miraba solo el grafo destino, el informe decia "0 nodos" mientras
   la funcion de al lado se llenaba de basura. Aqui se detecta cual es el
   grafo activo PEGANDO UNA SONDA de un solo nodo y viendo cual crece; si no
   es el destino, se hace clic en las pestanas hasta dar con el.

Uso:
    python Tools/paste_bp.py /Game/ruta/BP_X EventGraph Tools/bp_paste/50_x.txt

Acaba en "FALLOS: N".
"""
import argparse
import os
import re
import subprocess
import sys
import time

for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(RAIZ, "Tools")
SAVED = os.path.join(RAIZ, "Saved")
SONDA = os.path.join(TOOLS, "bp_paste", "99_Sonda.txt")
PY_UE = os.environ.get(
    "UE_PYTHON",
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe",
)

sys.path.insert(0, TOOLS)
import t3d_read  # noqa: E402

# Puntos de la barra de pestanas donde probar, en fraccion de la ventana.
# La barra esta justo debajo de la barra de herramientas; las pestanas van de
# izquierda a derecha y su anchura depende del nombre, asi que se barre.
TABS_Y = 0.086
TABS_X = [0.17, 0.22, 0.26, 0.30, 0.34, 0.37, 0.41, 0.45, 0.49, 0.53, 0.57]

# Puntos del lienzo donde hacer clic antes de pegar (Slate necesita que el
# panel del grafo tenga el foco de teclado; sin clic no llega el Ctrl+V).
LIENZO = [(0.55, 0.55), (0.45, 0.72), (0.62, 0.38), (0.50, 0.85)]


def _limpio(txt):
    """La salida de PowerShell trae bytes que no son UTF-8 validos."""
    return (txt or "").encode("ascii", "replace").decode("ascii").rstrip()


def remoto(script):
    r = subprocess.run(
        [PY_UE, os.path.join(TOOLS, "ue_remote.py"), os.path.join(TOOLS, script)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    salida = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        print(salida)
        raise SystemExit("FALLO remoto en %s" % script)
    return salida


def fijar_objetivo(asset_path, salida_t3d):
    os.makedirs(SAVED, exist_ok=True)
    with open(os.path.join(SAVED, "_paste_target.txt"), "w", encoding="utf-8") as fh:
        fh.write("%s\n%s\n" % (asset_path, salida_t3d))


def censo(asset_path, etiqueta="censo"):
    """{grafo: n_nodos} de TODOS los grafos del Blueprint."""
    salida = os.path.join(SAVED, "PasteT3D_%s.copy" % etiqueta)
    if os.path.exists(salida):
        os.remove(salida)
    fijar_objetivo(asset_path, salida)
    remoto("_remote_export_one.py")
    if not os.path.exists(salida):
        raise SystemExit("el export T3D no produjo %s" % salida)
    return dict((g, len(n)) for g, n in t3d_read.parse(salida).items())


def _ps(args):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", os.path.join(TOOLS, "paste_win.ps1")] + args,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, _limpio(r.stdout), _limpio(r.stderr)


def pegar(fichero, titulo, fx, fy, verboso=False):
    cod, out, err = _ps(["-File", fichero, "-WindowTitle", titulo,
                         "-FracX", str(fx), "-FracY", str(fy), "-Click"])
    if verboso or cod != 0:
        print(out)
        if cod != 0:
            print(err)
    return cod == 0


def clic(titulo, fx, fy):
    cod, out, err = _ps(["-WindowTitle", titulo, "-FracX", str(fx),
                         "-FracY", str(fy), "-Click", "-SoloClic"])
    return cod == 0


def enviar_tecla(titulo, combo, fx=None, fy=None):
    """Manda una combinacion al editor. Tiene que salir de paste_win.ps1, que
    es quien sabe enfocar la ventana: lanzarla desde otro proceso pierde la
    pulsacion porque la consola que lo lanza se queda con el foco."""
    args = ["-WindowTitle", titulo, "-Enviar", combo]
    if fx is not None:
        args += ["-FracX", str(fx), "-FracY", str(fy), "-Click"]
    cod, out, err = _ps(args)
    if cod != 0:
        print(out)
        print(err)
    time.sleep(0.6)
    return cod == 0


def deshacer(titulo, n=1):
    for _ in range(n):
        enviar_tecla(titulo, "ctrl+z", LIENZO[0][0], LIENZO[0][1])
    time.sleep(0.8)


def vaciar_grafo(asset, titulo, grafo):
    """Ctrl+A + Supr en el grafo enfocado, y comprueba que quedo vacio.

    CLAUDE.md daba esto por poco fiable, y lo era: si el foco no esta en el
    lienzo, Ctrl+A no hace nada y no avisa. Con el foco verificado (ver
    enfocar()) si es fiable, y aqui ademas se mide el resultado.
    """
    antes = censo(asset, "vaciar_antes").get(grafo, 0)
    for intento in range(3):
        # Ctrl+A sobre el lienzo. Hace falta el clic para que el panel del
        # grafo tenga el foco de teclado, igual que para pegar.
        enviar_tecla(titulo, "ctrl+a", LIENZO[0][0], LIENZO[0][1])
        enviar_tecla(titulo, "delete")
        time.sleep(1.2)
        queda = censo(asset, "vaciar_despues").get(grafo, 0)
        print("  vaciar %s: %d -> %d nodos" % (grafo, antes, queda))
        if queda == 0:
            return True
        if queda == antes:
            print("  (no se borro nada; reintento)")
        antes = queda
    return False


def crecio(antes, despues, preferido=None):
    """Nombre del grafo que gano nodos, o None.

    Ignora los grafos que NO existian antes: al compilar, Unreal fabrica
    grafos-stub por cada evento (EdGraph_28, EdGraph_32...) y aparecen de la
    nada. Sin este filtro el pegador creia que el pegado habia caido en un
    stub y lo deshacia, una y otra vez.
    """
    if preferido and despues.get(preferido, 0) > antes.get(preferido, 0):
        return preferido
    for g, n in despues.items():
        if g in antes and n > antes[g]:
            return g
    return None


def grafo_activo(asset, titulo):
    """Pega una sonda de un nodo, mira que grafo crece y lo deshace."""
    antes = censo(asset, "sonda_antes")
    for fx, fy in LIENZO:
        if not pegar(SONDA, titulo, fx, fy):
            continue
        time.sleep(1.0)
        despues = censo(asset, "sonda_despues")
        g = crecio(antes, despues)
        if g is None:
            # grafo recien creado y vacio: no estaba en el censo anterior
            for gn, n in despues.items():
                if gn not in antes and n:
                    g = gn
                    break
        if g:
            # El Ctrl+Z no siempre entra a la primera. Si la sonda sigue ahi
            # se reintenta: una sonda olvidada es un nodo de basura que se
            # queda GUARDADO en el asset, y no hay forma de borrar un nodo
            # suelto por script (remove_unused_nodes no se lleva los
            # comentarios).
            for intento in range(4):
                deshacer(titulo)
                vuelta = censo(asset, "sonda_vuelta")
                if vuelta.get(g, 0) <= antes.get(g, 0):
                    break
            else:
                print("  AVISO: la sonda NO se deshizo en %s "
                      "(queda un comentario suelto)" % g)
            return g
    return None


def enfocar(asset, titulo, destino):
    """Deja activa la pestana del grafo destino. Devuelve True si lo logra."""
    act = grafo_activo(asset, titulo)
    print("  grafo activo: %s" % act)
    if act == destino:
        return True
    for fx in TABS_X:
        clic(titulo, fx, TABS_Y)
        time.sleep(0.6)
        act = grafo_activo(asset, titulo)
        print("  pestana en x=%.2f -> grafo activo: %s" % (fx, act))
        if act == destino:
            return True
    return False


def nodos_del_fichero(fichero):
    with open(fichero, "r", encoding="utf-8") as fh:
        return len(re.findall(r"^Begin Object Class=", fh.read(), re.M))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("asset")
    ap.add_argument("grafo")
    ap.add_argument("fichero")
    ap.add_argument("--esperados", type=int, default=None)
    ap.add_argument("--no-abrir", action="store_true")
    ap.add_argument("--vaciar", action="store_true",
                    help="borra TODO el grafo destino antes de pegar "
                         "(se guarda copia del export previo)")
    a = ap.parse_args()

    fichero = a.fichero if os.path.isabs(a.fichero) else os.path.join(RAIZ, a.fichero)
    if not os.path.isfile(fichero):
        raise SystemExit("no existe el pegado %s" % fichero)
    esperados = a.esperados if a.esperados is not None else nodos_del_fichero(fichero)
    titulo = a.asset.rsplit("/", 1)[-1]

    print("=== PEGAR %s -> %s :: %s ===" % (os.path.basename(fichero), a.asset, a.grafo))
    print("  nodos en el fichero: %d" % esperados)

    if not a.no_abrir:
        fijar_objetivo(a.asset, "")
        remoto("_remote_open.py")
        time.sleep(3.0)

    if not enfocar(a.asset, titulo, a.grafo):
        print("  PROBLEMA: no se pudo activar la pestana del grafo %r" % a.grafo)
        print("FALLOS: 1")
        return 1

    if a.vaciar:
        copia = os.path.join(SAVED, "PrevioAlVaciado_%s_%s.copy"
                             % (titulo, a.grafo))
        import shutil
        censo(a.asset, "respaldo")
        shutil.copy(os.path.join(SAVED, "PasteT3D_respaldo.copy"), copia)
        print("  copia del grafo previo: %s" % copia)
        if not vaciar_grafo(a.asset, titulo, a.grafo):
            print("  PROBLEMA: no se pudo vaciar %r" % a.grafo)
            print("FALLOS: 1")
            return 1

    antes = censo(a.asset, "antes")
    print("  nodos ANTES en %s: %d" % (a.grafo, antes.get(a.grafo, 0)))

    ok = False
    for fx, fy in LIENZO:
        pegar(fichero, titulo, fx, fy, verboso=True)
        time.sleep(1.5)
        despues = censo(a.asset, "despues")
        ganados = despues.get(a.grafo, 0) - antes.get(a.grafo, 0)
        otro = crecio(antes, despues, preferido=a.grafo)
        if otro and otro != a.grafo:
            print("  PROBLEMA: el pegado entro en %r, no en %r. Deshaciendo."
                  % (otro, a.grafo))
            deshacer(titulo)
            continue
        if ganados:
            print("  nodos DESPUES: %d  (ganados %d, esperados %d)"
                  % (despues.get(a.grafo, 0), ganados, esperados))
            if ganados < esperados:
                print("  PROBLEMA: Unreal descarto %d nodos." % (esperados - ganados))
                deshacer(titulo)
                print("FALLOS: 1")
                return 1
            if ganados > esperados:
                # Unreal AÑADE nodos al pegar cuando el texto trae pines de
                # struct partidos: los materializa como BreakVector2D o
                # MakeStruct sueltos. Son legitimos. Antes esto se tomaba por
                # error y se deshacia el pegado entero -- 466 nodos dentro y
                # el grafo del personaje se quedaba vacio.
                print("  (Unreal anadio %d nodos auxiliares de pines partidos)"
                      % (ganados - esperados))
            ok = True
            break

    if not ok:
        print("  PROBLEMA: no entro ningun nodo.")
        print("FALLOS: 1")
        return 1

    fijar_objetivo(a.asset, "")
    print(remoto("_remote_compile_save.py").rstrip())
    print("FALLOS: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
