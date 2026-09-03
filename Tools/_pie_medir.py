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
        print("JUGADOR pos=(%.0f, %.0f, %.0f) cayendo=%s vel=%.0f" % (l.x, l.y, l.z, cm.is_falling(), cm.max_walk_speed))
    # contar por nombre de clase: get_all_actors_of_class con una BlueprintGeneratedClass
    # cargada desde el editor devuelve 0 en el mundo de PIE (son clases distintas).
    todos = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
    grunts = [a for a in todos if a.get_class().get_name() == "BP_Grunt_C"]
    movs = [g for g in grunts if g.character_movement.velocity.length() > 5.0]
    a0 = [g for g in grunts if g.get_actor_location().y < -220]
    print("SOLDADOS: %d  (Acto 0: %d)  moviendose ahora: %d" % (len(grunts), len(a0), len(movs)))
    for g in a0:
        v = g.character_movement.velocity.length()
        loc = g.get_actor_location()
        ctrl = g.get_editor_property("controller")
        print("   %-26s (%6.0f,%7.0f) vel=%5.1f ctrl=%s" % (
            g.get_name()[:26], loc.x, loc.y, v, "si" if ctrl else "NO"))
    print("COBERTURAS 'Cover': %d" % len(unreal.GameplayStatics.get_all_actors_with_tag(w, unreal.Name("Cover"))))
