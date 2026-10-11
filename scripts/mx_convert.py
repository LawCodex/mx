#!/usr/bin/env python3
"""Convert the downloaded LeyesBiblio PDFs (see mx_fetch.py) to LawCodex Markdown.

Text is extracted with poppler's `pdftotext -layout` (keeps paragraph breaks and indentation;
pypdf was tried first but splits words on these PDFs). Running headers/footers are removed,
paragraphs re-flowed, structural headings (Libro/Título/Capítulo/Sección...) and articles turned
into Markdown headings, and tabular blocks kept verbatim in fenced text blocks.

Usage: python mx_convert.py [--only FILE_STEM]
"""
import json
import os
import re
import subprocess
import sys
import textwrap
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wb  # noqa: E402
from mx_fetch import slugify  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RETRIEVED = os.environ.get("MX_RETRIEVED", date.today().isoformat())

HEADER_RE = re.compile(r"(C[ÁA]MARA DE DIPUTADOS DEL H\. CONGRESO|Secretar[íi]a General|"
                       r"Secretar[íi]a de Servicios Parlamentarios|[ÚU]ltima [Rr]eforma (publicada )?DOF|"
                       r"Nueva Ley (publicada )?DOF|Nuevo (C[óo]digo|Reglamento) (publicado )?DOF|"
                       r"Centro de Documentaci[óo]n, Informaci[óo]n y An[áa]lisis|"
                       r"[ÚU]ltima reforma|Sin reforma|Nuevo Estatuto|TEXTO VIGENTE)", re.I)
FOOTER_RE = re.compile(r"^\s*\d+\s+de\s+\d+\s*$")
NOTE_RE = re.compile(r"^(P[áa]rrafo|Art[íi]culo|Fracci[óo]n|Inciso|Apartado|Cap[íi]tulo|T[íi]tulo|"
                     r"Secci[óo]n|Libro|Parte|Base|Numeral|Denominaci[óo]n|Fe de erratas|Reforma|"
                     r"Subinciso|Sub ?apartado|Segundo p[áa]rrafo|P[áa]rrafos|Fracciones|Incisos|"
                     r"Art[íi]culos|Secciones|Cap[íi]tulos|T[íi]tulos|Tabla|Cuadro|Rengl[óo]n|"
                     r"Nota|Ley|Reglamento|C[óo]digo|Decreto|Anexo|Tarifa|Disposici[óo]n|Transitorio)"
                     r"[^\n]{0,60}?\b(reformad|adicionad|derogad|recorrid|DOF|abrogad|modificad|reubicad|"
                     r"reestructurad)", re.I)
DOFDATE = re.compile(r"DOF \d{2}-\d{2}-\d{4}")

KINDS = [
    ("parte", re.compile(r"^(PRIMERA|SEGUNDA|TERCERA|CUARTA|QUINTA)?\s*PARTE\b|^Parte\s+\w+$", re.I)),
    ("libro", re.compile(r"^LIBRO\b|^Libro\s+\w+$", re.I)),
    ("titulo", re.compile(r"^T[ÍI]TULO\b", re.I)),
    ("capitulo", re.compile(r"^CAP[ÍI]TULO\b", re.I)),
    ("seccion", re.compile(r"^SECCI[ÓO]N\b", re.I)),
]
ORD = r"(?i:[ÚU]nico|Primer[oa]?|Segund[oa]|Tercer[oa]?|Cuart[oa]|Quint[oa]|Sext[oa]|S[ée]ptim[oa]|Octav[oa]|Noven[oa]|D[ée]cim[oa]\w*|Und[ée]cim[oa]|Duod[ée]cim[oa]|Vig[ée]sim[oa]\w*|Trig[ée]sim[oa]\w*|Cuadrag[ée]sim[oa]\w*)"
SUFFIX = r"(?:Bis|BIS|Ter|TER|Qu[áa]ter|QU[ÁA]TER|Quintus|Quinquies|QUINQUIES|Sexies|SEXIES|Septies|SEPTIES|Octies|OCTIES|Nonies|NONIES|Decies|DECIES)"
NUM = (r"\d+(?:\s*[oº°])?(?:[\s-]+" + SUFFIX + r"\b(?:\s*\d+(?![\d/]))?)*"
       r"(?:[\s-]+[A-Z](?:[\s-]+" + SUFFIX + r")?(?=\.?\s*[-–—]))?")
ART_RE = re.compile(
    r"^(?P<label>(?:Art[íi]culo|ART[ÍI]CULO)\s+(?:" + NUM + "|" + ORD + r"(?:\s+" + ORD + r")?)(?![\w/]))"
    r"\s*(?P<dot>\.)?\s*(?:[-–—]+\s*)?(?P<rest>.*)$", re.S)
TRANS_RE = re.compile(r"^(ART[ÍI]CULOS\s+)?TRANSITORIOS?(\s+DE\s+DECRETOS?\s+DE\s+REFORMAS?)?\.?$|"
                      r"^Transitorios?$|^ART[ÍI]CULOS?\s+TRANSITORIOS?(\s+DE\s+.*)?$", re.I)


def pdftext(path):
    out = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", path, "-"],
                         capture_output=True, check=True)
    return out.stdout.decode("utf-8", "replace")


def strip_page(page):
    lines = page.split("\n")
    # header: within first ~10 non-empty lines, drop lines that match header patterns (or the
    # running law title which is right-aligned at the top)
    i, seen = 0, 0
    while i < len(lines) and seen < 9:
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if HEADER_RE.search(ln) or (seen == 0 and len(ln) - len(ln.lstrip()) > 25):
            seen += 1
            i += 1
            continue
        break
    if seen >= 2:
        lines = lines[i:]
    # footer
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and FOOTER_RE.match(lines[-1]):
        lines.pop()
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    return lines


def blocks(text):
    pages = text.split("\f")
    out_lines = []
    for p in pages:
        ls = strip_page(p)
        if not ls:
            continue
        if out_lines:
            prev = out_lines[-1].rstrip()
            first = ls[0]
            indent = len(first) - len(first.lstrip())
            cont = (prev and not re.search(r"[.:;]$", prev) and indent < 2
                    and not FOOTER_RE.match(prev))
            if not cont:
                out_lines.append("")
        out_lines.extend(ls)
    # split into blocks at blank lines; also split off right-aligned reform notes
    cur, res = [], []
    for ln in out_lines:
        if not ln.strip():
            if cur:
                res.append(cur)
            cur = []
            continue
        ind = len(ln) - len(ln.lstrip())
        if ind >= 30 and NOTE_RE.match(ln.strip()):
            if cur:
                res.append(cur)
            res.append(["\x00NOTE" + ln.strip()])
            cur = []
            continue
        cur.append(ln.rstrip())
    if cur:
        res.append(cur)
    # split off transitory headings and decree titles that share a block with other text
    res2 = []
    for b in res:
        cur = []
        for ln in b:
            st = ln.strip()
            if TRANS_RE.match(st) and not b[0].startswith("\x00"):
                if cur:
                    res2.append(cur)
                res2.append([ln])
                cur = []
                continue
            if cur and re.match(r"^DECRETO\s", st):
                res2.append(cur)
                cur = []
            cur.append(ln)
        if cur:
            res2.append(cur)
    res = res2
    # split full-width (small font) reform notes off the end of blocks
    out = []
    for b in res:
        j = next((i for i, ln in enumerate(b) if not b[0].startswith("\x00")
                  and NOTE_RE.match(ln.strip()) and DOFDATE.search(" ".join(b[i:i + 2]))), None)
        if j is None:
            out.append(b)
            continue
        if j > 0:
            out.append(b[:j])
        out.append(["\x00NOTE" + re.sub(r"\s+", " ", " ".join(l.strip() for l in b[j:]))])
    # join a lone structural heading line with the centred name block that follows it
    res, i = [], 0
    while i < len(out):
        b = out[i]
        if (len(b) == 1 and i + 1 < len(out) and not b[0].startswith("\x00") and heading_kind(b)
                and len(out[i + 1]) <= 2 and not out[i + 1][0].startswith("\x00")
                and len(out[i + 1][0]) - len(out[i + 1][0].lstrip()) >= 20
                and not heading_kind(out[i + 1]) and not ART_RE.match(flow(out[i + 1]))
                and not TRANS_RE.match(flow(out[i + 1]))):
            res.append(b + out[i + 1])
            i += 2
            continue
        res.append(b)
        i += 1
    return res


def is_table(block):
    gaps = 0
    for ln in block:
        s = ln.strip()
        s = re.sub(r"^([IVXLC]+\.|[a-zñ]\)|\d+\.|[A-Z]\.|\d+\))\s{2,}", r"\1 ", s)
        if len(re.findall(r"\S\s{3,}\S", s)) >= 1:
            gaps += 1
    return gaps >= 2 and gaps >= len(block) / 2


def flow(block):
    return re.sub(r"\s+", " ", " ".join(l.strip() for l in block)).strip()


def heading_kind(block):
    if len(block) > 4:
        return None
    first = block[0].strip()
    if len(first) > 120:
        return None
    for name, rx in KINDS:
        if rx.match(first):
            # avoid matching body text like "Capítulo reformado DOF" or sentences
            if NOTE_RE.match(first) or re.search(r"[.;,]$", first) and len(first) > 60:
                return None
            return name
    return None


def esc(s):
    s = re.sub(r"^(\s*)([#>+])", r"\1\\\2", s)
    s = re.sub(r"^(\s*)(\d+)\.(\s)", r"\1\2\\.\3", s)
    s = re.sub(r"^(\s*)([-*])(\s)", r"\1\\\2\3", s)
    return s


def kind_order(bl):
    firsts = {}
    for i, b in enumerate(bl):
        if b[0].startswith("\x00"):
            continue
        k = heading_kind(b)
        if k and k not in firsts:
            firsts[k] = i
    order = [k for k, _ in KINDS if k in firsts]
    if "parte" in firsts and "libro" in firsts and firsts["libro"] < firsts["parte"]:
        order.remove("parte")
        order.insert(order.index("libro") + 1, "parte")
    return order


def hx(level, text):
    if level <= 6:
        return "#" * level + " " + text
    return "**" + text + "**"


def convert(text, title):
    bl = blocks(text)
    order = kind_order(bl)
    level = {k: 2 + i for i, k in enumerate(order)}
    art_level = 2 + len(order)
    md = []
    mode = "body"
    for b in bl:
        if b[0].startswith("\x00NOTE"):
            md.append("*" + b[0][5:].replace("*", "\\*") + "*")
            continue
        first = b[0].strip()
        whole = flow(b)
        if len(b) <= 2 and TRANS_RE.match(whole):
            if re.search(r"DECRETOS?\s+DE\s+REFORMA", whole, re.I):
                mode = "reform"
                md.append("## " + whole)
            elif mode == "reform":
                md.append("#### " + whole)
            else:
                mode = "trans"
                md.append("## " + whole)
            continue
        k = heading_kind(b)
        if k and mode == "body":
            parts = [first] + [l.strip() for l in b[1:]]
            head = re.sub(r"\s+", " ", parts[0])
            rest = re.sub(r"\s+", " ", " ".join(parts[1:])).strip()
            md.append(hx(level[k], (head + (" — " + rest if rest else "")).replace("*", "\\*")))
            continue
        if mode == "reform" and re.match(r"^(DECRETO|Decreto)\b", first) and len(whole) < 1500:
            md.append("### " + whole)
            continue
        if is_table(b):
            md.append("```text\n" + textwrap.dedent("\n".join(b)) + "\n```")
            continue
        m = ART_RE.match(whole)
        if m:
            label = re.sub(r"\s+", " ", m.group("label")).strip() + (m.group("dot") or "")
            lvl = {"body": art_level, "trans": 3, "reform": 4}[mode]
            md.append(hx(lvl, label))
            rest = m.group("rest").strip()
            if rest:
                md.append(esc(rest))
            continue
        md.append(esc(whole))
    return "\n\n".join(md) + "\n"


def yaml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def front(it, title):
    lines = ["---", f"title: {yaml_str(title)}"]
    stem = os.path.splitext(os.path.basename(it["file"]))[0]
    lines.append(f"identifier: {yaml_str(stem)}")
    lines.append(f"type: {it['type']}")
    lines.append("jurisdiction: mx")
    lines.append("language: es")
    if it.get("date"):
        lines.append(f"date: {it['date']}")
    if it.get("last_amended"):
        lines.append(f"last_amended: {it['last_amended']}")
    lines.append(f"status: {it['status']}")
    lines.append(f"source: {yaml_str(it['source'])}")
    if it.get("wayback"):
        lines.append(f"archived_copy: {yaml_str(it['wayback'])}")
    if it.get("note"):
        lines.append(f"note: {yaml_str(it['note'])}")
    lines.append(f"retrieved: {RETRIEVED}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def pretty_title(t):
    t = re.sub(r"\s+", " ", t).strip()
    return t


def outpath(it, used):
    title = it["title"]
    if it["category"] == "constitucion":
        return "constitucion/constitucion-politica-de-los-estados-unidos-mexicanos.md"
    t = re.sub(r"\(.*?\)", "", title)
    slug = slugify(t)
    if it["category"] == "decretos":
        slug = slugify(t)
    base = f"{it['category']}/{slug}"
    p = base + ".md"
    n = 2
    while p in used:
        p = f"{base}-{n}.md"
        n += 1
    used.add(p)
    return p


def last_amended_from_text(text):
    m = re.search(r"[ÚU]ltima reforma publicada DOF (\d\d)-(\d\d)-(\d{4})", text, re.I)
    if m:
        d, mth, y = m.groups()
        return f"{y}-{mth}-{d}"
    return None


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    items = json.load(open(os.path.join(wb.ROOT, "manifest.json")))
    used = set()
    index = []
    for it in items:
        it["path"] = outpath(it, used)
        if it.get("missing"):
            continue
        stem = os.path.splitext(os.path.basename(it["file"]))[0]
        if only and stem != only:
            continue
        src = os.path.join(wb.ROOT, it["local"])
        if not os.path.exists(src):
            it["missing"] = True
            continue
        text = pdftext(src)
        if not it.get("last_amended"):
            la = last_amended_from_text(text)
            if la:
                it["last_amended"] = la
        title = pretty_title(it["title"])
        body = convert(text, title)
        dst = os.path.join(REPO, it["path"])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="\n") as f:
            f.write(front(it, title) + f"# {title}\n\n" + body)
        it["chars"] = len(body)
        print(it["path"], len(body), flush=True)
    if not only:
        with open(os.path.join(wb.ROOT, "converted.json"), "w") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
