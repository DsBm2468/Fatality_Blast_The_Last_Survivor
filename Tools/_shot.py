import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
unreal.SystemLibrary.execute_console_command(w, "shot showui")
print("PEDIDA")
