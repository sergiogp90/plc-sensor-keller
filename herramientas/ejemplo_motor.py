"""
Ejemplo: arranque/paro de motor con realimentacion, lampara de 'listo' a los 5 s
y contador de arranques con alarma por comparacion.
Ejemplo didactico: NO escribe en el proyecto. Genera ejemplo_motor.asc en la carpeta temporal del sistema
(o en la ruta que se pase como primer argumento).

Uso:  python ejemplo_motor.py [ruta_salida.asc]
Abrir en FPWIN con: Proyecto > Nuevo > Desde archivo... (archivo autocontenido)
"""
import os
import sys
import tempfile
from fpwin_asc import Var, Network, Program, read_export, render_project, write_asc, check_names

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = next(os.path.join(HERE, "..", f) for f in ("keller_export.asc", "exportado.asc", "herramientas/cabecera_fp0r.asc")
           if os.path.exists(os.path.join(HERE, "..", f)))
DST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(tempfile.gettempdir(), "ejemplo_motor.asc")

# Solo se reutiliza la cabecera (tipo de PLC, registros de sistema, comunicaciones).
header, _programas_viejos, _gvl_vieja = read_export(SRC)

# --- Variables globales (E/S fisicas del FP0R-C14) ---------------------------
gvl = [
    Var("Marcha",  "BOOL", "%IX0.0", comment="Pulsador de marcha, X0"),
    Var("Paro",    "BOOL", "%IX0.1", comment="Pulsador de paro, X1 (contacto NC en logica)"),
    Var("Reset",   "BOOL", "%IX0.2", comment="Pulsador de reset del contador, X2"),
    Var("Motor",   "BOOL", "%QX0.0", comment="Contactor del motor, Y0"),
    Var("Listo",   "BOOL", "%QX0.1", comment="Lampara motor en regimen, Y1"),
    Var("Alarma",  "BOOL", "%QX0.2", comment="Alarma: demasiados arranques, Y2"),
    Var("nArranques", "INT", "%MW5.0", init="0", comment="Numero de arranques, DT0"),
]

# --- Red 1: Marcha --- Paro(NC) --- ( Motor ), con Motor en paralelo a Marcha --
#   Titulo SIN comillas (prueba A)
red1 = Network(title="Arranque y paro del motor")
red1.contact("Marcha")
red1.parallel_contact("Motor", from_x=1)
red1.contact_nc("Paro")
red1.coil("Motor")

# --- Red 2: Motor --- TON 5 s --- ( Listo ) ----------------------------------
#   Titulo CON comillas simples (prueba B)
red2 = Network(title="'Lampara de motor en regimen tras 5 s'", row=3)
red2.contact("Motor")
red2.ton("T_Listo", "tiempoListo", "tiempoTranscurrido")
red2.coil("Listo")

# --- Red 3: flanco de Motor --- CTU (PV=3, R=Reset) --- ( SET Alarma ) --------
red3 = Network(title="Contador de arranques", row=3)
red3.comment("Cada arranque cuenta; a los 3 se activa la alarma")
red3.df("Motor")
red3.ctu("C_Arranques", pv="3", reset_var="Reset", cv_var="nArranques")
red3.coil_set("Alarma")

# --- Red 4: Reset --- ( RESET Alarma ) ----------------------------------------
red4 = Network(title="Reset de alarma")
red4.contact("Reset")
red4.coil_reset("Alarma")

# --- Red 5: nArranques > 2 --- ( Aviso )  prueba de comparacion ---------------
red5 = Network(title="Aviso por comparacion", row=3)
red5.compare("GT", "nArranques", "2")
red5.coil("Aviso")

motor = Program(
    name="Motor",
    externals=["Marcha", "Paro", "Reset", "Motor", "Listo", "Alarma", "nArranques"],
    locals=[
        Var("T_Listo", "TON"),
        Var("tiempoListo", "TIME", init="T#5s"),
        Var("tiempoTranscurrido", "TIME", init="T#0s"),
        Var("C_Arranques", "CTU"),
        Var("Aviso", "BOOL"),
    ],
    networks=[red1, red2, red3, red4, red5],
)

problemas = check_names([motor], gvl)
if problemas:
    sys.exit("Nombres en conflicto: " + "; ".join(problemas))

write_asc(DST, render_project(header, [motor], gvl))
print("Generado:", os.path.normpath(DST))
