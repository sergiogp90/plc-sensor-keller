# AGENTS.md — Programación ladder para FPWIN Pro 7 con generación de `.asc`

Guía para un agente (o persona) que tenga que desarrollar nuevas funcionalidades en este proyecto.
Todo lo que hay aquí se ha verificado en Control FPWIN Pro 7.7.4.1 con un PLC FP0R-C14MRS,
salvo donde se indique "sin verificar".

## 1. Contexto y flujo de trabajo

- **Entorno del usuario:** Windows 11, Control FPWIN Pro 7.7.4.1 (Panasonic), PLC **FP0R-C14MRS**
  (8 entradas X0–X7, 6 salidas relé Y0–Y5, puerto COM **RS485** integrado, 16k pasos).
  Pantalla HMI: Panasonic serie **GT** (modelo por confirmar), lee el PLC por MEWTOCOL.
- **FPWIN no tiene API.** Ni COM/automatización ni línea de comandos. El `.pro` es binario propietario:
  **nunca editarlo**. La única vía de integración es el formato de texto `.asc`
  (Proyecto > Exportar/Importar > Objetos).
- **Flujo acordado con el usuario:**
  1. El agente escribe/modifica un script Python en `herramientas/` que describe la lógica.
  2. El script genera un `.asc` autocontenido en la raíz del proyecto (p. ej. `keller.asc`).
  3. El usuario lo abre en FPWIN con **Proyecto > Nuevo > Desde archivo…**, compila y prueba
     (simulador o PLC). Este modo parte de cero y nunca produce conflictos.
  4. Si el usuario modifica algo a mano en FPWIN, exporta con **Proyecto > Exportar > Todos los Objetos**
     a un `.asc` y el agente lo lee para incorporar los cambios o aprender sintaxis nueva.
- **No usar Proyecto > Importar > Objetos** sobre un proyecto existente: es aditivo, no sobrescribe,
  y renombra los duplicados como `Nombre_!Conflicto1!` (provoca error de compilación).
- La fuente de verdad es el texto: los scripts de `herramientas/` y los `.asc`. El `.pro` es
  un artefacto regenerable.
- Comunicación con el usuario en **español**, con tildes correctas.

## 1b. Puesta en marcha en otro PC

- **Requisitos:** Python 3.10 o superior (el generador usa `str | None`); sin dependencias externas.
  Control FPWIN Pro 7 solo hace falta para abrir/compilar los `.asc`, no para generarlos.
- **Regenerar un programa:** `cd herramientas && python ejemplo_keller.py` → escribe `../keller.asc`.
- **Verificar el generador sin FPWIN:** ejecutar `python ejemplo_motor.py` y `python ejemplo_keller.py`;
  ambos deben terminar con "Generado: …". `ejemplo_motor.py` escribe en la carpeta temporal del sistema
  (o en la ruta que se le pase), **nunca en el proyecto**: la raíz solo debe contener los `.asc` reales. La validación real (dibujo y compilación) solo la da FPWIN.
- `catalogo_instrucciones.json` ya está generado y **no requiere** tener la ayuda offline instalada.
  Solo hace falta FPWIN instalado si se quiere regenerarlo con `construir_catalogo.py`
  (ruta de la ayuda en la sección 2) o consultar ejemplos LD de instrucciones nuevas.
- **Fuentes documentales usadas** (por si hay que volver a ellas):
  - Keller, *Communication protocol X-Line* v3.7 (registros Modbus, formato serie):
    https://us.keller-pressure.com/file-cache/website_component/5e2f286f9d8b1060a188c36a/manuals/1625167817459
  - Panasonic, *FP0R User's Manual* (puertos, modos de comunicación, referencias Modbus):
    https://mediap.industry.panasonic.eu/assets/download-files/import/mn_63489_0010_en_fp0r_hardware_europe.pdf
  - Panasonic InfoHub, `FP_MODBUS_MASTER` (parámetros):
    https://infohub.industry.panasonic.eu/data/fpwin/en/topics/t-0000017827.html
- El proyecto no está bajo control de versiones. Se recomienda `git init` en la raíz; el `.gitignore`
  incluido excluye `__pycache__/` y los binarios `.pro/.bak`, que son regenerables.

## 2. Archivos del proyecto

```
prueba/
├── AGENTS.md                      ← este documento (guía completa)
├── CLAUDE.md                      ← puntero a AGENTS.md (Claude Code carga CLAUDE.md automáticamente)
├── .gitignore
├── keller.asc                     ← programa actual generado (lectura Keller 33X)
└── herramientas/
    ├── fpwin_asc.py               ← GENERADOR: clases Var, Network, Program; render_project; write_asc
    ├── cabecera_fp0r.asc          ← cabecera de proyecto (tipo de PLC + registros de sistema) extraída
    │                                 de una exportación real; base de todo .asc generado
    ├── ejemplo_keller.py          ← programa real: presión y temperatura de un Keller 33X por Modbus RTU
    ├── ejemplo_motor.py           ← ejemplo didáctico validado (arranque/paro, TON, CTU, GT, SET/RESET)
    ├── construir_catalogo.py      ← extrae de la ayuda offline de FPWIN el catálogo de instrucciones
    ├── catalogo_instrucciones.json← 550 instrucciones: tipo de bloque, nombre .asc, pines, tamaño, params
    ├── ayuda_indice.json          ← índice título → html de la ayuda offline
    └── pines_ayuda.json           ← cadenas de pines de todos los bloques vistos en la ayuda
```

Ayuda offline de FPWIN (fuente de todo el catálogo; 3679 páginas HTML con ejemplos LD en sintaxis `.asc`):
`C:\Program Files (x86)\Panasonic Industry Control\Control FPWIN Pro 7\OfflineHelp\src\data\fpwin\es\topics\`
Para buscar cualquier instrucción: `grep`/`python` sobre esos HTML, o `catalogo_instrucciones.json`.

## 3. Formato `.asc` (descifrado y verificado)

- **Codificación:** UTF-16LE con BOM `FF FE`, saltos de línea CRLF. `write_asc()` ya lo hace.
- **Estructura del archivo autocontenido:**
  1. Cabecera `BEGIN_OBJECT PROJECT … END_OBJECT PROJECT` + `PLC_CONFIG/END_PLC_CONFIG`
     (tipo de PLC, registros de sistema, parámetros de comunicación PC↔PLC). Se copia de `cabecera_fp0r.asc`.
  2. Uno o más bloques `PROGRAM Nombre … END_PROGRAM` (cabecera de variables + cuerpo LD).
  3. `CONFIGURATION scConfiguration` con `VAR_GLOBAL`, la lista de `TASK` y
     `PROGRAM X WITH Programs: scProgramType` por cada programa. **Todo programa listado en una tarea
     debe existir en el archivo** (si no: error T_C5045 "nombre no válido").
- **Declaraciones:** `nombre AT %IX0.0: BOOL:=FALSE;` Direcciones IEC del FP0R:
  `%IX0.n` = Xn, `%QX0.n` = Yn, `%MX0.w.b` = R (relé interno, palabra w bit b), `%MW5.n` = DTn,
  `%MD5.n` = DDTn (doble palabra/REAL en DTn–DTn+1). Arrays: `ARRAY [0..3] OF WORD:=[4(0)]`.
  Bloques de función se declaran como variables locales: `T_Listo: TON;`, `C_Errores: CTU;`.
  Cada sección VAR termina con la línea literal `@'': @'';` antes de `END_VAR` (conservarla).
- **Los identificadores NO distinguen mayúsculas/minúsculas.** `T_Listo` y `t_Listo` colisionan
  (FPWIN renombra uno a `_!Conflicto1!`). `check_names()` lo detecta.
- **Red LD:** cuadrícula de celdas. Barra izquierda en x=1 con `L(1,0,1,ALTO)`. Elementos:

| Elemento | Sintaxis | Notas |
|---|---|---|
| Contacto | `B(B_CONTACT,,var,x1,y1,x2,y2,MOD);` | 2×2 celdas; hilo en la fila central. MOD: `` NO, `N` NC, `R` flanco subida (DF), `F` flanco bajada |
| Bobina | `B(B_COIL,,var,37,y1,39,y2,MOD);` | columna 37; MOD: `` normal, `S` SET, `E` RESET |
| Función | `B(B_F,Nombre!,,x1,y1,x2,y2,,PINES);` | `?D` entrada, `?H` entrada solo constante, `?C`/`?A` salida, `?DEN`/`?AENO` |
| Bloque de función | `B(B_FB,Tipo!,Instancia,x1,y1,x2,y2,,PINES);` | **campo 2 = tipo, campo 3 = instancia**; `?B` entrada, `?A` salida |
| Variable a pin | `B(B_VARIN,,var,x1,y1,x2,y2,);` / `B(B_VAROUT,,…)` | 2×2, pegada al bloque, centrada en la fila del pin |
| Comentario | `B(B_COMMENT,,texto,x1,y1,x2,y2,);` | **sin comas** en el texto (la coma separa campos) |
| Línea | `L(x1,y1,x2,y2);` | horizontal o vertical; sin segmentos de longitud cero |

- **Pines de un bloque:** ocupan las últimas filas del bloque, uno por fila, en el orden de la cadena
  de pines. Cabecera de 2 filas si algún pin tiene nombre (TON, CTU, E_MOVE, DF…), de 1 fila si todos
  son anónimos (`MOVE ?D?C`, `@GT-2 ?D?D?C`). Alto = cabecera + max(n_entradas, n_salidas).
- **Operadores IEC** llevan `@` y número de entradas en el nombre `.asc`: `@GT-2`, `@ADD-2`, `@AND-2`…
  Las variantes con EN/ENO se llaman `E_ADD-2`, `E_MOVE`, etc.
- **Textos:** `NETWORK_TITLE` **pierde los espacios** al importar (limitación de FPWIN; aparcado por el
  usuario). Los comentarios `B_COMMENT` sí conservan espacios, pero no admiten comas.
- **Solape de direcciones:** dos globales pueden compartir dirección (`REAL AT %MD5.202` y
  `ARRAY OF WORD AT %MW5.202`). FPWIN da una **advertencia**, no error. Es la técnica para
  reinterpretar palabras como REAL. Verificado en simulador.

### Registros de sistema del puerto COM (FP0R) — verificados

| Reg. | Valor | Significado |
|---|---|---|
| 412 | 0 / **64** | MEWTOCOL-COM / **Modbus RTU Maestro-Esclavo** |
| 413 | 771 / **259** | 8 bits paridad impar 1 stop / **8 bits sin paridad 1 stop** |
| 415 | 102 / **38** | 115200 / **9600** baudios |

`set_system_registers(header, {412: 64, 413: 259, 415: 38})` los fija en la cabecera. Constantes
`COM_MODBUS_RTU_MAESTRO`, `COM_FORMATO_8N1`, `COM_BAUD` en `fpwin_asc.py`.
El puerto COM del FP0R es **COM1** para las instrucciones (`SYS_COM1_PORT`) y sus banderas son
`sys_bIsComPort1F145F146NotActive`, `sys_bIsComPort1F145F146Error`, `sys_bIsComPort1MasterCommunication`.

## 4. API del generador (`herramientas/fpwin_asc.py`)

```python
from fpwin_asc import (Var, Network, Program, read_export, render_project, write_asc,
                       check_names, set_system_registers, COM_MODBUS_RTU_MAESTRO, COM_FORMATO_8N1, COM_BAUD)

header, _, _ = read_export("herramientas/cabecera_fp0r.asc")      # cabecera del proyecto
header = set_system_registers(header, {**COM_MODBUS_RTU_MAESTRO, **COM_FORMATO_8N1, 415: COM_BAUD[9600]})

gvl = [Var("Marcha", "BOOL", "%IX0.0"), Var("nCiclos", "INT", "%MW5.0", init="0"),
       Var("rPresion", "REAL", "%MD5.202", init="0.0")]

red = Network(title="Sin comas ni acentos", row=3)   # row>=3 si la red lleva bloques con cabecera de 2 filas
red.comment("Texto sin comas")                       # si va primero, desplaza el hilo 2 filas hacia abajo
red.contact("Marcha")                                # NO   | .contact_nc(v) NC | .df(v) flanco ↑ | .df_neg(v) flanco ↓
red.parallel_contact("Motor", from_x=1)              # rama en paralelo desde la barra hasta la posición actual
red.ton("T1", "tiempoPreset", "tiempoTranscurrido")  # TON: IN desde el hilo, Q sigue por el hilo
red.ctu("C1", pv="3", reset_var="Reset", cv_var="nCiclos")
red.compare("GT", "nCiclos", "2")                    # GT/GE/EQ/NE/LT/LE al inicio del hilo (su salida es la condición)
red.block("E_MOVE", entradas={"D1": "a"}, salidas={"C1": "b"})          # genérico: pines anónimos = D1,D2…/C1,C2…
red.block("FP_MODBUS_MASTER", entradas={"Port": "SYS_COM1_PORT", ...}, salidas={"Result": "w"})
red.coil("Motor")  # .coil_set(v) SET | .coil_reset(v) RESET | .parallel_coil(v, "E", sep=3) segunda bobina en paralelo
red.parallel_block("E_MOVE", entradas={"D1": "c"}, salidas={"C1": "d"})  # rama bajo el último bloque, misma condición

prog = Program(name="MiPrograma", externals=["Marcha", "nCiclos"],       # globales usadas
               locals=[Var("T1", "TON"), Var("tiempoPreset", "TIME", init="T#5s")],
               networks=[red])
assert not check_names([prog], gvl)                  # colisiones de nombre sin distinguir mayúsculas
write_asc("salida.asc", render_project(header, [prog], gvl))
```

- `block(nombre, …)` busca `nombre` primero en `OPERADORES` (operadores IEC, E_*, FP_MODBUS_MASTER)
  y después en `catalogo_instrucciones.json` (550 instrucciones con su cadena de pines).
  `hilo_in`/`hilo_out` eligen qué pin recibe/continúa el hilo (por defecto el primero de cada lado;
  `""` para ninguno).
- **Espaciado automático según los rótulos** (desde 19-09-2026). FPWIN dibuja el nombre de cada
  elemento como texto libre: centrado sobre un contacto o bobina, a la izquierda del conector de un
  `B_VARIN` (alineado a la derecha) y a la derecha del de un `B_VAROUT`. Si dos textos caen en la misma
  fila se pisan (era el caso de `keller.asc`: contactos `sys_*` seguidos y E_MOVE encadenados).
  El generador estima el ancho en celdas con `ancho_texto()` (≈2.8 caracteres por celda en fuente
  normal; ≈4.5 para variables `sys_*`/`SYS_*`, que FPWIN dibuja en fuente pequeña con su comentario)
  y lleva por fila la última columna ocupada (`Network._ocupado`). `contact()` y `block()` desplazan
  el elemento a la derecha lo justo para que su rótulo no pise al anterior; los rótulos de entrada de
  un bloque tampoco invaden la zona de los contactos. Las constantes están en `CHARS_PER_CELL` y
  `CHARS_PER_CELL_SYS`: ajustarlas si en pantalla siguen viéndose solapes o huecos excesivos.
- Ancho útil de una red: el hilo debe llegar a la bobina en x=37; si no cabe, `contact()`/`block()`/`coil()`
  lanzan `ValueError` con el nombre de la red. Cada contacto ocupa como mínimo 4 columnas, cada bloque
  `gap(6)+ancho` más lo que exijan sus rótulos. Dos bloques con rótulos largos **no caben encadenados**:
  usar `parallel_block()` (rama bajo el bloque anterior, alimentada por el mismo nodo, sin continuar el
  hilo; patrón de `ejemplo_keller.py` redes 3 y 4) o repartir en varias redes con una variable BOOL
  intermedia (pulso `bNuevaLectura`).
- `parallel_coil(v, mod, sep=2)`: `sep=2` es el paso nativo de FPWIN (el rótulo de la segunda bobina
  queda pegado a la primera); `sep=3` deja una fila libre y se lee mejor.

## 5. Procedimiento para una funcionalidad nueva

1. **Aclarar E/S y direcciones** con el usuario (X, Y, DT que usará la pantalla GT).
2. **Comprobar cada instrucción nueva** en `catalogo_instrucciones.json`. Si no está o no tiene
   `pines`, **no inventar la cadena de pines**: pedir al usuario que coloque la instrucción en una red
   (aunque quede sin conectar) y exporte con Todos los Objetos; copiar la cadena exacta a `OPERADORES`.
   Ejemplo real: la estimación de `FP_MODBUS_MASTER` falló (error C2004 "la cabecera ha cambiado")
   hasta ver la exportación (`?H` y `?AResult`).
3. Escribir el script en `herramientas/`, ejecutar `check_names`, generar el `.asc`.
4. Pedir al usuario: abrir con **Nuevo > Desde archivo**, compilar, y pegar código + texto de cada error.
   Errores conocidos: `C2004` (pines de bloque incorrectos), `T_C5045` (programa en tarea que no
   existe), `_!Conflicto1!` (nombres duplicados o importación aditiva).
5. Para lógica sin hardware, incluir un **contacto de prueba en paralelo** con la condición real
   (p. ej. `bPruebaSwap`, retirarlo antes de la entrega) y dar al usuario valores concretos a forzar en el **simulador de PLC**
   (activado por registro `IsPlcSimulationEnabled`). El simulador ejecuta la lógica pero **no simula
   puertos serie** ni sus banderas.
6. Cuando el usuario exporte su versión, leer el `.asc` (decodificar UTF-16) para detectar cambios y
   aprender sintaxis nueva; actualizar esta guía si se descubre algo.

## 6. Proyecto en curso: transmisor de presión KELLER 33X (`ejemplo_keller.py` → `keller.asc`)

- **Sensor:** Keller serie 33X (PR-33X), RS485 half-duplex, protocolo X-Line v3.7. Keller bus y
  **Modbus RTU** activos simultáneamente, sin configurar nada. Dirección 1, **9600 baud, 8N1**.
- **Registros Modbus (FC03, float32 IEEE754, palabra ALTA primero):**
  - `0x0002` P1 [bar], `0x0008` TOB1 [°C] — compatibles con cualquier firmware (máx. 2–4 registros por
    petición en firmware antiguo).
  - **`0x0100` P1 + `0x0102` TOB1** en una sola lectura de 4 palabras — requiere firmware ≥ 5.20-10.40.
    **Es lo que usa el programa actual.** Si el sensor devolviera error/ceros, pasar a dos peticiones.
  - Vectores de prueba del manual: `3F75 E3D2 41B6 1C20` → 0.9605 bar y 22.76 °C (validado en simulador).
- **El FP0R guarda REAL con la palabra BAJA primero** → hay que intercambiar palabras (E_MOVE cruzados
  a un array que solapa el REAL). Validado en simulador: 0.9607 / 0.9605 / 22.76 correctos.
- **Cableado:** FP0R-C14MRS tiene RS485 en el puerto COM (bornes + y −, malla a tierra). Sin conversor.
- **Mapa de variables para la pantalla GT:**

| Variable | Tipo | Dirección FP | Contenido |
|---|---|---|---|
| `rPresionBar` | REAL | DT202–203 | Presión P1 [bar] |
| `rTemperaturaC` | REAL | DT204–205 | Temperatura TOB1 [°C] |
| `awKellerRaw` | ARRAY[0..3] OF WORD | DT190–193 | Respuesta Modbus cruda |
| `awKellerSwap` | ARRAY[0..3] OF WORD | DT202–205 | Palabras reordenadas (solapa los REAL) |
| `bKellerOK` / `bKellerError` | BOOL | R100 / R101 | Estado de la comunicación |
| `nErroresKeller` | INT | DT210 | Errores acumulados |
| `iKellerAddr` | INT | DT211 | Dirección Modbus del sensor (1) |

- **Estado:** compila sin errores (1 advertencia de solape esperada), conversión validada en simulador.
  Versión del 19-09-2026 con el espaciado automático y los E_MOVE en rama paralela: **verificada
  visualmente en FPWIN** (sin solapes en las 5 redes).
  El contacto de prueba `bPruebaSwap` ya se ha retirado del programa; cómo reponerlo está comentado en
  `ejemplo_keller.py` (red 2). **Pendiente:** prueba con el sensor real.

## 7. Ideas acordadas para más adelante

- Empaquetar el generador como **servidor MCP** (herramientas: crear variables/redes/programas, leer
  exportaciones) y, opcionalmente, automatización de la GUI de FPWIN (pywinauto) y comunicación
  **MEWTOCOL** directa con el PLC para monitorizar/forzar variables.
- Si se necesita ST en vez de LD: FPWIN importa POUs `.st` (nivel de reutilización PLCopen), aún sin probar.
