import unreal
UES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w = UES.get_game_world()
if w is None:
    print("FALLO: no hay mundo de juego")
else:
    pc = unreal.GameplayStatics.get_player_character(w, 0)
    if pc is None:
        print("FALLO: no hay personaje de jugador")
    else:
        l = pc.get_actor_location(); cm = pc.character_movement
        print("JUGADOR pos=(%.0f, %.0f, %.0f) cayendo=%s vel=%.0f" % (l.x,l.y,l.z, cm.is_falling(), cm.max_walk_speed))
    GR = unreal.EditorAssetLibrary.load_blueprint_class("/Game/ThirdPerson/Blueprints/BP_Grunt")
    grunts = unreal.GameplayStatics.get_all_actors_of_class(w, GR)
    movs = sum(1 for g in grunts if g.character_movement.velocity.length() > 5.0)
    a0 = sum(1 for g in grunts if g.get_actor_location().y < -220)
    print("SOLDADOS: %d  (Acto 0: %d)  moviendose ahora: %d" % (len(grunts), a0, movs))
    print("COBERTURAS con tag 'Cover' en runtime: %d" % len(unreal.GameplayStatics.get_all_actors_with_tag(w, unreal.Name("Cover"))))
