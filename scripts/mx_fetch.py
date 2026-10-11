#!/usr/bin/env python3
"""Enumerate and download the federal laws and regulations listed by the Cámara de Diputados
(LeyesBiblio) "Leyes Federales Vigentes" (index.htm) and "Reglamentos de Leyes Federales
Vigentes" (regla.htm) pages.

The origin www.diputados.gob.mx is tried first; if it is unreachable (it was, from our network,
see README), the latest Internet Archive Wayback Machine capture of each page / PDF is used.

Output: _raw/mx/manifest.json and the PDFs under _raw/mx/files/.
Usage: python mx_fetch.py [--limit N]
"""
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wb  # noqa: E402

DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def iso(s):
    m = DATE.search(s or "")
    if not m:
        return None
    d, mth, y = map(int, m.groups())
    try:
        return date(y, mth, d).isoformat()
    except ValueError:
        return None


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def slugify(s, maxlen=90):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s


def get_page(name):
    def fetch():
        data = wb.direct(name)
        if data:
            return data
        snaps = wb.cdx(name, since="2025")
        ts, orig = snaps[name.lower()]
        print(f"page {name}: wayback {ts}", flush=True)
        return wb.snapshot(ts, orig)
    raw = wb.cached("pages/" + name, fetch)
    return raw.decode("latin-1") if b"charset=utf-8" not in raw[:3000].lower() else raw.decode("utf-8")


def parse_laws(html):
    s = BeautifulSoup(html, "lxml")
    out = []
    for tr in s.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 4:
            continue
        pdf = [a["href"] for a in tds[3].find_all("a", href=True) if a["href"].lower().startswith("pdf/")]
        if not pdf:
            continue
        doc = [a["href"] for a in tds[3].find_all("a", href=True) if a["href"].lower().startswith("doc/")]
        ps = [clean(p.get_text(" ")) for p in tds[1].find_all("p")]
        ps = [p for p in ps if p]
        title = ps[0] if ps else clean(tds[1].get_text(" "))
        note = " ".join(ps[1:])
        ref = tds[1].find("a", href=True)
        last = clean(tds[2].get_text(" "))
        num = clean(tds[0].get_text(" "))
        status = "repealed" if re.search(r"abrogad", note + " " + title, re.I) and num.isalpha() else "in_force"
        first = title.split()[0].upper()
        if first.startswith("CONSTITUCI"):
            cat, typ = "constitucion", "constitution"
        elif first.startswith("CÓDIGO") or first.startswith("CODIGO"):
            cat, typ = "codigos", "code"
        elif first == "REGLAMENTO":
            cat, typ = "reglamentos", "regulation"
        elif first == "PRESUPUESTO":
            cat, typ = "decretos", "decree"
        else:
            cat, typ = "leyes", "law"
        out.append({
            "list": "leyes", "num": num, "title": title, "note": note, "category": cat, "type": typ,
            "date": iso(note), "last_amended_text": last,
            "last_amended": iso(last) if "DOF" in last and status == "in_force" else None,
            "abrogated": iso(last) if status == "repealed" else None,
            "file": pdf[0], "doc": doc[0] if doc else None,
            "ref": ref["href"] if ref and not ref["href"].lower().startswith(("pdf/", "doc/")) else None,
            "status": status,
        })
    return out


def parse_regs(html):
    s = BeautifulSoup(html, "lxml")
    out = []
    for tr in s.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 5:
            continue
        pdf = [a["href"] for a in tds[3].find_all("a", href=True) if a["href"].lower().endswith(".pdf")]
        if not pdf:
            continue
        doc = [a["href"] for a in tds[4].find_all("a", href=True)]
        ps = [clean(p.get_text(" ")) for p in tds[1].find_all("p")]
        ps = [p for p in ps if p]
        title = ps[0] if ps else ""
        num = clean(tds[0].get_text(" "))
        reforms = [iso(a.get_text(" ")) for p in tds[1].find_all("p") if "Reforma" in p.get_text()
                   for a in p.find_all("a")]
        reforms = sorted(r for r in reforms if r)
        note = " ".join(ps[1:])
        repealed = num.isalpha() or bool(re.search(r"\babrogad", note, re.I))
        col = iso(tds[2].get_text(" "))
        orig = re.search(r"Original\s+DOF\s+(\d{1,2}/\d{1,2}/\d{4})", note)
        out.append({
            "list": "reglamentos", "num": num, "title": title, "note": note,
            "category": "reglamentos", "type": "regulation",
            "date": (iso(orig.group(1)) if orig else None) if repealed else col,
            "abrogated": col if repealed else None,
            "last_amended_text": "DOF " + reforms[-1] if reforms else "",
            "last_amended": reforms[-1] if reforms else None,
            "file": pdf[0], "doc": doc[0] if doc else None, "ref": None,
            "status": "repealed" if repealed else "in_force",
        })
    return out


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    laws = parse_laws(get_page("index.htm"))
    regs = parse_regs(get_page("regla.htm"))
    print(f"{len(laws)} laws, {len(regs)} reglamentos listed", flush=True)
    items = laws + regs
    if limit:
        items = items[:limit]

    snaps = {}
    for prefix in ("pdf/", "regley/"):
        snaps.update(wb.cdx(prefix, prefix=True, since="2024"))
    def work(it):
        key = it["file"].lower()
        local = "files/" + it["file"]
        it["local"] = local
        it["source"] = wb.ORIGIN + it["file"]
        if os.path.exists(os.path.join(wb.ROOT, local)):
            return
        data = wb.direct(it["file"])
        if data and data[:4] == b"%PDF":
            it["via"] = "origin"
        else:
            data = None
            cands = [snaps[key]] if key in snaps else []

            def more():
                try:
                    return [c for c in wb.all_captures(it["file"]) if c != snaps.get(key)]
                except RuntimeError as e:
                    print("CDXFAIL", e, flush=True)
                    return []
            tried = 0
            while True:
                if not cands:
                    if tried:
                        break
                    tried = 1
                    cands = more()[:6]
                    if not cands:
                        break
                ts, orig = cands.pop(0)
                try:
                    d = wb.snapshot(ts, orig)
                except RuntimeError as e:
                    print("FAIL", e, flush=True)
                    continue
                if d[:4] == b"%PDF":
                    data = d
                    snaps[key] = (ts, orig)
                    wb.cached(local + ".json", lambda: json.dumps([ts, orig]).encode())
                    break
            if data is None:
                print("MISSING", it["file"], it["title"][:60], flush=True)
                it["missing"] = True
                return
        wb.cached(local, lambda: data)
        print("ok", it["file"], flush=True)

    with ThreadPoolExecutor(3) as ex:
        list(ex.map(work, items))
    # annotate snapshot info for cached files too
    for it in items:
        key = it["file"].lower()
        side = os.path.join(wb.ROOT, it["local"] + ".json")
        if os.path.exists(side):
            snaps[key] = tuple(json.load(open(side)))
        if "snapshot" not in it and key in snaps and it.get("via") != "origin" and not it.get("missing"):
            ts, orig = snaps[key]
            it["via"] = "wayback"
            it["wayback"] = f"https://web.archive.org/web/{ts}/{orig}"
            it["snapshot"] = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        it["stale"] = bool(it.get("snapshot") and it.get("last_amended") and it["snapshot"] < it["last_amended"])
    with open(os.path.join(wb.ROOT, "manifest.json"), "w") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    print("stale:", sum(i["stale"] for i in items), "missing:", sum(bool(i.get("missing")) for i in items))


if __name__ == "__main__":
    main()
