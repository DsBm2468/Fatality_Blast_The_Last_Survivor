# -*- coding: utf-8 -*-
"""
Banco de pruebas de INVENTARIO, SOLTAR y LANZAR, medido en PIE.

    "<engine>/Binaries/ThirdParty/Python3/Win64/python.exe" Tools/run_item_tests.py

Informe en Saved/ItemTest_Report.txt. Acaba en "FALLOS: N" y devuelve 0 si no
hay ninguno.

Que comprueba, y por que cada cosa:

  base  el pawn tiene los dos componentes y el inventario arranca con 4 huecos
  c1    recoger un arma la EQUIPA, la mete en el hueco 0, la engancha a la
        mano y la saca de la lista de interactuables
  c2    soltar con F la desengancha, vacia el hueco y devuelve el arma a la
        lista, para poder recogerla otra vez sin salir del radio
  c3    recoger una granada va al hueco 1 y NO pisa el hueco 0: cada categoria
        tiene el suyo
  c4    lanzar desengancha, libera EquippedItem y vacia el hueco
  c5    la explosion alcanza a los TRES peones del radio. Es la prueba del
        fallo de fondo del sistema de lanzado: SphereTraceSingleForObjects
        devolvia uno solo
  c6    entrar en el radio mete el item UNA vez (no una por cada entrada) y
        salir lo quita

COMO ESTA MONTADO
  - Un paso por llamada remota: escribir, invocar y leer en la misma llamada
    devuelve el valor viejo, porque el Blueprint corre en el frame siguiente.
  - Los items de prueba se siembran en el mundo de EDITOR antes de arrancar
    PIE: spawn_actor_from_class no puede meter actores dentro de PIE.
  - Soltar se prueba llamando al MISMO evento que llama la tecla F
    (BPC_Interaction.Ev_SoltarEquipado). La tecla en si no se puede pulsar
    desde fuera: la entrada inyectada NO llega al viewport de PIE, ni con
    keybd_event ni con SendInput por scancode, con la ventana enfocada y el
    raton capturado (se comprobo que ni W ni P surtian efecto). Que F este
    atada a ese evento lo verifica Tools/check_drop_binding.py leyendo el
    grafo y el mapeo de entrada.
  - El nivel queda SUCIO en el editor (items y peones sembrados). El banco NO
    lo guarda, igual que run_lab_tests.py.
"""
import json
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PASO_TXT = os.path.join(AQUI, "_paso_item.txt")
EJECUTOR = os.path.join(AQUI, "item_test.py")
REMOTO = os.path.join(AQUI, "ue_remote.py")
PS_WIN = os.path.join(AQUI, "paste_win.ps1")
ESTADO = os.path.join(RAIZ, "Saved", "_item_state.json")
INFORME = os.path.join(RAIZ, "Saved", "ItemTest_Report.txt")
PY_UE = os.environ.get(
    "UE_PYTHON",
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe",
)

# (paso, segundos de espera DESPUES)
BLOQUES = [
    ("fase 0", [("reset", 0), ("pie_off", 3), ("preparar", 2)]),
    ("arranque", [("pie_on", 7), ("base", 0)]),
    ("c1 - recoger arma", [
        ("c1_acercar", 1.2), ("c1_recoger", 1.2), ("c1_check", 0)]),
    ("c2 - soltar", [
        ("c2_soltar", 1.5), ("c2_check", 0)]),
    ("c3 - recoger granada", [
        ("c3_acercar", 1.2), ("c3_recoger", 1.2), ("c3_check", 0)]),
    ("c4 - lanzar", [("c4_lanzar", 1.0), ("c4_check", 0)]),
    ("c5 - alcance de la explosion", [("c5_explotar", 0)]),
    ("c6 - entrar y salir del radio", [
        ("c6_acercar", 1.5), ("c6_dentro", 0),
        ("c6_alejar", 1.5), ("c6_fuera", 0)]),
    ("cierre", [("pie_off", 2)]),
]


def remoto(paso):
    with open(PASO_TXT, "w", encoding="utf-8") as f:
        f.write(paso)
    r = subprocess.run([PY_UE, REMOTO, EJECUTOR], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    salida = ((r.stdout or "") + (r.stderr or "")).rstrip()
    if salida:
        print(salida)
    return salida


def pulsar_f():
    """Pulsa F en la ventana del editor, donde corre PIE. El clic previo es
    imprescindible: sin el, la pulsacion no llega al viewport y se pierde sin
    avisar (medido el 2026-09-11)."""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS_WIN,
         "-WindowTitle", "Unreal Editor", "-Enviar", "f",
         "-FracX", "0.5", "-FracY", "0.45", "-Click"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("   .. tecla F -> %s" % ((r.stdout or "").strip().replace("\n", " | ")))
    return r.returncode == 0


def main():
    print("=" * 68)
    print("BANCO DE INVENTARIO / SOLTAR / LANZAR")
    print("=" * 68)
    t0 = time.time()
    for titulo, pasos in BLOQUES:
        print("")
        print("--- %s ---" % titulo)
        for paso, espera in pasos:
            if paso == "__tecla__":
                pulsar_f()
            elif paso == "__dormir__":
                pass
            else:
                remoto(paso)
            if espera:
                time.sleep(espera)

    st = {"checks": [], "notas": []}
    if os.path.isfile(ESTADO):
        with open(ESTADO, encoding="utf-8") as f:
            st = json.load(f)

    lineas = ["BANCO DE INVENTARIO / SOLTAR / LANZAR", ""]
    fallos = 0
    for c in st["checks"]:
        if not c["ok"]:
            fallos += 1
        lineas.append("%-5s [%s] %s%s" % (
            "OK" if c["ok"] else "FALLO", c["caso"], c["texto"],
            ("  -> " + c["detalle"]) if c["detalle"] else ""))
    if st.get("notas"):
        lineas.append("")
        lineas.append("NOTAS")
        lineas.extend("  " + n for n in st["notas"])
    lineas.append("")
    lineas.append("COMPROBACIONES: %d   FALLOS: %d" % (len(st["checks"]), fallos))
    lineas.append("tiempo: %.0f s" % (time.time() - t0))

    with open(INFORME, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")

    print("")
    print("=" * 68)
    for l in lineas:
        print(l)
    print("informe -> %s" % INFORME)
    print("FALLOS: %d" % fallos)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
