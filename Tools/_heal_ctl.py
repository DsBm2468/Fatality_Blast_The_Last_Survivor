import unreal, sys, os
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if w is None:
    print("SIN_MUNDO"); raise SystemExit
modo=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"_heal_modo.txt")).read().strip()
def comp(a,n):
    for c in a.get_components_by_class(unreal.ActorComponent):
        if c.get_class().get_name()==n: return c
def actores(c):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
            if a.get_class().get_name()==c]
pj=unreal.GameplayStatics.get_player_character(w,0)
hs=comp(pj,"BPC_HealthSystem_C"); cur=comp(pj,"BPC_Curation_C"); inv=comp(pj,"BPC_Inventary_C")
gs=actores("BP_Grunt_C")
g=gs[0]
for x in actores("BP_GruntAIController_C"):
    if x.get_editor_property("GruntPawn")==g: ctrl=x
lg=g.get_actor_location(); fw=g.get_actor_forward_vector()
CERCA=unreal.Vector(lg.x+fw.x*500, lg.y+fw.y*500, lg.z)
LEJOS=unreal.Vector(lg.x+fw.x*4000, lg.y+fw.y*4000, lg.z)

if modo=="cerca":
    pj.set_actor_location(CERCA, False, False)
    print("POS=cerca")
elif modo=="lejos":
    pj.set_actor_location(LEJOS, False, False)
    print("POS=lejos")
elif modo=="curar":
    kits=actores("BP_FirstAidKit_C")
    kits[0].call_method("Interact", args=(pj,))
    hs.set_editor_property("Health", 50.0)
    cur.call_method("TryStartHeal")
    print("CURA=pedida")
elif modo=="volver":
    pj.set_actor_location(CERCA, False, False)
    print("POS=cerca_otra_vez")
hs.set_editor_property("IsDead", False)
v=ctrl.get_editor_property("State")
print("ESTADO=%s" % int(getattr(v,"value",v)))
print("VIDA=%.1f" % hs.get_editor_property("Health"))
print("DIST=%.0f" % unreal.MathLibrary.vector_distance(pj.get_actor_location(), g.get_actor_location()))
