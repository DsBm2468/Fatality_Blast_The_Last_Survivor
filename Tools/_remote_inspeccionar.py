# -*- coding: utf-8 -*-
"""Lista componentes y variables (con tipo) de los Blueprints de
Saved/_export_lote.txt. Sirve para no inventarse nombres al generar pegados."""
import unreal
import os

saved = unreal.Paths.project_saved_dir()
with open(os.path.join(saved, "_export_lote.txt"), "r", encoding="utf-8") as fh:
    rutas = [l.strip() for l in fh if l.strip()]

for ruta in rutas:
    bp = unreal.EditorAssetLibrary.load_asset(ruta)
    if bp is None:
        print("NO EXISTE:", ruta)
        continue
    gc = bp.generated_class()
    cdo = unreal.get_default_object(gc)
    print("### %s" % ruta.rsplit("/", 1)[-1])
    print("  -- componentes --")
    try:
        for c in cdo.get_components_by_class(unreal.ActorComponent):
            print("     %-28s %s" % (c.get_name(), c.get_class().get_name()))
    except Exception as e:
        print("     (no es un actor: %s)" % e)
    print("  -- variables --")
    for p in unreal.get_type_from_class(gc)().__dir__() if False else []:
        pass
    # Las variables del Blueprint se leen del CDO por reflexion
    vistos = set()
    for nombre in dir(cdo):
        if nombre.startswith("_"):
            continue
        vistos.add(nombre)
    props = []
    it = unreal.PropertyIterator(gc) if hasattr(unreal, "PropertyIterator") else None
    if it is None:
        # sin iterador: se prueban los nombres conocidos del Blueprint
        for v in sorted(vistos):
            try:
                val = cdo.get_editor_property(v)
            except Exception:
                continue
            props.append((v, type(val).__name__, val))
    for v, t, val in props:
        s = str(val)
        print("     %-30s %-22s = %s" % (v, t, s[:60]))
