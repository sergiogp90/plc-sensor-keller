"""
Generador de archivos .asc para Control FPWIN Pro 7 (PLC FP0R-C14).

El .asc es texto UTF-16LE con BOM y CRLF. Cada red LD se describe en una
cuadricula: la barra izquierda esta en x=1, los contactos ocupan 2x2 celdas,
la bobina va en x=37..39 y las conexiones se dibujan con segmentos L(x1,y1,x2,y2).

Sintaxis verificada (exportacion real + ejemplos LD de la ayuda offline):
  B(B_CONTACT,,var,x1,y1,x2,y2,MOD)   MOD: '' NO | N negado | R flanco subida | F flanco bajada
  B(B_COIL,,var,x1,y1,x2,y2,MOD)      MOD: '' normal | S set | E reset
  B(B_F,Nombre!,,x1,y1,x2,y2,,?Dp1?Dp2?Cq)          funcion: ?D entrada, ?H entrada solo constante,
                                                    ?C/?A salida (EN/ENO: ?DEN ?AENO)
  Textos (comentarios, titulos): sin comas; los titulos pierden los espacios al importar.
  B(B_FB,Tipo!,Instancia,x1,y1,x2,y2,,?Bp?Aq)       bloque de funcion: ?B entrada, ?A salida
  B(B_VARIN,,var,x1,y1,x2,y2,)  B(B_VAROUT,,var,...)  B(B_COMMENT,,texto,...)
  Pines de un bloque: uno por fila tras la cabecera (1 fila si pines anonimos, 2 si tienen nombre).
  Los identificadores NO distinguen mayusculas/minusculas.
"""
import json
import math
import os
import re
import time
from dataclasses import dataclass, field

COIL_X = 37          # columna de la bobina
CELL = 2             # ancho de contacto

# Estimacion del ancho que ocupa un texto en celdas de la cuadricula (medido sobre capturas de FPWIN 7.7.4):
# nombres de variable en fuente normal ~2.8 caracteres por celda; las variables de sistema (sys_*, SYS_*)
# se dibujan en fuente pequena junto con su comentario, ~4.5 caracteres por celda.
CHARS_PER_CELL = 2.8
CHARS_PER_CELL_SYS = 4.5


def ancho_texto(texto):
    """Ancho aproximado (en celdas, float) del rotulo de una variable o constante en el editor LD."""
    cpc = CHARS_PER_CELL_SYS if texto.lower().startswith("sys_") else CHARS_PER_CELL
    return len(texto) / cpc

_CAT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalogo_instrucciones.json")
CATALOGO = json.load(open(_CAT_PATH, encoding="utf-8")) if os.path.exists(_CAT_PATH) else {}

# Operadores IEC estandar que la ayuda documenta solo por su sintaxis en los ejemplos.
# Clave: nombre logico. Valor: (tipo de bloque, nombre en el .asc, pines, ancho)
OPERADORES = {
    "GT": ("B_F", "@GT-2", "?D?D?C", 5), "GE": ("B_F", "@GE-2", "?D?D?C", 5),
    "EQ": ("B_F", "@EQ-2", "?D?D?C", 5), "NE": ("B_F", "@NE", "?D?D?C", 5),
    "LT": ("B_F", "@LT-2", "?D?D?C", 5), "LE": ("B_F", "@LE-2", "?D?D?C", 5),
    "ADD": ("B_F", "@ADD-2", "?D?D?C", 5), "SUB": ("B_F", "@SUB-2", "?D?D?C", 5),
    "MUL": ("B_F", "@MUL-2", "?D?D?C", 5), "DIV": ("B_F", "@DIV-2", "?D?D?C", 5),
    "AND": ("B_F", "@AND-2", "?D?D?C", 5), "OR": ("B_F", "@OR-2", "?D?D?C", 5),
    "XOR": ("B_F", "@XOR-2", "?D?D?C", 5), "NOT": ("B_F", "NOT", "?D?C", 5),
    "MOVE": ("B_F", "MOVE", "?D?C", 5),
    # variantes con EN/ENO (se activan desde el hilo)
    "E_GT": ("B_F", "E_GT-2", "?DEN?D?D?AENO?C", 6), "E_EQ": ("B_F", "E_EQ-2", "?DEN?D?D?AENO?C", 6),
    "E_ADD": ("B_F", "E_ADD-2", "?DEN?D?D?AENO?C", 6), "E_SUB": ("B_F", "E_SUB", "?DEN?D?D?AENO?C", 6),
    "E_MUL": ("B_F", "E_MUL-2", "?DEN?D?D?AENO?C", 6), "E_DIV": ("B_F", "E_DIV", "?DEN?D?D?AENO?C", 6),
    "E_MOVE": ("B_F", "E_MOVE", "?DEN?D?AENO?C", 6),
    # Modbus RTU maestro (FP0R/FP-X/FP0H/FP7). VERIFICADO con exportacion real de FPWIN 7.7.4:
    # '?H' = entrada que solo admite constante (FunctionCode*, NumberOfRegisters*); Result sale como '?A'.
    "FP_MODBUS_MASTER": ("B_F", "FP_MODBUS_MASTER",
                         "?DEN?DPort?DSlaveAddress?HFunctionCode?DStartRegister?HNumberOfRegisters?DMasterData?AENO?AResult", 11),
    "F145F146_MODBUS_MASTER": ("B_F", "F145F146_MODBUS_MASTER",
                               "?DEN?DPort?DSlaveAddress?HFunctionCode?DStartRegister?HNumberOfRegisters?DMasterData?AENO", 14),
}


def info_instruccion(nombre):
    """Devuelve (tipo_bloque, nombre_asc, pines, ancho) desde OPERADORES o el catalogo."""
    if nombre in OPERADORES:
        return OPERADORES[nombre]
    e = CATALOGO.get(nombre)
    if not e or not e.get("pines"):
        raise KeyError(f"Instruccion '{nombre}' no esta en el catalogo; exporta una muestra desde FPWIN.")
    return e["bloque"], e["nombre_asc"], e["pines"], e["ancho"] or 5


def parse_pines(pines):
    """'?BIN?BPT?AQ?AET' -> (['IN','PT'], ['Q','ET']). Pines sin nombre ('?D') se numeran D1, D2..."""
    ins, outs = [], []
    anon = {"D": 0, "C": 0, "B": 0, "A": 0, "H": 0}
    for p in pines.split("?")[1:]:
        lado = ins if p[0] in "BDH" else outs      # H: entrada solo constante
        if p[1:]:
            lado.append(p[1:])
        else:                                   # pin anonimo: D1, D2... / C1, C2...
            anon[p[0]] += 1
            lado.append(f"{p[0]}{anon[p[0]]}")
    return ins, outs


@dataclass
class Var:
    name: str
    typ: str = "BOOL"
    addr: str | None = None      # direccion IEC, p.ej. %IX0.0 (X0), %QX0.0 (Y0), %MW5.0 (DT0)
    init: str | None = None
    comment: str = ""

    def decl(self, with_addr=True):
        at = f" AT {self.addr}" if (self.addr and with_addr) else ""
        if self.init is not None:
            init = f":={self.init}"
        elif self.typ == "BOOL":
            init = ":=FALSE"
        else:
            init = ""
        return f"{self.name}{at}: {self.typ}{init};"


class Network:
    """Una red ladder. Los metodos devuelven self para encadenar."""

    def __init__(self, title="", label="", row=2):
        self.title, self.label = title, label
        self.blocks, self.lines = [], []
        self.x = 1          # columna actual del hilo principal
        self.y = row        # fila del hilo principal (usar >=3 si la red lleva bloques)
        self.height = row + 3
        # Columna mas a la derecha ya ocupada por texto en cada fila. Sirve para que los rotulos
        # (nombre sobre un contacto, variable de un pin) no pisen al elemento anterior.
        self._ocupado = {}
        self._x_contactos = -99.0   # columna donde acaba el ultimo contacto: los rotulos no la invaden
        self._ultimo_bloque = None  # geometria del ultimo bloque del hilo (para parallel_block)

    # --- control de solapes ---------------------------------------------------
    def _libre(self, fila):
        """Ultima columna ocupada por texto en la fila (los rotulos pueden salirse por la izquierda)."""
        return max(self._ocupado.get(fila, -99.0), self._x_contactos)

    def _reservar(self, fila, x_der):
        self._ocupado[fila] = max(self._ocupado.get(fila, -99.0), x_der)

    def _comprobar_ancho(self, x_fin):
        if x_fin > COIL_X:
            raise ValueError(f"Red '{self.title}': el hilo llega a x={x_fin} y la bobina esta en x={COIL_X}. "
                             "Reparte la logica en varias redes (variable BOOL intermedia).")

    # --- contactos y bobinas ------------------------------------------------
    def contact(self, var, mod=""):
        """mod: '' NO, 'N' negado (NC), 'R' flanco de subida (DF), 'F' flanco de bajada (DF/)."""
        x = self._x_contacto(var, self.x + 2, self.y - 1)
        self.blocks.append(f"B(B_CONTACT,,{var},{x},{self.y-1},{x+CELL},{self.y+1},{mod});")
        self.lines.append(f"L({self.x},{self.y},{x},{self.y});")
        self.x = x + CELL
        self._x_contactos = self.x
        self._comprobar_ancho(self.x)
        return self

    def _x_contacto(self, var, x_min, fila_rotulo):
        """Columna del contacto: la minima que deja su rotulo (centrado sobre el simbolo) sin pisar
        el texto anterior de esa fila. Reserva el espacio que ocupa el rotulo."""
        w = ancho_texto(var)
        x = max(x_min, math.ceil(self._libre(fila_rotulo) + 1 + w / 2 - 1))
        self._reservar(fila_rotulo, x + 1 + w / 2)
        self._reservar(fila_rotulo + 1, x + CELL)
        return x

    def contact_nc(self, var):
        return self.contact(var, "N")

    def df(self, var):
        """Contacto con deteccion de flanco de subida (DF)."""
        return self.contact(var, "R")

    def df_neg(self, var):
        """Contacto con deteccion de flanco de bajada (DF/)."""
        return self.contact(var, "F")

    def parallel_contact(self, var, from_x=1, mod=""):
        """Contacto en paralelo con el tramo entre from_x y la posicion actual (realimentacion)."""
        y = self.y + 2
        x = from_x + 2
        self._reservar(y - 1, x + 1 + ancho_texto(var) / 2)
        self.blocks.append(f"B(B_CONTACT,,{var},{x},{y-1},{x+CELL},{y+1},{mod});")
        self.lines.append(f"L({from_x},{y},{x},{y});")
        self.lines.append(f"L({x+CELL},{y},{self.x},{y});")
        self.lines.append(f"L({self.x},{self.y},{self.x},{y});")   # union vertical
        self.height = max(self.height, y + 3)
        return self

    def coil(self, var, mod=""):
        """mod: '' normal, 'S' SET, 'E' RESET."""
        self._comprobar_ancho(self.x)
        self.blocks.append(f"B(B_COIL,,{var},{COIL_X},{self.y-1},{COIL_X+CELL},{self.y+1},{mod});")
        self.lines.append(f"L({self.x},{self.y},{COIL_X},{self.y});")
        self.x = COIL_X + CELL
        return self

    def coil_set(self, var):
        return self.coil(var, "S")

    def coil_reset(self, var):
        return self.coil(var, "E")

    def parallel_coil(self, var, mod="", sep=2):
        """Segunda bobina en paralelo con la anterior (misma condicion).
        sep: filas entre bobinas; 2 es el paso nativo de FPWIN, 3 deja una fila libre para el rotulo."""
        y = self.y + sep
        self.blocks.append(f"B(B_COIL,,{var},{COIL_X},{y-1},{COIL_X+CELL},{y+1},{mod});")
        self.lines.append(f"L({COIL_X},{self.y},{COIL_X},{y});")
        self.height = max(self.height, y + 3)
        return self

    # --- bloques (funciones y bloques de funcion) ----------------------------
    def block(self, nombre, instancia="", entradas=None, salidas=None, hilo_in=None, hilo_out=None, gap=6):
        """Inserta una funcion (B_F) o bloque de funcion (B_FB) en el hilo.

        nombre:    nombre logico (TON, CTU, GT, E_ADD, DF, MOVE, F-instruccion...).
        instancia: nombre de la variable instancia (solo B_FB).
        entradas:  {pin: variable_o_constante}; el pin hilo_in se alimenta del hilo.
        salidas:   {pin: variable}; el pin hilo_out continua el hilo hacia la derecha.
        hilo_in / hilo_out: por defecto el primer pin de entrada y de salida; '' para ninguno.
        gap:       separacion minima entre el final del hilo y el bloque; se amplia sola si algun
                   rotulo de entrada pisaria un texto anterior de su fila.
        """
        b = self._preparar_bloque(nombre, instancia, entradas, salidas, hilo_in, hilo_out)
        y1 = self.y - b["hdr"]
        if y1 < 0:
            raise ValueError("La fila del hilo debe ser >= 2 para colocar un bloque (usa Network(row=3)).")
        x1 = self._x_bloque(b, y1, self.x + gap)
        self._colocar_bloque(b, x1, y1, self.x)
        self._ultimo_bloque = {"x_in": self.x, "x1": x1, "y2": y1 + b["alto"]}
        self.x = x1 + b["ancho"]
        self._comprobar_ancho(self.x)
        return self

    def parallel_block(self, nombre, instancia="", entradas=None, salidas=None, hilo_in=None, sep=1):
        """Bloque en una rama paralela debajo del ultimo bloque del hilo, alimentado por la misma
        condicion (el nodo justo antes de ese bloque). No continua el hilo: sus salidas solo pueden
        ir a variables. Es la forma legible de poner varios E_MOVE con la misma condicion, en vez
        de encadenarlos en horizontal (no caben los rotulos).
        sep: filas libres entre el bloque anterior y este."""
        ub = self._ultimo_bloque
        if ub is None:
            raise ValueError("parallel_block requiere un block() previo en la misma red.")
        b = self._preparar_bloque(nombre, instancia, entradas, salidas, hilo_in, "")
        y1 = ub["y2"] + sep + (1 if instancia else 0)     # sitio para el nombre de instancia
        y_hilo = y1 + b["hdr"]
        x1 = self._x_bloque(b, y1, ub["x1"])
        self.lines.append(f"L({ub['x_in']},{self.y},{ub['x_in']},{y_hilo});")   # bajada desde el nodo
        self._colocar_bloque(b, x1, y1, ub["x_in"])
        self._ultimo_bloque = {"x_in": ub["x_in"], "x1": x1, "y2": y1 + b["alto"]}
        return self

    def _preparar_bloque(self, nombre, instancia, entradas, salidas, hilo_in, hilo_out):
        entradas, salidas = entradas or {}, salidas or {}
        tipo, asc, pines, ancho = info_instruccion(nombre)
        ins, outs = parse_pines(pines)
        hilo_in = hilo_in if hilo_in is not None else (ins[0] if ins else "")
        hilo_out = hilo_out if hilo_out is not None else (outs[0] if outs else "")
        for p in list(entradas) + list(salidas):
            if p not in ins + outs:
                raise KeyError(f"{nombre}: el pin '{p}' no existe. Pines: {ins} -> {outs}")
        # Cabecera del bloque: 1 fila si todos los pines son anonimos (MOVE, @GT-2, @ADD-2),
        # 2 filas si algun pin tiene nombre (TON, CTU, E_MOVE, SHL, DF...). Verificado en la ayuda.
        # Los pines ocupan las filas siguientes, uno por fila (verificado en ejemplos de la ayuda).
        hdr = 1 if all(len(x) == 1 for x in pines.split("?")[1:]) else 2
        return dict(tipo=tipo, asc=asc, pines=pines, ancho=ancho, ins=ins, outs=outs, hdr=hdr,
                    alto=hdr + max(len(ins), len(outs), 1), instancia=instancia,
                    entradas=entradas, salidas=salidas, hilo_in=hilo_in, hilo_out=hilo_out)

    def _x_bloque(self, b, y1, x_min):
        """Columna izquierda del bloque: x_min ampliado si algun rotulo de entrada (B_VARIN, texto
        alineado a la derecha delante de un conector de 2 celdas) pisaria un texto anterior de su
        fila, o si el nombre de instancia (centrado sobre el bloque) pisaria el rotulo de un contacto."""
        x1 = x_min
        for i, p in enumerate(b["ins"]):
            if p != b["hilo_in"] and p in b["entradas"]:
                fila = y1 + b["hdr"] + i
                x1 = max(x1, math.ceil(self._libre(fila) + 3 + ancho_texto(b["entradas"][p])))
        if b["instancia"]:
            x1 = max(x1, math.ceil(self._libre(y1 - 1) + 1 + ancho_texto(b["instancia"]) / 2 - b["ancho"] / 2))
        return x1

    def _colocar_bloque(self, b, x1, y1, x_desde):
        """Emite el bloque en (x1, y1), el hilo de entrada desde x_desde y sus B_VARIN / B_VAROUT."""
        x2, hdr = x1 + b["ancho"], b["hdr"]
        self.blocks.append(f"B({b['tipo']},{b['asc']}!,{b['instancia']},{x1},{y1},{x2},{y1+b['alto']},,{b['pines']});")
        if b["instancia"]:
            self._reservar(y1 - 1, x1 + b["ancho"] / 2 + ancho_texto(b["instancia"]) / 2)
        for f in range(y1, y1 + b["alto"] + 1):
            self._reservar(f, x2)
        for i, p in enumerate(b["ins"]):
            fila = y1 + hdr + i
            if p == b["hilo_in"]:
                self.lines.append(f"L({x_desde},{fila},{x1},{fila});")
            elif p in b["entradas"]:
                self.blocks.append(f"B(B_VARIN,,{b['entradas'][p]},{x1-2},{fila-1},{x1},{fila+1},);")
        for i, p in enumerate(b["outs"]):
            fila = y1 + hdr + i
            if p != b["hilo_out"] and p in b["salidas"]:
                self.blocks.append(f"B(B_VAROUT,,{b['salidas'][p]},{x2},{fila-1},{x2+2},{fila+1},);")
                self._reservar(fila, x2 + 2 + ancho_texto(b["salidas"][p]))
        self.height = max(self.height, y1 + b["alto"] + 2)

    def ton(self, instance, pt_var, et_var=None):
        return self.block("TON", instance, {"PT": pt_var}, {"ET": et_var} if et_var else {})

    def ctu(self, instance, pv, reset_var=None, cv_var=None):
        ent = {"PV": pv}
        if reset_var:
            ent["R"] = reset_var
        return self.block("CTU", instance, ent, {"CV": cv_var} if cv_var else {})

    def compare(self, op, a, b):
        """Comparacion sin EN (GT, GE, EQ, NE, LT, LE) al inicio del hilo: su salida BOOL es la condicion."""
        return self.block(op, "", {"D1": a, "D2": b}, hilo_in="", gap=4)

    # --- comentario ------------------------------------------------------------
    def comment(self, text, x1=None, y1=None, width=None):
        """Comentario libre dentro de la red (por defecto en la fila superior, a la derecha del hilo)."""
        # La coma separa los campos de B(...): FPWIN trunca el comentario en la primera coma.
        text = text.replace(",", ";")
        x1 = x1 if x1 is not None else self.x + 2
        y1 = y1 if y1 is not None else 0
        width = width or max(10, len(text) // 2)
        self.blocks.append(f"B(B_COMMENT,,{text},{x1},{y1},{x1+width},{y1+1},);")
        # Si la red aun esta vacia, el comentario reserva las filas superiores y el hilo baja
        # (evita que pise el nombre de instancia que FPWIN dibuja encima de los bloques).
        if y1 == 0 and not self.lines and len(self.blocks) == 1:
            self.y += 2
            self.height += 2
        return self

    # --- salida ------------------------------------------------------------
    def render(self):
        rail = f"L(1,0,1,{self.height});"
        lines = [l for l in self.lines if not re.fullmatch(r"L\((\d+),(\d+),\1,\2\);", l)]
        body = "\r\n".join([*self.blocks, rail, *lines])
        return (
            "    NET_WORK\r\n"
            "        NETWORK_TYPE := NWTYPELD ;\r\n"
            f"        NETWORK_LABEL := {self.label} ;\r\n"
            f"        NETWORK_TITLE := {self.title} ;\r\n"
            f"        NETWORK_HEIGHT := {self.height} ;\r\n"
            "        NETWORK_BODY\r\n"
            f"{body}\r\n"
            "        END_NETWORK_BODY\r\n"
            "    END_NET_WORK"
        )


EMPTY_NET = (
    "    NET_WORK\r\n        NETWORK_TYPE := NWTYPELD ;\r\n        NETWORK_LABEL :=  ;\r\n"
    "        NETWORK_TITLE :=  ;\r\n        NETWORK_HEIGHT := 6 ;\r\n        NETWORK_BODY\r\n"
    "L(1,0,1,6);\r\n        END_NETWORK_BODY\r\n    END_NET_WORK\r\n"
)


@dataclass
class Program:
    name: str
    externals: list = field(default_factory=list)   # nombres de globales usadas
    locals: list = field(default_factory=list)      # Var locales (incluye instancias TON, CTU...)
    networks: list = field(default_factory=list)

    def render(self, gvl):
        ext = "\r\n".join(f"\t\t{v.decl(with_addr=False)}" for v in gvl if v.name in self.externals)
        loc = "\r\n".join(f"\t\t{v.decl()}" for v in self.locals)
        nets = "\r\n".join(n.render() for n in self.networks)
        return (
            f"(*$MODIFICATIONDATE_UTC:{_stamp()}*)\r\n"
            f"PROGRAM {self.name}\r\n(**)\r\n(**)\r\n"
            f"\tVAR_EXTERNAL\r\n{ext}\r\n\tEND_VAR\r\n"
            f"\tVAR\r\n{loc}\r\n\t\t@'': @'';\r\n\tEND_VAR\r\n"
            "'LD'\r\nBODY\r\n"
            "    WORKSPACE\r\n        NETWORK_LIST_TYPE := NWTYPELD ;\r\n    END_WORKSPACE\r\n"
            f"{nets}\r\n{EMPTY_NET}"
            "END_BODY\r\nEND_PROGRAM\r\n\r\n"
        )


def _stamp():
    t = int(time.time())
    return f"{t} (= {time.strftime('%d.%m.%Y %H:%M:%S', time.gmtime(t))} UTC)"


INTERRUPTS = [f"Interrupt {i}" for i in range(24)]


def render_project(header, programs, gvl, extra_program_text="", programas_ya_en_proyecto=()):
    """header: bloque BEGIN_OBJECT PROJECT ... END_PLC_CONFIG copiado de una exportacion real.
    extra_program_text: bloques PROGRAM a incluir tal cual (solo si NO existen ya en el proyecto).
    programas_ya_en_proyecto: nombres que deben seguir asignados a la tarea sin reimportar su cuerpo.
    NOTA: 'Nuevo proyecto desde archivo' exige un archivo autocontenido (flujo recomendado).
    NOTA: 'Importar > Objetos' es aditivo; un objeto repetido se renombra como X_!Conflicto1!."""
    progs = "".join(p.render(gvl) for p in programs)
    gvars = "\r\n".join(f"\t\t\t{v.decl()}" for v in gvl)
    tasks = "\t\tTASK\r\n\t\t\tPrograms(SINGLE:=TRUE, INTERVAL:=0, PRIORITY:=31)\r\n"
    tasks += "\t\tTASK\r\n\t\t\t@'Programs 2'(SINGLE:=TRUE, INTERVAL:=0, PRIORITY:=31)\r\n"
    for i, n in enumerate(INTERRUPTS):
        tasks += f"\t\tTASK\r\n\t\t\t@'{n}'(SINGLE:=I{i}, INTERVAL:=0, PRIORITY:=31)\r\n"
    tasks += "\t\tTASK\r\n\t\t\t@'Timer Interrupt'(SINGLE:=FALSE, INTERVAL:=T#10ms, PRIORITY:=31)\r\n"
    names = list(programas_ya_en_proyecto) + _names_in(extra_program_text) + [p.name for p in programs]
    assigns = "\r\n".join(f"\t\tPROGRAM {n} WITH Programs: scProgramType" for n in names)
    dates = "".join(f"(*$MODIFICATIONDATE_UTC:TASK:{n}:0 (= 01.01.1970 00:00:00 UTC)*)\r\n"
                    for n in ["Programs 2", *INTERRUPTS, "Timer Interrupt"])
    return (
        f"{header}\r\n\r\n{extra_program_text}{progs}"
        f"(*$MODIFICATIONDATE_UTC:TASK:Programs:{_stamp()}*)\r\n{dates}"
        f"(*$MODIFICATIONDATE_UTC:GVL:{_stamp()}*)\r\n(*$GVL_NAME:GVL*)\r\n"
        "CONFIGURATION scConfiguration\r\n\tRESOURCE scResource ON scResourceType\r\n\r\n"
        f"\t\tVAR_GLOBAL\r\n{gvars}\r\n\t\t\t@'': @'';\r\n\t\tEND_VAR\r\n\r\n"
        f"{tasks}\r\n{assigns}\r\n\tEND_RESOURCE\r\nEND_CONFIGURATION\r\n"
    )


# Registros de sistema del puerto COM del FP0R (valores verificados con exportacion de FPWIN 7.7.4)
COM_MODBUS_RTU_MAESTRO = {412: 64}                     # 16#40: Modbus RTU Maestro/Esclavo (0 = MEWTOCOL-COM)
COM_FORMATO_8N1 = {413: 259}                           # 16#103: 8 bits, sin paridad, 1 stop (16#303 = paridad impar)
COM_BAUD = {9600: 38, 115200: 102}                     # registro 415 (16#26 = 9600, 16#66 = 115200)


def set_system_registers(header, valores):
    """Sustituye en la cabecera exportada los registros de sistema indicados ({num: valor})."""
    for num, val in valores.items():
        header, n = re.subn(rf"(?m)^(\t{num} = )\d+(\t;16#)[0-9A-Fa-f]+(?=\r?$)",
                            rf"\g<1>{val}\g<2>{val:X}", header)
        if n != 1:
            raise ValueError(f"Registro de sistema {num} no encontrado en la cabecera")
    return header


def _names_in(text):
    return re.findall(r"^PROGRAM (\w+)\s*$", text, flags=re.M)


def read_export(path):
    """Devuelve (header, bloques PROGRAM existentes, variables globales) de una exportacion .asc."""
    d = open(path, "rb").read().decode("utf-16")
    header = d.split("END_PLC_CONFIG")[0] + "END_PLC_CONFIG"
    progs = "".join(m.group(0) for m in re.finditer(
        r"\(\*\$MODIFICATIONDATE_UTC:\d+[^\n]*\*\)\r\nPROGRAM .*?END_PROGRAM\r\n\r\n", d, flags=re.S))
    gvl = []
    m = re.search(r"VAR_GLOBAL\r\n(.*?)\r\n\t\t\t@'': @'';", d, flags=re.S)
    if m:
        for line in m.group(1).split("\r\n"):
            mm = re.match(r"\s*(\w+)(?: AT (\S+))?: (\w+)(?::=(\S+))?;", line)
            if mm:
                gvl.append(Var(mm.group(1), mm.group(3), mm.group(2), mm.group(4)))
    return header, progs, gvl


def check_names(programs, gvl):
    """Detecta colisiones de identificadores sin distinguir mayusculas (FPWIN las rechaza)."""
    problemas = []
    for p in programs:
        vistos = {}
        for v in [g for g in gvl if g.name in p.externals] + p.locals:
            k = v.name.lower()
            if k in vistos and vistos[k] != v.name:
                problemas.append(f"{p.name}: '{vistos[k]}' y '{v.name}' colisionan")
            vistos.setdefault(k, v.name)
    return problemas


def write_asc(path, text):
    with open(path, "wb") as f:
        f.write(b"\xff\xfe" + text.encode("utf-16-le"))
