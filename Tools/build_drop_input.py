# -*- coding: utf-8 -*-
"""
Crea la accion de entrada IA_Drop (soltar objeto) y la mapea a la tecla F.

No habia ninguna: el sistema de soltar no existia ni a nivel de entrada. F
estaba libre (E interactuar, G usar equipo, Q botiquin, C agacharse, R
recargar, rueda del raton cambiar hueco).

Idempotente: si IA_Drop ya existe no la duplica, y si el mapeo ya esta no lo
repite. Acaba en "PROBLEMAS: N".

Uso:  python Tools/ue_remote.py Tools/build_drop_input.py
"""
import unreal

EAL = unreal.EditorAssetLibrary
RUTA_IA = "/Game/Input/IA_Drop"
MODELO = "/Game/Input/IA_Heal"       # misma forma: booleana, pulsacion simple
IMC = "/Game/Input/IMC_Default"
TECLA = "F"

problemas = []

# ------------------------------------------------------------ la accion
if EAL.does_asset_exist(RUTA_IA):
    print("IA_Drop ya existe")
else:
    if not EAL.duplicate_asset(MODELO, RUTA_IA):
        problemas.append("no se pudo crear IA_Drop a partir de %s" % MODELO)
    else:
        print("IA_Drop creada a partir de IA_Heal")

ia = EAL.load_asset(RUTA_IA)
if ia is None:
    problemas.append("IA_Drop no carga")

# ------------------------------------------------------------ el mapeo
imc = EAL.load_asset(IMC)
if imc is None:
    problemas.append("no carga %s" % IMC)
elif ia is not None:
    datos = imc.get_editor_property("default_key_mappings")
    mapeos = list(datos.get_editor_property("mappings"))
    ya = False
    for m in mapeos:
        a = m.get_editor_property("action")
        if a is not None and a.get_name() == "IA_Drop":
            ya = True
    if ya:
        print("IA_Drop ya estaba mapeada")
    else:
        nuevo = unreal.EnhancedActionKeyMapping()
        nuevo.set_editor_property("action", ia)
        k = unreal.Key()
        k.set_editor_property("key_name", unreal.Name(TECLA))
        nuevo.set_editor_property("key", k)
        mapeos.append(nuevo)
        datos.set_editor_property("mappings", mapeos)
        imc.set_editor_property("default_key_mappings", datos)
        EAL.save_loaded_asset(imc, only_if_is_dirty=False)
        print("IA_Drop mapeada a la tecla %s" % TECLA)

# ------------------------------------------------------------ comprobacion
imc = EAL.load_asset(IMC)
datos = imc.get_editor_property("default_key_mappings")
encontrada = False
for m in datos.get_editor_property("mappings"):
    a = m.get_editor_property("action")
    if a is not None and a.get_name() == "IA_Drop":
        encontrada = True
        print("  verificado: IA_Drop <- %s"
              % m.get_editor_property("key").get_editor_property("key_name"))
if not encontrada:
    problemas.append("IA_Drop no aparece en el IMC tras guardar")

print("PROBLEMAS: %d" % len(problemas))
for p in problemas:
    print("   ", p)
