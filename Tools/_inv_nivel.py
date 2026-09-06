import unreal, collections
les=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
les.load_level("/Game/ThirdPerson/Lvl_01_MilitaryBase")
eas=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
acts=eas.get_all_level_actors()
print("TOTAL ACTORES:", len(acts))
byc=collections.Counter(a.get_class().get_name() for a in acts)
for c,n in byc.most_common(): print("  %-42s %d" % (c,n))
xs=[];ys=[];zs=[]
for a in acts:
    l=a.get_actor_location(); xs.append(l.x); ys.append(l.y); zs.append(l.z)
print("\nBOUNDS  X: %.0f .. %.0f   Y: %.0f .. %.0f   Z: %.0f .. %.0f" % (min(xs),max(xs),min(ys),max(ys),min(zs),max(zs)))
print("\n-- Actores no-StaticMesh (gameplay) --")
for a in acts:
    cn=a.get_class().get_name()
    if cn!="StaticMeshActor":
        l=a.get_actor_location()
        print("  %-34s %-28s (%.0f, %.0f, %.0f)" % (a.get_actor_label(), cn, l.x,l.y,l.z))
