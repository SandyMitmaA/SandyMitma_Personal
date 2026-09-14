// Frame 2. Carga de precios. Preview obligatorio, idempotente, sin recalcular.
import {
  API, aviso, el, enlaceModulo, enviarJson, estadoGlobal, formatearCelda, formatearFecha,
  guardarFiltros, limpiar, modal, pedir, confirmarConMotivo,
} from '../componentes/nucleo.js';
import { estadoVacio, marca, tabla } from '../componentes/tabla.js';

const NIVEL_FILA = { nueva: 'ok', identica: 'neutro', conflicto: 'warn', rechazada: 'alert' };

export async function render(raiz, ctx) {
  raiz.appendChild(el('div', { class: 'encabezado-modulo' }, [
    el('h1', { texto: 'Carga de precios' }),
    el('span', { class: 'pregunta', texto: 'Que precios y tipos de cambio hay, y cuales faltan.' }),
  ]));

  const isin = el('input', { list: 'lista-isines', value: estadoGlobal.isin, size: 16,
    placeholder: 'todos' });
  const desde = el('input', { type: 'date', value: estadoGlobal.desde });
  const hasta = el('input', { type: 'date', value: estadoGlobal.hasta });
  const archivo = el('input', { type: 'file', accept: '.csv,.xlsx,.xlsm,.txt' });

  const catalogo = await pedir('/instrumentos');
  const datalist = el('datalist', { id: 'lista-isines' },
    catalogo.instrumentos.map((i) => el('option', { value: i.isin })));

  const aplicar = () => {
    estadoGlobal.isin = isin.value.trim().toUpperCase();
    estadoGlobal.desde = desde.value; estadoGlobal.hasta = hasta.value;
    guardarFiltros(); refrescar();
  };

  raiz.appendChild(el('div', { class: 'filtros' }, [
    datalist,
    el('div', { class: 'campo' }, [el('label', { texto: 'Instrumento' }), isin]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Desde' }), desde]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Hasta' }), hasta]),
    el('button', { texto: 'Aplicar', onclick: aplicar }),
    el('div', { class: 'campo solo-captura' }, [
      el('label', { texto: 'Archivo CSV o Excel' }), archivo]),
    el('button', { class: 'solo-captura', texto: 'Previsualizar carga',
      onclick: () => previsualizar(archivo, isin.value.trim().toUpperCase(), ctx, refrescar) }),
    el('button', { class: 'secundario solo-captura', texto: 'Captura manual',
      onclick: () => capturaManual(catalogo, ctx, refrescar) }),
    el('button', { class: 'secundario', texto: 'Exportar CSV',
      onclick: () => descargar('precios', 'csv', isin.value, desde.value, hasta.value) }),
    el('button', { class: 'secundario', texto: 'Exportar Excel',
      onclick: () => descargar('precios', 'xlsx', isin.value, desde.value, hasta.value) }),
  ]));

  const cuerpo = el('div');
  raiz.appendChild(cuerpo);

  async function refrescar() {
    limpiar(cuerpo);
    const q = new URLSearchParams();
    if (isin.value.trim()) q.set('isin', isin.value.trim().toUpperCase());
    if (desde.value) q.set('desde', desde.value);
    if (hasta.value) q.set('hasta', hasta.value);
    const datos = await pedir('/precios?' + q.toString());

    cuerpo.appendChild(el('div', { class: 'panel' }, [
      el('h2', {}, ['Serie de precios cargada']),
      datos.filas.length
        ? tabla(['fecha', 'isin', 'precio', 'tipo_cambio', 'fuente', 'cargado_en',
                 'cargado_por', 'accion'],
            datos.filas.map((f) => ({ ...f, accion: 'eliminar' })),
            { celdaClicable: (c, f) => (c === 'accion' ? () => eliminar(f, refrescar, ctx) : null) })
        : estadoVacio(
            'No hay precios cargados para este filtro.',
            `No hay precios entre ${formatearFecha(desde.value)} y ${formatearFecha(hasta.value)}`
              + (isin.value ? ` para ${isin.value.toUpperCase()}.` : '.')
              + ' Carga un archivo CSV o Excel, o usa la captura manual.',
            el('button', { class: 'solo-captura', texto: 'Cargar archivo',
              onclick: () => archivo.click() })),
    ]));

    if (datos.huerfanos.length) {
      cuerpo.appendChild(el('div', { class: 'panel' }, [
        el('h2', {}, ['Series huerfanas de instrumentos eliminados']),
        tabla(['isin', 'n', 'desde', 'hasta', 'accion'],
          datos.huerfanos.map((h) => ({ ...h, accion: 'purgar' })),
          { celdaClicable: (c, f) => (c === 'accion' ? () => purgar(f, refrescar) : null) }),
        el('div', { class: 'leyenda' }, [
          'Se conservan como referencia. Si el instrumento se vuelve a registrar, no hay que recargarlas.']),
      ]));
    }
  }

  await refrescar();
}

function descargar(vista, formato, isin, desde, hasta) {
  const q = new URLSearchParams({ formato });
  if (isin) q.set('isin', isin.toUpperCase());
  if (desde) q.set('desde', desde);
  if (hasta) q.set('hasta', hasta);
  window.open(`${API}/exportar/${vista}?${q}`, '_blank');
}

// --- Preview obligatorio --------------------------------------------------
async function previsualizar(entradaArchivo, isinForzado, ctx, refrescar) {
  const f = entradaArchivo.files && entradaArchivo.files[0];
  if (!f) { modal('Sin archivo', aviso('Elige un archivo CSV o Excel primero.', 'warn'), []); return; }
  const contenido = await f.arrayBuffer();
  const q = new URLSearchParams({ archivo: f.name });
  if (isinForzado) q.set('isin', isinForzado);
  let vista;
  try {
    vista = await pedir('/precios/preview?' + q, { method: 'POST', body: contenido });
  } catch (e) { modal('No se pudo leer el archivo', aviso(e.message, 'alert'), []); return; }

  const r = vista.resumen;
  const conflictos = vista.filas.filter((x) => x.estado === 'conflicto');
  const rechazadas = vista.filas.filter((x) => x.estado === 'rechazada');
  const mensajes = vista.filas.flatMap((x) => x.mensajes || []);

  const contenido2 = el('div', {}, [
    vista.ya_cargado
      ? aviso(`Este archivo ya se cargo el ${vista.ya_cargado.momento}. `
        + 'La carga es idempotente: confirmar de nuevo no cambia nada.', 'warn')
      : null,
    el('div', { class: 'cifras' }, [
      cifra('Filas nuevas', r.nuevas), cifra('Identicas', r.identicas),
      cifra('En conflicto', r.conflicto), cifra('Rechazadas', r.rechazadas),
      cifra('TC en cero', r.tipo_cambio_en_cero), cifra('Duplicados internos', r.duplicados_internos),
    ]),
    conflictos.length
      ? el('div', { class: 'panel' }, [
          el('h2', {}, ['Filas en conflicto: valor anterior contra valor nuevo']),
          tabla(['fecha', 'isin', 'precio_anterior', 'precio', 'tipo_cambio_anterior', 'tipo_cambio'],
            conflictos)])
      : null,
    rechazadas.length
      ? el('div', { class: 'panel' }, [
          el('h2', {}, ['Filas rechazadas']),
          tabla(['linea', 'fecha', 'isin', 'precio', 'tipo_cambio'], rechazadas)])
      : null,
    el('div', { class: 'panel' }, [
      el('h2', {}, ['Todas las filas del archivo']),
      tabla(['linea', 'estado', 'fecha', 'isin', 'precio', 'tipo_cambio',
             'precio_local_implicito', 'precio_expresado_en'],
        vista.filas, { claseFila: () => '' })]),
    vista.cobertura.length
      ? el('div', { class: 'panel' }, [
          el('h2', {}, ['Cobertura resultante por instrumento']),
          tabla(['isin', 'rango_desde', 'rango_hasta', 'requeridas', 'cubiertas', 'faltantes'],
            vista.cobertura),
          el('div', { class: 'leyenda' }, [
            vista.cobertura.some((c) => c.faltantes)
              ? 'Las fechas que sigan faltando quedaran listadas en la bandeja de pendientes.'
              : 'La cobertura quedara completa para el rango obligatorio.'])])
      : null,
    mensajes.length
      ? el('div', { class: 'panel' }, [
          el('h2', {}, ['Avisos por fila']),
          el('div', { class: 'cuerpo' }, mensajes.slice(0, 80).map((m) =>
            el('div', { class: 'mono-pequeno', texto: m })))])
      : null,
  ]);

  modal(`Preview de ${f.name}`, contenido2, [{
    texto: 'Confirmar carga', clase: '',
    al: async () => {
      const res = await pedir('/precios/confirmar?' + q, { method: 'POST', body: contenido });
      await refrescar();
      await ctx.recargarNav();
      resultadoCarga(res);
      return true;
    },
  }]);
}

function resultadoCarga(res) {
  modal('Carga confirmada', el('div', {}, [
    res.idempotente
      ? aviso('El archivo ya estaba cargado. No cambio nada.', 'ok')
      : aviso(`${res.resumen.nuevas} filas nuevas, ${res.resumen.conflicto} corregidas, `
          + `${res.resumen.identicas} identicas, ${res.resumen.rechazadas} rechazadas.`, 'ok'),
    res.fechas_desactualizadas
      ? aviso(`${res.fechas_desactualizadas} fechas quedaron desactualizadas, entre `
          + `${formatearFecha(res.rango_desactualizado_desde)} y `
          + `${formatearFecha(res.rango_desactualizado_hasta)}. La carga no dispara recalculo.`,
          'warn', [enlaceModulo('Ir a Reproceso', 'reproceso',
            { desde: res.rango_desactualizado_desde, hasta: res.rango_desactualizado_hasta })])
      : null,
  ]), []);
}

// --- Captura manual -------------------------------------------------------
function capturaManual(catalogo, ctx, refrescar) {
  const filas = [];
  const tbody = el('tbody');
  const err = el('div', { class: 'error-campo' });

  const agregar = (valores = {}) => {
    const isin = el('input', { list: 'lista-isines', value: valores.isin || estadoGlobal.isin || '', size: 14 });
    const fecha = el('input', { type: 'date', value: valores.fecha || estadoGlobal.hasta || '' });
    const precio = el('input', { size: 14, value: valores.precio || '' });
    const tc = el('input', { size: 10, value: valores.tipo_cambio || '' });
    const fila = { isin, fecha, precio, tipo_cambio: tc };
    filas.push(fila);
    const tr = el('tr', {}, [isin, fecha, precio, tc].map((x) => el('td', {}, [x])));
    // Navegacion por tabulador natural: los campos van en orden de lectura.
    tc.addEventListener('keydown', (e) => {
      if (e.key === 'Tab' && !e.shiftKey && filas[filas.length - 1] === fila) agregar();
    });
    tbody.appendChild(tr);
    return fila;
  };
  for (let i = 0; i < 3; i += 1) agregar();

  const contenido = el('div', {}, [
    aviso('Tabula al final de la ultima fila para agregar otra. La captura pasa por el '
        + 'mismo preview y las mismas validaciones que un archivo.'),
    el('table', {}, [
      el('thead', {}, [el('tr', {}, ['ISIN', 'Fecha', 'Precio', 'Tipo de cambio']
        .map((t) => el('th', { texto: t })))]),
      tbody]),
    el('button', { class: 'secundario', texto: 'Agregar fila', onclick: () => agregar() }),
    err,
  ]);

  modal('Captura manual de precios', contenido, [{
    texto: 'Cargar', al: async () => {
      const datos = filas
        .map((f) => ({ isin: f.isin.value.trim().toUpperCase(), fecha: f.fecha.value,
          precio: f.precio.value.trim(), tipo_cambio: f.tipo_cambio.value.trim() }))
        .filter((f) => f.isin && f.fecha && f.precio);
      if (!datos.length) { err.textContent = 'No hay ninguna fila completa.'; return false; }
      try {
        const res = await enviarJson('/precios/manual', 'POST', { filas: datos });
        await refrescar(); await ctx.recargarNav(); resultadoCarga(res);
        return true;
      } catch (e) { err.textContent = e.message; return false; }
    },
  }]);
}

async function eliminar(fila, refrescar, ctx) {
  confirmarConMotivo(`Eliminar el precio de ${fila.isin} del ${formatearFecha(fila.fecha)}`,
    aviso('Si la fecha queda dentro del rango obligatorio del instrumento, este pasa a '
        + 'cobertura parcial y aparece en la bandeja de pendientes. No se sustituye en '
        + 'silencio por un arrastre.', 'warn'),
    async (motivo) => {
      const r = await enviarJson(`/precios/${fila.id}`, 'DELETE', { motivo });
      await refrescar(); await ctx.recargarNav();
      modal('Precio eliminado', aviso(`${r.fechas_desactualizadas} fecha(s) desactualizada(s).`,
        'warn', [enlaceModulo('Ir a Reproceso', 'reproceso')]), []);
    });
}

async function purgar(fila, refrescar) {
  confirmarConMotivo(`Purgar la serie huerfana de ${fila.isin}`,
    aviso(`Se eliminaran logicamente ${fila.n} registros entre ${formatearFecha(fila.desde)} `
        + `y ${formatearFecha(fila.hasta)}. Es una operacion separada y explicita.`, 'alert'),
    async (motivo) => {
      await enviarJson('/precios/purgar-huerfanos', 'POST', { isin: fila.isin, motivo });
      await refrescar();
    });
}

function cifra(etiqueta, valor) {
  return el('div', { class: 'cifra' }, [
    el('div', { class: 'etiqueta', texto: etiqueta }),
    el('div', { class: 'valor', texto: String(valor) })]);
}
