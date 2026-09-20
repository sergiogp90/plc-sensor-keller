# plc-sensor-keller
PLC Panasonic FP0R-C14MRS conectado con sensor Keller PR-33X Serie 11 mediante RS485

## Puesta en marcha en otro PC

El desarrollo se hace con scripts de Python en `herramientas/` que generan archivos `.asc`
importables en Control FPWIN Pro 7, con ayuda de Claude Code. Para trabajar con las mismas
herramientas hacen falta tres cosas: Git, Python y Claude Code con una cuenta. Todo el
conocimiento del proyecto (reglas, formato `.asc`, catálogo de instrucciones, cabecera del PLC)
viaja dentro del repositorio.

### 1. Git para Windows

Necesario para clonar y, además, Claude Code lo exige en Windows porque usa Git Bash como shell.
Si el repositorio es privado, pedir acceso como colaborador en GitHub.

```
git clone https://github.com/sergiogp90/plc-sensor-keller.git
```

### 2. Python 3.10 o superior

Instalar desde python.org o Microsoft Store marcando "Add to PATH". No hay dependencias externas:
el generador usa solo la librería estándar, no hace falta `pip install`. Comprobación sin FPWIN:

```
cd herramientas
python ejemplo_motor.py
python ejemplo_keller.py
```

Ambos deben terminar con `Generado: …`. `ejemplo_motor.py` escribe en la carpeta temporal del
sistema; `ejemplo_keller.py` regenera `keller.asc` en la raíz.

### 3. Claude Code

Instalador nativo desde PowerShell (no requiere Node.js):

```
irm https://claude.ai/install.ps1 | iex
```

Después, abrir `claude` dentro de la carpeta del proyecto y ejecutar `/login`. Hace falta una
cuenta: suscripción Claude Pro, Max o Team, o una clave de API de la consola de Anthropic.

Ajustes personales recomendados con `/config` (no viajan con el repositorio): idioma Español y
nivel de esfuerzo alto. El proyecto no requiere servidores MCP ni plugins.

Claude Code carga automáticamente `CLAUDE.md` y `AGENTS.md` al abrir la carpeta; ahí están las
reglas de trabajo, el formato `.asc` descifrado y el estado actual del proyecto.

### 4. Control FPWIN Pro 7 (solo para compilar y cargar al PLC)

No es necesario para generar los `.asc`. Solo hace falta para abrirlos con
**Proyecto > Nuevo > Desde archivo…**, compilar, simular y transferir al PLC. Los `.pro` y `.bak`
están excluidos del repositorio porque se regeneran desde los `.asc`.

### Qué no viaja con el repositorio

- La memoria persistente de Claude Code es por usuario y por ruta de carpeta. Un desarrollador
  nuevo empieza sin ella; por eso todo descubrimiento se documenta en `AGENTS.md`.
- `herramientas/construir_catalogo.py` solo funciona con FPWIN instalado (lee su ayuda offline).
  No hace falta ejecutarlo: `catalogo_instrucciones.json` ya está generado.

Opcional: la CLI `gh` para crear pull requests desde Claude Code y la extensión de Claude Code
para VS Code.
