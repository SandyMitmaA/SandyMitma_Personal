"""Lectura de CSV y Excel con la libreria estandar. Sin dependencias externas.

Un .xlsx es un zip de XML: se lee con zipfile y xml.etree. Los numeros se
devuelven siempre como texto para que nunca pasen por punto flotante.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import date, datetime, timedelta
from typing import Any, Iterable

NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

ALIAS = {
    "fecha": {"fecha", "date", "fecha_valorizacion", "fecha valorizacion", "f"},
    "isin": {"isin", "instrumento", "codigo", "id", "security"},
    "precio": {"precio", "price", "precio_proveedor", "precio proveedor", "px", "clean price"},
    "tipo_cambio": {"tipo_cambio", "tipo de cambio", "tc", "fx", "tipocambio",
                    "exchange rate", "tipo_de_cambio"},
    "fuente": {"fuente", "source", "proveedor"},
}


class ErrorArchivo(ValueError):
    pass


def _normalizar_encabezado(h: str) -> str:
    limpio = re.sub(r"\s+", " ", (h or "").strip().lower())
    for canonico, alias in ALIAS.items():
        if limpio in alias:
            return canonico
    return limpio


def _coordenada_a_columna(ref: str) -> int:
    letras = re.match(r"([A-Z]+)", ref or "")
    if not letras:
        return 0
    n = 0
    for c in letras.group(1):
        n = n * 26 + (ord(c) - 64)
    return n - 1


def _serial_excel_a_fecha(valor: str) -> str:
    try:
        n = float(valor)
    except ValueError:
        return valor
    if n < 1 or n > 100000:
        return valor
    base = datetime(1899, 12, 30)
    return (base + timedelta(days=int(n))).date().isoformat()


def leer_xlsx(contenido: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        import xml.etree.ElementTree as ET

        compartidas: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            raiz = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in raiz.findall("x:si", NS):
                compartidas.append("".join(t.text or "" for t in si.iter(
                    "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))

        hojas = sorted(n for n in z.namelist()
                       if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        if not hojas:
            raise ErrorArchivo("El archivo Excel no contiene hojas legibles.")
        raiz = ET.fromstring(z.read(hojas[0]))

        # Formatos de fecha declarados en el libro, para reconstruir seriales.
        estilos_fecha: set[int] = set()
        if "xl/styles.xml" in z.namelist():
            se = ET.fromstring(z.read("xl/styles.xml"))
            fmt_fecha = {14, 15, 16, 17, 22, 164, 165, 166, 167}
            for i, xf in enumerate(se.iter(
                    "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}xf")):
                nf = xf.get("numFmtId")
                if nf and int(nf) in fmt_fecha:
                    estilos_fecha.add(i)

        filas: list[list[str]] = []
        for fila in raiz.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
            celdas: dict[int, str] = {}
            for c in fila.findall("x:c", NS):
                idx = _coordenada_a_columna(c.get("r", ""))
                tipo = c.get("t")
                v = c.find("x:v", NS)
                if tipo == "inlineStr":
                    t = c.find("x:is/x:t", NS)
                    texto = t.text or "" if t is not None else ""
                elif tipo == "s" and v is not None:
                    texto = compartidas[int(v.text)] if v.text else ""
                else:
                    texto = v.text or "" if v is not None else ""
                    s = c.get("s")
                    if s is not None and int(s) in estilos_fecha and texto:
                        texto = _serial_excel_a_fecha(texto)
                celdas[idx] = texto
            if celdas:
                ancho = max(celdas) + 1
                filas.append([celdas.get(i, "") for i in range(ancho)])
        return filas


def leer_csv(contenido: bytes) -> list[list[str]]:
    for cod in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            texto = contenido.decode(cod)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ErrorArchivo("No se pudo decodificar el archivo.")
    muestra = texto[:4096]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t|")
    except csv.Error:
        dialecto = csv.excel
    return [list(f) for f in csv.reader(io.StringIO(texto), dialecto)]


def normalizar_fecha(v: str) -> str:
    """Acepta ISO, dd/mm/aaaa, dd-mm-aaaa y seriales de Excel."""
    s = (v or "").strip()
    if not s:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", s)
    if m:
        d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(a, mes, d).isoformat()
    if re.fullmatch(r"\d{4}[/.]\d{2}[/.]\d{2}", s):
        return s.replace("/", "-").replace(".", "-")
    if re.fullmatch(r"\d{5}(\.\d+)?", s):
        return _serial_excel_a_fecha(s)
    return s


def normalizar_numero(v: str) -> str:
    """Devuelve texto decimal. No convierte a float en ningun momento."""
    s = (v or "").strip().replace(" ", "")
    if not s:
        return ""
    s = s.replace(" ", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        entero, _, frac = s.partition(",")
        s = f"{entero}.{frac}" if len(frac) != 3 or len(entero) > 3 else s.replace(",", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    return s


def a_registros(filas: list[list[str]]) -> tuple[list[dict[str, str]], list[str]]:
    """Convierte una matriz en registros usando la primera fila no vacia como encabezado."""
    filas = [f for f in filas if any((c or "").strip() for c in f)]
    if not filas:
        raise ErrorArchivo("El archivo esta vacio.")

    # Busca la fila de encabezado. Permite banners previos, por ejemplo los que
    # el propio sistema escribe al exportar, para que reimportar funcione.
    indice = None
    for i, fila in enumerate(filas[:20]):
        cols = [_normalizar_encabezado(c) for c in fila]
        if "isin" in cols and "fecha" in cols:
            indice = i
            encabezado = cols
            break
    if indice is None:
        vistas = ", ".join(x for x in (_normalizar_encabezado(c) for c in filas[0]) if x)
        raise ErrorArchivo(
            "El archivo debe tener columnas 'fecha' e 'isin'. "
            f"En la primera fila se encontraron: {vistas}."
        )

    registros: list[dict[str, str]] = []
    for fila in filas[indice + 1:]:
        r: dict[str, str] = {}
        for i, col in enumerate(encabezado):
            if not col:
                continue
            r[col] = (fila[i] if i < len(fila) else "") or ""
        registros.append(r)
    return registros, encabezado


def leer(nombre: str, contenido: bytes) -> tuple[list[dict[str, str]], list[str]]:
    n = (nombre or "").lower()
    if n.endswith(".xlsx") or n.endswith(".xlsm"):
        filas = leer_xlsx(contenido)
    elif n.endswith(".xls"):
        raise ErrorArchivo(
            "El formato .xls antiguo no es legible. Guarda el archivo como .xlsx o .csv."
        )
    else:
        filas = leer_csv(contenido)
    return a_registros(filas)
