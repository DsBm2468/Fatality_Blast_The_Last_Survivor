# -*- coding: utf-8 -*-
"""
Auditoria completa del proyecto: compila todo, exporta todo a T3D y deja los
ficheros listos para el analisis de cables.

Fase 1 (esta) corre dentro del editor:
  - compila cada Blueprint y captura si el compilador se queja
  - exporta cada uno a Saved/AuditT3D_<Nombre>.copy
  - vuelca el inventario del nivel

Fase 2 la hace Tools/audit_report.py fuera del editor, leyendo esos ficheros.

Uso:
    python Tools/ue_remote.py Tools/audit_full.py
"""
import unreal
import os

BEL = unreal.BlueprintEditorLibrary
EAL = unreal.EditorAssetLibrary
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LES = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

RAIZ = "/Game/ThirdPerson"
SALIDA = unreal.Paths.project_saved_dir()

# Todos los Blueprints del proyecto, buscados en el registro de assets.
ar = unreal.AssetRegistryHelpers.get_asset_registry()
assets = ar.get_assets_by_path(unreal.Name(RAIZ), recursive=True)

rutas = []
for a in assets:
    cls_ = str(a.asset_class_path.asset_name) if hasattr(a, "asset_class_path") else ""
    ruta = str(a.package_name)
    if cls_ in ("Blueprint", "WidgetBlueprint"):
        rutas.append(ruta)
rutas = sorted(set(rutas))

print("BLUEPRINTS ENCONTRADOS: %d" % len(rutas))
print("")

for ruta in rutas:
    nombre = ruta.rsplit("/", 1)[-1]
    bp = EAL.load_asset(ruta)
    if bp is None:
        print("  NO CARGA  %s" % ruta)
        continue
    # compilar (los errores salen en el log, que se lee despues)
    try:
        BEL.compile_blueprint(bp)
    except Exception as e:
        print("  EXCEPCION al compilar %s: %s" % (nombre, e))
    # exportar
    t = unreal.AssetExportTask()
    t.object = bp
    t.filename = os.path.join(SALIDA, "AuditT3D_%s.copy" % nombre)
    t.automated = True
    t.prompt = False
    t.replace_identical = True
    t.exporter = unreal.ObjectExporterT3D()
    ok = unreal.Exporter.run_asset_export_task(t)
    print("  %-6s %s" % ("OK" if ok else "FALLO", nombre))

# ---------------------------------------------------------------- el nivel
print("")
print("=" * 60)
LES.load_level("/Game/ThirdPerson/Lvl_01_MilitaryBase")
import collections
acts = EAS.get_all_level_actors()
print("NIVEL Lvl_01_MilitaryBase: %d actores" % len(acts))
for c, n in collections.Counter(a.get_class().get_name() for a in acts).most_common():
    print("   %-34s %d" % (c, n))

# items y soldados, por si falta algo del GDD
print("")
print("ITEMS COLOCADOS")
for c in ("BP_FirstAidKit_C", "BP_Shield_C", "BP_ConventionalGun_C",
          "BP_SubmachineGun_C", "BP_MunitionConventionalGun_C",
          "BP_Grenade_C", "BP_Bomb_C", "BP_Bandage_C"):
    n = sum(1 for a in acts if a.get_class().get_name() == c)
    print("   %-32s %d" % (c, n))

# soldados sin ruta de patrulla
sin_ruta = []
for a in acts:
    if a.get_class().get_name() != "BP_Grunt_C":
        continue
    try:
        pp = a.get_editor_property("PatrolPoints")
        if not pp:
            sin_ruta.append(a.get_actor_label())
    except Exception:
        pass
print("")
print("SOLDADOS SIN PatrolPoints: %d" % len(sin_ruta))
for s in sorted(sin_ruta):
    print("   " + s)

print("")
print("EXPORTACION TERMINADA")
