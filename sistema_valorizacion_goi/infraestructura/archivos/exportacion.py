"""Exportacion a CSV y Excel. Conserva la marca de dato imputado."""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from typing import Any, Sequence

ENCABEZADO_SISTEMA = "Sistema de Valorizacion Interno - GOI"


def a_csv(columnas: Sequence[str], filas: Sequence[dict], titulo: str = "") -> bytes:
    salida = io.StringIO()
    w = csv.writer(salida, lineterminator="\n")
    w.writerow([ENCABEZADO_SISTEMA])
    if titulo:
        w.writerow([titulo])
    w.writerow([f"Generado {datetime.now().isoformat(timespec='seconds')}"])
    w.writerow([])
    w.writerow(columnas)
    for f in filas:
        w.writerow(["" if f.get(c) is None else str(f.get(c)) for c in columnas])
    return salida.getvalue().encode("utf-8-sig")


def _escapar(v: Any) -> str:
    return (str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def a_xlsx(columnas: Sequence[str], filas: Sequence[dict], titulo: str = "") -> bytes:
    """Genera un .xlsx minimo y valido con cadenas en linea."""
    def celda(ref_col: int, ref_fila: int, valor: Any) -> str:
        col = ""
        n = ref_col
        while True:
            col = chr(65 + n % 26) + col
            n = n // 26 - 1
            if n < 0:
                break
        if valor is None or valor == "":
            return ""
        s = str(valor)
        try:
            float(s)
            es_numero = s.strip() != "" and not s.strip().startswith("+")
        except ValueError:
            es_numero = False
        if es_numero:
            return f'<c r="{col}{ref_fila}"><v>{_escapar(s)}</v></c>'
        return (f'<c r="{col}{ref_fila}" t="inlineStr"><is><t xml:space="preserve">'
                f"{_escapar(s)}</t></is></c>")

    partes: list[str] = []
    n_fila = 1
    for encabezado in (ENCABEZADO_SISTEMA, titulo,
                       f"Generado {datetime.now().isoformat(timespec='seconds')}", ""):
        partes.append(f'<row r="{n_fila}">{celda(0, n_fila, encabezado)}</row>')
        n_fila += 1
    partes.append(
        f'<row r="{n_fila}">'
        + "".join(celda(i, n_fila, c) for i, c in enumerate(columnas))
        + "</row>"
    )
    n_fila += 1
    for f in filas:
        partes.append(
            f'<row r="{n_fila}">'
            + "".join(celda(i, n_fila, f.get(c)) for i, c in enumerate(columnas))
            + "</row>"
        )
        n_fila += 1

    hoja = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(partes) + "</sheetData></worksheet>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   "</Types>")
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   "</Relationships>")
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheets><sheet name="Valorizacion" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                   "</Relationships>")
        z.writestr("xl/worksheets/sheet1.xml", hoja)
    return buf.getvalue()
