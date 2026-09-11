# -*- coding: utf-8 -*-
"""Exporta UN Blueprint a T3D. Lee el destino de Saved/_paste_target.txt."""
import unreal, os

saved = unreal.Paths.project_saved_dir()
with open(os.path.join(saved, "_paste_target.txt"), "r", encoding="utf-8") as fh:
    asset_path, salida = [l.strip() for l in fh.read().splitlines()[:2]]

asset = unreal.EditorAssetLibrary.load_asset(asset_path)
if asset is None:
    print("NO EXISTE:", asset_path)
else:
    task = unreal.AssetExportTask()
    task.object = asset
    task.filename = salida
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    task.exporter = unreal.ObjectExporterT3D()
    ok = unreal.Exporter.run_asset_export_task(task)
    print(("OK  " if ok else "FALLO "), asset_path, "->", salida)
