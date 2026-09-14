// Frame 3 — Carga de Precios y FX del día.

import * as store from '../datos/almacen.js';
import { hoyISO, comparar } from '../core/fechas.js';
import { parsearTabla, aNumero, aFechaISO, aCSV } from '../datos/csv.js';
import { el, fmt, tabla, campo, entrada, boton, panel, nota, aviso, listaErrores, etiqueta, descargar } from './comunes.js';

let fecha = null;
let pegado = '';
let modo = 'precios';

export function render(contenedor, refrescar) {
  const datos = store.estado();
  if (!fecha) fecha = ultimaFechaConPrecio(datos) || hoyISO();

  contenedor.replaceChildren(
    el('div', { clase: 'encabezado-frame' },
      el('div', {},
        el('h1', {}, 'Precios y FX del día'),
        el('p', { clase: 'subtitulo' }, 'Capa de inputs: precio limpio por ISIN y tipo de cambio. Una revisión de precio no sobrescribe la historia — el valor anterior queda en la bitácora.')),
      el('div', { clase: 'barra' },
        campo('Fecha de valorización', entrada({ type: 'date', value: fecha, onchange: (e) => { fecha = e.target.value; refrescar(); } })))),

    panel(`Precios limpios al ${fmt.fecha(fecha)}`,
      nota(`Política de precio faltante vigente: ${datos.config.politicaPrecio === 'stale' ? 'arrastrar el último precio disponible con marca «stale»' : 'marcar error y no valorizar'}. Se cambia en Configuración.`, 'info'),
      tabla([
        { titulo: 'ISIN', render: (i) => el('code', {}, i.isin) },
        { clave: 'emisor', titulo: 'Emisor' },
        { clave: 'moneda', titulo: 'Moneda' },
        {
          titulo: 'Precio limpio', alinear: 'der', render: (i) => {
            const actual = datos.precios.find((p) => p.isin === i.isin && p.fecha === fecha);
            return entrada({
              type: 'number', step: '0.000001', clase: 'mini', value: actual?.precioLimpio ?? '',
              placeholder: 'sin cargar',
              onchange: (e) => {
                if (e.target.value === '') return;
                const r = store.guardarPrecio({ isin: i.isin, fecha, precioLimpio: aNumero(e.target.value), fuente: i.fuente });
                aviso(r.ok ? `Precio de ${i.isin} guardado.` : r.errores[0], r.ok ? 'ok' : 'error');
                refrescar();
              },
            });
          },
        },
        {
          titulo: 'Estado', render: (i) => {
            const hoy = datos.precios.find((p) => p.isin === i.isin && p.fecha === fecha);
            if (hoy) return etiqueta('oficial del día', 'ok');
            const previo = datos.precios.filter((p) => p.isin === i.isin && comparar(p.fecha, fecha) < 0).sort((a, b) => comparar(a.fecha, b.fecha)).pop();
            if (previo) return etiqueta(`stale · ${fmt.fecha(previo.fecha)}`, 'aviso');
            return etiqueta('sin precio', 'error');
          },
        },
        { titulo: 'Fuente', render: (i) => el('span', { clase: 'tenue' }, datos.precios.find((p) => p.isin === i.isin && p.fecha === fecha)?.fuente || i.fuente || '—') },
      ], datos.instrumentos, { vacio: 'Cargue instrumentos en el maestro antes de registrar precios.' })),

    panel(`Tipos de cambio al ${fmt.fecha(fecha)}`, formularioFX(datos, refrescar),
      tabla([
        { clave: 'par', titulo: 'Par' },
        { titulo: 'Fecha', render: (f) => fmt.fecha(f.fecha) },
        { titulo: 'Tipo de cambio', alinear: 'der', render: (f) => fmt.cambio(f.tipo) },
        { clave: 'fuente', titulo: 'Fuente' },
        { titulo: '', render: (f) => boton('Quitar', () => { store.quitarFX(f.id); refrescar(); }, 'peligro') },
      ], datos.fx.filter((f) => f.fecha === fecha), { vacio: 'Sin tipos de cambio para esta fecha. Si el portafolio es de una sola moneda, no hace falta cargar ninguno.' })),

    panelPegado(refrescar),

    panel('Historial cargado',
      el('div', { clase: 'acciones' },
        boton('Exportar precios a CSV', () => {
          const filas = datos.precios.slice().sort((a, b) => comparar(a.fecha, b.fecha) || a.isin.localeCompare(b.isin))
            .map((p) => [p.fecha, p.isin, p.precioLimpio, p.fuente]);
          descargar(`precios_${hoyISO()}.csv`, aCSV(['fecha', 'isin', 'precio_limpio', 'fuente'], filas));
        }),
        boton('Exportar FX a CSV', () => {
          const filas = datos.fx.slice().sort((a, b) => comparar(a.fecha, b.fecha)).map((f) => [f.fecha, f.par, f.tipo, f.fuente]);
          descargar(`fx_${hoyISO()}.csv`, aCSV(['fecha', 'par', 'tipo_cambio', 'fuente'], filas));
        })),
      el('p', { clase: 'tenue' }, `${datos.precios.length} precios y ${datos.fx.length} tipos de cambio en el almacén.`)),
  );
}

function formularioFX(datos, refrescar) {
  const par = entrada({ placeholder: 'USD/PEN', value: datos.fx.at(-1)?.par || 'USD/PEN' });
  const tipo = entrada({ type: 'number', step: '0.000001', placeholder: '3.5520' });
  const fuente = entrada({ placeholder: 'SBS / BCRP' });
  const errores = el('div');
  return el('div', {},
    el('div', { clase: 'rejilla' },
      campo('Par (base/cotizada)', par, 'USD/PEN significa 1 USD = X PEN.'),
      campo('Tipo de cambio', tipo),
      campo('Fuente', fuente)),
    errores,
    el('div', { clase: 'acciones' }, boton('Guardar tipo de cambio', () => {
      const r = store.guardarFX({ par: par.value.trim().toUpperCase(), fecha, tipo: aNumero(tipo.value), fuente: fuente.value });
      if (!r.ok) { errores.replaceChildren(listaErrores(r.errores)); return; }
      aviso('Tipo de cambio guardado.');
      refrescar();
    }, 'primario')));
}

function panelPegado(refrescar) {
  const area = el('textarea', {
    rows: 6, clase: 'pegado',
    placeholder: modo === 'precios'
      ? 'Pegue desde Excel: fecha; isin; precio_limpio; fuente\n2026-09-14; US91282CJT89; 98.4210; Bloomberg'
      : 'Pegue desde Excel: fecha; par; tipo_cambio; fuente\n2026-09-14; USD/PEN; 3.5510; SBS',
    oninput: (e) => { pegado = e.target.value; },
  });
  area.value = pegado;
  const resultado = el('div');

  return panel('Carga masiva (pegar desde Excel)',
    el('div', { clase: 'barra' },
      boton('Precios', () => { modo = 'precios'; refrescar(); }, modo === 'precios' ? 'primario' : ''),
      boton('Tipos de cambio', () => { modo = 'fx'; refrescar(); }, modo === 'fx' ? 'primario' : '')),
    nota('Acepta separador coma, punto y coma o tabulación, fechas dd/mm/aaaa o aaaa-mm-dd, y decimales con punto o coma. Si la primera fila es un encabezado, se ignora.', 'info'),
    area, resultado,
    el('div', { clase: 'acciones' }, boton('Procesar', () => {
      const filas = parsearTabla(pegado);
      if (!filas.length) { resultado.replaceChildren(listaErrores(['No hay nada que procesar.'])); return; }
      const errores = [];
      let cargadas = 0;
      for (const [n, celdas] of filas.entries()) {
        const f = aFechaISO(celdas[0]);
        if (!f) { if (n > 0) errores.push(`Fila ${n + 1}: fecha «${celdas[0]}» no reconocida.`); continue; }
        const r = modo === 'precios'
          ? store.guardarPrecio({ isin: (celdas[1] || '').trim(), fecha: f, precioLimpio: aNumero(celdas[2]), fuente: celdas[3] || '' })
          : store.guardarFX({ par: (celdas[1] || '').trim().toUpperCase(), fecha: f, tipo: aNumero(celdas[2]), fuente: celdas[3] || '' });
        if (r.ok) cargadas++;
        else errores.push(`Fila ${n + 1}: ${r.errores.join(' ')}`);
      }
      resultado.replaceChildren(
        el('p', { clase: 'nota nota-ok' }, `${cargadas} registro(s) cargado(s).`),
        errores.length ? listaErrores(errores) : null);
      if (cargadas) { pegado = ''; refrescar(); }
    }, 'primario')));
}

function ultimaFechaConPrecio(datos) {
  return datos.precios.map((p) => p.fecha).sort(comparar).pop() || null;
}
