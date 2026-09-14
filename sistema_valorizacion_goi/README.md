# Sistema de Valorización Interno · GOI

Sistema web de back office para valorizar carteras de renta fija. Entrega el valor
de mercado de cada posición, su desagregación en precio y devengo, y el puente
Begin MV a End MV. El caso de uso central es el **reproceso retroactivo**.

---

## Cómo abrirlo

No requiere instalar nada: ni `pip`, ni `npm`, ni un servidor de base de datos.
Lo único necesario es **Python 3.9 o superior**, que viene de fábrica en macOS y
Linux y se instala desde la Microsoft Store en Windows.

```
python3 run.py
```

Se abre solo en <http://127.0.0.1:8765>. En Windows puedes hacer doble clic en
`iniciar.bat`; en macOS o Linux, ejecutar `./iniciar.sh`.

| Opción | Qué hace |
|---|---|
| `--puerto 9000` | Arranca en otro puerto |
| `--bd cartera.sqlite` | Usa otro archivo de base de datos |
| `--sembrar` | Carga los datos de ejemplo de la Parte IV |
| `--reiniciar` | Borra la base y la vuelve a crear |
| `--pruebas` | Ejecuta las 130 pruebas y sale |
| `--sin-navegador` | No abre el navegador |

La primera vez, si la base está vacía, se cargan los tres instrumentos, las tres
posiciones y los siete precios del juego de prueba. Ve a **Reproceso** y ejecuta
el rango propuesto para ver la cartera valorizada.

### La base de datos

Es un único archivo **SQLite** en `datos/valorizacion_goi.sqlite`. Se puede abrir
y consultar con cualquier visor (DB Browser for SQLite, la extensión SQLite de
VS Code, el propio `sqlite3`) sin necesidad de tener el sistema corriendo, y se
copia o respalda copiando el archivo. Al detener el servidor con `Ctrl+C` se
vuelca el diario WAL al archivo principal, de modo que basta con ese fichero;
si copias la base con el sistema corriendo, lleva también los `-wal` y `-shm`
que estén junto a ella.

> **Nota de precisión.** SQLite es de tipado dinámico y convierte la afinidad
> `NUMERIC` a coma flotante binaria en cuanto el literal no es entero. Para no
> perder un solo dígito, **todo monto, tasa, precio y tipo de cambio se almacena
> como `TEXT`** con su representación decimal exacta y se reconstruye con
> `Decimal` al leer. Ningún valor monetario existe como `FLOAT` en ningún punto
> del sistema; hay una prueba dedicada que lo verifica.

---

## Arquitectura

Cuatro capas, con las dependencias apuntando en una sola dirección.

```
/dominio                  librería pura: sin base de datos, sin HTTP, sin framework
    /valorizacion         motor, calendario de cupones, convenciones, series de mercado
    /puente               Begin/End MV y la columna de control
    /caja                 cobros y redenciones en moneda de origen
    /control              clasificación del quiebre contra T+0
/aplicacion
    /casos_uso            registrar, cargar precios, reprocesar, consultar, validar
    puertos.py            interfaces de repositorio que implementa la infraestructura
/infraestructura
    /persistencia         repositorios SQLite, migraciones, semilla
    /archivos             lectura de CSV y Excel, exportación a CSV y Excel
    /trabajos             cola de reprocesos en segundo plano
/api                      REST v1 y servidor HTTP (solo biblioteca estándar)
/web
    /modulos              un archivo por frame
    /componentes          grilla numérica, formato de cifras, modales
    /estilos              tokens.css es el único lugar con hexadecimales
/tests
    /dominio  /integracion  /e2e  /fixtures
/migraciones              versionadas y reversibles
```

**El dominio se ejecuta sin levantar la aplicación.** Las pruebas de
`tests/dominio` cargan la maestra, la posición y un precio en memoria, invocan el
motor y comparan contra las cifras de la Parte IV. Ninguna necesita base de datos.

No hay reglas de negocio en SQL, en triggers ni en componentes de interfaz.
Ningún número mágico vive en el código: `desfase_devengo`, `dias_max_arrastre`,
`tolerancia_quiebre` y los demás salen de `dominio/configuracion.py`, con valores
por defecto en un único lugar y sobreescritura por portafolio en la tabla
`parametro`.

### Sin dependencias externas

Todo se construyó sobre la biblioteca estándar, que es lo que permite abrir el
sistema sin instalar nada:

| Necesidad | Solución |
|---|---|
| Aritmética decimal de precisión arbitraria | `decimal.Decimal` |
| Base de datos | `sqlite3` |
| Servidor HTTP | `http.server.ThreadingHTTPServer` |
| Lectura y escritura de Excel | `zipfile` + `xml.etree` (un `.xlsx` es un zip de XML) |
| Lectura de CSV | `csv`, con detección de delimitador |
| Cola de trabajos | `queue` + `threading` |
| Pruebas | `unittest` |
| Frontend | ES modules nativos, sin framework y sin paso de compilación |

---

## Los tres frames

Son independientes: se operan por separado, posiblemente por personas distintas
y en momentos distintos. Lo que los une es el **estado de cada instrumento**, que
el sistema deriva y muestra siempre, y la **bandeja de pendientes**, que es la
pantalla de inicio.

1. **Registro de instrumentos.** Alta, consulta, edición y baja lógica. Al
   guardar muestra el calendario de cupones derivado para confirmación visual.
   No pide precios ni dispara cálculos.
2. **Carga de precios.** CSV, Excel y captura manual, con preview obligatorio y
   clave única `(fecha, isin)`. Rechaza duplicados, no los suma. Es idempotente.
   No dispara recálculo: marca fechas como desactualizadas.
3. **Reproceso.** El único módulo que dispara cálculo. Análisis de impacto antes
   de ejecutar, ejecución transaccional en segundo plano, historial y reporte de
   reexpresión.

---

## Decisiones de implementación que conviene conocer

Tres puntos donde la especificación admitía lectura y el sistema tomó una
posición explícita. Los tres están comentados en el código y cubiertos por
pruebas.

### 1. El precio en moneda local se cuantiza a la precisión de precio

El modelo de referencia de la Parte IV reconstruye `precio_local` a seis
decimales y usa ese valor en todo el cálculo. Sin esa cuantización, el Total MV
de `CA135087M276` al 31/07/2026 da **13,162,247.00** en vez de los
**13,162,246.93** verificados, y el consolidado del portafolio se desvía en
0.07. Es la única cuantización que no es de presentación, por eso es un parámetro
declarado y no un redondeo escondido:

```
cuantizar_precio_local = true      # dominio/configuracion.py
decimales_precio       = 6
```

Ponerlo en `false` deja el cálculo sin ningún redondeo intermedio, y hay una
prueba que documenta la diferencia exacta que eso produce.

### 2. La guarda de vencimiento también cubre la búsqueda inclusiva

La guarda de la sección 1.3 usa mayor estricto, de modo que con
`fecha_devengo` igual al vencimiento no dispara y el devengo sale por la vía
normal dando el periodo completo. Eso es correcto bajo búsqueda **estricta**.
Bajo búsqueda **inclusiva** —la convención del control T+0— esa misma fecha deja
el calendario sin próximo cupón. El sistema aplica entonces la misma guarda:
`dias = 0`, `devengo = 0`. Nunca se rellena el calendario con una fecha
centinela; el motor lanza una excepción antes que dejar pasar una fecha de
relleno al resultado.

### 3. El cupón de la fecha de vencimiento no se cuenta dos veces

Con la caja activa, la redención aporta `nominal * (1 + cupon_por_periodo/100)`,
es decir principal **más** cupón final. Contar además ese cupón en la línea
«cupón pagado» del puente lo duplicaría y rompería la columna de control. Por eso
la condición de cupón pagado exige vigencia también en `t`, y el cupón de
vencimiento viaja dentro de la redención. Con esa regla el control da cero en las
186 combinaciones, con caja y sin ella, que es lo que la Parte IV exige.

### 4. Una versión de cálculo es una publicación completa de sus fechas

La versión vigente se resuelve por **fecha**, no por `(fecha, isin)`. Con la
segunda forma, una versión que deja de publicar un instrumento —porque su
posición fue eliminada— no lo retiraba: la fila antigua seguía siendo el máximo
para esa combinación y sobrevivía al reproceso. Un reproceso parcial arrastra sin
tocar las filas que no recalcula, de modo que cada versión sigue siendo una foto
completa del rango.

### 5. El arrastre de precios en el juego de prueba

La Parte IV trae precios en fechas sueltas y exige valorizar los 62 días del
periodo, con las 186 filas del puente en cero. Eso solo es posible con un
arrastre generoso, así que la carga de ejemplo fija `dias_max_arrastre = 120`.
**El valor por defecto del sistema sigue siendo 4**, como indica la sección 7.1.
Todo dato arrastrado se marca como imputado y se distingue visualmente en la
interfaz y en las exportaciones.

---

## Pruebas

```
python3 run.py --pruebas
```

130 pruebas, con el peso en la base de la pirámide:

| Capa | Qué cubre |
|---|---|
| `tests/dominio` | Las cuatro filas de resultados esperados, el consolidado, el control T+0, la caja, el puente, las cuatro convenciones y los casos de borde |
| `tests/integracion` | Carga con duplicados, con tipo de cambio en cero y con huecos; idempotencia; registro y eliminación; panel de validaciones; cola de trabajos; contrato de la API |
| `tests/e2e` | La prueba de reproceso retroactivo completa (siete pasos) y la de eliminación con reproceso (ocho pasos) |
| `tests/test_regresion_numerica.py` | Corrida completa del periodo contra `tests/fixtures/referencia.json`, versionado en el repositorio |

Ninguna prueba compara montos por igualdad exacta: todas usan una tolerancia
declarada en `tests/fixtures/datos.py`.

Para regenerar el archivo de referencia tras un cambio justificado:

```
python3 -m tests.generar_referencia
```

Cobertura de línea del dominio medida con `trace` de la biblioteca estándar:
**98.2 %** (1279 de 1302 líneas ejecutables). Las líneas restantes son guardas
defensivas inalcanzables, como la que impide que un calendario mal derivado
entre en bucle. La exigencia de 100 % de **ramas** de la sección 17 no se puede
acreditar con la biblioteca estándar: `trace` mide líneas, no ramas. Con
`coverage` instalado, `coverage run --branch -m unittest discover -s tests -t .`
da la medida exacta.

---

## Cifras de aceptación reproducidas

| Comprobación | Esperado | Resultado |
|---|---|---|
| Portafolio al 31/05/2026 | 64,337,667.97 | ✅ |
| Control T+0 al 31/05/2026 | 64,331,028.10 | ✅ |
| Portafolio al 31/07/2026 | 63,212,688.76 | ✅ |
| Control T+0 al 31/07/2026 | 63,206,499.83 | ✅ |
| End MV con caja al 31/07/2026 | 114,413,367.76 | ✅ |
| Efectivo al 31/07/2026 | 51,200,679.00 | ✅ |
| Precio implícito en CAD al 31/05/2026 | 92.798 | ✅ |
| Cupón de CA135087M276 el 01/06/2026 | 108,311.07 USD | ✅ |
| Control del puente en 186 combinaciones | cero | ✅ |
| 62 días clasificados como un día de devengo, residual | 0.00 | ✅ |
| Calendario de US91282CQY02 | 30/06 y 31/12 | ✅ |
| Diferencia contra el valor de redención | 11,902.32 | ✅ |
| Reproceso retroactivo, 32 fechas del 30/06 al 31/07 | 32 | ✅ |
| Total tras el alta retroactiva | 63,212,688.76 | ✅ |
| Reejecución sin cambios | sin versión nueva | ✅ |
| Eliminación y reproceso | 13,162,246.93 | ✅ |
| Begin MV al 31/05 sin la posición inicial | 50,783,915.44 | ✅ |

Las dos filas críticas —la fecha de devengo cayendo exactamente sobre una fecha
de cupón (31/05/2026, CA135087M276) y sobre el vencimiento (30/07/2026,
US91282CLB53)— dan 0.75 y 2.1875, no cero, confirmando que la búsqueda estricta
está implementada literalmente.

---

## API

REST versionada bajo `/api/v1`. El usuario se identifica con la cabecera
`X-Usuario`, que alimenta la bitácora.

| Método | Ruta | Para qué |
|---|---|---|
| `GET` | `/estado` | Portafolio, parámetros y rango valorizado |
| `PUT` | `/parametros` | Cambia parámetros y marca lo afectado |
| `GET` | `/pendientes` | Bandeja de pendientes y estado de cada instrumento |
| `GET` `POST` | `/instrumentos` | Maestra y posiciones |
| `POST` | `/instrumentos/calendario` | Calendario derivado, sin guardar |
| `GET` | `/instrumentos/{isin}/impacto-eliminacion` | Análisis de impacto |
| `DELETE` | `/instrumentos/{isin}` · `/posiciones/{id}` | Eliminación lógica con motivo |
| `POST` | `/precios/preview` · `/precios/confirmar` | Carga con preview obligatorio |
| `POST` | `/reproceso/impacto` · `/reproceso` | Impacto y ejecución en segundo plano |
| `GET` | `/reproceso/{id}/reexpresion` | Reporte de reexpresión |
| `GET` | `/valorizacion` · `/puente` · `/control` · `/validaciones` | Grillas |
| `GET` | `/versiones` · `/comparar` · `/trazabilidad` | Modelo bitemporal |
| `GET` | `/exportar/{vista}?formato=csv\|xlsx` | Exportación con marca de imputado |

---

## Documentación funcional

`docs/DOCUMENTACION.md` describe todo lo que hace el sistema: metodología de
cálculo paso a paso, reglas de operación de los tres frames, las ocho pantallas,
el panel de validaciones, los parámetros, el modelo de datos, la API y el
glosario. Este README cubre la puesta en marcha y las decisiones de ingeniería;
aquella cubre el comportamiento.

---

## Atajos de teclado

`Alt+1` a `Alt+8` saltan a cada módulo en el orden de la navegación lateral. En
la captura manual de precios, tabular al final de la última fila agrega otra.
