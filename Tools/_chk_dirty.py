import unreal
UES=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print("mundo de editor:", UES.get_editor_world().get_name())
print("mundo de juego :", UES.get_game_world().get_name() if UES.get_game_world() else "None (sin PIE)")
sucios=[p for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
sucios+= [p for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
print("paquetes sin guardar: %d" % len(sucios))
for p in sucios: print("   ", p.get_name())
