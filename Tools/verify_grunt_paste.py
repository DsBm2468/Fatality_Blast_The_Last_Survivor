# -*- coding: utf-8 -*-
"""
Valida el texto de pegado de Tools/bp_paste/ CONTRA LA REFLEXION REAL DEL
MOTOR, antes de pegar nada.

Existe porque un pegado con un nombre mal escrito no falla: el pin se queda
huerfano, el Blueprint compila limpio y en runtime no hace nada. Este script
resuelve cada funcion, cada propiedad, cada struct y cada entrada de enum que
aparece en los pegados y avisa de lo que el motor no reconoce.

    "<engine>/.../python.exe" Tools/ue_remote.py Tools/verify_grunt_paste.py

Informe en Saved/GruntPaste_Report.txt. Acaba en "TOTAL DE PROBLEMAS: N".
"""
import os
import re

import unreal

DIR = os.path.join(unreal.Paths.project_dir(), "Tools", "bp_paste")

out = []
problemas = []


def say(m):
    out.append(m)
    print(m)


def mal(m):
    problemas.append(m)
    say("    FALLO  " + m)


# ------------------------------------------------------------------ parseo
RE_OBJ = re.compile(r'Begin Object Class=/Script/\w+\.(\w+) Name="([^"]+)"(.*?)\nEnd Object',
                    re.S)
RE_MEMBER = re.compile(r'MemberParent=Class\'"([^"]+)"\',MemberName="([^"]+)"')
RE_SELFCTX = re.compile(r'MemberName="([^"]+)",bSelfContext=True')
RE_PIN = re.compile(r'CustomProperties Pin \((.*?),\)\s*$', re.M)
RE_PINNAME = re.compile(r'PinName="([^"]+)"')
RE_STRUCTTYPE = re.compile(r'StructType=ScriptStruct\'"([^"]+)"\'')
RE_ENUMOBJ = re.compile(r'PinType\.PinSubCategoryObject=UserDefinedEnum\'"([^"]+)"\'')
RE_DEFAULT = re.compile(r'DefaultValue="([^"]*)"')
RE_CUSTOMEV = re.compile(r'CustomFunctionName="([^"]+)"')
RE_OBJCLASS = re.compile(r'Begin Object Class=/Script/(\w+)\.(\w+) ')

RE_TYPEREF = re.compile(r"PinType\.PinSubCategoryObject=(Class|ScriptStruct|Enum|UserDefinedEnum|UserDefinedStruct|BlueprintGeneratedClass)'\"([^\"]+)\"'")

_clases_nodo = {}
_refs_tipo = {}


def camel_a_snake(n):
    n = re.sub(r'^K2_', '', n)
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', n)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return s.lower()


def normaliza_pin(p):
    """Los bindings de Python renombran los parametros respecto al nombre real
    del pin: quitan la 'b' de los booleanos (bNewVisibility -> new_visibility)
    y el prefijo 'In' (InCollisionProfileName -> collision_profile_name).
    Hay que deshacer eso antes de comparar o casi todo son falsos positivos."""
    if re.match(r'^b[A-Z]', p):
        p = p[1:]
    if re.match(r'^In[A-Z]', p):
        p = p[2:]
    return camel_a_snake(p)


_clases = {}


def carga_clase(path):
    if path not in _clases:
        try:
            _clases[path] = unreal.load_object(None, path)
        except Exception:
            _clases[path] = None
    return _clases[path]


def existe_funcion(class_path, fn):
    """1) intenta cargar la UFunction directamente
       2) si no, mira si existe el binding de Python (los
          BlueprintImplementableEvent como ReceiveMoveCompleted no se pueden
          cargar con load_object pero si existen)
       3) si no, la busca subiendo por las clases padre"""
    try:
        if unreal.load_object(None, "%s:%s" % (class_path, fn)) is not None:
            return True
    except Exception:
        pass
    nombre_py = class_path.split(".")[-1]
    py = getattr(unreal, nombre_py, None)
    if py is not None:
        if hasattr(py, camel_a_snake(fn)) or hasattr(py, fn):
            return True
    return False


def existe_ufunction_estricta(class_path, fn):
    """Solo load_object, SIN el atajo del binding de Python. Hace falta para
    la regla del K2_: camel_a_snake("K2_SetVisibility") da "set_visibility",
    que existe siempre, asi que el atajo daria positivo para todo."""
    try:
        return unreal.load_object(None, "%s:%s" % (class_path, fn)) is not None
    except Exception:
        return False


PINS_IMPLICITOS = {"execute", "then", "self", "ReturnValue", "WorldContextObject",
                   "Duration", "CastFailed", "AsTarget", "Object", "bSuccess"}


def params_de_funcion(class_path, fn):
    """Nombres de los parametros reales de una funcion, sacados de la firma
    del binding de Python. Devuelve None si no se puede averiguar.

    Esto es lo que pilla los pines mal escritos (el caso Vector_Distance:
    los pines son V1/V2, no A/B). Un pin con nombre inventado no rompe el
    pegado: se queda huerfano y el Blueprint compila igual."""
    import inspect
    nombre_py = class_path.split(".")[-1]
    py = getattr(unreal, nombre_py, None)
    if py is None:
        return None
    for cand in (camel_a_snake(fn), fn):
        f = getattr(py, cand, None)
        if f is None:
            continue
        try:
            sig = inspect.signature(f)
        except (TypeError, ValueError):
            doc = getattr(f, "__doc__", "") or ""
            m = re.search(r'\(([^)]*)\)', doc)
            if not m:
                return None
            return {p.split("=")[0].strip().lstrip("*")
                    for p in m.group(1).split(",") if p.strip()}
        return {p for p in sig.parameters if p not in ("self", "args", "kwargs")}
    return None


def existe_propiedad(class_path, prop):
    c = carga_clase(class_path)
    if c is None:
        return None  # clase no resoluble
    try:
        cdo = unreal.get_default_object(c)
        cdo.get_editor_property(prop)
        return True
    except Exception:
        return False


def entradas_enum(enum_path):
    """Nombres internos NewEnumeratorN de un UserDefinedEnum, leidos del
    binario del .uasset (la API de Python no los expone)."""
    rel = enum_path.split(".")[0].replace("/Game/", "Content/") + ".uasset"
    f = os.path.join(unreal.Paths.project_dir(), rel)
    if not os.path.isfile(f):
        return None
    d = open(f, "rb").read()
    return sorted({m.decode() for m in re.findall(rb'NewEnumerator\d+', d)})


def campos_struct(struct_path):
    if struct_path.startswith("/Script/"):
        return None  # nativo: los pines los reconstruye el motor
    rel = struct_path.split(".")[0].replace("/Game/", "Content/") + ".uasset"
    f = os.path.join(unreal.Paths.project_dir(), rel)
    if not os.path.isfile(f):
        return None
    d = open(f, "rb").read()
    return sorted({m.decode() for m in
                   re.findall(rb'[A-Za-z_][A-Za-z0-9_]*_\d+_[0-9A-F]{32}', d)})


# -------------------------------------------------------- variables propias
VARS_AIC = None
VARS_GRUNT = None


def vars_de(bp_path):
    try:
        bp = unreal.EditorAssetLibrary.load_asset(bp_path)
        cdo = unreal.get_default_object(
            unreal.BlueprintEditorLibrary.generated_class(bp))
        return cdo
    except Exception:
        return None


CDO_AIC = vars_de("/Game/ThirdPerson/AI/BP_GruntAIController")
CDO_GRUNT = vars_de("/Game/ThirdPerson/Blueprints/BP_Grunt")

# A que Blueprint va cada pegado. Sin esto el verificador daba por rotas todas
# las variables propias de cualquier pegado que no fuese del controlador de la
# IA, que es para lo que se escribio (29 falsos positivos el 2026-09-03).
DESTINO = [
    ("Grunt_Muerte", "/Game/ThirdPerson/Blueprints/BP_Grunt"),
    ("20_Gun_", "/Game/ThirdPerson/Blueprints/Interactables/BP_ConventionalGun"),
    ("21_Ammo_", "/Game/ThirdPerson/Blueprints/Interactables/BP_MunitionConventionalGun"),
    ("22_Char_", "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter"),
]
_CACHE = {}


def cdo_para(fichero):
    """Devuelve (cdo, nombre_legible) del Blueprint destino del pegado."""
    for marca, ruta in DESTINO:
        if marca in fichero:
            if ruta not in _CACHE:
                _CACHE[ruta] = vars_de(ruta)
            return _CACHE[ruta], ruta.rsplit("/", 1)[-1]
    return CDO_AIC, "BP_GruntAIController"

# eventos personalizados definidos por los propios pegados: se recopilan
# primero para no dar por rota una llamada a un evento que llega en otro fichero
EVENTOS = set()


def recoge_eventos():
    for f in sorted(os.listdir(DIR)):
        if not f.endswith(".txt"):
            continue
        txt = open(os.path.join(DIR, f), encoding="utf-8").read()
        for kind, name, body in RE_OBJ.findall(txt):
            if kind == "K2Node_CustomEvent":
                m = RE_CUSTOMEV.search(body)
                if m:
                    EVENTOS.add(m.group(1))


# ------------------------------------------------------------------ chequeo
say("=" * 66)
say(" VERIFICACION DEL TEXTO DE PEGADO CONTRA LA REFLEXION DEL MOTOR")
say("=" * 66)

if not os.path.isdir(DIR):
    say("No existe %s" % DIR)
else:
    recoge_eventos()
    say("")
    say("Eventos personalizados que definen los pegados: %s"
        % ", ".join(sorted(EVENTOS)))

    for fichero in sorted(os.listdir(DIR)):
        if not fichero.endswith(".txt") or fichero.startswith("00_"):
            continue
        ruta = os.path.join(DIR, fichero)
        txt = open(ruta, encoding="utf-8").read()
        bloques = RE_OBJ.findall(txt)
        say("")
        say("-- %s  (%d nodos) --" % (fichero, len(bloques)))
        cdo_propio, nombre_destino = cdo_para(fichero)

        # ---- LA COMPROBACION MAS IMPORTANTE: la clase del nodo existe?
        # Si no existe, el nodo NO se crea al pegar y se pierden en silencio
        # todas las conexiones que pasaban por el. Sin error, sin aviso.
        # Asi se colo K2Node_Delay (que no existe: el Delay es un
        # K2Node_CallFunction a KismetSystemLibrary::Delay).
        for m, kind in RE_OBJCLASS.findall(txt):
            ruta = "/Script/%s.%s" % (m, kind)
            if ruta in _clases_nodo:
                continue
            try:
                _clases_nodo[ruta] = unreal.load_object(None, ruta) is not None
            except Exception:
                _clases_nodo[ruta] = False
            if not _clases_nodo[ruta]:
                mal("la clase de nodo %s NO EXISTE: al pegar no se creara el "
                    "nodo y se perderan sus conexiones" % ruta)

        # ---- toda referencia de tipo en un pin tiene que resolver.
        # Si PinSubCategoryObject apunta a algo inexistente, Unreal DESCARTA
        # EL NODO ENTERO al pegar, sin avisar, y se pierden sus conexiones.
        # Asi se perdieron los 5 SetText: FText no es un ScriptStruct.
        for ref in set(RE_TYPEREF.findall(txt)):
            kindname, ruta = ref
            if ruta in _refs_tipo:
                continue
            try:
                _refs_tipo[ruta] = unreal.load_object(None, ruta) is not None
            except Exception:
                _refs_tipo[ruta] = False
            if not _refs_tipo[ruta]:
                mal("la referencia de tipo %s'%s' no resuelve: al pegar se "
                    "descartara el nodo que la use" % (kindname, ruta))

        for kind, name, body in bloques:
            # ---- llamadas a funciones de otras clases
            if kind in ("K2Node_CallFunction", "K2Node_Message",
                        "K2Node_CallArrayFunction", "K2Node_Event"):
                m = RE_MEMBER.search(body)
                if m:
                    cp, fn = m.group(1), m.group(2)
                    if cp.startswith("/Script/"):
                        if not existe_funcion(cp, fn):
                            mal("%s: no existe %s:%s" % (name, cp, fn))
                        elif (not fn.startswith("K2_")
                              and existe_ufunction_estricta(cp, "K2_" + fn)
                              and existe_ufunction_estricta(cp, fn)):
                            # Cuando conviven Xxx y K2_Xxx, la version de
                            # Blueprint es SIEMPRE la K2_; la otra suele ser
                            # nativa u obsoleta, y al pegar un nodo que la
                            # llama Unreal DESCARTA EL NODO en silencio.
                            # Asi se perdieron los 5 SetText.
                            mal("%s: usa %s pero existe K2_%s, que es la que "
                                "expone Blueprint. Con la otra el nodo se "
                                "descarta al pegar" % (name, fn, fn))
                        elif kind != "K2Node_Event":
                            # los pines de un evento vienen de la firma de un
                            # delegado; Python no la expone de forma fiable
                            reales = params_de_funcion(cp, fn)
                            if reales:
                                reales_snake = {r.lower() for r in reales}
                                for pin in RE_PIN.findall(body):
                                    pn = RE_PINNAME.search(pin)
                                    if not pn:
                                        continue
                                    p = pn.group(1)
                                    if p in PINS_IMPLICITOS:
                                        continue
                                    if (normaliza_pin(p) not in reales_snake
                                            and camel_a_snake(p) not in reales_snake
                                            and p.lower() not in reales_snake):
                                        mal("%s (%s): el pin '%s' no es un "
                                            "parametro de %s. Reales: %s"
                                            % (name, fn, p, fn,
                                               ", ".join(sorted(reales))))
                    else:
                        # interfaz o clase de Blueprint del proyecto
                        if carga_clase(cp) is None:
                            mal("%s: no resuelve la clase %s" % (name, cp))
                else:
                    ms = RE_SELFCTX.search(body)
                    if ms:
                        fn = ms.group(1)
                        if fn not in EVENTOS:
                            mal("%s: llama a '%s' y ningun pegado lo define"
                                % (name, fn))

            # ---- variables
            if kind in ("K2Node_VariableGet", "K2Node_VariableSet"):
                m = RE_MEMBER.search(body)
                if m:
                    cp, pr = m.group(1), m.group(2)
                    r = existe_propiedad(cp, pr)
                    if r is None:
                        mal("%s: no resuelve la clase %s" % (name, cp))
                    elif not r:
                        mal("%s: %s no tiene la propiedad '%s'" % (name, cp, pr))
                else:
                    ms = RE_SELFCTX.search(body)
                    if ms and cdo_propio is not None:
                        pr = ms.group(1)
                        try:
                            cdo_propio.get_editor_property(pr)
                        except Exception:
                            mal("%s: la variable propia '%s' no existe en %s"
                                % (name, pr, nombre_destino))

            # ---- structs
            if kind in ("K2Node_MakeStruct", "K2Node_BreakStruct"):
                m = RE_STRUCTTYPE.search(body)
                if m:
                    sp = m.group(1)
                    campos = campos_struct(sp)
                    if campos is not None:
                        for pin in RE_PIN.findall(body):
                            pn = RE_PINNAME.search(pin)
                            if not pn:
                                continue
                            p = pn.group(1)
                            if p in ("StructOut", sp.split(".")[-1]):
                                continue
                            if p not in campos:
                                mal("%s: '%s' no es un campo de %s"
                                    % (name, p, sp.split(".")[-1]))

            # ---- entradas de enum usadas como valor por defecto
            for pin in RE_PIN.findall(body):
                me = RE_ENUMOBJ.search(pin)
                md = RE_DEFAULT.search(pin)
                if me and md and md.group(1).startswith("NewEnumerator"):
                    ents = entradas_enum(me.group(1))
                    if ents is not None and md.group(1) not in ents:
                        mal("%s: %s no tiene la entrada %s (tiene %s)"
                            % (name, me.group(1).split(".")[-1], md.group(1),
                               ", ".join(ents)))

        say("    revisado")

say("")
say("=" * 66)
say("TOTAL DE PROBLEMAS: %d" % len(problemas))
for p in problemas:
    say("   - " + p)

ruta_inf = unreal.Paths.project_saved_dir() + "GruntPaste_Report.txt"
with open(ruta_inf, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("")
print("informe -> " + ruta_inf)
