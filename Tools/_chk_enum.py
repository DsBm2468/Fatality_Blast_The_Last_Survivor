import unreal
e=unreal.load_object(None,'/Game/ThirdPerson/Blueprints/Interfaces/DamageSystem/E_DamageType')
print("expuesto como tipo python:", hasattr(unreal,"E_DamageType"))
if hasattr(unreal,"E_DamageType"):
    T=unreal.E_DamageType
    for i in range(9):
        try: print("  %d -> %s" % (i, T.cast(i)))
        except Exception as ex: print("  %d -> %s" % (i, str(ex)[:50]))
# ruta alternativa: pedirle al motor el nombre por indice
for m in ("get_display_name_by_index","get_name_by_index","get_display_name_text_by_index"):
    print(m, hasattr(e,m))
