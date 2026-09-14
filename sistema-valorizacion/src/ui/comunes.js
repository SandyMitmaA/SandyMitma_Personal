// Capa 3 — utilidades de presentación compartidas por todos los frames.

export function el(tag, props = {}, ...hijos) {
  const nodo = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === 'clase') nodo.className = v;
    else if (k === 'html') nodo.innerHTML = v;
    else if (k === 'texto') nodo.textContent = v;
    else if (k === 'datos') for (const [dk, dv] of Object.entries(v)) nodo.dataset[dk] = dv;
    else if (k.startsWith('on') && typeof v === 'function') nodo.addEventListener(k.slice(2), v);
    else if (k === 'valor') nodo.value = v;
    else nodo.setAttribute(k, v === true ? '' : v);
  }
  agregar(nodo, hijos);
  return nodo;
}

function agregar(nodo, hijos) {
  for (const h of hijos.flat(4)) {
    if (h == null || h === false) continue;
    nodo.append(h instanceof Node ? h : document.createTextNode(String(h)));
  }
}

const numero = (min, max) => new Intl.NumberFormat('es-PE', { minimumFractionDigits: min, maximumFractionDigits: max });

export const fmt = {
  monto: (x) => (x == null || Number.isNaN(x) ? '—' : numero(2, 2).format(x)),
  nominal: (x) => (x == null || Number.isNaN(x) ? '—' : numero(0, 2).format(x)),
  precio: (x) => (x == null || Number.isNaN(x) ? '—' : numero(4, 6).format(x)),
  tasa: (x) => (x == null || Number.isNaN(x) ? '—' : `${numero(2, 4).format(x)} %`),
  entero: (x) => (x == null || Number.isNaN(x) ? '—' : numero(0, 0).format(x)),
  cambio: (x) => (x == null || Number.isNaN(x) ? '—' : numero(4, 6).format(x)),
  fecha: (iso) => (iso ? iso.split('-').reverse().join('/') : '—'),
  fechaISO: (iso) => iso || '—',
};

/** Tabla genérica. `columnas` = [{clave, titulo, alinear, formato, titulo2}] */
export function tabla(columnas, filas, opciones = {}) {
  const t = el('table', { clase: `tabla ${opciones.clase || ''}` });
  const thead = el('thead', {}, el('tr', {}, columnas.map((c) => el('th', { clase: c.alinear === 'der' ? 'der' : '', title: c.ayuda || null }, c.titulo))));
  const cuerpo = el('tbody', {}, filas.length
    ? filas.map((fila, i) => el('tr', { clase: opciones.claseFila ? opciones.claseFila(fila, i) : '' },
        columnas.map((c) => {
          const valor = c.render ? c.render(fila, i) : (c.formato ? c.formato(fila[c.clave], fila) : fila[c.clave]);
          return el('td', { clase: c.alinear === 'der' ? 'der' : '', title: c.tooltip ? c.tooltip(fila) : null },
            valor instanceof Node ? valor : (valor == null || valor === '' ? '—' : String(valor)));
        })))
    : [el('tr', {}, el('td', { colspan: columnas.length, clase: 'vacio' }, opciones.vacio || 'Sin datos.'))]);
  t.append(thead, cuerpo);
  if (opciones.pie) t.append(el('tfoot', {}, opciones.pie));
  return el('div', { clase: 'tabla-scroll' }, t);
}

export function etiqueta(texto, tono = 'neutro') {
  return el('span', { clase: `chip chip-${tono}` }, texto);
}

export function campo(titulo, control, ayuda) {
  return el('label', { clase: 'campo' }, el('span', { clase: 'campo-titulo' }, titulo), control,
    ayuda ? el('span', { clase: 'campo-ayuda' }, ayuda) : null);
}

export function entrada(props) {
  return el('input', { ...props });
}

export function seleccion(props, opciones, seleccionado) {
  return el('select', props, opciones.map(([valor, texto]) =>
    el('option', { value: valor, selected: String(valor) === String(seleccionado) || null }, texto)));
}

export function boton(texto, onclick, tono = '') {
  return el('button', { type: 'button', clase: `btn ${tono}`, onclick }, texto);
}

export function panel(titulo, ...contenido) {
  return el('section', { clase: 'panel' },
    titulo ? el('h2', { clase: 'panel-titulo' }, titulo) : null, ...contenido);
}

export function nota(texto, tono = 'info') {
  return el('p', { clase: `nota nota-${tono}` }, texto);
}

let contenedorAvisos = null;
export function aviso(mensaje, tono = 'ok') {
  if (!contenedorAvisos) {
    contenedorAvisos = el('div', { clase: 'avisos' });
    document.body.append(contenedorAvisos);
  }
  const n = el('div', { clase: `aviso aviso-${tono}` }, mensaje);
  contenedorAvisos.append(n);
  setTimeout(() => n.classList.add('saliendo'), 3200);
  setTimeout(() => n.remove(), 3800);
}

export function listaErrores(errores) {
  return el('ul', { clase: 'errores' }, errores.map((e) => el('li', {}, e)));
}

export function descargar(nombre, contenido, mime = 'text/csv;charset=utf-8') {
  const blob = new Blob([contenido], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = el('a', { href: url, download: nombre });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function confirmar(mensaje) {
  return window.confirm(mensaje);
}
