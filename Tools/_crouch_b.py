import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
pc=unreal.GameplayStatics.get_player_character(w,0)
print("bIsCrouched=%s  media_altura=%.1f  MaxWalkSpeed=%.0f" % (
    pc.get_editor_property("is_crouched"),
    pc.capsule_component.get_editor_property("capsule_half_height"),
    pc.character_movement.max_walk_speed))
