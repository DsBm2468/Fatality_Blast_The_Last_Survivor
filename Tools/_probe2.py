import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
pj=unreal.GameplayStatics.get_player_character(w,0)
def comp(a,n):
    for c in a.get_components_by_class(unreal.ActorComponent):
        if c.get_class().get_name()==n: return c
cur=comp(pj,"BPC_Curation_C")
for nombre in ("NoExisteEstoDeVerdad","TryStartHeal","CancelHeal","StartDecay"):
    try:
        cur.call_method(nombre)
        print("  %-22s -> sin excepcion" % nombre)
    except Exception as e:
        print("  %-22s -> %s" % (nombre, str(e)[:70]))
