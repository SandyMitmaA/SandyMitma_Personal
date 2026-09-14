# Sistema de Valorización de Portafolios de Renta Fija — Fase 1

Sistema web que valoriza diariamente un portafolio de renta fija, instrumento
por instrumento y consolidado, en dos versiones de accrued/precio sucio
(**A**: oficial de mercado, **B**: sistema interno +1 día), y que deja guardados
los **BMV/EMV** diarios que la Fase 2 consumirá para calcular el TWRR sin
rediseñar nada.

Si un día no hay operaciones, no se carga nada: el motor sigue arrastrando la
posición vigente, devengando el cupón y generando los flujos de caja del
calendario por su cuenta.

## Cómo ejecutarlo

El sistema no necesita instalarse ni compilarse: es HTML con módulos ES nativos.
Lo único que hace falta es **servirlo por `http://`**, porque el navegador
bloquea los módulos ES abiertos con doble clic sobre el archivo (`file://`).
Cualquier servidor estático sirve.

**Opción 1 — doble clic (la más simple).** `abrir-windows.bat` en Windows,
`abrir-mac-linux.sh` en macOS o Linux. Levanta el servidor, abre el navegador y
usa Node si está instalado o Python si no.

**Opción 2 — por consola.** Abrir una terminal en esta carpeta y correr:

```bash
npm start                     # con Node: http://localhost:8123
python -m http.server 8123    # alternativa sin Node, mismo resultado
```

En Windows, para abrir la terminal en la carpeta: escribir `cmd` en la barra de
direcciones del Explorador de archivos y presionar Enter.

**Opción 3 — sin instalar nada.** Abrir la carpeta en VS Code e instalar la
extensión *Live Server*; luego clic derecho sobre `index.html` → *Open with Live
Server*.

Para correr las pruebas del motor sí hace falta Node 18 o superior:

```bash
npm test     # 21 pruebas
```

La primera vez que se abre, el sistema siembra un **portafolio de ejemplo**
(4 instrumentos en dólares, con un cupón y una amortización dentro de la
ventana, 1 al 14 de setiembre de 2026) para que se pueda recorrer de inmediato.
Al cargar datos reales, bórrelo desde **Configuración → Borrar todo**; una vez
borrado no se vuelve a sembrar. También se puede recargar cuando se quiera desde
**Configuración → Cargar portafolio de demostración**.

Los datos se guardan en el `localStorage` del navegador. Exporte el respaldo
JSON desde Configuración antes de cambiar de equipo o limpiar el navegador.

## Arquitectura en 3 capas

```
src/datos/almacen.js ── Capa 1  INPUTS      maestro, calendario, operaciones, precios, FX, feriados
src/core/motor.js    ── Capa 2  MOTOR       posición vigente, accrued, SMV, TMV, BMV/EMV, caja
src/ui/frame-*.js    ── Capa 3  REPORTES    tabla comparativa, consolidado, alertas, serie BMV/EMV
```

El motor (`src/core/`) no toca el DOM ni el navegador: son funciones puras que
se importan igual desde las pruebas de Node y desde la interfaz. La capa 2 se
recalcula entera en cada consulta a partir de la capa 1 — **no existe ningún
valor calculado que se persista y pueda quedar desactualizado**.

### Pantallas

| Frame | Capa | Qué hace |
|---|---|---|
| **Maestro de Instrumentos** | Inputs | Alta/edición de instrumentos y generación del `Calendario_Cupones` hacia atrás desde el vencimiento, con edición fila por fila para calendarios irregulares. |
| **Operaciones** | Inputs | Compra, venta, aporte y rescate. Tabla append-only con reversa. |
| **Precios y FX** | Inputs | Precio limpio por ISIN y tipo de cambio, con carga masiva pegando desde Excel. |
| **Valorización** | Reportes | Tabla comparativa A vs. B, detalle campo por campo, consolidado, movimientos de caja, cuadre y serie BMV/EMV. |
| **Configuración** | Gobierno | Reglas de cálculo, feriados por plaza, respaldo JSON y bitácora de revisiones. |

## Reglas de negocio implementadas

Las diez reglas no negociables del diseño, y dónde viven:

1. **Posición vigente jamás cargada a mano** — no existe API para escribirla.
   Se deriva en `correrMotor()` de `posición(t−1) ± operaciones(t) ± amortizaciones(t)`.
2. **Cupones y amortizaciones automáticos** — salen del `Calendario_Cupones` en
   su fecha de pago. `validarOperacion()` rechaza explícitamente cargarlos como operación.
3. **Caja como posición** — ISIN sintético `CASH_<moneda>`, con su propio BMV/EMV.
4. **Flujo interno/externo desde el origen** — cada movimiento de caja nace marcado.
5. **Operaciones append-only** — el almacén expone `agregarOperacion()` y
   `reversarOperacion()`; no hay editar ni borrar.
6. **Versión A es la única fuente de retornos** — la serie BMV/EMV se alimenta
   solo de A; el EMV de B se muestra como referencia y nunca se arrastra.
7. **Cuadre diario obligatorio** — la identidad se recalcula desde los inputs
   crudos y se compara contra el nominal que arrastra el motor, con alerta si no cuadra.
8. **Jerarquía de fuentes** — fuente y fecha de última verificación por
   instrumento; toda revisión de precio queda en la bitácora.
9. **Precio faltante nunca falla en silencio** — política explícita (arrastrar
   con marca `stale`, o marcar error), siempre con alerta visible.
10. **Feriados por plaza** — definen tanto el T+n de la Versión A como el
    «+1 día» de la Versión B.

## Cálculo

**Versión A** — fecha de liquidación = T+n hábiles de la plaza del instrumento.
**Versión B** — fecha de liquidación = fecha de valorización + 1 día (hábil o
calendario, configurable). Idéntica a A en todo lo demás.

```
accrued_por_100 = cupón_del_período × días_transcurridos ÷ días_del_período   (30/360, ACT/ACT ICMA)
accrued_por_100 = cupón_anual × días_transcurridos ÷ 365  (ó 360)             (ACT/365, ACT/360)

SMV = nominal_vigente × precio_limpio ÷ 100
TMV = SMV + accrued + cupón_devengado_por_cobrar

EMV_i(t) = TMV_i(t) de la Versión A
BMV_i(t) = EMV_i(t−1)          (el primer día de la serie, el TMV inicial de carga)
```

Convenciones soportadas: `30/360` (US bond basis), `ACT/ACT` (ICMA), `ACT/365`
y `ACT/360`. Tipos: bullet, amortizable y cupón cero.

## Decisiones de modelado que van más allá del enunciado

Tres casos donde el diseño literal producía un valor de portafolio que saltaba
sin que pasara nada económico. Como esos saltos se convertirían en retornos
diarios falsos encadenados al TWRR oficial de la Fase 2, el motor los puentea:

**1. Liquidaciones pendientes (`PEND_<moneda>`).** La posición cambia en la
fecha de operación, pero la caja recién se mueve en la fecha de liquidación.
Entre ambas, el importe vive en una posición sintética, de modo que el TMV total
no salte al liquidar. Es contabilidad a fecha de operación con su cuenta por
pagar/cobrar.

**2. Cupón devengado por cobrar.** Cuando la fecha de liquidación cruza una
fecha de pago que todavía no ocurrió, la convención de mercado reinicia el
devengo en el período nuevo — pero el efectivo aún no entró a caja. Sin puente,
un bono con T+2 muestra una caída del tamaño del cupón varios días antes del
pago y un rebote el día del pago. Medido sobre el portafolio de demostración con
precios congelados, eran −90.175 el 03/09 y +69.929 el 08/09; con el puente, la
serie solo devenga. El monto se muestra como columna propia y `TMV = SMV +
accrued + cupón por cobrar`. La prueba
`la liquidación que cruza una fecha de cupón no crea un salto ficticio de valor`
fija este comportamiento.

**3. Consolidado siempre en moneda de reporte.** Cada instrumento se muestra en
su **moneda de origen** y el consolidado del portafolio va en la **moneda de
reporte** (USD por defecto). Todos los totales —SMV, accrued, TMV A, TMV B, BMV,
EMV y el flujo externo `F(t)`— se convierten con el mismo criterio de FX antes
de sumarse: sumar importes de monedas distintas sin convertir no significa nada,
y `F(t)` tiene que estar en la misma moneda que `V(t)` para que la fórmula de
retorno de la Fase 2 cierre. En un portafolio de una sola moneda, como el de
demostración, la conversión es la identidad y no hay que cargar ningún tipo de
cambio.

Supuestos declarados, por si conviene revisarlos con el área de inversiones:

- El cupón se paga sobre el nominal vigente al **inicio** del día de pago; una
  compra del mismo día no lo cobra.
- El accrued de un amortizable se calcula sobre el nominal vigente a la fecha de
  valorización (no se prorratea dentro del período de amortización).
- La compra y la venta mueven caja por **precio + accrued** a la fecha de
  liquidación de la operación.
- El primer día de la serie, `BMV = EMV` (carga inicial), por lo que la
  variación de ese día es cero por construcción.

## Lo que queda para la Fase 2

Fuera de alcance por decisión de diseño, pero con el modelo de datos ya
preparado: frame de Retornos TWRR, atribución por instrumento, tasas flotantes,
bonos callables y reportes de gobernanza avanzada.

La Fase 2 **solo consume**, no recalcula. Para cada fecha, el consolidado ya
expone lo que pide la fórmula:

```
r(t)  = (V(t) − F(t)) ÷ V(t−1) − 1        V(t−1) = consolidado.bmv
TWRR  = Π (1 + r(t)) − 1                  V(t)   = consolidado.emv
                                          F(t)   = consolidado.flujoExterno
```

Los flujos internos (compra/venta, cupones, amortizaciones) no se restan: ya
están reflejados en la variación de `V(t)` porque tanto el bono como la caja son
posiciones sumadas. La serie se puede exportar a CSV desde el frame de
Valorización.

## Estructura

```
sistema-valorizacion/
├── index.html, app.css          Shell y estilos
├── abrir-windows.bat            Lanzadores de doble clic
├── abrir-mac-linux.sh
├── src/
│   ├── app.js                   Navegación entre frames
│   ├── core/                    MOTOR (puro, sin DOM)
│   │   ├── fechas.js            Días hábiles, feriados, aritmética de fechas
│   │   ├── conteo-dias.js       30/360, ACT/ACT, ACT/365, ACT/360 y devengo
│   │   ├── calendario.js        Generación del Calendario_Cupones
│   │   ├── fx.js                Tipo de cambio directo, inverso y stale
│   │   └── motor.js             Posición, caja, valorización A/B, BMV/EMV
│   ├── datos/                   INPUTS
│   │   ├── almacen.js           Persistencia, validaciones, append-only
│   │   ├── demo.js              Portafolio de demostración
│   │   └── csv.js               Importación/exportación
│   └── ui/                      REPORTES (los 5 frames)
├── pruebas/motor.test.mjs       21 pruebas del motor
└── herramientas/
    ├── servidor.mjs             Servidor estático sin dependencias
    └── construir-artefacto.mjs  Deriva de index.html la página para publicar
```

## Publicar como página web

`node herramientas/construir-artefacto.mjs <destino.html>` deriva de `index.html`
la variante que esperan los visores que aportan su propio `<!doctype>`/`<head>`
(la página publicada no puede traer esas etiquetas). Se genera en vez de
mantenerse a mano para que no existan dos plantillas que se desincronicen; hay
que publicarla junto con `app.css` y el árbol `src/` en sus mismas rutas
relativas.

## Escalamiento

El motor recalcula toda la serie desde el inicio del portafolio en cada consulta.
Con decenas de instrumentos y meses de histórico es instantáneo. Si crece a
cientos de instrumentos o años de histórico con recálculo diario, el paso
natural es mover `src/core/` a un backend con base de datos: las funciones son
puras y no dependen del navegador, así que migran sin reescribirse.
