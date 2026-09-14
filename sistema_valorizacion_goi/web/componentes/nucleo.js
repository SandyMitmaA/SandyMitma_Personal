// Utilidades compartidas: peticiones, formato numerico y construccion de DOM.

export const API = '/api/v1';

export async function pedir(camino, opciones = {}) {
  const r = await fetch(API + camino, {
    headers: { 'X-Usuario': estadoGlobal.usuario, ...(opciones.headers || {}) },
    ...opciones,
  });
  const tipo = r.headers.get('Content-Type') || '';
  if (!tipo.includes('application/json')) {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r;
  }
  const cuerpo = await r.json();
  if (!r.ok) {
    const e = new Error(cuerpo.error || `HTTP ${r.status}`);
    e.campo = cuerpo.campo;
    e.estado = r.status;
    throw e;
  }
  return cuerpo;
}

export const enviarJson = (camino, metodo, datos) =>
  pedir(camino, {
    method: metodo,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos),
  });

// --- Estado compartido: filtros persistentes entre modulos ----------------
const CLAVE = 'goi.filtros';
export const estadoGlobal = {
  usuario: 'analista',
  desde: '',
  hasta: '',
  isin: '',
  version: '',
  portafolio: '',
  monedaBase: 'USD',
  fechaInicio: '',
  parametros: {},
};

export function cargarFiltros() {
  try {
    Object.assign(estadoGlobal, JSON.parse(localStorage.getItem(CLAVE) || '{}'));
  } catch (e) { /* almacenamiento no disponible: se sigue con los valores por defecto */ }
}

export function guardarFiltros() {
  try {
    const { desde, hasta, isin, version, usuario } = estadoGlobal;
    localStorage.setItem(CLAVE, JSON.stringify({ desde, hasta, isin, version, usuario }));
  } catch (e) { /* sin persistencia local: los filtros duran la sesion */ }
}

// --- Formato de cifras. Seccion 12.2 -------------------------------------
export const DECIMALES = {
  precio: 6, tipo_cambio: 4, devengo_100: 8, monto: 2, entero: 0,
};

// Conteos: se formatean como enteros aunque su nombre contenga "total".
const COLUMNAS_ENTERAS = new Set([
  'fechas_faltantes_total', 'fechas_desactualizadas', 'valorizaciones_afectadas',
  'valorizaciones_totales', 'valorizaciones_cambiadas', 'requeridas', 'cubiertas',
  'faltantes', 'hallazgos', 'n', 'filas', 'linea', 'id', 'reproceso_id',
  'posicion_id', 'duracion_ms', 'frecuencia', 'fechas_en_archivo', 'primera',
]);

function tipoDeColumna(nombre) {
  const n = (nombre || '').toLowerCase();
  if (COLUMNAS_ENTERAS.has(n)) return 'entero';
  if (n.startsWith('precio')) return 'precio';
  if (n === 'fx' || n.includes('tipo_cambio')) return 'tipo_cambio';
  if (n.includes('devengo_por_100') || n.includes('cupon_por_periodo')) return 'devengo_100';
  if (n.includes('dias') || n === 'posiciones' || n.includes('version')) return 'entero';
  if (n.includes('nominal')) return 'monto';
  if (/(mv|devengo|control|quiebre|caja|cupon|alta|baja|cobros|efecto|residual|diferencia|total|impacto|valor)/.test(n)) {
    return 'monto';
  }
  return null;
}

export function esColumnaNumerica(nombre) {
  return tipoDeColumna(nombre) !== null;
}

/** Separador de miles, negativos entre parentesis, ceros como guion. */
export function formatearNumero(valor, decimales) {
  if (valor === null || valor === undefined || valor === '') return '';
  const n = Number(valor);
  if (!Number.isFinite(n)) return String(valor);
  // Ceros como guion. Un residuo que redondea a cero en la precision mostrada
  // es un cero de presentacion: mostrarlo como 0.00 sugiere un valor que no hay.
  if (Math.abs(n) < 0.5 * 10 ** -decimales) return '-';
  const abs = Math.abs(n).toLocaleString('es-PE', {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  });
  return n < 0 ? `(${abs})` : abs;
}

export function formatearCelda(columna, valor) {
  const tipo = tipoDeColumna(columna);
  if (tipo === null) return valor === null || valor === undefined ? '' : String(valor);
  return formatearNumero(valor, DECIMALES[tipo]);
}

export const monto = (v) => formatearNumero(v, 2);

export function formatearFecha(iso) {
  if (!iso) return '';
  const [a, m, d] = String(iso).slice(0, 10).split('-');
  return d ? `${d}/${m}/${a}` : iso;
}

// --- Construccion de DOM --------------------------------------------------
export function el(etiqueta, atributos = {}, hijos = []) {
  const nodo = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(atributos)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') nodo.className = v;
    else if (k === 'html') nodo.innerHTML = v;
    else if (k === 'texto') nodo.textContent = v;
    else if (k.startsWith('on')) nodo.addEventListener(k.slice(2).toLowerCase(), v);
    else nodo.setAttribute(k, v);
  }
  for (const h of [].concat(hijos)) {
    if (h === null || h === undefined || h === false) continue;
    nodo.appendChild(typeof h === 'string' ? document.createTextNode(h) : h);
  }
  return nodo;
}

export function limpiar(nodo) { while (nodo.firstChild) nodo.removeChild(nodo.firstChild); }

// --- Avisos ---------------------------------------------------------------
export function aviso(texto, nivel = '', siguiente = null) {
  const nodo = el('div', { class: `aviso ${nivel}` }, [el('div', { texto })]);
  if (siguiente) {
    const barra = el('div', { class: 'siguiente' });
    for (const s of [].concat(siguiente)) barra.appendChild(s);
    nodo.appendChild(barra);
  }
  return nodo;
}

export function enlaceModulo(texto, modulo, parametros = {}) {
  return el('button', {
    class: 'secundario',
    texto,
    onclick: () => {
      if (parametros.isin !== undefined) estadoGlobal.isin = parametros.isin || '';
      if (parametros.desde) estadoGlobal.desde = parametros.desde;
      if (parametros.hasta) estadoGlobal.hasta = parametros.hasta;
      guardarFiltros();
      location.hash = '#/' + modulo;
    },
  });
}

// --- Modal ----------------------------------------------------------------
export function modal(titulo, contenido, acciones = []) {
  const fondo = el('div', { class: 'fondo-modal' });
  const cerrar = () => fondo.remove();
  const caja = el('div', { class: 'modal' }, [
    el('h2', { texto: titulo }),
    el('div', { class: 'cuerpo' }, [contenido]),
    el('div', { class: 'pie' }, [
      ...acciones.map((a) =>
        el('button', {
          class: a.clase || 'secundario',
          texto: a.texto,
          onclick: async () => { const r = await a.al(); if (r !== false) cerrar(); },
        })),
      el('button', { class: 'secundario', texto: 'Cerrar', onclick: cerrar }),
    ]),
  ]);
  fondo.appendChild(caja);
  fondo.addEventListener('click', (e) => { if (e.target === fondo) cerrar(); });
  document.body.appendChild(fondo);
  return { cerrar, caja };
}

export function confirmarConMotivo(titulo, descripcion, alConfirmar) {
  const entrada = el('textarea', { rows: 3, style: 'width:100%',
    placeholder: 'Motivo obligatorio, en texto libre' });
  const error = el('div', { class: 'error-campo' });
  const contenido = el('div', {}, [descripcion, el('div', { style: 'margin-top:10px' }, [
    el('label', { texto: 'Motivo' }), entrada, error])]);
  modal(titulo, contenido, [{
    texto: 'Confirmar', clase: 'peligro',
    al: async () => {
      if (!entrada.value.trim()) { error.textContent = 'El motivo es obligatorio.'; return false; }
      await alConfirmar(entrada.value.trim());
      return true;
    },
  }]);
}
