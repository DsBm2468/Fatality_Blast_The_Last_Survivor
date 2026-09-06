# -*- coding: utf-8 -*-
"""
Genera el texto de pegado (T3D) del SISTEMA DE RECARGA.

Produce tres ficheros en Tools/bp_paste/:

  20_Gun_ReloadMunition.txt   -> EventGraph de BP_ConventionalGun
                                 Y TAMBIEN de BP_SubmachineGun: las dos armas
                                 tienen exactamente los mismos nombres de
                                 variable, asi que el mismo pegado sirve.
  21_Ammo_Pickup.txt          -> EventGraph de BP_MunitionConventionalGun
  22_Char_Reload_Input.txt    -> EventGraph de BP_ThirdPersonCharacter

Las variables las crea antes Tools/build_reload_system.py (por script si se
puede; la logica no, porque UEdGraphPin no es un UObject).

Uso:
    python Tools/gen_reload_paste.py
    powershell -File Tools/clip.ps1 20      (carga el pegado en el portapapeles)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bpgen import (Graph, cls, CAT_EXEC, CAT_BOOL, CAT_INT, CAT_REAL,
                   CAT_STRING, CAT_OBJECT, CAT_CLASS)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bp_paste")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

# --- clases del motor -------------------------------------------------------
C_KSL = "/Script/Engine.KismetSystemLibrary"
C_KML = "/Script/Engine.KismetMathLibrary"
C_GSL = "/Script/Engine.GameplayStatics"
# OJO: Conv_IntToString y Concat_StrStr NO estan en KismetMathLibrary ni en
# KismetSystemLibrary, aunque lo parezca. Viven en KismetStringLibrary.
C_KSTR = "/Script/Engine.KismetStringLibrary"
C_ACTOR = "/Script/Engine.Actor"
C_OBJECT = "/Script/CoreUObject.Object"

# --- clases del proyecto ----------------------------------------------------
C_BPI_WEAPON = "/Game/ThirdPerson/Blueprints/Interfaces/BPI_WeaponSystem.BPI_WeaponSystem_C"
C_BPI_INTERACT = "/Game/ThirdPerson/Blueprints/Interfaces/BPI_Interactable.BPI_Interactable_C"
C_CHAR = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.BP_ThirdPersonCharacter_C"
C_CONVGUN = "/Game/ThirdPerson/Blueprints/Interactables/BP_ConventionalGun.BP_ConventionalGun_C"
C_INVENT = "/Game/ThirdPerson/Components/BPC_Inventary.BPC_Inventary_C"

IA_RELOAD = "/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Reload.IA_Reload'"

generados = []


def emit(g, fichero):
    g.save(os.path.join(OUT, fichero))
    generados.append((fichero, len(g.nodes)))
    print("  %-32s %3d nodos" % (fichero, len(g.nodes)))


# --------------------------------------------------------------- ayudantes

def print_dbg(g, texto, x, y, color="(R=1.0,G=0.8,B=0.0,A=1.0)"):
    """En este proyecto el PrintString NO es andamiaje: las escrituras a
    instancias de PIE se revierten y el log no, asi que es el instrumento de
    medida (ver LAB_DE_PRUEBAS.md)."""
    p = g.call("PrintString", C_KSL, x, y)
    p.pin("InString", CAT_STRING, default=texto)
    p.pin("bPrintToScreen", CAT_BOOL, default="true")
    p.pin("bPrintToLog", CAT_BOOL, default="true")
    p.pin("Duration", CAT_REAL, sub="double", default="2.000000")
    return p


def delay(g, x, y):
    """TRAMPA ya medida el 2026-08-27: NO existe la clase K2Node_Delay. El
    nodo Delay es un K2Node_CallFunction a la funcion latente
    KismetSystemLibrary::Delay. Con una clase inexistente el nodo simplemente
    no se crea, sin dar ningun error, y se lleva por delante las conexiones
    que pasaban por el."""
    d = g.call("Delay", C_KSL, x, y)
    d.pin("Duration", CAT_REAL, sub="double", default="2.000000")
    return d


def op_int(g, funcion, x, y, a=None, b=None):
    """Operador puro de dos enteros: A, B -> ReturnValue."""
    n = g.call(funcion, C_KML, x, y, pure=True)
    n.pin("A", CAT_INT, default=a)
    n.pin("B", CAT_INT, default=b)
    n.pin("ReturnValue", CAT_INT if funcion.startswith(("Add", "Subtract", "Min", "Max"))
          else CAT_BOOL, out=True)
    return n


def int_a_texto(g, x, y):
    n = g.call("Conv_IntToString", C_KSTR, x, y, pure=True)
    n.pin("InInt", CAT_INT)
    n.pin("ReturnValue", CAT_STRING, out=True)
    return n


def concat(g, x, y, a=None, b=None):
    n = g.call("Concat_StrStr", C_KSTR, x, y, pure=True)
    n.pin("A", CAT_STRING, default=a)
    n.pin("B", CAT_STRING, default=b)
    n.pin("ReturnValue", CAT_STRING, out=True)
    return n


# ===========================================================================
# 20  -  ARMA: evento ReloadMunition
# ===========================================================================
def gen_arma():
    g = Graph("Gun_ReloadMunition", titulo="""
RECARGA DEL ARMA  -  pegar en el EventGraph de BP_ConventionalGun
                     y tambien en el de BP_SubmachineGun.

Modelo cargador + reserva:
  si ya esta recargando        -> nada
  si el cargador esta lleno    -> nada
  si no queda reserva          -> nada
  si no: bloquea, espera ReloadTime, pasa balas de la reserva al cargador.

OJO con el orden de los tres SET del final. ReloadAmount se GUARDA en una
variable antes de tocar nada porque Min() es un nodo PURO: si se tirase de el
despues de haber cambiado CurrentMunition, devolveria un numero distinto y la
reserva se descontaria mal.
""")

    ev = g.event("ReloadMunition", C_BPI_WEAPON, 0, 0)
    ev.pin("QuantityMunition", CAT_INT, out=True)

    # --- guarda 1: ya esta recargando
    b_rec = g.branch(260, 0)
    ev.exec_out.to(b_rec.exec_in)
    v_rec = g.var_get("IsReloading", CAT_BOOL, 60, 150)
    v_rec.get("IsReloading").to(b_rec.get("Condition"))
    p_rec = print_dbg(g, "RECARGA: ya estas recargando", 480, -170)
    b_rec.get("then").to(p_rec.exec_in)

    # --- guarda 2: el cargador ya esta lleno  (CurrentMunition < MaxMunition)
    b_lleno = g.branch(480, 40)
    b_rec.get("else").to(b_lleno.exec_in)
    v_cur1 = g.var_get("CurrentMunition", CAT_INT, 60, 300)
    v_max1 = g.var_get("MaxMunition", CAT_INT, 60, 380)
    menor = op_int(g, "Less_IntInt", 270, 320)
    v_cur1.get("CurrentMunition").to(menor.get("A"))
    v_max1.get("MaxMunition").to(menor.get("B"))
    menor.get("ReturnValue").to(b_lleno.get("Condition"))
    p_lleno = print_dbg(g, "RECARGA: el cargador ya esta lleno", 700, -170)
    b_lleno.get("else").to(p_lleno.exec_in)

    # --- guarda 3: queda reserva  (MunitionReserve > 0)
    b_res = g.branch(700, 40)
    b_lleno.get("then").to(b_res.exec_in)
    v_res1 = g.var_get("MunitionReserve", CAT_INT, 60, 500)
    mayor = op_int(g, "Greater_IntInt", 270, 500, b="0")
    v_res1.get("MunitionReserve").to(mayor.get("A"))
    mayor.get("ReturnValue").to(b_res.get("Condition"))
    p_sin = print_dbg(g, "RECARGA: sin municion en reserva", 920, -170,
                      color="(R=1.0,G=0.1,B=0.0,A=1.0)")
    b_res.get("else").to(p_sin.exec_in)

    # --- bloquear y esperar
    s_lock = g.var_set("IsReloading", CAT_BOOL, 920, 40)
    s_lock.get("IsReloading").default = "true"
    b_res.get("then").to(s_lock.exec_in)

    p_go = print_dbg(g, "RECARGANDO...", 1140, 40)
    s_lock.exec_out.to(p_go.exec_in)

    d = delay(g, 1360, 40)
    p_go.exec_out.to(d.exec_in)
    v_tiempo = g.var_get("ReloadTime", CAT_REAL, 1160, 220, sub="double")
    v_tiempo.get("ReloadTime").to(d.get("Duration"))

    # --- cuantas balas entran:  ReloadAmount = Min(MaxMunition - CurrentMunition,
    #                                               MunitionReserve)
    v_max2 = g.var_get("MaxMunition", CAT_INT, 1360, 340)
    v_cur2 = g.var_get("CurrentMunition", CAT_INT, 1360, 420)
    hueco = op_int(g, "Subtract_IntInt", 1560, 360)
    v_max2.get("MaxMunition").to(hueco.get("A"))
    v_cur2.get("CurrentMunition").to(hueco.get("B"))

    v_res2 = g.var_get("MunitionReserve", CAT_INT, 1560, 480)
    minimo = op_int(g, "Min", 1760, 380)
    hueco.get("ReturnValue").to(minimo.get("A"))
    v_res2.get("MunitionReserve").to(minimo.get("B"))

    s_amount = g.var_set("ReloadAmount", CAT_INT, 1600, 40)
    d.exec_out.to(s_amount.exec_in)
    minimo.get("ReturnValue").to(s_amount.get("ReloadAmount"))

    # --- cargador += ReloadAmount
    v_cur3 = g.var_get("CurrentMunition", CAT_INT, 1620, 600)
    v_amt1 = g.var_get("ReloadAmount", CAT_INT, 1620, 680)
    suma = op_int(g, "Add_IntInt", 1820, 620)
    v_cur3.get("CurrentMunition").to(suma.get("A"))
    v_amt1.get("ReloadAmount").to(suma.get("B"))

    s_cur = g.var_set("CurrentMunition", CAT_INT, 1860, 40)
    s_amount.exec_out.to(s_cur.exec_in)
    suma.get("ReturnValue").to(s_cur.get("CurrentMunition"))

    # --- reserva -= ReloadAmount
    v_res3 = g.var_get("MunitionReserve", CAT_INT, 1880, 780)
    v_amt2 = g.var_get("ReloadAmount", CAT_INT, 1880, 860)
    resta = op_int(g, "Subtract_IntInt", 2080, 800)
    v_res3.get("MunitionReserve").to(resta.get("A"))
    v_amt2.get("ReloadAmount").to(resta.get("B"))

    s_res = g.var_set("MunitionReserve", CAT_INT, 2120, 40)
    s_cur.exec_out.to(s_res.exec_in)
    resta.get("ReturnValue").to(s_res.get("MunitionReserve"))

    # --- soltar el candado
    s_unlock = g.var_set("IsReloading", CAT_BOOL, 2380, 40)
    s_unlock.get("IsReloading").default = "false"
    s_res.exec_out.to(s_unlock.exec_in)

    # --- traza final:  "RECARGA OK - CARGADOR: n / RESERVA: m"
    v_cur4 = g.var_get("CurrentMunition", CAT_INT, 2380, 300)
    t_cur = int_a_texto(g, 2560, 300)
    v_cur4.get("CurrentMunition").to(t_cur.get("InInt"))
    c1 = concat(g, 2740, 280, a="RECARGA OK - CARGADOR: ")
    t_cur.get("ReturnValue").to(c1.get("B"))

    v_res4 = g.var_get("MunitionReserve", CAT_INT, 2380, 460)
    t_res = int_a_texto(g, 2560, 460)
    v_res4.get("MunitionReserve").to(t_res.get("InInt"))
    c2 = concat(g, 2740, 440, a=" / RESERVA: ")
    t_res.get("ReturnValue").to(c2.get("B"))

    c3 = concat(g, 2920, 360)
    c1.get("ReturnValue").to(c3.get("A"))
    c2.get("ReturnValue").to(c3.get("B"))

    p_fin = print_dbg(g, "", 2640, 40, color="(R=0.0,G=1.0,B=0.3,A=1.0)")
    s_unlock.exec_out.to(p_fin.exec_in)
    c3.get("ReturnValue").to(p_fin.get("InString"))

    g.comment("RECARGA  (cargador + reserva)", -60, -260, 3100, 1200)
    emit(g, "20_Gun_ReloadMunition.txt")


# ===========================================================================
# 21  -  PICKUP DE MUNICION: evento Interact
# ===========================================================================
def gen_pickup():
    g = Graph("Ammo_Pickup", titulo="""
RECOGER MUNICION  -  pegar en el EventGraph de BP_MunitionConventionalGun.

Suma MunitionAmount a la reserva del arma que el jugador lleva equipada y se
destruye. Si no lleva arma convencional, avisa y NO se consume.

La referencia al arma equipada vive en BPC_Inventary.Object_Is_Weapon, que es
la ruta VIVA (ver la nota de las dos familias paralelas: BP_Item y compania no
se ejecutan).
""")

    ev = g.event("Interact", C_BPI_INTERACT, 0, 0)

    jugador = g.call("GetPlayerCharacter", C_GSL, 0, 220, pure=True)
    jugador.pin("PlayerIndex", CAT_INT, default="0")
    jugador.pin("ReturnValue", CAT_OBJECT, out=True, sub_object=cls("/Script/Engine.Character"))

    cast_char = g.cast(C_CHAR, 260, 0)
    ev.exec_out.to(cast_char.exec_in)
    jugador.get("ReturnValue").to(cast_char.get("Object"))

    # BPC_Inventary del jugador
    inv = g.call("GetComponentByClass", C_ACTOR, 260, 300, pure=True)
    inv.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR))
    inv.pin("ComponentClass", CAT_CLASS, default=C_INVENT,
            sub_object=cls("/Script/Engine.ActorComponent"))
    inv.pin("ReturnValue", CAT_OBJECT, out=True,
            sub_object=cls("/Script/Engine.ActorComponent"))
    cast_char.get("AsTarget").to(inv.get("self"))

    arma = g.var_get_target("Object_Is_Weapon", CAT_OBJECT, C_INVENT, 520, 300,
                            sub_object=cls(C_ACTOR))
    inv.get("ReturnValue").to(arma.get("self"))

    cast_gun = g.cast(C_CONVGUN, 560, 0)
    cast_char.exec_out.to(cast_gun.exec_in)
    arma.get("Object_Is_Weapon").to(cast_gun.get("Object"))

    # fallo: no lleva arma compatible -> avisa y NO se consume
    p_no = print_dbg(g, "MUNICION: no llevas un arma convencional", 860, -200,
                     color="(R=1.0,G=0.1,B=0.0,A=1.0)")
    cast_gun.get("CastFailed").to(p_no.exec_in)

    # exito: reserva += MunitionAmount
    v_res = g.var_get_target("MunitionReserve", CAT_INT, C_CONVGUN, 860, 320)
    cast_gun.get("AsTarget").to(v_res.get("self"))
    v_cant = g.var_get("MunitionAmount", CAT_INT, 860, 440)
    suma = op_int(g, "Add_IntInt", 1080, 360)
    v_res.get("MunitionReserve").to(suma.get("A"))
    v_cant.get("MunitionAmount").to(suma.get("B"))

    s_res = g.var_set_target("MunitionReserve", CAT_INT, C_CONVGUN, 1120, 0)
    cast_gun.exec_out.to(s_res.exec_in)
    cast_gun.get("AsTarget").to(s_res.get("self"))
    suma.get("ReturnValue").to(s_res.get("MunitionReserve"))

    # traza
    v_res2 = g.var_get_target("MunitionReserve", CAT_INT, C_CONVGUN, 1380, 320)
    cast_gun.get("AsTarget").to(v_res2.get("self"))
    t_res = int_a_texto(g, 1560, 320)
    v_res2.get("MunitionReserve").to(t_res.get("InInt"))
    c = concat(g, 1740, 300, a="MUNICION RECOGIDA - RESERVA: ")
    t_res.get("ReturnValue").to(c.get("B"))
    p_ok = print_dbg(g, "", 1400, 0, color="(R=0.0,G=1.0,B=0.3,A=1.0)")
    s_res.exec_out.to(p_ok.exec_in)
    c.get("ReturnValue").to(p_ok.get("InString"))

    # destruir el pickup
    dest = g.call("K2_DestroyActor", C_ACTOR, 1660, 0)
    p_ok.exec_out.to(dest.exec_in)

    g.comment("RECOGER MUNICION -> reserva del arma equipada", -60, -280, 2000, 800)
    emit(g, "21_Ammo_Pickup.txt")


# ===========================================================================
# 22  -  PERSONAJE: la tecla R llama a ReloadMunition del arma equipada
# ===========================================================================
def gen_personaje():
    g = Graph("Char_Reload_Input", titulo="""
TECLA R  -  pegar en el EventGraph de BP_ThirdPersonCharacter.

IA_Reload ya esta mapeada a R en IMC_Default (lo hace build_reload_system.py).
Si no llevas arma no hace nada; si la llevas, manda ReloadMunition por la
interfaz BPI_WeaponSystem al arma guardada en BPC_Inventary.Object_Is_Weapon.
""")

    ev = g.input_action(IA_RELOAD, 0, 0)

    b = g.branch(320, 0)
    ev.get("Triggered").to(b.exec_in)
    v_have = g.var_get("HaveGun", CAT_BOOL, 100, 200)
    v_have.get("HaveGun").to(b.get("Condition"))

    p_no = print_dbg(g, "RECARGA: no llevas arma", 560, -180,
                     color="(R=1.0,G=0.1,B=0.0,A=1.0)")
    b.get("else").to(p_no.exec_in)

    inv = g.var_get("BPC_Inventary", CAT_OBJECT, 320, 340, sub_object=cls(C_INVENT))
    arma = g.var_get_target("Object_Is_Weapon", CAT_OBJECT, C_INVENT, 540, 340,
                            sub_object=cls(C_ACTOR))
    inv.get("BPC_Inventary").to(arma.get("self"))

    msg = g.message("ReloadMunition", C_BPI_WEAPON, 620, 0)
    msg.pin("self", CAT_OBJECT, sub_object=cls(C_OBJECT))
    msg.pin("QuantityMunition", CAT_INT, default="0")
    b.get("then").to(msg.exec_in)
    arma.get("Object_Is_Weapon").to(msg.get("self"))

    g.comment("TECLA R -> recargar el arma equipada", -60, -260, 1100, 700)
    emit(g, "22_Char_Reload_Input.txt")


if __name__ == "__main__":
    print("Generando pegados del sistema de recarga en %s\n" % OUT)
    gen_arma()
    gen_pickup()
    gen_personaje()
    print("\n%d ficheros, %d nodos en total"
          % (len(generados), sum(n for _, n in generados)))
