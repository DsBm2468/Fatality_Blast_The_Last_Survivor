# -*- coding: utf-8 -*-
"""
t3d_to_paste.py - convierte los nodos de un grafo YA EXPORTADO en texto de
pegado, con la posibilidad de excluir nodos y de sustituir el FunctionEntry
por un evento.

Para que sirve: un grafo de funcion no se puede enfocar por script (el editor
abre el asset, no una pestana concreta), asi que no hay forma de pegar dentro
de el. El EventGraph si. Esta herramienta permite mover la logica de un grafo
de funcion al EventGraph colgandola de un evento, reutilizando los nodos tal y
como los escribio el exportador, sin volver a declararlos a mano.

Trabaja sobre el TEXTO de los bloques Begin Object / End Object, no sobre una
reconstruccion: asi conserva lo que bpgen no modela (knots, defaults de
struct, operadores promocionables, pines avanzados).

Uso tipico, mover BP_Item.Interact al EventGraph como evento de interfaz:

    python Tools/t3d_to_paste.py Saved/T3D_BP_Item.copy Interact salida.txt \
        --excluir K2Node_FunctionResult_0,K2Node_Self_0 \
        --evento K2Node_FunctionEntry_0 --evento-nombre Interact \
        --evento-parent "<MemberParent tal cual>" --sufijo _ev
"""
import argparse
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import t3d_read  # noqa: E402

RE_BEGIN = re.compile(r'^\s*Begin Object Class=([\w/\.]+) Name="([^"]+)"')
RE_END = re.compile(r'^\s*End Object\s*$')


RE_ANY_BEGIN = re.compile(r'^(\s*)Begin Object(?: Class=([\w/\.]+))?'
                          r'(?: Name="([^"]+)")?')


def bloques(path, grafo):
    """[(nombre, clase, [lineas_de_cuerpo])] de los nodos del grafo.

    TRAMPA DEL FORMATO: el exportador declara cada objeto DOS veces. Primero
    un stub anidado CON Class= y sin contenido, y despues el bloque con las
    propiedades y los pines pero SIN Class=. Un pegado necesita las dos
    mitades juntas, asi que aqui se fusionan por nombre. Coger solo la primera
    da nodos sin un solo pin (y el pegado entra vacio, sin avisar).
    """
    texto = t3d_read.load(path)
    pila = []
    en_grafo = False
    prof = 0
    clases = {}
    cuerpos = {}
    orden = []
    actual = None
    for linea in texto.splitlines():
        m = RE_ANY_BEGIN.match(linea)
        if m and linea.strip().startswith("Begin Object"):
            clase_full = m.group(2) or ""
            clase = clase_full.split(".")[-1]
            nombre = m.group(3) or ""
            # el segundo bloque (sin Class=) de un nodo ya visto
            if not clase and not (en_grafo and len(pila) == prof) and nombre in clases:
                pass
            pila.append((clase or clases.get(nombre, "").split(".")[-1], nombre))
            if (clase == "EdGraph"
                    or clases.get(nombre, "").endswith(".EdGraph")) \
                    and nombre == grafo:
                en_grafo = True
                prof = len(pila)
                clases[nombre] = "/Script/Engine.EdGraph"
                continue
            if en_grafo and len(pila) == prof + 1:
                if clase:
                    clases[nombre] = clase_full
                    if nombre not in orden:
                        orden.append(nombre)
                actual = (nombre, [])
                continue
        if actual is not None and not RE_END.match(linea):
            actual[1].append(linea)
        if RE_END.match(linea):
            if actual is not None and len(pila) == prof + 1:
                nombre, cuerpo = actual
                if cuerpo:
                    cuerpos[nombre] = cuerpo
                actual = None
            if pila:
                pila.pop()
                if en_grafo and len(pila) < prof:
                    en_grafo = False
    fuera = []
    for nombre in orden:
        cuerpo = cuerpos.get(nombre)
        if not cuerpo:
            continue
        cab = 'Begin Object Class=%s Name="%s"' % (clases[nombre], nombre)
        fuera.append((nombre, clases[nombre].split(".")[-1],
                      [cab] + cuerpo + ["End Object"]))
    return fuera


def pines_de(lineas):
    """{PinId: PinName} de un bloque de nodo."""
    d = {}
    for l in lineas:
        m = re.search(r'PinId=([0-9A-F]{32}).*?PinName="([^"]*)"', l)
        if m:
            d[m.group(1)] = m.group(2)
    return d


def guid(seed):
    return hashlib.md5(seed.encode("utf-8")).hexdigest().upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export")
    ap.add_argument("grafo")
    ap.add_argument("salida")
    ap.add_argument("--excluir", default="")
    ap.add_argument("--evento", default=None)
    ap.add_argument("--evento-nombre", default=None)
    ap.add_argument("--evento-parent", default=None)
    ap.add_argument("--evento-custom", action="store_true")
    ap.add_argument("--sufijo", default="_mv")
    ap.add_argument("--x", type=int, default=0)
    ap.add_argument("--y", type=int, default=0)
    a = ap.parse_args()

    nodos = bloques(a.export, a.grafo)
    if not nodos:
        raise SystemExit("no hay nodos en el grafo %r de %s" % (a.grafo, a.export))

    excluir = set(x for x in a.excluir.split(",") if x)
    redir = {}
    cabecera = []

    if a.evento:
        src = None
        for n in nodos:
            if n[0] == a.evento:
                src = n
        if src is None:
            raise SystemExit("no existe el nodo %r" % a.evento)
        nombre_ev = "K2Node_Event_%s" % (a.evento_nombre or "Ev")
        decl = []
        for pid, pn in pines_de(src[2]).items():
            nuevo = guid("%s|%s|%s" % (nombre_ev, pn, pid))
            redir[pid] = (nombre_ev, nuevo)
            orig = None
            for l in src[2]:
                if pid in l:
                    orig = l
            decl.append(orig.replace(pid, nuevo))
        if a.evento_custom:
            cab = ['Begin Object Class=/Script/BlueprintGraph.K2Node_CustomEvent '
                   'Name="%s"' % nombre_ev,
                   '   CustomFunctionName="%s"' % a.evento_nombre]
        else:
            cab = ['Begin Object Class=/Script/BlueprintGraph.K2Node_Event '
                   'Name="%s"' % nombre_ev,
                   '   EventReference=(MemberParent=%s,MemberName="%s")'
                   % (a.evento_parent, a.evento_nombre),
                   '   bOverrideFunction=True']
        cab.append('   NodePosX=%d' % a.x)
        cab.append('   NodePosY=%d' % a.y)
        cab.append('   NodeGuid=%s' % guid(nombre_ev))
        cab.extend(decl)
        cab.append('End Object')
        cabecera = cab
        excluir.add(a.evento)

    # pines de los nodos excluidos: los enlaces que apunten a ellos se rompen
    muertos = set()
    for nm, cl, ls in nodos:
        if nm in excluir and nm != a.evento:
            muertos.update(pines_de(ls))

    vivos = [n for n in nodos if n[0] not in excluir]
    renombre = dict((n[0], n[0] + a.sufijo) for n in vivos)

    def arregla(m):
        partes = []
        for mm in re.finditer(r'([\w]+)\s+([0-9A-F]{32})', m.group(1)):
            n2, pid = mm.group(1), mm.group(2)
            if pid in muertos:
                continue
            if pid in redir:
                partes.append("%s %s" % redir[pid])
            elif n2 in renombre:
                partes.append("%s %s" % (renombre[n2], pid))
            elif n2 in excluir:
                continue
            else:
                partes.append("%s %s" % (n2, pid))
        if not partes:
            return ""
        return "LinkedTo=(%s,)," % ",".join(partes)

    salida = []
    for nm, cl, ls in vivos:
        out = []
        for l in ls:
            l = re.sub(r'(Name=")%s(")' % re.escape(nm),
                       r'\g<1>%s\g<2>' % renombre[nm], l)
            l = re.sub(r'LinkedTo=\(([^)]*)\),', arregla, l)
            out.append(l)
        salida.append("\n".join(out))

    texto = ""
    if cabecera:
        texto += "\n".join(cabecera) + "\n"
    texto += "\n".join(salida) + "\n"
    with open(a.salida, "w", encoding="utf-8") as fh:
        fh.write(texto)

    print("escrito %s  (%d nodos, %d excluidos)"
          % (a.salida, texto.count("Begin Object Class="), len(excluir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
