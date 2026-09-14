// Frame 5 — Configuración, calendario de feriados, respaldo y bitácora.

import * as store from '../datos/almacen.js';
import { datosDemo } from '../datos/demo.js';
import { hoyISO } from '../core/fechas.js';
import { el, fmt, tabla, campo, entrada, seleccion, boton, panel, nota, aviso, etiqueta, descargar, confirmar } from './comunes.js';

let plazaNueva = 'US';

export function render(contenedor, refrescar) {
  const datos = store.estado();
  const c = datos.config;
  const plazas = [...new Set([...datos.instrumentos.map((i) => i.plaza), ...datos.feriados.map((f) => f.plaza), 'US', 'PE', 'EU'])].filter(Boolean);
  const monedas = [...new Set([...datos.instrumentos.map((i) => i.moneda), 'USD', 'PEN', 'EUR'])];

  contenedor.replaceChildren(
    el('div', { clase: 'encabezado-frame' },
      el('div', {},
        el('h1', {}, 'Configuración y gobierno de datos'),
        el('p', { clase: 'subtitulo' }, 'Reglas de cálculo, calendario de feriados por plaza, respaldo del almacén y bitácora de revisiones.'))),

    panel('Reglas de valorización',
      el('div', { clase: 'rejilla' },
        campo('Moneda de reporte', seleccion({ onchange: (e) => { store.actualizarConfig({ monedaReporte: e.target.value }); refrescar(); } }, monedas.map((m) => [m, m]), c.monedaReporte),
          'Moneda a la que se convierte el consolidado.'),
        campo('Umbral de alerta A vs. B (bp del nominal)', entrada({ type: 'number', step: '0.01', min: '0', value: c.umbralBp, onchange: (e) => { store.actualizarConfig({ umbralBp: Number(e.target.value) }); refrescar(); } }),
          'Si |TMV_A − TMV_B| supera este umbral, la posición se marca en alerta.'),
        campo('Política de precio faltante', seleccion({ onchange: (e) => { store.actualizarConfig({ politicaPrecio: e.target.value }); refrescar(); } },
          [['stale', 'Arrastrar el último precio con marca «stale»'], ['error', 'Marcar error y no valorizar']], c.politicaPrecio),
          'Nunca falla en silencio: en ambos casos la alerta queda visible.'),
        campo('«+1 día» de la Versión B', seleccion({ onchange: (e) => { store.actualizarConfig({ versionBHabil: e.target.value === 'habil' }); refrescar(); } },
          [['habil', 'Siguiente día hábil de la plaza'], ['calendario', 'Día calendario siguiente']], c.versionBHabil ? 'habil' : 'calendario')),
        campo('Plaza por defecto', seleccion({ onchange: (e) => { store.actualizarConfig({ plazaPorDefecto: e.target.value }); refrescar(); } }, plazas.map((p) => [p, p]), c.plazaPorDefecto)),
        campo('Fecha de inicio del portafolio', entrada({ type: 'date', value: c.fechaInicio || '', onchange: (e) => { store.actualizarConfig({ fechaInicio: e.target.value || null }); refrescar(); } }),
          'Primer día de la serie BMV/EMV. Si se deja vacío, se toma la primera operación registrada.')),
      nota('La Versión A es la única fuente válida para retornos oficiales. La Versión B es exclusivamente control interno de diferencias y nunca se mezcla con la serie histórica reportada.', 'info')),

    panel('Calendario de feriados por plaza de liquidación',
      nota('Determinan el T+n de la Versión A y el «+1 día» de la Versión B. Los sábados y domingos ya se excluyen automáticamente.', 'info'),
      formularioFeriado(plazas, refrescar),
      tabla([
        { clave: 'plaza', titulo: 'Plaza' },
        { titulo: 'Fecha', render: (f) => fmt.fecha(f.fecha) },
        { clave: 'descripcion', titulo: 'Descripción' },
        { titulo: '', render: (f) => boton('Quitar', () => { store.quitarFeriado(f.id); refrescar(); }, 'peligro') },
      ], datos.feriados.slice().sort((a, b) => (a.plaza === b.plaza ? a.fecha.localeCompare(b.fecha) : a.plaza.localeCompare(b.plaza))),
        { vacio: 'Sin feriados cargados: solo se excluyen fines de semana.' })),

    panel('Respaldo y datos de ejemplo',
      nota('Los datos viven en el navegador (localStorage). Exporte el respaldo antes de cambiar de equipo o de limpiar el navegador.', 'alerta'),
      el('div', { clase: 'acciones' },
        boton('Exportar respaldo JSON', () => {
          descargar(`valorizacion_respaldo_${hoyISO()}.json`, JSON.stringify(store.estado(), null, 2), 'application/json');
          aviso('Respaldo exportado.');
        }, 'primario'),
        importador(refrescar),
        boton('Cargar portafolio de demostración', () => {
          if (!confirmar('Se reemplazan todos los datos actuales por el portafolio de demostración. ¿Continuar?')) return;
          store.reemplazar(datosDemo());
          aviso('Portafolio de demostración cargado (1 al 14 de setiembre de 2026).');
          refrescar();
        }),
        boton('Borrar todo', () => {
          if (!confirmar('Se borran instrumentos, operaciones, precios y FX. Esta acción no se puede deshacer. ¿Continuar?')) return;
          store.limpiar();
          aviso('Almacén vacío.', 'alerta');
          refrescar();
        }, 'peligro')),
      el('p', { clase: 'tenue' }, `${datos.instrumentos.length} instrumentos · ${datos.calendario.length} filas de calendario · ${datos.operaciones.length} operaciones · ${datos.precios.length} precios · ${datos.fx.length} tipos de cambio.`)),

    panel('Bitácora de revisiones',
      nota('Registro de altas, ediciones, reversas y revisiones de precio, para poder reconstruir cómo se calculó cualquier valorización ya reportada.', 'info'),
      tabla([
        { titulo: 'Fecha y hora', render: (b) => new Date(b.ts).toLocaleString('es-PE') },
        { titulo: 'Acción', render: (b) => etiqueta(b.accion, b.accion.includes('revision') || b.accion === 'reversa' ? 'aviso' : 'neutro') },
        { clave: 'detalle', titulo: 'Detalle' },
      ], datos.bitacora.slice(0, 100), { vacio: 'Sin movimientos registrados.' })),
  );
}

function formularioFeriado(plazas, refrescar) {
  const fechaEntrada = entrada({ type: 'date' });
  const descripcion = entrada({ placeholder: 'Fiestas Patrias' });
  return el('div', {},
    el('div', { clase: 'rejilla' },
      campo('Plaza', seleccion({ onchange: (e) => { plazaNueva = e.target.value; } }, plazas.map((p) => [p, p]), plazaNueva)),
      campo('Fecha', fechaEntrada),
      campo('Descripción', descripcion)),
    el('div', { clase: 'acciones' }, boton('Agregar feriado', () => {
      if (!fechaEntrada.value) { aviso('Indique la fecha del feriado.', 'error'); return; }
      store.agregarFeriado({ plaza: plazaNueva, fecha: fechaEntrada.value, descripcion: descripcion.value });
      aviso('Feriado agregado.');
      refrescar();
    }, 'primario')));
}

function importador(refrescar) {
  const input = el('input', {
    type: 'file', accept: '.json', clase: 'oculto',
    onchange: async (e) => {
      const archivo = e.target.files?.[0];
      if (!archivo) return;
      try {
        const leido = JSON.parse(await archivo.text());
        if (!Array.isArray(leido.instrumentos)) throw new Error('El archivo no tiene la estructura esperada.');
        if (!confirmar('Se reemplazan todos los datos actuales por el contenido del respaldo. ¿Continuar?')) return;
        store.reemplazar(leido);
        aviso('Respaldo restaurado.');
        refrescar();
      } catch (err) {
        aviso(`No se pudo leer el respaldo: ${err.message}`, 'error');
      } finally {
        e.target.value = '';
      }
    },
  });
  const btn = boton('Restaurar respaldo JSON', () => input.click());
  return el('span', {}, btn, input);
}
