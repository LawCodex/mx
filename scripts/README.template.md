# LawCodex — México (Mexico)

Mexican federal legislation as plain Markdown, one file per law, generated from the consolidated
texts (*texto vigente*, with all reforms incorporated) published by the **Cámara de Diputados del
H. Congreso de la Unión** — Secretaría de Servicios Parlamentarios / Centro de Documentación,
Información y Análisis — in its *Leyes Federales Vigentes* collection (LeyesBiblio).

Part of [LawCodex](https://github.com/LawCodex): the legislation of every country as Markdown in git.

- Jurisdiction: Mexico (`mx`), federal level; language: Spanish (`es`)
- Source: Cámara de Diputados, *Leyes Federales Vigentes* — <https://www.diputados.gob.mx/LeyesBiblio/index.htm>
  and *Reglamentos de Leyes Federales Vigentes* — <https://www.diputados.gob.mx/LeyesBiblio/regla.htm>
- Retrieved: {{RETRIEVED}}
- Total: **{{TOTAL}}** files

## Coverage

| Directory | Content | Files |
|---|---|---:|
{{ROWS}}
| **Total** | | **{{TOTAL}}** |

The *Leyes Federales Vigentes* index lists {{NLAWS}} entries (the Constitution, codes, laws, plus a
few other instruments the Chamber publishes alongside them) and the *Reglamentos* index lists
{{NREGS}} federal regulations. Every listed entry whose PDF could be obtained is included:

- **`constitucion/`** — the Constitución Política de los Estados Unidos Mexicanos of 5 February 1917,
  current text with every reform applied, including the transitory articles of each reform decree.
- **`codigos/`** — Código Civil Federal, Código de Comercio, Código Penal Federal, Código Fiscal de la
  Federación, Código Nacional de Procedimientos Penales, Código Nacional de Procedimientos Civiles y
  Familiares, Código Federal de Procedimientos Civiles (being phased out by the national code),
  Código de Justicia Militar, Código Militar de Procedimientos Penales.
- **`leyes/`** — all leyes federales, leyes generales, leyes orgánicas, leyes reglamentarias and
  the annual Ley de Ingresos, plus the Estatuto de Gobierno del Distrito Federal, the Ordenanza
  General de la Armada and the 1968 *Impuesto sobre servicios expresamente declarados de interés
  público* law that appear in the same index.
- **`decretos/`** — the Presupuesto de Egresos de la Federación (annual budget decree), which the
  Chamber lists among the federal laws.
- **`reglamentos/`** — the regulations (*reglamentos*) issued by the Federal Executive under federal
  laws, from the Chamber's *Reglamentos de Leyes Federales Vigentes* page, plus the three internal
  rules of Congress listed in the laws index (Reglamento de la Cámara de Diputados, Reglamento del
  Senado, Reglamento para el Gobierno Interior del Congreso General).

Entries the Chamber marks as abrogated but still lists (e.g. because they remain applicable for a
transition period) are included with `status: repealed`:

{{REPEALED}}

### File format

Each file has YAML front matter (`title`, `identifier` = the Chamber's file name, `type`, `date` =
original DOF publication, `last_amended` = last reform published in the DOF according to the
document itself, `status`, `source` = official PDF URL, `archived_copy` = the Wayback Machine
capture actually used, `retrieved`) followed by the text:

- the law's own hierarchy (Libro / Parte / Título / Capítulo / Sección) becomes Markdown headings,
  levels assigned per document; articles are headings at the next level (or **bold** labels when
  the hierarchy is already six levels deep, as in the Código Civil Federal);
- the Chamber's editorial reform notes (*Artículo reformado DOF dd-mm-aaaa*, *Párrafo adicionado…*)
  are kept, in *italics*, after the provision they refer to;
- the transitory articles of the original law (`## TRANSITORIOS`) and of every reform decree
  (`## ARTÍCULOS TRANSITORIOS DE DECRETOS DE REFORMA`, then `### DECRETO …` per decree) are kept;
- tables (tariffs, rates, budget annexes, the tariff schedule of the LIGIE…) are kept as
  fixed-width `text` blocks reproducing the PDF layout; complex tables and mathematical formulas
  may not be perfectly aligned — check the official PDF (`source`) when in doubt. Images (seals,
  graphics) are not reproduced.

## Not covered

- State legislation (32 entidades federativas), municipal regulations.
- Treaties, Acuerdos, Normas Oficiales Mexicanas, decretos and other secondary instruments other than
  the reglamentos listed by the Chamber; historical (abrogated) laws in LeyesBiblio's *Leyes
  abrogadas* and *Reglamentos abrogados* pages; the reform history (individual reform decrees as
  published in the DOF).
- Entries whose PDF could not be obtained:

{{MISSING}}

### Possibly not the latest version

The PDF used is compared with the last-reform date shown in the index: the following files come
from a capture older than the latest reform listed by the Chamber, and may not include it:

{{STALE}}

## How the corpus was obtained (important)

`www.diputados.gob.mx` (and other Mexican federal government sites such as `dof.gob.mx` and
`ordenjuridico.gob.mx`) did not accept TCP connections from the network this corpus was built on
(connection timeouts on ports 80 and 443, apparently network-level filtering of non-Mexican
traffic). No attempt was made to circumvent that. Instead, the scripts use the **Internet Archive
Wayback Machine** copies of the very same official files: for every index page and PDF, the most
recent capture with HTTP 200 is fetched raw (`id_` mode, i.e. byte-identical to what the Chamber
served). The capture used is recorded in each file's `archived_copy` field and the official URL in
`source`. The capture dates are typically a few days to a few weeks before the retrieval date;
see the list above for files whose capture predates the last reform listed in the index.

When run from a network that can reach `www.diputados.gob.mx`, `scripts/mx_fetch.py` uses the
origin directly and only falls back to the Wayback Machine if the origin is unreachable.

## Licence / copyright

Under article 14, fraction VIII, of the Ley Federal del Derecho de Autor, legislative, regulatory,
administrative and judicial texts are not subject to copyright protection in Mexico: the texts are
in the public domain. The consolidated versions are prepared by the Cámara de Diputados for
information purposes; only the publication in the *Diario Oficial de la Federación* has legal
force. This Markdown conversion is unofficial.

## Regenerating

Requirements: Python 3 with `requests`, `lxml`, `beautifulsoup4` (`scripts/requirements.txt`) and
poppler's `pdftotext` on `PATH`.

```sh
python scripts/mx_fetch.py     # index pages + PDFs -> ../_raw/mx/ (cached), manifest.json
python scripts/mx_convert.py   # PDFs -> Markdown in constitucion/ codigos/ leyes/ decretos/ reglamentos/
python scripts/mx_readme.py    # README counts and lists (from scripts/README.template.md)
```

The Wayback Machine is accessed sequentially-ish (3 workers, ≥1.5 s between request starts) with
the User-Agent `LawCodex/1.0 (+https://github.com/LawCodex)`. Raw downloads are kept outside the
repository (`_raw/mx/`) and deleted after conversion.
