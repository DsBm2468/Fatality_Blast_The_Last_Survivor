import unreal
BEL=unreal.BlueprintEditorLibrary
EAL=unreal.EditorAssetLibrary
def props(k):
    out=[]
    it = unreal.get_type_from_class(k) if False else None
    cdo=unreal.get_default_object(k)
    for n in dir(cdo):
        if n.startswith('_'): continue
        try:
            v=cdo.get_editor_property(n)
        except Exception:
            continue
        out.append("%s = %r" % (n, v))
    return out
for ruta in ["/Game/ThirdPerson/Components/BPC_Curation",
             "/Game/ThirdPerson/Components/BPC_Inventary"]:
    if not EAL.does_asset_exist(ruta): print("NO EXISTE:",ruta); continue
    bp=EAL.load_asset(ruta); k=BEL.generated_class(bp)
    print("="*60); print(ruta)
    for l in props(k): print("   ",l)
