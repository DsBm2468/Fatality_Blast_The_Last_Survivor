# -*- coding: utf-8 -*-
"""
Mete en `WBP_HUB_Inventary` el sitio donde pintar las balas del arma.

El arbol del widget era, para el hueco del arma:

    Arm (SizeBox) -> Button_0 -> IMG-ConvencionalGun (Image)

Un `Button` solo admite UN hijo, asi que para poner el numero ENCIMA del icono
hay que intercalar un `Overlay`:

    Arm (SizeBox) -> Button_0 -> OVL-Arm (Overlay) -> [ IMG-ConvencionalGun,
                                                        TXT-Munition ]

TRAMPA: `bIsVariable` es una propiedad **protegida**, asi que desde Python no
se puede marcar el TextBlock como "variable" desde el panel del Disenador. Y
tampoco vale tirar de `GetWidgetFromName`: **no esta expuesta a Blueprint**
(mirado en `UserWidget.h`; `WidgetTree::FindWidget` tampoco).

La salida es el enganche por NOMBRE del compilador de UMG: al inicializar el
widget, `UWidgetBlueprintGeneratedClass` recorre las propiedades de objeto de
la clase y le asigna a cada una el widget del arbol **que se llame igual**. O
sea que basta con crear a mano una variable miembro `TXT_Munition` de tipo
`TextBlock` y llamar al widget exactamente igual. Por eso el nombre lleva guion
BAJO y no medio: tiene que ser un nombre de variable valido.

Es idempotente: si el Overlay ya esta, no lo vuelve a crear.

Uso (dentro del editor):
    "<engine>/.../python.exe" Tools/ue_remote.py Tools/build_hud_munition.py
"""
import unreal

RUTA = "/Game/ThirdPerson/Blueprints/WBP/HUB/WBP_HUB_Inventary"
N_OVERLAY = "OVL-Arm"
N_TEXTO = "TXT_Munition"   # con guion BAJO: tiene que valer como nombre de variable

problemas = []


def log(ok, msg):
    if not ok:
        problemas.append(msg)
    print("  %s  %s" % ("ok   " if ok else "FALLO", msg))


bp = unreal.load_asset(RUTA)
tree = unreal.find_object(bp, "WidgetTree")
if tree is None:
    raise SystemExit("no se encontro el WidgetTree de " + RUTA)

boton = unreal.find_object(tree, "Button_0")
imagen = unreal.find_object(tree, "IMG-ConvencionalGun")
log(boton is not None, "Button_0 (el hueco del arma) esta en el arbol")
log(imagen is not None, "IMG-ConvencionalGun esta en el arbol")

overlay = unreal.find_object(tree, N_OVERLAY)
if overlay is None:
    overlay = unreal.new_object(unreal.Overlay, outer=tree, name=N_OVERLAY)
    boton.remove_child(imagen)
    boton.add_child(overlay)
    s = overlay.add_child(imagen)
    s.set_horizontal_alignment(unreal.HorizontalAlignment.H_ALIGN_FILL)
    s.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_FILL)
    log(True, "%s creado: el icono pasa a estar dentro del Overlay" % N_OVERLAY)
else:
    log(True, "%s ya existia" % N_OVERLAY)

texto = unreal.find_object(tree, N_TEXTO)
if texto is None:
    texto = unreal.new_object(unreal.TextBlock, outer=tree, name=N_TEXTO)
    s = overlay.add_child(texto)
    s.set_horizontal_alignment(unreal.HorizontalAlignment.H_ALIGN_RIGHT)
    s.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_BOTTOM)
    s.set_padding(unreal.Margin(0.0, 0.0, 4.0, 2.0))
    log(True, "%s creado sobre el icono del arma" % N_TEXTO)
else:
    log(True, "%s ya existia" % N_TEXTO)

# aspecto: pequeno, blanco y con sombra, para que se lea sobre cualquier icono
f = texto.get_editor_property("font")
f.set_editor_property("size", 14)
texto.set_editor_property("font", f)
texto.set_editor_property("color_and_opacity",
                          unreal.SlateColor(unreal.LinearColor(1.0, 1.0, 1.0, 1.0)))
texto.set_editor_property("shadow_offset", unreal.Vector2D(1.0, 1.0))
texto.set_editor_property("shadow_color_and_opacity",
                          unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
texto.set_text(unreal.Text(""))
# arranca oculto: sin arma no hay balas que enseñar. El Tick lo enciende.
texto.set_editor_property("visibility", unreal.SlateVisibility.HIDDEN)

# --- la variable miembro que el compilador enganchara con el widget ---
BEL = unreal.BlueprintEditorLibrary
tipo = unreal.EdGraphPinType()
tipo.import_text('(PinCategory="object",PinSubCategory="",'
                 'PinSubCategoryObject=Class'"/Script/UMG.TextBlock"',' 
                 'ContainerType=None,bIsReference=False)')
existe = False
try:
    unreal.get_default_object(bp.generated_class()).get_editor_property(N_TEXTO)
    existe = True
except Exception:
    existe = False
if not existe:
    BEL.add_member_variable(bp, N_TEXTO, tipo)
    log(True, "variable miembro %s creada (el compilador la engancha por nombre)" % N_TEXTO)
else:
    log(True, "la variable miembro %s ya existia" % N_TEXTO)

unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.EditorAssetLibrary.save_asset(RUTA)

# comprobacion sobre el arbol ya guardado
tree2 = unreal.find_object(unreal.load_asset(RUTA), "WidgetTree")
t2 = unreal.find_object(tree2, N_TEXTO)
log(t2 is not None, "%s sigue en el arbol despues de guardar" % N_TEXTO)
if t2 is not None:
    log(t2.get_parent() is not None and t2.get_parent().get_name() == N_OVERLAY,
        "%s cuelga de %s" % (N_TEXTO, N_OVERLAY))

print("\nPROBLEMAS: %d" % len(problemas))
for p in problemas:
    print("   - " + p)
