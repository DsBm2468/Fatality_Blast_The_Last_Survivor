# -*- coding: utf-8 -*-
"""Exporta a T3D todos los assets listados en Saved/_export_lote.txt.

Una ruta /Game/... por linea. Salida: Saved/T3D_<Nombre>.copy (UTF-16).
"""
import unreal
import os

saved = unreal.Paths.project_saved_dir()
with open(os.path.join(saved, "_export_lote.txt"), "r", encoding="utf-8") as fh:
    rutas = [l.strip() for l in fh if l.strip()]

for ruta in rutas:
    nombre = ruta.rsplit("/", 1)[-1]
    asset = unreal.EditorAssetLibrary.load_asset(ruta)
    if asset is None:
        print("NO EXISTE:", ruta)
        continue
    t = unreal.AssetExportTask()
    t.object = asset
    t.filename = os.path.join(saved, "T3D_%s.copy" % nombre)
    t.automated = True
    t.prompt = False
    t.replace_identical = True
    t.exporter = unreal.ObjectExporterT3D()
    ok = unreal.Exporter.run_asset_export_task(t)
    print("%-6s %s" % ("OK" if ok else "FALLO", nombre))
