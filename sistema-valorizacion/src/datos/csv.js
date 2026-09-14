// Utilidades CSV: importación de precios/FX pegados desde Excel y exportación
// de la tabla de valorización.

/** Acepta separador coma, punto y coma o tabulación (lo que venga de Excel). */
export function parsearTabla(texto) {
  const lineas = String(texto).trim().split(/\r?\n/).filter((l) => l.trim());
  if (!lineas.length) return [];
  const sep = detectarSeparador(lineas[0]);
  return lineas.map((linea) => linea.split(sep).map((c) => c.trim().replace(/^"|"$/g, '')));
}

function detectarSeparador(linea) {
  const candidatos = ['\t', ';', ','];
  let mejor = ',';
  let max = 0;
  for (const c of candidatos) {
    const n = linea.split(c).length;
    if (n > max) { max = n; mejor = c; }
  }
  return mejor;
}

/** Convierte "1.234,56" o "1,234.56" o "98.42" a número. */
export function aNumero(texto) {
  if (typeof texto === 'number') return texto;
  let t = String(texto).trim().replace(/\s/g, '');
  if (!t) return NaN;
  const ultimaComa = t.lastIndexOf(',');
  const ultimoPunto = t.lastIndexOf('.');
  if (ultimaComa > -1 && ultimoPunto > -1) {
    if (ultimaComa > ultimoPunto) t = t.replace(/\./g, '').replace(',', '.');
    else t = t.replace(/,/g, '');
  } else if (ultimaComa > -1) {
    t = t.replace(',', '.');
  }
  return Number(t);
}

/** Normaliza dd/mm/aaaa y aaaa-mm-dd a ISO. */
export function aFechaISO(texto) {
  const t = String(texto).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(t)) return t;
  const m = t.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/);
  if (m) return `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
  return null;
}

export function aCSV(encabezados, filas) {
  const escapar = (v) => {
    const s = v == null ? '' : String(v);
    return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [encabezados.map(escapar).join(';'), ...filas.map((f) => f.map(escapar).join(';'))].join('\n');
}
