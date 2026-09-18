import unreal
EAS=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
por_clase={}
for a in EAS.get_all_level_actors():
    c=a.get_class().get_name()
    if c.startswith("BP_") or "MARCADOR" in a.get_actor_label():
        por_clase.setdefault(c, []).append(a)
for c in sorted(por_clase):
    print("%-34s %d" % (c, len(por_clase[c])))
    for a in por_clase[c][:12]:
        l=a.get_actor_location()
        print("      %-42s (%7.0f,%8.0f,%6.0f)" % (a.get_actor_label()[:42], l.x, l.y, l.z))
