# -*- coding: utf-8 -*-
"""
Banco de pruebas automatico de curacion y proteccion (Lvl_02_TestLab).

Los 11 casos del guion de LAB_DE_PRUEBAS.md seccion 9, medidos en PIE por
control remoto, sin jugar a mano.

    "<engine>/Binaries/ThirdParty/Python3/Win64/python.exe" Tools/run_lab_tests.py

    --caso 6      corre solo ese caso (util al depurar uno)
    --no-preparar salta la fase 0 (nivel + variables editables)

Tarda unos 2-3 minutos. Informe en Saved/LabTest_Report.txt, acaba en
"FALLOS: N". Devuelve 0 si no hay fallos.

COMO ESTA MONTADO, Y POR QUE ASI
--------------------------------
* **Un paso por llamada remota.** Escribir una propiedad, invocar logica y leer
  el resultado en la misma llamada devuelve el valor viejo: el Blueprint corre
  en el frame siguiente. Este fichero CONDUCE; Tools/lab_test.py EJECUTA un
  paso, que le llega por Tools/_paso.txt.
* **Las esperas van aqui.** Mientras el driver duerme, el editor sigue
  tickeando, que es justo lo que hace falta para medir canalizaciones de 3.5 s
  o el decaimiento de las vendas a los 10 s.
* **PIE nuevo antes de cada bloque.** Si el jugador muere, el macro
  CanBeDamaged corta todo dano posterior y los casos siguientes salen a cero
  sin aviso (LAB_DE_PRUEBAS.md seccion 12, trampa 4).
* **Los items se cogen del nivel**, no se spawnean: E1 ya tiene botiquines,
  vendas y escudos, y usarlos es mas fiel a como se juega.
* **La velocidad base se mide**, no se supone (la plantilla Third Person anda
  a 600, no a 500).
* **AutoFire se apaga en el mundo de EDITOR, no en PIE.** El emisor lee AutoFire
  UNA SOLA VEZ en BeginPlay para arrancar un timer; apagarlo durante la partida
  no para el timer ya lanzado, y el dano perdido contamina los casos siguientes
  (se midio la vida cayendo de 100 a 10 en mitad del caso 6). Eso deja
  Lvl_02_TestLab marcado como sucio en el editor: el banco NO lo guarda.

Reconstruido el 2026-08-31 (el original se perdio con Tools/).
"""
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PASO_TXT = os.path.join(AQUI, "_paso.txt")
LAB = os.path.join(AQUI, "lab_test.py")
REMOTO = os.path.join(AQUI, "ue_remote.py")
INFORME = os.path.join(RAIZ, "Saved", "LabTest_Report.txt")

# (paso, segundos de espera DESPUES de ejecutarlo)
BLOQUES = [
    # pie_off primero: si quedo un PIE de una tanda anterior, preparar no puede
    # cargar el nivel ni los assets (get_editor_world() da None en PIE), y
    # pararlo es asincrono, asi que hace falta esperar antes de preparar.
    ("fase 0", [("reset", 0), ("pie_off", 3), ("preparar", 2)]),
    ("arranque", [("pie_on", 6), ("base", 0)]),
    # El caso 3 va el primero a proposito: necesita el inventario vacio, y eso
    # es exactamente lo que hay en un PIE recien arrancado. Vaciarlo a mano no
    # se puede: Object_Is_FirstAidKit no admite escritura por instancia.
    ("caso 3 - sin suministros", [
        ("c3_montar", 1), ("c3_lanzar", 1), ("c3_check", 0)]),

    # El canal del botiquin dura 3.5 s: c1_medio mide a mitad (1.5 s) y c1_fin
    # solo despues de esperar el resto. Medir el fin antes de tiempo daba
    # cuatro fallos fantasma.
    ("caso 1 - botiquin", [
        ("c1_montar", 1), ("c1_lanzar", 1.5), ("c1_medio", 2.8), ("c1_fin", 0)]),

    ("caso 2 - vida llena", [
        ("c2_montar", 1), ("c2_lanzar", 1), ("c2_check", 0)]),
    ("caso 4 - interrupcion", [
        ("c4_montar", 1), ("c4_lanzar", 1), ("c4_golpe", 1), ("c4_check", 0)]),

    ("caso 5 - vendas", [
        ("c5_montar", 1), ("c5_lanzar", 2), ("c5_curado", 0)]),
    ("caso 5 - decaimiento", [("__dormir__", 12), ("c5_decay", 0)]),
    ("caso 5 - tope", [("__dormir__", 14), ("c5_fin", 0)]),

    ("reinicio", [("pie_off", 2), ("pie_on", 6), ("base", 0)]),

    ("caso 6 - durabilidad", [
        ("c6_montar", 1), ("c6_guardia", 1), ("c6_verguardia", 0),
        ("c6_tiro", 0.8), ("c6_tiro", 0.8), ("c6_tiro", 0.8),
        ("c6_tiro", 0.8), ("c6_tiro", 1.2), ("c6_check", 0)]),

    ("caso 7 - arco frontal", [
        ("c7_montar", 1), ("c7_guardia", 1), ("c7_golpe", 1), ("c7_check", 0)]),

    ("caso 8 - parry", [
        ("c8_montar", 1), ("c8_parry", 1), ("c8_check", 0)]),

    ("caso 9 - no bloqueable", [
        ("c9_montar", 1), ("c9_golpe", 1), ("c9_check", 0)]),

    ("caso 10 - cobertura", [
        ("c10_montar", 1.5), ("c10_golpe", 1), ("c10_check", 0)]),

    ("caso 11 - reflejo", [
        ("c11_montar", 1), ("c11_golpe", 1.2), ("c11_check", 0)]),

    ("cierre", [("pie_off", 3), ("restaurar", 0), ("informe", 0)]),
]


def remoto(paso):
    with open(PASO_TXT, "w", encoding="utf-8") as f:
        f.write(paso)
    r = subprocess.run([sys.executable, REMOTO, LAB],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    salida = (r.stdout or "") + (r.stderr or "")
    for linea in salida.splitlines():
        if linea.strip():
            # La consola de Windows va en cp1252 y el log del editor trae
            # acentos: sin esto, un caracter raro tumba la tanda entera al final.
            texto = ("   " + linea.rstrip())
            try:
                print(texto)
            except UnicodeEncodeError:
                print(texto.encode("ascii", "replace").decode("ascii"))
    return r.returncode == 0, salida


def main(argv):
    solo = None
    if "--caso" in argv:
        solo = argv[argv.index("--caso") + 1]
    saltar_prep = "--no-preparar" in argv

    t0 = time.time()
    print("=" * 70)
    print(" BANCO DE PRUEBAS - curacion y proteccion (Lvl_02_TestLab)")
    print("=" * 70)

    fallo_duro = False
    for nombre, pasos in BLOQUES:
        if saltar_prep and nombre == "fase 0":
            continue
        if solo and nombre.startswith("caso") and ("caso %s " % solo) not in nombre:
            continue
        print("")
        print("[%s]" % nombre)
        for paso, espera in pasos:
            if paso == "__dormir__":
                print("   .. esperando %.1f s" % espera)
                time.sleep(espera)
                continue
            ok, _ = remoto(paso)
            if not ok:
                print("   !! la llamada remota fallo en el paso %s" % paso)
                fallo_duro = True
            if espera:
                time.sleep(espera)

    print("")
    print("=" * 70)
    if os.path.isfile(INFORME):
        with open(INFORME, encoding="utf-8") as f:
            texto = f.read()
        print(texto.strip().splitlines()[-1])
        print("informe -> " + INFORME)
        ultimo = texto.strip().splitlines()[-1]
        n = int(ultimo.split(":")[-1]) if ":" in ultimo else 1
        print("tiempo: %.0f s" % (time.time() - t0))
        return 1 if (n or fallo_duro) else 0
    print("NO se genero el informe")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
