# Fatality Blast: The Last Survivor

Shooter táctico de supervivencia en tercera persona · Unreal Engine 5.7.4 · Imagine Studios

## Sinopsis

“Fatality Blast: The Last Survivor” es un shooter táctico de supervivencia en tercera persona enfocado en la
gestión de recursos en momentos críticos. El jugador se pone en los zapatos de Arthur, un sobreviviente de una
letal guerra global que busca encontrar un hogar pacífico alejado lo más posible de todo el conflicto.

Arthur no es un soldado: es un civil sin entrenamiento que despierta encerrado en una celda de una base militar
y tiene que escapar con lo puesto. Empieza con muy poco (10 balas, un botiquín y un escudo) y cada recurso
cuenta: disparar, curarse o cubrirse es siempre una decisión. Ese es el pilar del juego: **sobrevivir
gestionando recursos extremadamente escasos bajo presión**.

La demo contiene el **Nivel 1, «Infiltración de emergencia»**: un tutorial en las salas iniciales y la huida
por la base (patio de evacuación, barracones, sala de energía y muelle), con puertas que se abren con
terminales y tarjetas de acceso, y puntos de control.

### Qué se puede hacer

- **Combate con pocas balas**: cargador y reserva, recarga, más daño a la cabeza.
- **Inventario de 4 huecos**, uno por categoría: arma, lanzable, protección y curación. Al recoger un objeto de
  una categoría ocupada, el que llevas cae al suelo.
- **Curación**: el botiquín cura del todo pero te deja quieto; las vendas curan poco, dejan andar despacio y
  su curación es temporal.
- **Escudo**: frena los disparos de frente, se desgasta y, si bloqueas justo a tiempo (*parry*), no se desgasta.
- **Lanzables**: granada (daño por distancia y tras cobertura), granada cegadora (humo y aturdimiento) y
  frasco de veneno.
- **Enemigos con IA**: patrullan, te ven y te oyen (los disparos y explosiones hacen ruido), buscan
  cobertura, avisan por radio a su sector, la mitad de la escuadra flanquea y, si te pierden, te buscan.
- **Puntos de control**: se guardan solo cuando no hay enemigos cerca; al morir puedes reintentar desde el último.
- **Mando** (Xbox / XInput) en el juego y en todos los menús.

## Controles principales

- **Movimiento:** `WASD` o flechas *(mando: stick izquierdo)*
- **Agacharse:** Mantener `C` *(mando: `R3`)*
- **Saltar:** Barra espaciadora *(mando: `A`)*
- **Apuntar:** Mantener clic derecho *(mando: `LT`)*
- **Disparar / Lanzar:** Clic izquierdo mientras se apunta *(mando: `RT`)*
- **Recargar:** `R` *(mando: `RB`)*
- **Interactuar:** `E` *(mando: `X`)*
- **Selección de inventario:** `1`, `2`, `G` (escudo antibalas / parry con clic izquierdo) y `Q` (curación manteniendo clic izquierdo) *(mando: `Y`, cruceta arriba, `LB` y `B`)*
- **Soltar objeto:** `F` *(mando: cruceta abajo)*
- **Pausa:** `P` *(mando: botón Menú)* · En los menús, `Esc` o `B` vuelven atrás

## Aspectos técnicos mínimos

### Motor y plataforma

| | |
|---|---|
| Motor | **Unreal Engine 5.7.4** (`EngineAssociation` 5.7) |
| Plataforma | Windows 64 bits, DirectX 12 |
| Lenguaje | **Solo Blueprints**: el proyecto no tiene código C++ y no necesita Visual Studio para abrirse ni para empaquetarse |
| Plugins | `ModelingToolsEditorMode`, `PythonScriptPlugin` y `EditorScriptingUtilities`, los tres **solo de editor** |
| Resolución recomendada | 1920×1080 |

### Abrir el proyecto

1. Instalar Unreal Engine 5.7 desde el Epic Games Launcher.
2. Clonar el repositorio. Ocupa alrededor de **1,1 GB** de contenido.
3. Abrir `FatalityBlast.uproject`. La primera apertura compila los *shaders* y tarda varios minutos.
4. El editor abre el nivel 1. Para jugar desde el principio, abrir `Lvl_MainMenu` y pulsar *Play*.

### Mapas

| Mapa (`Content/ThirdPerson/`) | Qué es |
|---|---|
| `Lvl_MainMenu` | Menú principal: es el mapa con el que arranca el juego |
| `Lvl_01_MilitaryBase` | **El nivel 1**: tutorial y la base militar completa |
| `Lvl_02_TestLab` | Sala de pruebas (se entra desde el menú principal): una sala por sistema (IA, tiro, granadas, cobertura, animaciones, locomoción, curación y protección) |
| `Lvl_ThirdPerson` | *Grid* de pruebas original con los objetos sueltos |

### Empaquetar

Desde el editor: *Platforms → Windows → Package Project*. Tres cosas que hay que respetar:

- **Todo mapa al que se viaje tiene que estar en `+MapsToCook`** (`Config/DefaultGame.ini`). `OpenLevel` recibe
  el nombre del mapa como texto y el cocinador no sigue esa referencia: un mapa que falte ahí no existe en el
  build (el botón que lo abre «no hace nada»).
- **No activar plugins de juego** (que no sean solo de editor). Obligarían a compilar un ejecutable propio, y en
  una ruta con caracteres no ASCII (como `Producción`) esa compilación falla.
- **Rutas cortas**: la ruta cocinada de un asset no puede pasar de 260 caracteres. Un asset con más de ~140
  caracteres de ruta dentro de `Content/` rompe el cocinado.

### Requisitos del sistema (estimados, no medidos)

| | Mínimos | Recomendados |
|---|---|---|
| SO | Windows 10 64-bit | Windows 11 64-bit |
| CPU | 4 núcleos · 3.0 GHz | 6 núcleos · 3.6 GHz |
| RAM | 8 GB | 16 GB |
| GPU | GTX 1060 6 GB / RX 580 | RTX 2070 / RX 6700 |
| DirectX | 12 | 12 |
| Disco | 5 GB libres | SSD · 5 GB libres |

**Ejecución:** abrir el `.uproject` en Unreal Engine 5.7, o ejecutar el `.exe` del build empaquetado.

## Estructura del repositorio

| Carpeta | Contenido |
|---|---|
| `Content/ThirdPerson/Blueprints` | Personaje, enemigo (`BP_Grunt`), objetos, progresión del nivel, efectos y widgets del HUD |
| `Content/ThirdPerson/Components` | Sistemas reutilizables como componentes: vida, protección, curación, inventario, interacción y progresión |
| `Content/ThirdPerson/AI` | Controlador de la IA del soldado (percepción y máquina de estados) |
| `Content/Input` | Acciones y contextos de Enhanced Input (teclado, ratón y mando) |
| `Content/SafeZone`, `Content/Environment` | Ambientación del nivel |
| `Content/Audio` | Música y efectos de sonido |
| `Tools/` | Scripts de Python del editor: generan partes del nivel y de los Blueprints, y **bancos de pruebas automáticos** que juegan en PIE y acaban en `FALLOS: N` |
| `Config/` | Configuración del motor y del juego (mapas, entrada, mapas a empaquetar) |

## Créditos

- **Diana Sofia Benavides Monroy:** Creadora del juego y de la idea original del proyecto, diseño general, desarrollo de la programación base, implementación de sonidos y dirección de la propuesta.
- **Walter Fabián Silva Díaz:** Mejoras y complementos en programación, ajustes en el diseño de niveles, aportes en interfaz de usuario (UI) y tareas complementarias.
