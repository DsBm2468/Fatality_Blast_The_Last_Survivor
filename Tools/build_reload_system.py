# -*- coding: utf-8 -*-
"""
Infraestructura del SISTEMA DE RECARGA (cargador + reserva).

Crea las variables y fija los valores del GDD. La LOGICA no se puede crear
desde aqui (UEdGraphPin no es un UObject): va en el texto de pegado que
genera Tools/gen_reload_paste.py.

Modelo elegido (decidido con Walter el 2026-09-03):
  CurrentMunition  balas en el cargador          (ya existia)
  MaxMunition      tamano del cargador           (ya existia)
  MunitionReserve  balas sueltas fuera del arma  NUEVA
  IsReloading      candado mientras se recarga   NUEVA
  ReloadTime       segundos de recarga           NUEVA

GDD: arma convencional = 10 balas por cargador, 10 de dano, ConventionalBullet.
El jugador empieza con 1 cargador y 0 de reserva; la reserva sube recogiendo
BP_MunitionConventionalGun.

Idempotente. Acaba en "PROBLEMAS: N".

Uso:
    python Tools/ue_remote.py Tools/build_reload_system.py
"""
import unreal

BEL = unreal.BlueprintEditorLibrary
EAL = unreal.EditorAssetLibrary

problemas = []


def log(ok, msg):
    print(("  OK    " if ok else "  FALLO ") + msg)
    if not ok:
        problemas.append(msg)


# TRAMPA ya medida el 2026-08-31: BEL.get_basic_type_by_name() devuelve
# PinCategory="int" para TODO menos "bool" (tambien para "float" y "real").
# Hay que construir el EdGraphPinType por texto.
def pin_type(cat, sub="", subobj="None"):
    t = unreal.EdGraphPinType()
    ok = t.import_text(
        '(PinCategory="%s",PinSubCategory="%s",PinSubCategoryObject=%s,'
        'PinSubCategoryMemberReference=(),PinValueType=(),ContainerType=None,'
        'bIsReference=False,bIsConst=False,bIsWeakPointer=False,'
        'bIsUObjectWrapper=False,bSerializeAsSinglePrecisionFloat=False)'
        % (cat, sub, subobj))
    if not ok:
        raise RuntimeError("no se pudo construir el tipo %s/%s" % (cat, sub))
    return t


T_INT = ("int",)
T_BOOL = ("bool",)
T_DOUBLE = ("real", "double", "None")


def cdo(bp):
    return unreal.get_default_object(BEL.generated_class(bp))


def tiene(bp, nombre):
    try:
        cdo(bp).get_editor_property(nombre)
        return True
    except Exception:
        return False


def add_var(bp, nombre, tipo, valor=None, editable=False):
    """add_member_variable NO es idempotente: llamarla dos veces crea
    'Nombre' y 'Nombre1'. De ahi el guardia."""
    nuevo = False
    if not tiene(bp, nombre):
        BEL.add_member_variable(bp, nombre, pin_type(*tipo))
        BEL.compile_blueprint(bp)
        nuevo = True
    if not tiene(bp, nombre):
        log(False, "%s.%s no se creo" % (bp.get_name(), nombre))
        return
    if editable:
        try:
            BEL.set_blueprint_variable_instance_editable(bp, nombre, True)
        except Exception as e:
            log(False, "%s.%s no se pudo hacer editable (%s)" % (bp.get_name(), nombre, e))
    if valor is not None:
        try:
            cdo(bp).set_editor_property(nombre, valor)
        except Exception as e:
            log(False, "%s.%s no acepto el valor %r (%s)" % (bp.get_name(), nombre, valor, e))
            return
    leido = cdo(bp).get_editor_property(nombre)
    log(True, "%s.%s = %r%s" % (bp.get_name(), nombre, leido, "  (nueva)" if nuevo else ""))


# ============================================================== las dos armas
# (MaxMunition/CurrentMunition ya existen; se fijan a los valores del GDD)
ARMAS = [
    # ruta, cargador, reserva inicial, tiempo de recarga
    ("/Game/ThirdPerson/Blueprints/Interactables/BP_ConventionalGun", 10, 0, 2.0),
    ("/Game/ThirdPerson/Blueprints/Interactables/BP_SubmachineGun", 30, 0, 2.5),
]

for ruta, cargador, reserva, t_recarga in ARMAS:
    bp = EAL.load_asset(ruta)
    print("\n=== %s ===" % ruta.rsplit("/", 1)[-1])
    if bp is None:
        log(False, "no existe " + ruta)
        continue
    add_var(bp, "MunitionReserve", T_INT, reserva, editable=True)
    add_var(bp, "IsReloading", T_BOOL, False, editable=True)
    add_var(bp, "ReloadAmount", T_INT, 0)
    add_var(bp, "ReloadTime", T_DOUBLE, t_recarga, editable=True)
    # valores del GDD en lo que ya existia
    for nombre, val in (("MaxMunition", cargador), ("CurrentMunition", cargador)):
        if tiene(bp, nombre):
            try:
                BEL.set_blueprint_variable_instance_editable(bp, nombre, True)
            except Exception as e:
                log(False, "%s.%s no se pudo hacer editable (%s)" % (bp.get_name(), nombre, e))
            try:
                cdo(bp).set_editor_property(nombre, val)
                log(True, "%s.%s = %r" % (bp.get_name(), nombre, cdo(bp).get_editor_property(nombre)))
            except Exception as e:
                log(False, "%s.%s no acepto %r (%s)" % (bp.get_name(), nombre, val, e))
        else:
            log(False, "%s.%s NO EXISTE" % (bp.get_name(), nombre))
    BEL.compile_blueprint(bp)
    EAL.save_asset(ruta)

# ===================================================== el pickup de municion
# BP_MunitionConventionalGun esta vacio: necesita saber cuantas balas da.
ruta = "/Game/ThirdPerson/Blueprints/Interactables/BP_MunitionConventionalGun"
bp = EAL.load_asset(ruta)
print("\n=== BP_MunitionConventionalGun ===")
if bp is None:
    log(False, "no existe " + ruta)
else:
    add_var(bp, "MunitionAmount", T_INT, 10, editable=True)
    BEL.compile_blueprint(bp)
    EAL.save_asset(ruta)

# ============================================== IA_Reload -> tecla R
# Las Mappings del IMC no se pueden LEER desde Python (propiedad protegida:
# devuelve 0 aunque el contexto tenga mapeos). Si se pueden escribir, y
# unmap_all_keys_from_action + map_key deja la operacion idempotente.
print("")
print("=== IMC_Default ===")
imc = EAL.load_asset("/Game/Input/IMC_Default")
ia = EAL.load_asset("/Game/Input/Actions/IA_Reload")
if imc is None or ia is None:
    log(False, "falta IMC_Default o IA_Reload")
else:
    try:
        # TRAMPA: unreal.Key no se puede construir con argumentos ni tiene
        # key_name como propiedad, y no existe unreal.InputCoreLibrary. La
        # unica via es import_text(), igual que con EdGraphPinType.
        tecla = unreal.Key()
        if not tecla.import_text("R"):
            raise RuntimeError("import_text('R') fallo")
        imc.unmap_all_keys_from_action(ia)
        imc.map_key(ia, tecla)
        EAL.save_asset("/Game/Input/IMC_Default")
        log(True, "IA_Reload mapeada a la tecla %s" % tecla.export_text())
    except Exception as e:
        log(False, "no se pudo mapear IA_Reload a R (%s)" % e)

print("")
print("PROBLEMAS: %d" % len(problemas))
for p in problemas:
    print("   - " + p)
