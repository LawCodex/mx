#!/usr/bin/env python3
"""Regenerate README.md counts and lists from _raw/mx/converted.json (written by mx_convert.py)."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wb  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
items = json.load(open(os.path.join(wb.ROOT, "converted.json")))
done = [i for i in items if not i.get("missing") and os.path.exists(os.path.join(REPO, i["path"]))]
missing = [i for i in items if i.get("missing")]
stale = [i for i in done if i.get("stale")]
cnt = Counter(i["path"].split("/")[0] for i in done)
from datetime import date
retrieved = os.environ.get("MX_RETRIEVED", date.today().isoformat())

DESC = {
    "constitucion": "Constitución Política de los Estados Unidos Mexicanos (texto vigente, all reforms applied)",
    "codigos": "Federal and national codes (Civil, Comercio, Penal, Fiscal, Procedimientos...)",
    "leyes": "Leyes federales, generales, orgánicas, reglamentarias + Estatuto, Ordenanza and the 1968 tax law",
    "decretos": "Presupuesto de Egresos de la Federación (annual budget decree listed among the laws)",
    "reglamentos": "Reglamentos of federal laws (Executive regulations) + internal rules of Congress",
}

rows = "\n".join(f"| `{k}/` | {DESC[k]} | {cnt.get(k, 0)} |" for k in DESC)
total = sum(cnt.values())


def lst(xs):
    return "\n".join(f"- {i['title']} (`{i['file']}`)" for i in xs) or "- none"


tpl = open(os.path.join(os.path.dirname(__file__), "README.template.md"), encoding="utf-8").read()
out = (tpl.replace("{{ROWS}}", rows).replace("{{TOTAL}}", str(total))
       .replace("{{MISSING}}", lst(missing)).replace("{{STALE}}", lst(stale))
       .replace("{{NLAWS}}", str(sum(1 for i in items if i["list"] == "leyes")))
       .replace("{{NREGS}}", str(sum(1 for i in items if i["list"] == "reglamentos")))
       .replace("{{REPEALED}}", lst([i for i in done if i["status"] == "repealed"]))
       .replace("{{RETRIEVED}}", retrieved))
open(os.path.join(REPO, "README.md"), "w", encoding="utf-8").write(out)
print(total, dict(cnt), "missing", len(missing), "stale", len(stale))
