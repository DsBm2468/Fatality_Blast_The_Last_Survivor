import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
pc=unreal.GameplayStatics.get_player_character(w,0)
pc.crouch(False)
print("Crouch() pedido. bWantsToCrouch se aplica en el siguiente tick.")
