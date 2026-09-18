# -*- coding: utf-8 -*-
"""
Banco del cambio de slot en PIE.

Comprueba lo que arreglamos el 2026-09-08: que recorrer los cuatro slots del
inventario con las manos vacias NO produce ni un solo error de tiempo de
ejecucion. Antes, cada cambio de slot llamaba a Set Actor Hidden In Game sobre
las tres referencias que no eran la elegida, y esas suelen ser None; el
Message Log lo escupia todo junto al cerrar la reproduccion con ESC.

    python Tools/test_slot_visibility.py

El veredicto es doble:
  * ninguna linea "PIE: Error" ni "LogScript: Warning: Accessed None" nueva
    en el log durante la partida;
  * HaveGun / HaveGrenade coherentes con el slot (0=arma, 1=lanzable,
    2=escudo, 3=botiquin).

Acaba en "FALLOS: N".
"""
import os
import re
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PY = os.environ.get(
    "UE_PYTHON",
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe")
LOG = os.path.join(RAIZ, "Saved", "Logs", "FatalityBlast.log")
INFORME = os.path.join(RAIZ, "Saved", "SlotTest_Report.txt")

salida = []
fallos = []


def say(m):
    salida.append(m)
    print(m)


def mal(m):
    fallos.append(m)
    say("  FALLO  " + m)


def paso(nombre, espera=0.0):
    with open(os.path.join(AQUI, "_slot_paso.txt"), "w", encoding="utf-8") as fh:
        fh.write(nombre)
    r = subprocess.run([PY, os.path.join(AQUI, "ue_remote.py"),
                        os.path.join(AQUI, "slot_test.py")],
                       capture_output=True, text=True, cwd=RAIZ)
    txt = (r.stdout or "") + (r.stderr or "")
    if espera:
        time.sleep(espera)
    return txt.strip()


def lineas_log():
    try:
        with open(LOG, encoding="utf-8", errors="replace") as fh:
            return len(fh.readlines())
    except Exception:
        return 0


RE_ERROR = re.compile(r"PIE: Error|LogScript: Warning: Accessed None|"
                      r"LogScript: Warning: .*no es v")

say("=" * 70)
say(" BANCO DEL CAMBIO DE SLOT  (errores de tiempo de ejecucion en PIE)")
say("=" * 70)

say("\nExponiendo la variable de slot...")
say("  " + paso("exponer", 1.0))

marca = lineas_log()
say("\nArrancando PIE...")
say("  " + paso("arrancar", 8.0))

say("\nMetiendo un arma en el inventario; los otros tres se quedan a None,")
say("que es exactamente la situacion que producia los Accessed None...")
say("  " + paso("equipar", 0.5))

# HaveGun/HaveGrenade solo pasan a true si ADEMAS la referencia del item
# existe: esa rama cuelga del IsValid, igual que colgaba en el SwitchInteger
# original. Con el inventario vacio lo correcto es que sigan en false.
for n in (0, 1, 2, 3, 0):
    linea = paso("slot%d" % n, 0.6)
    say("\n  slot %d -> %s" % (n, linea))
    if "FALLO" in linea:
        mal("slot %d: %s" % (n, linea))
        continue
    m = re.search(r"SLOT=(\d+)\(pedido (\d+)\) ARMA_OCULTA=(\w+) "
                  r"HaveGun=(\w+) HaveGrenade=(\w+)", linea)
    if not m:
        mal("slot %d: no se pudo leer el estado" % n)
        continue
    puesto, pedido = int(m.group(1)), int(m.group(2))
    oculta, hg, hr = m.group(3), m.group(4) == "True", m.group(5) == "True"
    if puesto != pedido:
        mal("slot %d: ValueOptionInventary se quedo en %d" % (n, puesto))
        continue
    tiene_arma = "Object_Is_Weapon=None" not in linea
    tiene_lanz = "Object_Is_Throwable=None" not in linea
    if hg != (n == 0 and tiene_arma):
        mal("slot %d: HaveGun=%s (arma en inventario: %s)" % (n, hg, tiene_arma))
    if hr != (n == 1 and tiene_lanz):
        mal("slot %d: HaveGrenade=%s (lanzable en inventario: %s)"
            % (n, hr, tiene_lanz))
    if tiene_arma and oculta != ("False" if n == 0 else "True"):
        mal("slot %d: el arma deberia estar %s y esta oculta=%s"
            % (n, "visible" if n == 0 else "oculta", oculta))

say("\nParando PIE...")
say("  " + paso("parar", 3.0))
say("  " + paso("restaurar", 0.5))

say("\nErrores de tiempo de ejecucion durante la partida:")
try:
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        nuevas = fh.readlines()[marca:]
except Exception as e:
    nuevas = []
    mal("no se pudo leer el log: %s" % e)

malas = [l.rstrip() for l in nuevas if RE_ERROR.search(l)]
if malas:
    for l in malas[:20]:
        mal(l[:200])
    if len(malas) > 20:
        mal("... y %d mas" % (len(malas) - 20))
else:
    say("  ok     ninguno en %d lineas de log" % len(nuevas))

say("\n" + "=" * 70)
say("FALLOS: %d" % len(fallos))
with open(INFORME, "w", encoding="utf-8") as fh:
    fh.write("\n".join(salida))
print("informe -> %s" % INFORME)
sys.exit(1 if fallos else 0)
