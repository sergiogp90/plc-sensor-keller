"""
Construye catalogo_instrucciones.json a partir de la ayuda offline de FPWIN Pro 7.

Para cada instruccion (funcion o bloque de funcion) guarda: nombre, tipo de bloque LD
(B_F o B_FB), cadena de pines tal como la usa el .asc, tamano del bloque, descripcion,
parametros con tipo, PLCs mencionados y si esta marcada como redundante.

Uso:  python construir_catalogo.py
"""
import glob
import html
import json
import os
import re

HELP = r"C:\Program Files (x86)\Panasonic Industry Control\Control FPWIN Pro 7\OfflineHelp\src\data\fpwin\es\topics"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalogo_instrucciones.json")

PLCS = ["FP0R", "FP0H", "FP-X", "FP-XH", "FP7", "FP-Sigma", "FPΣ", "FP0", "FP2", "FP-e"]


def texto(raw):
    raw = re.sub(r"<script.*?</script>", "", raw, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", raw))
    return [l.strip() for l in t.split("\n") if l.strip()]


def parametros(lines):
    """Extrae 'nombre (TIPO)' + descripcion en las secciones Entrada/Salida."""
    ins, outs, cur = [], [], None
    for i, l in enumerate(lines):
        if re.fullmatch(r"(Parámetros\s+)?Entrada", l):
            cur = ins
        elif re.fullmatch(r"Salida", l):
            cur = outs
        elif l.startswith(("Observaciones", "Temas relacionados", "Ejemplo", "Diagrama")):
            cur = None
        elif cur is not None:
            m = re.fullmatch(r"([\w\[\]\.]+|Unnamed \w+) \(([^)]+)\)", l)
            if m:
                desc = lines[i + 1] if i + 1 < len(lines) else ""
                cur.append({"nombre": m.group(1), "tipo": m.group(2), "desc": desc[:120]})
    return ins, outs


def main():
    cat = {}
    for f in glob.glob(os.path.join(HELP, "*.html")):
        raw = open(f, encoding="utf-8", errors="ignore").read()
        m = re.search(r"<title>(.*?)</title>", raw, re.S)
        if not m:
            continue
        title = html.unescape(m.group(1)).strip()
        lines = texto(raw)
        # bloques LD del ejemplo que usan la propia instruccion
        blocks = re.findall(r"^B\((B_F|B_FB),([^,!]*)!,([^,]*),(\d+),(\d+),(\d+),(\d+),,([^)]*)\)", "\n".join(lines), re.M)
        mine = [b for b in blocks if b[1].lstrip("@").split("-")[0] == title]
        if not mine and not re.match(r"^[A-Z][A-Za-z0-9_]*$", title):
            continue
        if not mine and not blocks:
            continue
        b = mine[0] if mine else None
        ins, outs = parametros(lines)
        entry = {
            "nombre": title,
            "bloque": b[0] if b else None,
            "nombre_asc": b[1] if b else None,     # p.ej. E_ADD-2, @EQ-2
            "pines": b[7] if b else None,
            "ancho": int(b[5]) - int(b[3]) if b else None,
            "alto": int(b[6]) - int(b[4]) if b else None,
            "descripcion": next((l for l in lines[2:6] if len(l) > 15), "")[:200],
            "entradas": ins,
            "salidas": outs,
            "redundante": any("redundant" in l.lower() or "redundante" in l.lower() for l in lines[:6]),
            "plcs_mencionados": sorted({p for p in PLCS if p in raw}),
            "tema": os.path.basename(f),
        }
        # varias paginas comparten titulo (GT, ADD...): conservar la que trae ejemplo LD
        prev = cat.get(title)
        if (b or ins or outs) and not (prev and prev["bloque"] and not b):
            cat[title] = entry
    json.dump(cat, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    con_bloque = sum(1 for e in cat.values() if e["bloque"])
    print(f"Instrucciones catalogadas: {len(cat)} (con ejemplo LD: {con_bloque}) -> {OUT}")


if __name__ == "__main__":
    main()
