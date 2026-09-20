"""
Lectura de presion de un transmisor KELLER serie 33X por RS485 / Modbus RTU
con un FP0R (puerto COM configurado como Modbus RTU Maestro/Esclavo).

Protocolo Keller X-Line v3.7 (ambos protocolos, Keller bus y Modbus, activos a la vez):
  - Direccion esclavo por defecto: 1.  9600 baud, 8 bits, sin paridad, 1 stop.
  - FC 03 (Read Holding Registers), registro 0x0100, 4 palabras -> P1 [bar] y TOB1 [C], float32 IEEE754,
    palabra ALTA primero (ej. 3F75 E3D2 41B6 1C20 = 0.9605 bar, 22.76 C). Requiere firmware >= 5.20-10.40;
    en firmware mas antiguo usar reg 0x0002 (P1) y 0x0008 (TOB1) en dos peticiones.
  - El FP0R guarda los REAL con la palabra BAJA primero, por eso se intercambian las dos palabras.

Genera ../keller.asc. Abrir en FPWIN con Proyecto > Nuevo > Desde archivo.
"""
import os
import sys
from fpwin_asc import (Var, Network, Program, read_export, render_project, write_asc, check_names,
                       set_system_registers, COM_MODBUS_RTU_MAESTRO, COM_FORMATO_8N1, COM_BAUD)

HERE = os.path.dirname(os.path.abspath(__file__))
# Cabecera (tipo de PLC, registros de sistema): la exportacion mas reciente disponible
SRC = next(os.path.join(HERE, "..", f) for f in ("keller_export.asc", "exportado.asc", "herramientas/cabecera_fp0r.asc")
           if os.path.exists(os.path.join(HERE, "..", f)))
DST = os.path.join(HERE, "..", "keller.asc")

header, _, _ = read_export(SRC)
# Puerto COM del FP0R: Modbus RTU maestro, 9600 8N1 (igual que el Keller)
header = set_system_registers(header, {**COM_MODBUS_RTU_MAESTRO, **COM_FORMATO_8N1, 415: COM_BAUD[9600]})

# --- Variables globales -------------------------------------------------------
gvl = [
    Var("rPresionBar",    "REAL",  "%MD5.202", init="0.0", comment="Presion P1 del Keller en bar (DDT202), para la pantalla GT"),
    Var("rTemperaturaC",  "REAL",  "%MD5.204", init="0.0", comment="Temperatura TOB1 del Keller en grados C (DDT204), para la pantalla GT"),
    Var("awKellerSwap",   "ARRAY [0..3] OF WORD", "%MW5.202", init="[4(0)]", comment="DT202-205: palabras ya en orden FP0R (solapa rPresionBar y rTemperaturaC)"),
    Var("awKellerRaw",    "ARRAY [0..3] OF WORD", "%MW5.190", init="[4(0)]", comment="DT190-193: respuesta Modbus tal cual llega (P1 HWord, P1 LWord, TOB1 HWord, TOB1 LWord)"),
    Var("bKellerOK",      "BOOL",  "%MX0.10.0", comment="Ultima lectura correcta (R100)"),
    Var("bKellerError",   "BOOL",  "%MX0.10.1", comment="Error de comunicacion en la ultima peticion (R101)"),
    Var("nErroresKeller", "INT",   "%MW5.210", init="0", comment="Contador de errores de comunicacion (DT210)"),
    Var("iKellerAddr",    "INT",   "%MW5.211", init="1", comment="Direccion Modbus del Keller (por defecto 1)"),
]

# --- Red 1: peticion Modbus cada segundo cuando el puerto esta libre -----------
#   Registro 0x0100 (=256): P1 [bar] y TOB1 [C] en 4 palabras (firmware Keller 5.20-10.40 o posterior)
red1 = Network(title="Peticion Modbus FC03 al Keller: P1 y TOB1 float32 desde reg 16#0100", row=3)
red1.comment("Cada 1 s si el puerto esta libre: FC03 leer 4 registros desde 16#0100 (P1 bar + TOB1 gradosC)")
red1.contact("sys_bIsComPort1F145F146NotActive")
red1.df("sys_bPulse1s")
red1.block("FP_MODBUS_MASTER",
           entradas={"Port": "SYS_COM1_PORT",
                     "SlaveAddress": "iKellerAddr",
                     "FunctionCode": "SYS_MODBUS_03_READ_HOLDING_REGISTERS",
                     "StartRegister": "256",
                     "NumberOfRegisters": "4",
                     "MasterData": "awKellerRaw"},
           salidas={"Result": "wResultado"})
red1.coil("bPeticionEnviada")

# --- Red 2: respuesta recibida sin error -> pulso bNuevaLectura -----------------
#   Para probar sin hardware (simulador) anadir: red2.parallel_contact("bPruebaSwap", from_x=1)
#   y declarar bPruebaSwap como local; validado el 19-09-2026 con 3F75 E3D2 41B6 1C20 -> 0.9605 / 22.76
red2 = Network(title="Respuesta recibida sin error -> pulso de lectura nueva", row=2)
red2.df("sys_bIsComPort1F145F146NotActive")
red2.contact_nc("sys_bIsComPort1F145F146Error")
red2.coil("bNuevaLectura")

# --- Red 3: presion: intercambiar palabras -> rPresionBar (DT202-203) ---------
red3 = Network(title="Presion: HWord/LWord -> orden FP0R en DT202-203", row=3)
red3.comment("Keller envia palabra alta primero; el FP0R guarda la baja primero. Solape con rPresionBar intencionado")
red3.contact("bNuevaLectura")
red3.block("E_MOVE", entradas={"D1": "awKellerRaw[0]"}, salidas={"C1": "awKellerSwap[1]"})
red3.coil_set("bKellerOK")
red3.parallel_coil("bKellerError", "E", sep=3)
# Segundo E_MOVE en rama paralela (misma condicion) para que los rotulos no se solapen
red3.parallel_block("E_MOVE", entradas={"D1": "awKellerRaw[1]"}, salidas={"C1": "awKellerSwap[0]"})

# --- Red 4: temperatura: intercambiar palabras -> rTemperaturaC (DT204-205) ---
red4 = Network(title="Temperatura: HWord/LWord -> orden FP0R en DT204-205", row=3)
red4.contact("bNuevaLectura")
red4.block("E_MOVE", entradas={"D1": "awKellerRaw[2]"}, salidas={"C1": "awKellerSwap[3]"})
red4.coil("bConversionHecha")
red4.parallel_block("E_MOVE", entradas={"D1": "awKellerRaw[3]"}, salidas={"C1": "awKellerSwap[2]"})

# --- Red 5: error de comunicacion --------------------------------------------
red5 = Network(title="Error de comunicacion con el Keller", row=3)
red5.contact("sys_bIsComPort1F145F146Error")
red5.ctu("C_Errores", pv="32000", reset_var="bResetErrores", cv_var="nErroresKeller")
red5.coil_set("bKellerError")
red5.parallel_coil("bKellerOK", "E", sep=3)

keller = Program(
    name="LecturaKeller",
    externals=["rPresionBar", "rTemperaturaC", "awKellerSwap", "awKellerRaw", "bKellerOK", "bKellerError",
               "nErroresKeller", "iKellerAddr"],
    locals=[
        Var("wResultado", "WORD", init="0"),
        Var("bPeticionEnviada", "BOOL"),
        Var("bNuevaLectura", "BOOL"),
        Var("bConversionHecha", "BOOL"),
        Var("bResetErrores", "BOOL"),
        Var("C_Errores", "CTU"),
    ],
    networks=[red1, red2, red3, red4, red5],
)

problemas = check_names([keller], gvl)
if problemas:
    sys.exit("Nombres en conflicto: " + "; ".join(problemas))

write_asc(DST, render_project(header, [keller], gvl))
print("Generado:", os.path.normpath(DST))
