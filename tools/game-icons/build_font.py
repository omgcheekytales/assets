#!/usr/bin/env python3
"""Genera game-icons.{ttf,woff,woff2,css} a partir de los SVG oficiales de game-icons.net.

Uso: python build_font.py RUTA_AL_REPO_game-icons/icons RUTA_CARPETA_SALIDA
Mantiene names.json (SVG -> nombre de clase) y codepoints.json (nombre -> codigo)
para que los iconos existentes NUNCA cambien de nombre ni de codigo.
"""
import json, os, re, sys
os.environ.setdefault("SOURCE_DATE_EPOCH", "1700000000")  # fuentes identicas si no hay iconos nuevos
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path

HERE = os.path.dirname(os.path.abspath(__file__))
BG = "M0 0h512v512H0z"
FIRST_FREE, LAST_FREE = 0xE000, 0xEFFF   # zona privada segura (BMP)

CSS_HEAD = '''@font-face {
\tfont-family: "game-icons";
\tsrc: url("game-icons.woff2") format("woff2"),
\t\turl("game-icons.woff") format("woff"),
\t\turl("game-icons.ttf") format("truetype");
\tfont-display: swap;
}

.game-icon {
\tline-height: 1;
}

.game-icon:before {
\tfont-family: game-icons !important;
\tfont-style: normal;
\tfont-weight: normal !important;
\tvertical-align: top;
}

'''

def load(name, default):
    p = os.path.join(HERE, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

def svg_paths(path):
    s = open(path, encoding="utf-8").read()
    ds = re.findall(r'<path[^>]*?\sd="([^"]+)"', s)
    return [d for d in ds if not d.strip().startswith(BG)]

def main(src, out):
    names = load("names.json", {})          # "autor/archivo.svg" -> nombre
    cps = load("codepoints.json", {})       # nombre -> codigo
    icons = {}                              # nombre -> [d,...]
    # 1) SVG oficiales
    keys = []
    for r, _, fl in os.walk(src):
        if ".git" in r.split(os.sep): continue
        for f in fl:
            if f.endswith(".svg"):
                keys.append(os.path.relpath(os.path.join(r, f), src).replace(os.sep, "/"))
    taken = set(names.values())
    for k in sorted(keys):
        if k not in names:
            base = os.path.basename(k)[:-4]; n, i = base, 1
            while n in taken:
                i += 1; n = f"{base}-{i}"
            names[k] = n; taken.add(n)
            print("NUEVO:", k, "->", n)
        icons[names[k]] = svg_paths(os.path.join(src, k))
    # 2) iconos antiguos que ya no existen en la web (se conservan)
    leg = os.path.join(HERE, "legacy")
    for f in sorted(os.listdir(leg)):
        if f.endswith(".svg") and f[:-4] not in icons:
            icons[f[:-4]] = svg_paths(os.path.join(leg, f))
    # 3) codigos
    # U+FFFE y U+FFFF son "no caracteres": Chrome rechaza la fuente si se usa U+FFFF.
    for n in [n for n, c in cps.items() if c >= 0xFFFF]:
        print("AVISO: el icono", n, "usaba U+FFFF y se mueve a otro codigo")
        del cps[n]
    used = set(cps.values())
    free = (c for c in range(FIRST_FREE, LAST_FREE + 1) if c not in used)
    for n in sorted(icons):
        if n not in cps:
            cps[n] = next(free)
    # 4) glifos
    order = [".notdef"]; glyphs = {}; cmap = {}
    pen0 = TTGlyphPen(None); glyphs[".notdef"] = pen0.glyph()
    for n in sorted(list(icons), key=lambda x: cps[x]):
        gname = "i%04x" % cps[n]
        pen = TTGlyphPen(None)
        cpen = Cu2QuPen(pen, max_err=1.0, reverse_direction=True)
        tp = TransformPen(cpen, (1, 0, 0, -1, 0, 512))
        try:
            for d in icons[n]:
                parse_path(d, tp)
        except Exception:
            print("OMITIDO (SVG vacio o ilegible):", n); del icons[n]; del cps[n]; continue
        glyphs[gname] = pen.glyph(); order.append(gname); cmap[cps[n]] = gname
    fb = FontBuilder(512, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    glyf = fb.font["glyf"]
    fb.setupHorizontalMetrics({g: (512, getattr(glyf[g], "xMin", 0) or 0) for g in order})
    fb.setupHorizontalHeader(ascent=512, descent=0)
    fb.setupNameTable({"familyName": "game-icons", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=512, sTypoDescender=0, usWinAscent=512, usWinDescent=0)
    fb.setupPost(keepGlyphNames=False)
    os.makedirs(out, exist_ok=True)
    for flavor, ext in ((None, "ttf"), ("woff", "woff"), ("woff2", "woff2")):
        fb.font.flavor = flavor
        fb.save(os.path.join(out, f"game-icons.{ext}"))
    css = CSS_HEAD + "".join(
        f'.game-icon-{n}:before {{\n\tcontent: "\\{cps[n]:x}";\n}}\n' for n in sorted(icons))
    open(os.path.join(out, "game-icons.css"), "w", encoding="utf-8").write(css)
    json.dump(dict(sorted(names.items())), open(os.path.join(HERE, "names.json"), "w"), indent=0)
    json.dump(dict(sorted(cps.items())), open(os.path.join(HERE, "codepoints.json"), "w"), indent=0)
    print(f"Listo: {len(icons)} iconos")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
