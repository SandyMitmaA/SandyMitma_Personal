// Shell de la aplicacion: barra superior, navegacion y enrutado por hash.
import { cargarFiltros, el, estadoGlobal, guardarFiltros, limpiar, pedir } from './componentes/nucleo.js';

const MODULOS = [
  { id: 'pendientes',   titulo: 'Pendientes',             grupo: 'Inicio' },
  { id: 'registro',     titulo: 'Registro de instrumentos', grupo: 'Captura' },
  { id: 'precios',      titulo: 'Carga de precios',       grupo: 'Captura' },
  { id: 'reproceso',    titulo: 'Reproceso',              grupo: 'Calculo' },
  { id: 'valorizacion', titulo: 'Valorizacion',           grupo: 'Consulta' },
  { id: 'puente',       titulo: 'Begin/End MV',           grupo: 'Consulta' },
  { id: 'control',      titulo: 'Control y quiebres',     grupo: 'Consulta' },
  { id: 'validaciones', titulo: 'Validaciones',           grupo: 'Consulta' },
];

const cache = {};
let pendientesPorModulo = {};

async function cargarModulo(id) {
  if (!cache[id]) cache[id] = await import(`./modulos/${id}.js`);
  return cache[id];
}

function dibujarNav(activo) {
  const nav = document.getElementById('nav');
  limpiar(nav);
  let grupo = null;
  for (const m of MODULOS) {
    if (m.grupo !== grupo) {
      grupo = m.grupo;
      nav.appendChild(el('div', { class: 'grupo', texto: grupo }));
    }
    const n = pendientesPorModulo[m.id];
    nav.appendChild(el('a', { href: `#/${m.id}`, class: m.id === activo ? 'activo' : '' }, [
      el('span', { texto: m.titulo }),
      n !== undefined ? el('span', { class: `contador ${n ? '' : 'cero'}`, texto: String(n) }) : null,
    ]));
  }
}

async function refrescarContadores() {
  try {
    const p = await pedir('/pendientes');
    const t = p.resumen.por_tipo || {};
    pendientesPorModulo = {
      pendientes: p.resumen.total,
      registro: t.SIN_POSICION || 0,
      precios: (t.SIN_PRECIOS || 0) + (t.COBERTURA_PARCIAL || 0) + (t.PRECIOS_HUERFANOS || 0),
      reproceso: (t.PENDIENTE_RECALCULO || 0) + (t.ELIMINACION_PENDIENTE || 0),
    };
  } catch (e) { pendientesPorModulo = {}; }
}

async function enrutar() {
  const id = (location.hash.replace('#/', '') || 'pendientes').split('?')[0];
  const modulo = MODULOS.find((m) => m.id === id) ? id : 'pendientes';
  await refrescarContadores();
  dibujarNav(modulo);
  const vista = document.getElementById('vista');
  limpiar(vista);
  vista.appendChild(el('div', { class: 'vacio', texto: 'Cargando...' }));
  try {
    const m = await cargarModulo(modulo);
    limpiar(vista);
    await m.render(vista, { recargarNav: async () => { await refrescarContadores(); dibujarNav(modulo); } });
  } catch (e) {
    limpiar(vista);
    vista.appendChild(el('div', { class: 'aviso alert' }, [
      el('div', { texto: `No se pudo abrir el modulo ${modulo}: ${e.message}` }),
    ]));
    console.error(e);
  }
}

async function iniciar() {
  cargarFiltros();
  const estado = await pedir('/estado');
  estadoGlobal.parametros = estado.parametros;
  estadoGlobal.monedaBase = estado.parametros.moneda_base;
  estadoGlobal.fechaInicio = estado.parametros.fecha_inicio_portafolio;
  estadoGlobal.portafolio = estado.portafolio ? estado.portafolio.nombre : '-';
  if (!estadoGlobal.desde) estadoGlobal.desde = estado.rango_valorizado.desde || estadoGlobal.fechaInicio;
  if (!estadoGlobal.hasta) estadoGlobal.hasta = estado.rango_valorizado.hasta || estadoGlobal.fechaInicio;

  document.getElementById('bs-portafolio').textContent = estadoGlobal.portafolio;
  document.getElementById('bs-moneda').textContent = estadoGlobal.monedaBase;
  const fecha = document.getElementById('bs-fecha');
  fecha.value = estadoGlobal.hasta;
  fecha.addEventListener('change', () => {
    estadoGlobal.hasta = fecha.value;
    if (estadoGlobal.desde > estadoGlobal.hasta) estadoGlobal.desde = fecha.value;
    guardarFiltros();
    enrutar();
  });
  const usuario = document.getElementById('bs-usuario');
  usuario.value = estadoGlobal.usuario;
  usuario.addEventListener('change', () => {
    estadoGlobal.usuario = usuario.value.trim() || 'analista';
    guardarFiltros();
  });

  window.addEventListener('hashchange', enrutar);
  // Atajos de teclado para las acciones frecuentes.
  window.addEventListener('keydown', (e) => {
    if (!e.altKey || e.ctrlKey || e.metaKey) return;
    const indice = '12345678'.indexOf(e.key);
    if (indice >= 0) { location.hash = `#/${MODULOS[indice].id}`; e.preventDefault(); }
  });
  await enrutar();
}

iniciar().catch((e) => {
  document.getElementById('vista').innerHTML =
    `<div class="aviso alert">No se pudo iniciar la aplicacion: ${e.message}</div>`;
});
