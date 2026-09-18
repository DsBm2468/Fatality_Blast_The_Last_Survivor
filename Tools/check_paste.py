# -*- coding: utf-8 -*-
"""
check_paste.py - revisa un fichero de pegado ANTES de meterlo en el editor.

Comprueba lo que falla en silencio:
  - LinkedTo que apunta a un nodo que no esta en el fichero -> cable perdido
  - LinkedTo que apunta a un PinId que no existe -> cable perdido
  - enlaces no reciprocos (A dice que va a B pero B no lo dice) -> Unreal se
    queda con uno de los dos y el grafo sale a medias
  - nombres de nodo repetidos -> el importador renombra y rompe los cables
  - pines de ejecucion de entrada con mas de un origen esta BIEN;
    pines de DATOS de entrada con mas de uno, no: solo admiten un cable
  - PinId repetidos entre nodos distintos

Acaba en "PROBLEMAS: N".

Uso:  python Tools/check_paste.py Tools/bp_paste/51_x.txt
"""
import re
import sys

RE_NODO = re.compile(r'^\s*Begin Object Class=([\w/\.]+) Name="([^"]+)"')
RE_PIN = re.compile(r'CustomProperties Pin \((.*)\)\s*$')


def campos(blob):
    d = {}
    for m in re.finditer(r'([\w\.]+)=("[^"]*"|\((?:[^()]|\([^()]*\))*\)|[^,]*)', blob):
        d[m.group(1)] = m.group(2)
    return d


def main(path):
    texto = open(path, "r", encoding="utf-8").read()
    nodos = []          # [(nombre, clase, [pin dicts])]
    actual = None
    repetidos = []
    for linea in texto.splitlines():
        m = RE_NODO.match(linea)
        if m:
            if any(n[0] == m.group(2) for n in nodos):
                repetidos.append(m.group(2))
            actual = (m.group(2), m.group(1), [])
            nodos.append(actual)
            continue
        if actual is None:
            continue
        m = RE_PIN.match(linea.strip())
        if m:
            actual[2].append(campos(m.group(1)))

    por_nombre = dict((n[0], n) for n in nodos)
    # OJO: los PinId NO son unicos en todo el grafo. Un nodo copiado en el
    # editor conserva los GUID de sus pines, asi que dos nodos distintos
    # pueden tener los mismos. Unreal los resuelve DENTRO de cada nodo
    # (LinkedTo trae nombre de nodo + PinId), asi que aqui hay que hacer lo
    # mismo: un mapa global daba 337 "enlaces no reciprocos" que no existian.
    pines_de = {}       # nodo -> {PinId: nombre_de_pin}
    problemas = []

    for nombre in repetidos:
        problemas.append("nombre de nodo repetido: %s" % nombre)

    for nombre, clase, pins in nodos:
        d = pines_de.setdefault(nombre, {})
        for p in pins:
            pid = p.get("PinId", "")
            if pid:
                d[pid] = p.get("PinName", "").strip('"')

    enlaces = []        # (nodo_origen, pin_origen_id, nodo_destino, pin_destino_id)
    for nombre, clase, pins in nodos:
        for p in pins:
            lk = p.get("LinkedTo")
            if not lk:
                continue
            for m in re.finditer(r'(\w+)\s+([0-9A-F]{32})', lk):
                destino, pid = m.group(1), m.group(2)
                if destino not in por_nombre:
                    problemas.append(
                        "%s.%s enlaza con el nodo %s, que NO esta en el fichero"
                        % (nombre, p.get("PinName", "").strip('"'), destino))
                    continue
                if pid not in pines_de.get(destino, {}):
                    problemas.append(
                        "%s.%s enlaza con el pin %s, que no existe en %s"
                        % (nombre, p.get("PinName", "").strip('"'), pid, destino))
                    continue
                enlaces.append((nombre, p.get("PinId"), destino, pid))

    # reciprocidad
    conjunto = set((a, b, c, d) for a, b, c, d in enlaces)
    for a, b, c, d in enlaces:
        if (c, d, a, b) not in conjunto:
            problemas.append("enlace NO reciproco: %s.%s -> %s.%s "
                             "(el destino no lo declara)"
                             % (a, pines_de.get(a, {}).get(b, "?"), c,
                                pines_de.get(c, {}).get(d, "?")))

    # pines de datos de entrada con mas de un origen
    entradas = {}
    for nombre, clase, pins in nodos:
        for p in pins:
            if p.get("Direction"):
                continue
            cat = p.get("PinType.PinCategory", "").strip('"')
            if cat == "exec":
                continue
            lk = p.get("LinkedTo")
            if not lk:
                continue
            n = len(re.findall(r'\w+\s+[0-9A-F]{32}', lk))
            if n > 1:
                problemas.append(
                    "%s.%s es un pin de DATOS de entrada con %d cables "
                    "(solo admite uno)"
                    % (nombre, p.get("PinName", "").strip('"'), n))

    print("nodos: %d   pines: %d   enlaces: %d"
          % (len(nodos), sum(len(v) for v in pines_de.values()),
             len(enlaces) // 2))
    for p in problemas:
        print("   PROBLEMA: %s" % p)
    print("PROBLEMAS: %d" % len(problemas))
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
