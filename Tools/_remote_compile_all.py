# -*- coding: utf-8 -*-
"""Compila TODOS los Blueprints del proyecto y dice cuales se quejan.

Los errores del compilador salen por el log del editor; ue_remote los reenvia
marcados como Error/Warning. Aqui ademas se comprueba lo unico que si se puede
leer desde Python: que la clase generada exista y no este marcada como
'deprecated/abstract por error de compilacion'.
"""
import unreal

ar = unreal.AssetRegistryHelpers.get_asset_registry()
assets = ar.get_assets_by_path(unreal.Name("/Game"), recursive=True)

rutas = sorted({
    str(a.package_name) for a in assets
    if str(getattr(a, "asset_class_path", "").asset_name
           if hasattr(a, "asset_class_path") else "") in ("Blueprint", "WidgetBlueprint")
})

print("BLUEPRINTS: %d" % len(rutas))
malos = []
for ruta in rutas:
    nombre = ruta.rsplit("/", 1)[-1]
    try:
        bp = unreal.EditorAssetLibrary.load_asset(ruta)
    except Exception as e:
        malos.append((nombre, "NO CARGA: %s" % e)); continue
    if bp is None:
        malos.append((nombre, "NO CARGA")); continue
    try:
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    except Exception as e:
        malos.append((nombre, "EXCEPCION: %s" % e)); continue
    gc = bp.generated_class()
    if gc is None:
        malos.append((nombre, "sin clase generada (no compila)"))

print("")
if malos:
    print("CON PROBLEMA: %d" % len(malos))
    for n, m in malos:
        print("   %-34s %s" % (n, m))
else:
    print("Todos generan clase.")
print("PROBLEMAS: %d" % len(malos))
