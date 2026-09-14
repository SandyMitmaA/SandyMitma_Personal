// Bandeja de pendientes. Responde: que falta para poder valorizar.
import { el, enlaceModulo, formatearFecha, pedir } from '../componentes/nucleo.js';
import { estadoVacio, marca, tabla } from '../componentes/tabla.js';

const NIVEL = {
  SIN_POSICION: 'warn', SIN_PRECIOS: 'alert', COBERTURA_PARCIAL: 'warn',
  PENDIENTE_RECALCULO: 'warn', ELIMINACION_PENDIENTE: 'alert', PRECIOS_HUERFANOS: 'neutro',
};
const ETIQUETA_ESTADO = {
  Valorizado: 'ok', Listo: 'warn', 'Cobertura parcial': 'warn',
  'Sin precios': 'alert', Registrado: 'neutro',
};

export async function render(raiz) {
  const datos = await pedir('/pendientes');

  raiz.appendChild(el('div', { class: 'encabezado-modulo' }, [
    el('h1', { texto: 'Pendientes' }),
    el('span', { class: 'pregunta', texto: 'Que falta para que la cartera quede valorizada.' }),
  ]));

  const r = datos.resumen;
  raiz.appendChild(el('div', { class: 'panel' }, [
    el('div', { class: 'cifras' }, [
      cifra('Pendientes totales', r.total),
      cifra('Sin precios', r.por_tipo.SIN_PRECIOS || 0),
      cifra('Cobertura parcial', r.por_tipo.COBERTURA_PARCIAL || 0),
      cifra('Por reprocesar', (r.por_tipo.PENDIENTE_RECALCULO || 0) + (r.por_tipo.ELIMINACION_PENDIENTE || 0)),
      cifra('Instrumentos', datos.estados.length),
    ]),
  ]));

  const lista = el('div');
  if (!datos.pendientes.length) {
    lista.appendChild(estadoVacio(
      'No hay pendientes.',
      'Todos los instrumentos tienen cobertura completa de precios y su valorizacion esta al dia.',
      enlaceModulo('Ver la valorizacion', 'valorizacion')));
  } else {
    for (const p of datos.pendientes) {
      lista.appendChild(el('div', { class: 'pendiente' }, [
        marca(p.tipo.replace(/_/g, ' ').toLowerCase(), NIVEL[p.tipo] || 'neutro'),
        el('div', { class: 'texto' }, [
          el('div', { class: 'titulo', texto: p.titulo }),
          el('div', { class: 'detalle', texto: p.detalle }),
          p.fechas_faltantes && p.fechas_faltantes.length
            ? el('div', { class: 'mono-pequeno', texto: resumirFechas(p.fechas_faltantes) })
            : null,
        ]),
        enlaceModulo('Resolver', p.modulo, p.parametros || {}),
      ]));
    }
  }
  raiz.appendChild(el('div', { class: 'panel' }, [
    el('h2', {}, ['Cola de pendientes']), lista,
  ]));

  const columnas = ['isin', 'descripcion', 'moneda', 'nominal', 'fecha_alta',
    'fecha_vencimiento', 'estado', 'dias_cubiertos', 'dias_requeridos',
    'fechas_faltantes_total', 'fechas_desactualizadas'];
  raiz.appendChild(el('div', { class: 'panel' }, [
    el('h2', {}, ['Estado de cada instrumento']),
    tabla(columnas, datos.estados.map((e) => ({ ...e })), {
      claseFila: () => '',
      celdaClicable: (c, fila) => (c === 'isin'
        ? () => { location.hash = '#/valorizacion'; }
        : null),
    }),
    el('div', { class: 'leyenda' }, [
      'Estados:', ...Object.entries(ETIQUETA_ESTADO).map(([t, n]) => marca(t, n)),
    ]),
  ]));
}

/** Una lista de decenas de fechas no informa: se muestran las primeras. */
function resumirFechas(fechas) {
  const primeras = fechas.slice(0, 10).map(formatearFecha).join(', ');
  const resto = fechas.length - 10;
  return 'Primeras fechas sin precio: ' + primeras
    + (resto > 0 ? ` y ${resto} mas.` : '.');
}

function cifra(etiqueta, valor) {
  return el('div', { class: 'cifra' }, [
    el('div', { class: 'etiqueta', texto: etiqueta }),
    el('div', { class: 'valor', texto: String(valor) }),
  ]);
}
