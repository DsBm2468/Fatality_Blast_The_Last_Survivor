# -*- coding: utf-8 -*-
"""
Lector de export T3D de Blueprints: {grafo: {nodo: {class, props, pins}}}.

Las conexiones se resuelven POR NOMBRE de nodo: LinkedTo trae el nombre y el
GUID del pin, asi que no hace falta un mapa de GUIDs (y resolverlo por GUID
se equivocaba).

Por que no vale audit_graph.py aqui: decide "esto abre un grafo" por
heuristica de nombres y, en un Blueprint con muchos grafos-stub de evento,
mezcla nodos de grafos distintos. Medido el 2026-09-08 sobre
BP_ThirdPersonCharacter: 144 pines duplicados y los enlaces de exec
resueltos todos al mismo nodo. Aqui se sigue el anidamiento real de
Begin/End Object.

La otra trampa del formato: cada objeto se declara DOS veces, primero un stub
anidado CON Class= y luego el bloque con props y pines SIN Class=. Si el
segundo no se reconoce por el nombre, los nodos salen sin props ni pines.
"""

import re, collections

def load(path):
    raw=open(path,'rb').read()
    try: return raw.decode('utf-16')
    except Exception: return raw.decode('utf-8','replace')

BEGIN=re.compile(r'Begin Object(?: Class=([\w/\.]+))?(?: Name="([^"]+)")?')
PIN=re.compile(r'CustomProperties Pin \((.*)\)\s*$')

def kv(blob):
    d={}
    for m in re.finditer(r'([\w\.]+)=("[^"]*"|\((?:[^()]|\([^()]*\))*\)|[^,]*)', blob):
        d[m.group(1)]=m.group(2)
    return d

def parse(path):
    """Devuelve {grafo: {nodo: {class, props, pins}}} respetando el anidamiento
    real de Begin/End Object. El export declara cada objeto dos veces: primero
    un stub anidado y luego el bloque con contenido; se fusionan por nombre."""
    stack=[]              # pila de (clase, nombre)
    graphs=collections.OrderedDict()
    for line in load(path).splitlines():
        s=line.strip()
        m=BEGIN.match(s)
        if m and s.startswith('Begin Object'):
            stack.append(((m.group(1) or '').split('.')[-1], m.group(2) or ''))
            cls,nm=stack[-1]
            padre_es_grafo = len(stack)>=2 and stack[-2][0]=='EdGraph'
            # El export declara cada objeto DOS veces: un stub anidado con
            # Class=, y luego el bloque con props y pines SIN Class=. Ese
            # segundo bloque hay que reconocerlo por el nombre; si no, todos
            # los props y pines se pierden y los nodos salen vacios.
            if not cls and not padre_es_grafo and nm in graphs:
                stack[-1]=('EdGraph', nm); cls='EdGraph'
            if cls=='EdGraph':
                graphs.setdefault(nm, collections.OrderedDict())
            elif padre_es_grafo:
                gd=graphs[stack[-2][1]]
                if nm not in gd: gd[nm]={'class':cls,'props':{},'pins':[]}
                elif cls: gd[nm]['class']=cls
            continue
        if s.startswith('End Object'):
            if stack: stack.pop()
            continue
        if len(stack)<2 or stack[-2][0]!='EdGraph': continue
        node=graphs[stack[-2][1]][stack[-1][1]]
        m=PIN.match(s)
        if m:
            p=kv(m.group(1))
            if not any(q.get('PinId')==p.get('PinId') for q in node['pins']):
                node['pins'].append(p)
            continue
        m=re.match(r'([\w\.]+)=(.*)$', s)
        if m: node['props'][m.group(1)]=m.group(2)
    return graphs

def mem(props, key):
    mn=re.search(r'MemberName="?(\w+)', props.get(key,'')); return mn.group(1) if mn else '?'

def label(n):
    p=n['props']; c=n['class']
    if c=='K2Node_CustomEvent': return 'EVENT '+p.get('CustomFunctionName','?').strip('"')
    if c=='K2Node_Event': return 'EVENT(ovr) '+mem(p,'EventReference')
    if c=='K2Node_CallFunction':
        f=mem(p,'FunctionReference')
        return 'PRINT' if f=='PrintString' else 'call '+f
    if c=='K2Node_VariableSet': return 'SET '+mem(p,'VariableReference')
    if c=='K2Node_VariableGet': return 'get '+mem(p,'VariableReference')
    if c=='K2Node_IfThenElse': return 'BRANCH'
    if c=='K2Node_MacroInstance': return 'macro '+re.sub(r".*:(\w+)'.*",r'\1',p.get('MacroGraphReference',''))
    if c=='K2Node_Knot': return '(knot)'
    if c=='K2Node_DynamicCast': return 'CAST '+p.get('TargetType','?').split('.')[-1].strip('"\'')
    return c[7:] if c.startswith('K2Node_') else c

def index(g):
    owner={}
    for nm,n in g.items():
        for pin in n['pins']:
            pid=pin.get('PinId','').strip('"')
            if pid: owner.setdefault(pid, nm)
    return owner
