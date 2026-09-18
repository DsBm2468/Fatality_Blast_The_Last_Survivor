# -*- coding: utf-8 -*-
"""
Mide el sistema de recarga en PIE.  Se llama en TRES tandas desde el shell,
con esperas de PowerShell entre medias, porque un time.sleep dentro del script
remoto bloquea el hilo del editor y PIE no llega a arrancar.

    echo preparar > Tools/_modo.txt && python Tools/ue_remote.py Tools/test_reload.py
    (esperar ~3 s)
    echo recargar > Tools/_modo.txt && python Tools/ue_remote.py Tools/test_reload.py
    (esperar ~4 s, mas que ReloadTime)
    echo medir    > Tools/_modo.txt && python Tools/ue_remote.py Tools/test_reload.py

No se comprueba que call_method "devuelva OK": eso no significa nada en
Blueprint (dice OK aunque no encuentre el evento). Lo que se comprueba es el
EFECTO: cuantas balas hay en el cargador y en la reserva antes y despues.
"""
import os
import unreal

UES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
# ue_remote NO pasa argumentos al script remoto (sys.argv es el del editor),
# asi que el modo llega por un fichero que escribe el shell.
_dir = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(_dir, "_modo.txt"), "r", encoding="utf-8") as fh:
        modo = fh.read().strip()
except Exception:
    modo = "medir"
print("### modo: %s" % modo)

w = UES.get_game_world()
if w is None:
    print("FALLO: no hay mundo de juego (PIE no esta corriendo)")
    raise SystemExit

todos = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
armas = [a for a in todos if a.get_class().get_name() == "BP_ConventionalGun_C"]
munis = [a for a in todos if a.get_class().get_name() == "BP_MunitionConventionalGun_C"]

if not armas:
    print("FALLO: no hay ningun BP_ConventionalGun en el nivel")
    raise SystemExit

arma = armas[0]


def leer(a):
    return (a.get_editor_property("CurrentMunition"),
            a.get_editor_property("MunitionReserve"),
            a.get_editor_property("MaxMunition"),
            a.get_editor_property("IsReloading"),
            a.get_editor_property("ReloadTime"))


def pinta(etiqueta, a):
    c, r, m, rec, t = leer(a)
    print("%-22s cargador=%-3d reserva=%-3d max=%-3d recargando=%-5s ReloadTime=%.1f"
          % (etiqueta, c, r, m, rec, t))


if modo == "preparar":
    print("armas en el nivel: %d   cajas de municion: %d" % (len(armas), len(munis)))
    pinta("estado de fabrica", arma)
    # Escenario: cargador medio vacio y reserva con balas.
    # OJO: las escrituras a instancias de PIE se revierten solas, asi que hay
    # que RELEER y confirmar en vez de escribir y confiar.
    arma.set_editor_property("CurrentMunition", 3)
    arma.set_editor_property("MunitionReserve", 12)
    arma.set_editor_property("IsReloading", False)
    c, r, _, _, _ = leer(arma)
    if (c, r) != (3, 12):
        print("AVISO: la escritura no cuajo (cargador=%d reserva=%d); se revirtio" % (c, r))
    pinta("preparado", arma)

elif modo == "recargar":
    pinta("antes de recargar", arma)
    arma.call_method("ReloadMunition", (0,))
    print("ReloadMunition lanzado (no se juzga por su valor de retorno,")
    print("se juzga por el efecto que se mide en la tanda siguiente)")

elif modo == "medir":
    pinta("despues de recargar", arma)
    c, r, m, rec, _ = leer(arma)
    ok = True
    def comp(nombre, real, esperado):
        global ok
        bien = real == esperado
        ok = ok and bien
        print("   %-24s %-6r esperado %-6r  %s"
              % (nombre, real, esperado, "OK" if bien else "FALLO"))
    print("")
    print("COMPROBACIONES")
    comp("cargador", c, 10)          # 3 + min(10-3, 12) = 3 + 7 = 10
    comp("reserva", r, 5)            # 12 - 7 = 5
    comp("candado liberado", rec, False)
    print("")
    print("FALLOS: %d" % (0 if ok else 1))
