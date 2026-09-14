// Grilla de valorizacion. Responde: cuanto vale. Nada oculto.
import {
  API, aviso, el, enlaceModulo, estadoGlobal, formatearCelda, formatearFecha,
  guardarFiltros, limpiar, modal, monto, pedir,
} from '../componentes/nucleo.js';
import { estadoVacio, etiqueta, marca, tabla } from '../componentes/tabla.js';

const columnasConsolidado = (conCaja) => [
  'fecha', 'posiciones', 'security_mv_base', 'devengo_base', 'total_mv_base',
  ...(conCaja ? ['caja_base'] : []),
  'end_mv', 'total_mv_base_t0', 'quiebre_t0', 'estado_quiebre', 'eventos',
];

export async function render(raiz) {
  raiz.appendChild(el('div', { class: 'encabezado-modulo' }, [
    el('h1', { texto: 'Valorizacion' }),
    el('span', { class: 'pregunta',
      texto: 'Cuanto vale cada posicion y el portafolio, con todos los campos intermedios.' }),
  ]));

  const desde = el('input', { type: 'date', value: estadoGlobal.desde });
  const hasta = el('input', { type: 'date', value: estadoGlobal.hasta });
  const isin = el('input', { list: 'lista-isines', size: 16, value: estadoGlobal.isin,
    placeholder: 'todos' });
  const version = el('select', {}, []);
  const cuerpo = el('div');

  const catalogo = await pedir('/instrumentos');
  raiz.appendChild(el('datalist', { id: 'lista-isines' },
    catalogo.instrumentos.map((i) => el('option', { value: i.isin }))));

  const aplicar = async () => {
    estadoGlobal.desde = desde.value; estadoGlobal.hasta = hasta.value;
    estadoGlobal.isin = isin.value.trim().toUpperCase();
    estadoGlobal.version = version.value;
    guardarFiltros();
    await refrescar();
  };

  raiz.appendChild(el('div', { class: 'filtros' }, [
    el('div', { class: 'campo' }, [el('label', { texto: 'Desde' }), desde]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Hasta' }), hasta]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Instrumento' }), isin]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Version de calculo' }), version]),
    el('button', { texto: 'Aplicar', onclick: aplicar }),
    el('button', { class: 'secundario', texto: 'Comparar versiones',
      onclick: () => comparador(hasta.value) }),
    el('button', { class: 'secundario', texto: 'Exportar CSV',
      onclick: () => exportar('valorizacion', 'csv') }),
    el('button', { class: 'secundario', texto: 'Exportar Excel',
      onclick: () => exportar('valorizacion', 'xlsx') }),
  ]));
  raiz.appendChild(cuerpo);

  const vs = await pedir('/versiones');
  limpiar(version);
  version.appendChild(el('option', { value: '', texto: 'vigente' }));
  for (const v of vs.versiones) {
    version.appendChild(el('option', { value: String(v.id),
      texto: `v${v.id}  ${v.calculado_en}  (${v.filas} filas)` }));
  }
  version.value = estadoGlobal.version || '';

  function parametrosConsulta() {
    const q = new URLSearchParams({ desde: desde.value, hasta: hasta.value });
    if (isin.value.trim()) q.set('isines', isin.value.trim().toUpperCase());
    if (version.value) q.set('version', version.value);
    return q;
  }

  function exportar(vista, formato) {
    const q = parametrosConsulta(); q.set('formato', formato);
    window.open(`${API}/exportar/${vista}?${q}`, '_blank');
  }

  async function refrescar() {
    limpiar(cuerpo);
    const datos = await pedir('/valorizacion?' + parametrosConsulta());
    if (!datos.filas.length) {
      cuerpo.appendChild(el('div', { class: 'panel' }, [estadoVacio(
        'No hay valorizacion para este rango.',
        `No hay valorizacion calculada entre ${formatearFecha(desde.value)} y `
        + `${formatearFecha(hasta.value)}. Ejecuta el reproceso del rango.`,
        enlaceModulo('Ir a Reproceso', 'reproceso', { desde: desde.value, hasta: hasta.value }))]));
      return;
    }

    const ultimo = datos.consolidado[datos.consolidado.length - 1];
    cuerpo.appendChild(el('div', { class: 'panel' }, [
      el('h2', {}, [`Portafolio al ${formatearFecha(ultimo.fecha)}`]),
      el('div', { class: 'cifras' }, [
        cifra('Security MV base', monto(ultimo.security_mv_base)),
        cifra('Devengo base', monto(ultimo.devengo_base)),
        cifra('Total MV posiciones', monto(ultimo.total_mv_base)),
        datos.parametros.incluir_caja === 'true' ? cifra('Caja', monto(ultimo.caja_base)) : null,
        cifra('End MV', monto(ultimo.end_mv)),
        cifra('Control T+0', monto(ultimo.total_mv_base_t0)),
      ].filter(Boolean)),
    ]));

    cuerpo.appendChild(el('div', { class: 'panel' }, [
      el('h2', {}, ['Consolidado por fecha']),
      tabla(columnasConsolidado(datos.parametros.incluir_caja === 'true'),
        datos.consolidado, {
        claseFila: (f) => (f.estado_quiebre === 'Revisar' ? 'negativo' : ''),
        alHacerClic: (f) => { hasta.value = f.fecha; desde.value = f.fecha; aplicar(); },
      }),
    ]));

    cuerpo.appendChild(el('div', { class: 'panel' }, [
      el('h2', {}, [`Detalle por posicion (${datos.filas.length} filas)`]),
      tabla(datos.columnas, datos.filas, {
        alHacerClic: (f) => trazabilidad(f.fecha_valorizacion, f.isin),
        claseFila: (f) => (f.error ? 'negativo' : ''),
      }),
      el('div', { class: 'leyenda' }, [
        'Marcas:', marca('dato imputado', 'warn'),
        'Toda cifra se puede reconstruir a mano desde esta grilla. '
        + 'Haz clic en una fila para ver el precio y el tipo de cambio que la originaron.',
      ]),
    ]));
  }

  await refrescar();
}

async function trazabilidad(fecha, isin) {
  const t = await pedir(`/trazabilidad?fecha=${fecha}&isin=${isin}`);
  const v = t.valorizacion || {};
  const pasos = [
    ['1. Fecha de devengo', `${formatearFecha(v.fecha_valorizacion)} + ${estadoGlobal.parametros.desfase_devengo} dia(s) = ${formatearFecha(v.fecha_devengo)}`],
    ['2. Ubicacion en el calendario', `ultimo cupon ${formatearFecha(v.ultimo_cupon)}, proximo ${formatearFecha(v.proximo_cupon)} (busqueda ${estadoGlobal.parametros.busqueda_cupon})`],
    ['3. Dias', `${v.dias_transcurridos} de ${v.dias_periodo}`],
    ['4. Cupon por periodo', `${formatearCelda('cupon_por_periodo', v.cupon_por_periodo)} (convencion ${t.instrumento ? t.instrumento.convencion : ''})`],
    ['5. Devengo por 100', formatearCelda('devengo_por_100', v.devengo_por_100)],
    ['6. Precio del proveedor', `${formatearCelda('precio_proveedor', v.precio_proveedor)} expresado en ${t.instrumento ? t.instrumento.precio_expresado_en : ''}`],
    ['7. Tipo de cambio', formatearCelda('tipo_cambio', v.tipo_cambio)],
    ['8. Precio en moneda local', formatearCelda('precio_local', v.precio_local)],
    ['9. Security MV local', formatearCelda('security_mv_local', v.security_mv_local)],
    ['10. Devengo local', formatearCelda('devengo_local', v.devengo_local)],
    ['11. FX aplicado', formatearCelda('fx', v.fx)],
    ['12. Total MV base', formatearCelda('total_mv_base', v.total_mv_base)],
  ];
  modal(`${isin} al ${formatearFecha(fecha)}`, el('div', {}, [
    v.precio_imputado || v.tipo_cambio_imputado
      ? aviso('Esta fila usa datos imputados por arrastre. '
        + `Precio de origen ${formatearFecha(v.fecha_origen_precio)}, `
        + `tipo de cambio de ${formatearFecha(v.fecha_origen_tipo_cambio)}.`, 'warn')
      : null,
    tabla(['paso', 'valor'], pasos.map(([paso, valor]) => ({ paso, valor }))),
    el('div', { class: 'panel', style: 'margin-top:10px' }, [
      el('h2', {}, ['Registro de precio que la origino']),
      t.precio_origen
        ? tabla(['fecha', 'isin', 'precio', 'tipo_cambio', 'fuente', 'cargado_en', 'cargado_por'],
            [t.precio_origen])
        : estadoVacio('Sin registro de precio.', 'La fila se resolvio sin precio observado.')]),
    el('div', { class: 'panel' }, [
      el('h2', {}, ['Calendario de cupones del instrumento']),
      el('div', { class: 'cuerpo tabular',
        texto: t.calendario.map(formatearFecha).join('  ') })]),
    el('div', { class: 'panel' }, [
      el('h2', {}, ['Versiones de calculo de esta fecha']),
      tabla(['id', 'calculado_en', 'calculado_por', 'reproceso_id', 'filas'], t.versiones)]),
  ]), []);
}

async function comparador(fecha) {
  const vs = await pedir(`/versiones?fecha=${fecha}`);
  if (vs.versiones.length < 2) {
    modal('Comparador de versiones',
      aviso(`La fecha ${formatearFecha(fecha)} tiene una sola version de calculo. `
        + 'El comparador necesita dos.', 'warn'), []);
    return;
  }
  const a = el('select', {}, vs.versiones.map((v) =>
    el('option', { value: String(v.id), texto: `v${v.id}  ${v.calculado_en}` })));
  const b = el('select', {}, vs.versiones.map((v) =>
    el('option', { value: String(v.id), texto: `v${v.id}  ${v.calculado_en}` })));
  a.value = String(vs.versiones[1].id);
  b.value = String(vs.versiones[0].id);
  const salida = el('div');
  const comparar = async () => {
    limpiar(salida);
    const r = await pedir(`/comparar?fecha=${fecha}&a=${a.value}&b=${b.value}`);
    salida.appendChild(el('div', { class: 'cifras' }, [
      cifra(`Total v${r.version_a}`, monto(r.total_a)),
      cifra(`Total v${r.version_b}`, monto(r.total_b)),
      cifra('Diferencia', monto(Number(r.total_b) - Number(r.total_a))),
    ]));
    salida.appendChild(tabla(
      ['isin', 'presente_en_a', 'presente_en_b', 'total_a', 'total_b', 'diferencia',
       'diferencia_relativa'],
      r.filas.map((f) => ({ ...f, campos_distintos: (f.campos_distintos || []).join(', ') }))));
  };
  modal(`Comparar versiones al ${formatearFecha(fecha)}`, el('div', {}, [
    el('div', { class: 'filtros' }, [
      el('div', { class: 'campo' }, [el('label', { texto: 'Version A' }), a]),
      el('div', { class: 'campo' }, [el('label', { texto: 'Version B' }), b]),
      el('button', { texto: 'Comparar', onclick: comparar })]),
    salida]), []);
  await comparar();
}

function cifra(etiqueta, valor) {
  return el('div', { class: 'cifra' }, [
    el('div', { class: 'etiqueta', texto: etiqueta }),
    el('div', { class: 'valor', texto: String(valor) })]);
}
