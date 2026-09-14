// Capa 0 — utilidades de fecha.
// Todas las fechas del sistema se manejan como texto ISO 'YYYY-MM-DD' y se
// operan en UTC para evitar corrimientos por zona horaria.

const MS_DIA = 86400000;

export function desdeISO(iso) {
  const [a, m, d] = String(iso).split('-').map(Number);
  return new Date(Date.UTC(a, m - 1, d));
}

export function aISO(fecha) {
  return fecha.toISOString().slice(0, 10);
}

export function esISO(valor) {
  return typeof valor === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(valor);
}

export function hoyISO() {
  return aISO(new Date());
}

export function comparar(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

export function sumarDias(iso, n) {
  return aISO(new Date(desdeISO(iso).getTime() + n * MS_DIA));
}

export function diasCalendario(iso1, iso2) {
  return Math.round((desdeISO(iso2).getTime() - desdeISO(iso1).getTime()) / MS_DIA);
}

/** Suma meses conservando el día de mes; si el día no existe, usa fin de mes. */
export function sumarMeses(iso, n) {
  const f = desdeISO(iso);
  const dia = f.getUTCDate();
  const base = new Date(Date.UTC(f.getUTCFullYear(), f.getUTCMonth() + n, 1));
  const ultimoDia = new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth() + 1, 0)).getUTCDate();
  base.setUTCDate(Math.min(dia, ultimoDia));
  return aISO(base);
}

export function esFinDeSemana(iso) {
  const d = desdeISO(iso).getUTCDay();
  return d === 0 || d === 6;
}

/**
 * @param {string} iso
 * @param {Set<string>} feriados fechas ISO no hábiles de la plaza
 */
export function esHabil(iso, feriados = new Set()) {
  return !esFinDeSemana(iso) && !feriados.has(iso);
}

export function siguienteHabil(iso, feriados = new Set()) {
  let f = iso;
  let guarda = 0;
  while (!esHabil(f, feriados)) {
    f = sumarDias(f, 1);
    if (++guarda > 400) throw new Error(`No se encontró día hábil desde ${iso}`);
  }
  return f;
}

/** Suma n días hábiles. n = 0 devuelve la misma fecha sin ajustar (T+0). */
export function sumarHabiles(iso, n, feriados = new Set()) {
  if (n <= 0) return iso;
  let f = iso;
  for (let i = 0; i < n; i++) f = siguienteHabil(sumarDias(f, 1), feriados);
  return f;
}

/** Lista inclusiva de fechas calendario entre dos ISO. */
export function rangoFechas(desde, hasta) {
  const out = [];
  for (let f = desde; comparar(f, hasta) <= 0; f = sumarDias(f, 1)) out.push(f);
  return out;
}
