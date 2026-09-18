# -*- coding: utf-8 -*-
"""
Inventario de lo que se puede BORRAR sin cambiar el comportamiento.

Analiza los Saved/AuditT3D_*.copy que deja audit_full.py y marca, por grafo,
los nodos a los que no puede llegar la ejecucion.

Alcanzabilidad de verdad, en dos pasadas, porque con una sola se marcan como
muertos nodos que si se usan:
  1) EXEC: desde cada arrancador (evento, entrada de funcion, nodo de input)
     se sigue hacia delante por los pines de ejecucion.
  2) DATOS: de cada nodo alcanzado se sigue hacia ATRAS por sus pines de
     entrada de datos, atravesando knots y nodos puros. Un `get` o un
     `NotEqual` no tienen pin de ejecucion y solo estan vivos si alguien
     alcanzable lee su salida.
Lo que no queda en ninguna de las dos pasadas es codigo muerto.

    python Tools/dead_code.py            resumen
    python Tools/dead_code.py -v         lista nodo a nodo
    python Tools/dead_code.py BP_Nombre  solo ese Blueprint

Los comentarios (EdGraphNode_Comment) no son codigo y no se cuentan.
"""
import collections
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import t3d_read as T  # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "Saved")

ARRANCADORES = {
    "K2Node_Event", "K2Node_CustomEvent", "K2Node_FunctionEntry",
    "K2Node_InputKey", "K2Node_InputDebugKey", "K2Node_EnhancedInputAction",
    "K2Node_ComponentBoundEvent", "K2Node_ActorBoundEvent",
    "K2Node_InputAxisEvent", "K2Node_Timeline", "K2Node_Tunnel",
}
NO_ES_CODIGO = {"EdGraphNode_Comment", "EdGraphNode_Documentation"}

RE_LINK = re.compile(r"([A-Za-z_][\w]*) [0-9A-F]{32}")


def analiza(g):
    """Devuelve (vivos, muertos) por nombre de nodo."""
    def pins(nm):
        return g[nm]["pins"]

    def es_exec(p):
        return p.get("PinType.PinCategory", "").strip('"') == "exec"

    def es_salida(p):
        return p.get("Direction", "").strip('"') == "EGPD_Output"

    def destinos(p):
        return RE_LINK.findall(p.get("LinkedTo") or "")

    vivos = set()

    # --- pasada 1: ejecucion hacia delante
    pila = [nm for nm, n in g.items() if n["class"] in ARRANCADORES]
    while pila:
        nm = pila.pop()
        if nm in vivos or nm not in g:
            continue
        vivos.add(nm)
        for p in pins(nm):
            # los knots no tienen categoria exec fiable: se siguen siempre
            if (es_exec(p) and es_salida(p)) or g[nm]["class"] == "K2Node_Knot":
                if g[nm]["class"] == "K2Node_Knot" and not es_salida(p):
                    continue
                pila += [d for d in destinos(p) if d not in vivos]

    # --- pasada 2: dependencias de datos hacia atras
    pila = list(vivos)
    while pila:
        nm = pila.pop()
        if nm not in g:
            continue
        for p in pins(nm):
            if es_salida(p) or es_exec(p):
                continue
            for d in destinos(p):
                if d not in vivos:
                    vivos.add(d)
                    pila.append(d)

    muertos = [nm for nm, n in g.items()
               if nm not in vivos and n["class"] not in NO_ES_CODIGO]
    return vivos, muertos



# --------------------------------------------------------------- variables

RE_VAR = re.compile(r'NewVariables\(\d+\)=\(VarName="([^"]+)"')
RE_MIEMBRO = re.compile(r'MemberName="([^"]+)"')


def variables_muertas():
    """Variables declaradas por un Blueprint que no aparecen en NINGUN nodo de
    NINGUN Blueprint exportado.

    Se busca el nombre en los 34 exports, no solo en el propio: las cuatro
    refs de BPC_Inventary se leen desde BP_ThirdPersonCharacter.

    OJO: esto NO ve las instancias del NIVEL. Una variable editable por
    instancia puede estar puesta a mano en un actor colocado (los PatrolPoints
    de cada soldado) y aqui saldria como muerta. Antes de borrar una variable
    expuesta, mirar el nivel.
    """
    crudo = {}
    for ruta in sorted(glob.glob(os.path.join(RAIZ, "AuditT3D_*.copy"))):
        crudo[os.path.basename(ruta)[len("AuditT3D_"):-len(".copy")]] = T.load(ruta)
    usados = collections.Counter()
    for txt in crudo.values():
        for m in RE_MIEMBRO.findall(txt):
            usados[m] += 1
    fuera = []
    for nombre, txt in crudo.items():
        for v in RE_VAR.findall(txt):
            if usados[v] == 0:
                fuera.append((nombre, v))
    return fuera


def es_stub(nodos):
    """Un grafo de 2-3 nodos con FunctionEntry es un stub del compilador para
    un evento personalizado, no una funcion vacia."""
    return (len(nodos) <= 3
            and any(n["class"] == "K2Node_FunctionEntry" for n in nodos.values()))


def main():
    verboso = "-v" in sys.argv
    filtro = [a for a in sys.argv[1:] if not a.startswith("-")]

    total = 0
    filas = []
    for ruta in sorted(glob.glob(os.path.join(RAIZ, "AuditT3D_*.copy"))):
        nombre = os.path.basename(ruta)[len("AuditT3D_"):-len(".copy")]
        if filtro and not any(f.lower() in nombre.lower() for f in filtro):
            continue
        try:
            grafos = T.parse(ruta)
        except Exception as e:
            print("  no se pudo leer %s: %s" % (nombre, e))
            continue
        for gname, g in grafos.items():
            if not g or es_stub(g):
                continue
            vivos, muertos = analiza(g)
            if not muertos:
                continue
            total += len(muertos)
            filas.append((nombre, gname, len(g), muertos))

    print("=" * 74)
    print(" NODOS MUERTOS (la ejecucion no puede llegar a ellos)")
    print("=" * 74)
    for nombre, gname, n, muertos in sorted(filas, key=lambda f: -len(f[3])):
        print("\n%s :: %s   %d de %d nodos" % (nombre, gname, len(muertos), n))
        cuenta = collections.Counter()
        for nm in muertos:
            cuenta[T.label(_G[nombre][gname][nm]) if False else nm] = 0
        if verboso:
            for nm in muertos:
                print("      %s" % nm)
        else:
            print("      %s" % ", ".join(sorted(muertos)[:8])
                  + (" ..." if len(muertos) > 8 else ""))
    print("\n" + "=" * 74)
    print("TOTAL DE NODOS MUERTOS: %d" % total)

    if not filtro:
        vm = variables_muertas()
        print("\n" + "=" * 74)
        print(" VARIABLES QUE NO APARECEN EN NINGUN NODO (%d)" % len(vm))
        print(" ojo: esto no mira las instancias del nivel")
        print("=" * 74)
        for bp, v in sorted(vm):
            print("   %-28s %s" % (bp, v))



_G = {}

if __name__ == "__main__":
    main()
