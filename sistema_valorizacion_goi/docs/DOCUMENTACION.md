# Documentación funcional · Sistema de Valorización Interno · GOI

Referencia completa de lo que hace el sistema: metodología de cálculo, reglas de
operación, pantallas, controles, parámetros, modelo de datos y API.

- [1. Qué hace y qué no hace](#1-qué-hace-y-qué-no-hace)
- [2. Cómo se opera](#2-cómo-se-opera)
- [3. Motor de cálculo](#3-motor-de-cálculo)
- [4. Puente Begin MV a End MV](#4-puente-begin-mv-a-end-mv)
- [5. Caja](#5-caja)
- [6. Control T+0 y quiebres](#6-control-t0-y-quiebres)
- [7. Reproceso, versionado y reexpresión](#7-reproceso-versionado-y-reexpresión)
- [8. Las ocho pantallas](#8-las-ocho-pantallas)
- [9. Panel de validaciones](#9-panel-de-validaciones)
- [10. Parámetros](#10-parámetros)
- [11. Carga de datos](#11-carga-de-datos)
- [12. Modelo de datos](#12-modelo-de-datos)
- [13. API](#13-api)
- [14. Pruebas y cifras verificadas](#14-pruebas-y-cifras-verificadas)
- [15. Glosario](#15-glosario)

---

## 1. Qué hace y qué no hace

El sistema valoriza carteras de renta fija. El usuario carga instrumentos,
posiciones y precios, y obtiene la valorización diaria de cada posición y del
portafolio consolidado.

**Entrega tres cosas:**

1. El valor de mercado de cada posición, en moneda local y en moneda base.
2. Su desagregación en precio (*security MV*) y devengo.
3. El puente Begin MV a End MV, con cada componente explicado y una columna de
   control que debe dar cero.

**No calcula** retornos, rentabilidad, TWRR, atribución ni estadísticas de
riesgo. Está fuera de alcance por diseño.

**La prioridad es la auditabilidad, no la estética.** Cada cifra de pantalla se
puede reconstruir a mano: la grilla muestra todos los campos intermedios, y desde
cualquier Total MV se llega en un clic al precio y al tipo de cambio que lo
originaron, con su fecha de carga.

### El caso de uso central: el reproceso retroactivo

Dar de alta un instrumento con fecha de alta anterior a hoy, cargar sus precios
históricos y recalcular la valorización desde esa fecha es una **operación
normal**, no una excepción. El sistema recalcula, muestra qué cambió respecto de
lo calculado antes, y conserva el resultado anterior como versión consultable.

---

## 2. Cómo se opera

### 2.1 Tres módulos desacoplados

Los tres frames de captura y cálculo son independientes: se operan por separado,
posiblemente por personas distintas y en momentos distintos.

| Frame | Qué hace | Qué **no** hace |
|---|---|---|
| **Registro de instrumentos** | Alta, consulta, edición y baja lógica de instrumentos y posiciones | No pide precios ni dispara cálculos |
| **Carga de precios** | CSV, Excel y captura manual, con preview obligatorio | No dispara recálculo |
| **Reproceso** | El único módulo que dispara cálculo | No captura datos |

Separar la captura del cálculo permite cargar durante todo el día y recalcular
una sola vez, y deja el recálculo como decisión explícita y auditable.

### 2.2 Lo que une a los tres módulos: el estado del instrumento

No hay un asistente encadenado. Lo que conecta los módulos es el estado que el
sistema deriva de cada instrumento y muestra siempre.

| Estado | Condición |
|---|---|
| **Registrado** | Existe en la maestra, sin posición asociada |
| **Sin precios** | Tiene posición, no tiene ningún precio cargado |
| **Cobertura parcial** | Faltan precios en fechas dentro de su rango obligatorio |
| **Listo** | Cobertura completa, sin valorizar o desactualizado |
| **Valorizado** | Cobertura completa y valorización vigente al día |

El **rango obligatorio de precios** de un instrumento va desde su `fecha_alta`
hasta `min(fecha_actual, fecha_vencimiento)`.

### 2.3 La bandeja de pendientes

Es la pantalla de inicio. Lista todo lo que está incompleto, con un enlace
directo al módulo que resuelve cada pendiente.

| Tipo de pendiente | Qué significa | Resuelve en |
|---|---|---|
| `SIN_POSICION` | Instrumento en la maestra sin posición | Registro |
| `SIN_PRECIOS` | Posición sin ningún precio cargado | Carga de precios |
| `COBERTURA_PARCIAL` | Faltan fechas dentro del rango obligatorio | Carga de precios |
| `PENDIENTE_RECALCULO` | Hay fechas marcadas como desactualizadas | Reproceso |
| `ELIMINACION_PENDIENTE` | Posición eliminada con valorizaciones aún vigentes | Reproceso |
| `PRECIOS_HUERFANOS` | Serie de precios de un instrumento eliminado | Carga de precios |

Esto reemplaza el bloqueo por un seguimiento: un instrumento sin precios no
impide operar el sistema, pero no desaparece de la vista hasta completarse.

---

## 3. Motor de cálculo

El motor es una librería pura: recibe datos y devuelve resultados, sin base de
datos, sin HTTP y sin framework. Se puede ejecutar en un test unitario.

### 3.1 Convención de devengo

El sistema devenga a **fecha de valorización más un día**:

```
fecha_devengo = fecha_valorizacion + desfase_devengo      (desfase_devengo = 1 por defecto)
```

Tanto el desfase como el modo de búsqueda son parámetros de configuración, no
constantes en código.

### 3.2 Calendario de cupones

Se **deriva** del vencimiento y la frecuencia. Nunca se captura a mano.

```
paso = 12 / frecuencia                       (meses)
fechas = [fecha_vencimiento]
d = fecha_vencimiento
mientras d > fecha_emision:
    d = d - paso meses
    si fecha_vencimiento es el último día de su mes:
        d = último día del mes de d
    agregar d a fechas
ordenar fechas ascendente
```

La **regla de fin de mes es obligatoria**: un instrumento que vence el 30/06 paga
31/12 y 30/06, no 30/12 y 30/06.

> Al guardar un instrumento, la pantalla muestra de inmediato el calendario
> derivado para que el usuario confirme visualmente que las fechas son las que
> espera. Es el control de calidad más barato del sistema: un vencimiento mal
> capturado se detecta ahí y no tres meses después.

### 3.3 Ubicación en el calendario: búsqueda estricta

```
ultimo_cupon  = máxima fecha del calendario ESTRICTAMENTE MENOR a fecha_devengo
proximo_cupon = mínima fecha del calendario MAYOR O IGUAL a fecha_devengo
```

Los operadores son el núcleo de la metodología. Cuando `fecha_devengo` coincide
exactamente con una fecha de cupón, la búsqueda estricta **no rueda al periodo
siguiente**: deja el último cupón en el pago anterior y el próximo en la fecha
misma. El resultado es un devengo igual al **periodo completo**. Es intencional.

Si `ultimo_cupon` no existe porque `fecha_devengo` es anterior al primer cupón,
se usa `fecha_emision`.

El control T+0 usa la variante **inclusiva** (`<=` y `>`), que sí rueda al
periodo siguiente. Es la convención estándar de mercado.

### 3.4 Guarda de vencimiento

```
si fecha_devengo > fecha_vencimiento:
    ultimo_cupon = proximo_cupon = fecha_vencimiento
    dias_transcurridos = dias_periodo = 0
    devengo_por_100 = 0
```

El operador es **mayor estricto**: con `fecha_devengo` igual al vencimiento la
guarda no dispara bajo búsqueda estricta, y el devengo sale por la vía normal,
dando el periodo completo.

Bajo búsqueda **inclusiva** esa misma fecha deja el calendario sin próximo cupón;
ahí la guarda sí aplica. **Nunca se usa una fecha centinela** para completar el
calendario: el motor lanza una excepción antes que dejar pasar una fecha de
relleno al resultado, que produciría periodos de decenas de miles de días.

### 3.5 Convenciones de conteo de días

```
dias_transcurridos = fecha_devengo - ultimo_cupon        (días calendario)
dias_periodo       = proximo_cupon - ultimo_cupon
cupon_por_periodo  = tasa_cupon / frecuencia             (porcentaje)
```

| Convención | Fórmula del devengo por 100 |
|---|---|
| `ACT/ACT` | `cupon_por_periodo * dias_transcurridos / dias_periodo` |
| `ACT/365` | `tasa_cupon * dias_transcurridos / 365` |
| `ACT/360` | `tasa_cupon * dias_transcurridos / 360` |
| `30/360` | `cupon_por_periodo * dias_30360 / (360 / frecuencia)` |

**La convención se toma siempre de la maestra y el motor no la sobreescribe
jamás.** Si el sistema detecta una desviación respecto del uso de mercado —por
ejemplo un soberano canadiense declarado `ACT/ACT` cuando el estándar es
`ACT/365`— la reporta en el panel de validaciones con su impacto cuantificado en
moneda base, y deja el cálculo intacto. Un motor que corrige datos por su cuenta
es imposible de auditar.

### 3.6 Vigencia

```
vigente(fecha) = fecha >= fecha_alta  AND  fecha < fecha_vencimiento
```

El instrumento sale de la cartera **el día de su vencimiento**. Si el parámetro
`valorizar_vencido_a_redencion` está activo, la vigencia se extiende al
vencimiento inclusive, y ese día el instrumento se valoriza a `valor_redencion`
con devengo igual al cupón completo del periodo, ignorando cualquier precio de
mercado.

### 3.7 Precio y moneda

Cada instrumento declara en qué moneda llega su precio:

```
precio_local = (precio_expresado_en == 'BASE')
               ? precio_proveedor * tipo_cambio
               : precio_proveedor
```

`BASE` significa que el proveedor entrega el precio ya convertido a la moneda
base del portafolio. Es un caso real y frecuente. El sistema reconstruye el
precio en moneda local para poder mostrarlo y contrastarlo contra una fuente de
mercado.

El `tipo_cambio` se expresa en **unidades de la moneda del instrumento por unidad
de moneda base**. Si la base es USD y el instrumento es CAD, `1.3804` significa
1.3804 CAD por USD, y la conversión a base **divide**.

> **Cuantización declarada.** `precio_local` se cuantiza a `decimales_precio`
> (6 por defecto) y ese valor se usa en todo el cálculo. Es la única
> cuantización que no es de presentación, y está expuesta como parámetro
> (`cuantizar_precio_local`) en lugar de escondida en el código. Sin ella, el
> Total MV de CA135087M276 al 31/07/2026 da 13,162,247.00 en vez de los
> 13,162,246.93 verificados contra el modelo de referencia.

### 3.8 Valor de mercado

```
security_mv_local = precio_local    / 100 * nominal
devengo_local     = devengo_por_100 / 100 * nominal
total_mv_local    = security_mv_local + devengo_local

fx = (moneda_instrumento == moneda_base) ? 1 : tipo_cambio

security_mv_base  = security_mv_local / fx
devengo_base      = devengo_local     / fx
total_mv_base     = security_mv_base  + devengo_base
```

Ambos componentes nacen en la moneda del instrumento y se convierten con el
**mismo** tipo de cambio de esa fecha. Usar una fuente distinta para el precio y
para el devengo produce posiciones internamente inconsistentes. La salida muestra
el valor en moneda local y en moneda base por separado.

### 3.9 Precisión numérica

- Aritmética **decimal** de precisión arbitraria en todo el motor (`Decimal` de
  Python, 50 dígitos de contexto). Nunca punto flotante binario.
- **Sin redondeo en pasos intermedios**, con la única excepción declarada de
  `precio_local` descrita en 3.7.
- El redondeo es exclusivamente de presentación, con modo explícito media-par.
- El motor **rechaza** un `float` en la entrada con un error de tipo, y hay una
  prueba dedicada que verifica que ningún valor monetario lo atraviesa como tal.
- En la base de datos, todo monto, tasa, precio y tipo de cambio se almacena como
  `TEXT` con su representación decimal exacta, porque SQLite convertiría la
  afinidad `NUMERIC` a coma flotante.

---

## 4. Puente Begin MV a End MV

Cada combinación de fecha e instrumento tiene su propio Begin MV y End MV. El
portafolio consolidado es la suma.

```
BEGIN MV  =  End MV del día anterior       (0 si la posición no existía)

          +  Efecto precio y tipo de cambio
          +  Devengo del día
          -  Cupón pagado
          +  Alta de posición
          -  Baja por vencimiento
          +  Cobros del día                (si incluir_caja)
          +  Efecto FX sobre la caja       (si incluir_caja)

=  END MV
```

Donde `t-1` es la fecha de valorización inmediatamente anterior del mismo
instrumento:

| Componente | Cálculo |
|---|---|
| Efecto precio y FX | `security_mv_base(t) - security_mv_base(t-1)`, solo si vigente en ambas fechas, si no 0 |
| Devengo del día | `devengo_base(t) - devengo_base(t-1) + cupón pagado`, solo si vigente en ambas, si no 0 |
| Cupón pagado | Si `t` es fecha de cupón, estaba vigente en `t-1`, sigue vigente en `t` y `t > fecha_alta`: `cupon_por_periodo / 100 * nominal`, convertido a base |
| Alta de posición | Si vigente en `t`, no vigente en `t-1` y `t > fecha_inicio_portafolio`: `total_mv_base(t)` |
| Baja por vencimiento | Si no vigente en `t` y vigente en `t-1`: `total_mv_base(t-1)` |

> **Por qué el cupón exige vigencia también en `t`.** Con la caja activa, la
> redención aporta `nominal * (1 + cupon_por_periodo/100)`: principal **más**
> cupón final. Contar además ese cupón en la línea de cupón pagado lo duplicaría
> y rompería la columna de control. El cupón del día de vencimiento viaja dentro
> de la redención.

En la **fecha de inicio del portafolio**, Begin MV = End MV y la variación es
cero. No es un día valorizado, es la foto inicial; las posiciones presentes en
esa fecha **no** generan alta.

### 4.1 La columna de control

```
control = End MV − Begin MV − suma de componentes
```

Debe dar cero en todas las filas, por instrumento y consolidado. **Está visible
en pantalla**, no escondida en los tests: es el mecanismo de detección de errores
de construcción.

Se contrasta contra la tolerancia declarada (`tolerancia_quiebre`), nunca por
igualdad exacta: la división decimal de un cociente no exacto —por ejemplo
`1/1.3804`— deja un residuo en el dígito 20.

Sin caja activa, el Total MV cae el día del cupón y el día del vencimiento. La
columna **Evento** marca esas fechas (`CUPON`, `VENCIMIENTO`) para que el salto
quede explicado y nadie lo lea como una pérdida.

---

## 5. Caja

Bajo el parámetro `incluir_caja`. Cuando está activa:

- Los cupones cobrados y las redenciones se acumulan **en la moneda de origen**,
  no convertidos de una vez.
- El saldo acumulado se revalúa cada fecha al tipo de cambio de esa fecha.
- Al vencimiento entra `nominal * (1 + cupon_por_periodo / 100)`: principal más
  cupón final.
- El Total MV del portafolio pasa a ser posiciones más caja.
- El efecto de tipo de cambio sobre el saldo en moneda extranjera es una línea
  propia del puente, de modo que el control siga dando cero.

El nominal usado para la redención se lee de la **tabla de posiciones**, no de
una columna de cálculo que se anula cuando el instrumento deja de estar vigente.

El saldo **se recalcula como la suma de cobros hasta la fecha**, no como un
contador incremental: no existe ningún saldo acumulado que se arrastre y no pueda
reconstruirse.

---

## 6. Control T+0 y quiebres

El motor está parametrizado. Con `desfase_devengo = 0` y
`busqueda_cupon = INCLUSIVA` produce la valorización a fecha de valorización, que
es la convención estándar de mercado para cartera.

Cuando `calcular_control_t0 = true`, el sistema calcula ambas en paralelo y
presenta la segunda como **columna de control** junto al resultado oficial. No lo
reemplaza; lo acompaña.

### Por qué importa

Bajo la convención del sistema, el quiebre contra T+0 es, por construcción,
**exactamente un día de devengo del portafolio, todos los días, sin excepción**.
Esa identidad convierte un desfase conocido en una constante verificable, y todo
lo que se salga de ella en señal de error.

```
quiebre        = Total MV del control T+0 − Total MV del sistema
devengo_diario = Σ cupon_por_periodo / 100 * nominal / dias_periodo, en base,
                 sobre las posiciones vigentes
residual       = quiebre + devengo_diario
```

| Condición | Estado |
|---|---|
| `abs(quiebre) <= tolerancia` | Sin quiebre |
| `abs(quiebre + devengo_diario) <= tolerancia` | Quiebre equivale a un día de devengo |
| Cualquier otro caso | **Revisar** |

Todo lo que caiga en **Revisar** tiene un error distinto al desfase conocido.

---

## 7. Reproceso, versionado y reexpresión

### 7.1 Principio: el motor no acumula estado

Cada fecha se calcula exclusivamente a partir de:

1. La maestra, posiciones y precios vigentes para esa fecha.
2. El End MV del día anterior por instrumento, que a su vez es recalculable por
   la misma regla.

Consecuencia obligatoria: recalcular un rango desde cero produce exactamente el
mismo resultado que el cálculo original si los datos no cambiaron. **La
reejecución es idempotente**, y hay una prueba automatizada que recalcula dos
veces y compara.

### 7.2 Selección y análisis de impacto

El módulo de reproceso propone por defecto el **rango mínimo que cubre todas las
fechas marcadas como desactualizadas**, y permite acotar a un subconjunto de
instrumentos.

Antes de ejecutar, muestra:

- Rango a recalcular y cuántas valorizaciones se ven afectadas.
- Qué cambió desde el último cálculo: instrumentos nuevos, posiciones
  modificadas, instrumentos o posiciones eliminados, precios cargados, corregidos
  o eliminados, parámetros alterados.
- Si alguna fecha cae en periodo cerrado.
- Total MV actual del portafolio en la fecha inicial y final del rango, para que
  el usuario vea el antes antes de aprobar.

### 7.3 Ejecución

- Corre **en segundo plano** con estado visible: pendiente, en proceso,
  terminado, con error. El usuario no espera bloqueado.
- Es **transaccional**: o se completa el rango entero, o no se publica nada.
- Un solo reproceso activo por portafolio; los demás encolan.
- Al terminar muestra el resumen: fechas procesadas, fechas modificadas e
  impacto total en moneda base.
- Existe un **recálculo forzado** de un rango arbitrario, sin necesidad de que
  haya cambiado un dato. Es la herramienta de diagnóstico cuando algo no cuadra.

### 7.4 Modelo bitemporal

Cada valorización almacena dos ejes de tiempo:

- `fecha_valorizacion`: la fecha del negocio que se valoriza.
- `calculado_en`: el instante en que se ejecutó el cálculo.

Recalcular **no sobreescribe**: crea una versión nueva y conserva la anterior. La
vista por defecto muestra la versión vigente; el usuario puede consultar
cualquier versión anterior y compararlas lado a lado para una misma fecha.

> **Una versión publica su rango completo de fechas, no instrumentos sueltos.**
> Resolver la versión vigente por `(fecha, isin)` dejaba vivas las filas antiguas
> de una posición eliminada: seguían siendo el máximo para ese par y sobrevivían
> al reproceso. Un reproceso parcial arrastra sin tocar las filas que no
> recalcula, de modo que cada versión sigue siendo una foto completa del rango.

Si el recálculo no produce ninguna diferencia, **no se genera versión nueva**.

### 7.5 Reporte de reexpresión

Cada recálculo que modifique valores ya calculados genera un reporte con:

| Campo |
|---|
| Fecha valorizada |
| Instrumento |
| Valor anterior |
| Valor nuevo |
| Diferencia absoluta y relativa |
| Qué dato de entrada cambió |
| Usuario y momento del recálculo |

Causas que el sistema atribuye automáticamente:

`Alta de instrumento o posición` · `Eliminación de instrumento o posición` ·
`Cambio de nominal` · `Precio` · `Tipo de cambio` ·
`Parámetro o convención de devengo` · `Cambio de fecha de alta o de vigencia` ·
`Recálculo`

Una fila que antes no existía y ahora vale cero no entra al reporte: no hay valor
previo que corregir.

### 7.6 Cierre y reapertura de periodo

Un periodo puede marcarse como cerrado. Recalcular o cargar precios sobre un
periodo cerrado **exige reapertura explícita con justificación en texto libre**,
queda registrado en bitácora y genera obligatoriamente reporte de reexpresión.

### 7.7 Bitácora

Registro append-only de qué se cargó o modificó, quién, cuándo, qué rango de
recálculo disparó y cuántas valorizaciones cambiaron.

Acciones registradas: `ALTA_INSTRUMENTO`, `EDICION_INSTRUMENTO`,
`ELIMINACION_INSTRUMENTO`, `REACTIVACION_INSTRUMENTO`, `ALTA_POSICION`,
`EDICION_POSICION`, `ELIMINACION_POSICION`, `REACTIVACION_POSICION`,
`CARGA_PRECIOS`, `ELIMINACION_PRECIO`, `PURGA_PRECIOS_HUERFANOS`,
`CAMBIO_PARAMETROS`, `REPROCESO`, `CIERRE_PERIODO`, `REAPERTURA_PERIODO`.

### 7.8 Eliminación y reactivación

**Nunca se borra físicamente.** Toda eliminación es lógica: el registro conserva
`eliminado_en`, `eliminado_por` y un motivo en texto libre **obligatorio**.

- **Jerarquía.** Un instrumento con posiciones asociadas no se elimina
  directamente: hay que eliminar primero las posiciones, o confirmar una
  eliminación en cascada que lista explícitamente qué se va a eliminar.
- **Precios.** Eliminar un instrumento **no elimina su serie de precios**, que
  queda como dato de referencia huérfano y marcado. Si el instrumento se vuelve a
  registrar, la serie sigue disponible y no hay que recargarla. La purga de
  precios huérfanos es una operación separada y explícita.
- **Análisis de impacto antes de confirmar.** Rango de fechas con valorización
  existente, cuántas quedarán desactualizadas, Total MV actual y resultante en la
  fecha inicial y final del rango, y si alguna fecha cae en periodo cerrado.
- **La eliminación no recalcula.** Marca las fechas afectadas como
  desactualizadas y las envía a la bandeja. El recálculo se decide en el frame de
  reproceso, igual que cualquier otro cambio.
- **Restitución.** Existe una reactivación que revierte la eliminación, con el
  mismo análisis de impacto, el mismo registro en bitácora y el mismo recálculo
  posterior.

> Este módulo corrige **errores de registro**. No sirve para registrar una venta
> ni un vencimiento, que son eventos de mercado con fecha y precio.

### 7.9 Modificación posterior

Cambiar el nominal, la fecha de alta o cualquier campo de la maestra de un
instrumento ya valorizado **no recalcula automáticamente**. Marca las fechas
afectadas como desactualizadas, las deja visibles en la bandeja, y el recálculo
se dispara desde el frame de reproceso. La edición nunca es silenciosa, pero
tampoco decide por el usuario cuándo reprocesar.

Un **alta retroactiva** marca todo lo ya valorizado desde su fecha de alta,
acotado al último día que el portafolio tiene calculado.

### 7.10 Reglas del alta retroactiva

- Si `fecha_alta <= fecha_inicio_portafolio`, la posición forma parte del saldo
  inicial y **no** genera alta en el puente. El Begin MV del portafolio en la
  fecha de inicio cambia.
- Si `fecha_alta > fecha_inicio_portafolio`, genera alta en el puente en esa
  fecha, por su Total MV completo.
- Si `fecha_alta` coincide con la fecha de emisión, el devengo de ese día da cero
  bajo T+0 y un día bajo la convención del sistema.
- Si `fecha_alta` es posterior al vencimiento, **se rechaza el registro**.

---

## 8. Las ocho pantallas

Barra superior fija con el nombre del sistema, el portafolio activo, la fecha de
valorización seleccionada, la moneda base y el usuario. Navegación lateral con
los ocho módulos. **Cada pantalla responde una pregunta.**

| # | Pantalla | Pregunta que responde |
|---|---|---|
| 1 | Pendientes | ¿Qué falta para que la cartera quede valorizada? |
| 2 | Registro de instrumentos | ¿Qué hay en cartera y desde cuándo? |
| 3 | Carga de precios | ¿Qué precios y tipos de cambio hay, y cuáles faltan? |
| 4 | Reproceso | ¿Qué hay que recalcular, y qué cambiaría si lo hago? |
| 5 | Valorización | ¿Cuánto vale? |
| 6 | Begin/End MV | ¿Por qué vale hoy algo distinto de ayer? |
| 7 | Control y quiebres | ¿En qué difiere del estándar de mercado? |
| 8 | Validaciones | ¿Qué está mal? |

### 8.1 Pendientes

Cifras de cabecera (pendientes totales, sin precios, cobertura parcial, por
reprocesar, instrumentos), la cola de pendientes con enlace *Resolver* a su
módulo, y la tabla de estado de cada instrumento con su cobertura
(`días cubiertos / días requeridos`).

### 8.2 Registro de instrumentos

**Maestra:** ISIN, descripción, moneda, tasa de cupón, frecuencia, fechas de
emisión y vencimiento, convención de días, moneda en que llega el precio, valor
de redención. Validación en línea de cada campo, con el error señalado sobre el
campo que lo produce.

**Posición:** nominal y fecha de alta en cartera, que puede ser cualquier fecha.

Al guardar, muestra el **calendario de cupones derivado**. Al confirmar una
posición, informa el estado resultante, si forma parte del saldo inicial o
generará alta en el puente, y el rango de precios que queda pendiente con enlace
directo al módulo de carga. No bloquea: informa.

Desde la tabla se accede al detalle del instrumento, a su edición, a la
eliminación con análisis de impacto y a la reactivación.

### 8.3 Carga de precios

Filtros por instrumento y rango. Carga de archivo CSV o Excel, captura manual en
grilla con navegación por tabulador, y exportación. Muestra la serie cargada con
su fuente y trazabilidad (`cargado_en`, `cargado_por`), y las series huérfanas
con su opción de purga.

El **preview obligatorio** se describe en la sección 11.

### 8.4 Reproceso

Rango propuesto, selección opcional de instrumentos, casilla de recálculo
forzado, análisis de impacto, ejecución con estado en vivo, historial de
reprocesos y acceso al reporte de reexpresión de cada ejecución.

### 8.5 Valorización

Cifras del portafolio a la fecha seleccionada (Security MV base, Devengo base,
Total MV posiciones, Caja si está activa, End MV, Control T+0), el consolidado
por fecha y el detalle por posición.

La grilla de detalle muestra **todos los campos intermedios**: fecha de devengo,
último y próximo cupón, días transcurridos, días del periodo, cupón por periodo,
devengo por 100, precio del proveedor, precio en moneda local, tipo de cambio,
security MV y devengo en moneda local y en base, total, y las columnas T+0.

Un clic en cualquier fila abre la **trazabilidad**: los doce pasos del cálculo en
orden, el registro de precio que lo originó con su fecha de carga, el calendario
de cupones del instrumento y las versiones de cálculo de esa fecha.

Filtros por rango de fechas, instrumento y versión de cálculo. **Comparador de
versiones** lado a lado para una misma fecha. Exportación a CSV y Excel.

### 8.6 Begin/End MV

Puente consolidado del portafolio y puente por instrumento, con todos los
componentes y la columna de control. Un aviso en cabecera confirma si el control
da cero en todas las filas o señala cuántas se salen de tolerancia. Las columnas
de caja aparecen solo cuando `incluir_caja` está activo.

### 8.7 Control y quiebres

Fechas evaluadas, cuántas sin quiebre, cuántas equivalen a un día de devengo,
cuántas en **Revisar**, y el residual máximo. Tabla de quiebre por fecha con
Total MV del sistema, del control T+0, quiebre, devengo diario teórico, residual
y estado.

### 8.8 Validaciones

Las trece comprobaciones de la sección 9, cada una con su nivel, su conteo de
hallazgos y su detalle tabular.

### 8.9 Convenciones de presentación

- **Paleta institucional de azules.** El color codifica información, no decora.
  Los tres colores semánticos están reservados exclusivamente para estado:
  verde `ok` (conciliado, control en cero, carga exitosa), ámbar `warn` (dato
  imputado, arrastre de precio o tipo de cambio), rojo `alert` (quiebre sobre
  tolerancia, estado Revisar, error de carga). Si el usuario ve ámbar, es porque
  hay un dato imputado.
- **Cifras con dígitos tabulares**, alineadas a la derecha. Separador de miles,
  negativos entre paréntesis, ceros como guion. Precios con seis decimales,
  tipos de cambio con cuatro, devengo por 100 con ocho, montos con dos.
- **Datos imputados** con fondo ámbar y sufijo `·i`, distintos de los observados
  en toda la interfaz y en las exportaciones.
- **Nada destructivo sin preview.** Toda carga, alta, edición o recálculo muestra
  qué va a pasar antes de que pase, con cifras.
- **Estados vacíos que enseñan.** Una tabla sin datos explica qué falta y ofrece
  la acción para resolverlo.
- **Errores accionables.** Nunca "Error al procesar": qué pasó, en qué fila y
  cómo se corrige.
- **Filtros persistentes** entre módulos. Atajos `Alt+1` a `Alt+8` para saltar de
  pantalla.
- **Diseño denso y tabular**, tipo terminal de mercado. Responsive hasta tablet;
  en móvil, consulta sin captura.

---

## 9. Panel de validaciones

Recalculado con cada proceso. Trece comprobaciones:

| # | Validación | Nivel |
|---|---|---|
| 1 | Registros de precio duplicados por fecha e instrumento | alert |
| 2 | Fechas con tipo de cambio en cero o ausente, y cuáles se imputaron | warn |
| 3 | Fechas vigentes sin precio, y cuántas se resolvieron por arrastre | warn / alert |
| 4 | Precio implícito en moneda local fuera de rango razonable | alert |
| 5 | Instrumentos que vencen sin precio en la fecha de vencimiento | warn |
| 6 | Fechas de valorización en día no hábil | warn |
| 7 | Convenciones de la maestra desviadas del uso de mercado, con impacto cuantificado | warn |
| 8 | Fechas con estado Revisar | alert |
| 9 | Filas donde el control del puente no da cero | alert |
| 10 | Posiciones cuya serie de precios tiene huecos entre la fecha de alta y hoy | warn |
| 11 | Reexpresiones pendientes de comunicar | warn |
| 12 | Instrumentos o posiciones eliminados con valorizaciones aún vigentes | alert |
| 13 | Series de precios huérfanas de instrumentos eliminados | warn |

La validación 4 delata que el precio llega ya convertido cuando la maestra dice
lo contrario, o al revés. La validación 5 contrasta el valor de redención contra
la última valorización de mercado disponible y **reporta la diferencia en lugar
de absorberla en silencio**.

---

## 10. Parámetros

Todos por portafolio, con valores por defecto en un único lugar. Ningún número
mágico vive en el código.

| Parámetro | Defecto | Qué controla |
|---|---|---|
| `moneda_base` | `USD` | Moneda de consolidación del portafolio |
| `fecha_inicio_portafolio` | `2026-05-31` | Foto inicial: Begin MV = End MV y sin altas |
| `desfase_devengo` | `1` | Días que se suman a la fecha de valorización para devengar |
| `busqueda_cupon` | `ESTRICTA` | `ESTRICTA` (`<`, `>=`) o `INCLUSIVA` (`<=`, `>`) |
| `incluir_caja` | `false` | Acumula cobros y redenciones en el Total MV |
| `valorizar_vencido_a_redencion` | `false` | Extiende la vigencia al día de vencimiento, a valor de redención |
| `calcular_control_t0` | `true` | Calcula en paralelo la convención estándar de mercado |
| `dias_max_arrastre` | `4` | Días máximos de arrastre de precio antes de dar la fecha por errónea |
| `tolerancia_quiebre` | `0.01` | Tolerancia del control del puente y de la clasificación de quiebres |
| `decimales_precio` | `6` | Precisión de precios |
| `decimales_tipo_cambio` | `4` | Precisión de tipos de cambio |
| `decimales_devengo` | `8` | Precisión del devengo por 100 |
| `decimales_monto` | `2` | Precisión de montos |
| `cuantizar_precio_local` | `true` | Cuantiza `precio_local` a `decimales_precio` (ver 3.7) |
| `precio_local_min_razonable` | `20` | Cota inferior de la validación 4 |
| `precio_local_max_razonable` | `300` | Cota superior de la validación 4 |

Cambiar un parámetro **no recalcula**: marca las fechas afectadas como
desactualizadas y registra el cambio en bitácora.

> La carga de ejemplo fija `dias_max_arrastre = 120` porque el juego de prueba
> trae precios en fechas sueltas y exige valorizar los 62 días del periodo. El
> valor por defecto del sistema sigue siendo 4.

---

## 11. Carga de datos

### 11.1 Formatos aceptados

- **CSV**, con detección automática de delimitador (`,` `;` tabulador `|`) y
  codificación (UTF-8, UTF-8 con BOM, Latin-1).
- **Excel** `.xlsx` y `.xlsm`, incluyendo la reconstrucción de fechas guardadas
  como serial.
- **Captura manual** en grilla, que pasa por la misma ruta y las mismas
  validaciones que un archivo.

Columnas reconocidas, con alias: `fecha`, `isin`, `precio`, `tipo_cambio`,
`fuente`. Fechas en ISO, `dd/mm/aaaa`, `dd-mm-aaaa` o serial de Excel. Números
con separador de miles y decimal en cualquiera de las dos convenciones, y
negativos entre paréntesis.

Permite carga para cualquier rango de fechas, incluyendo fechas ya valorizadas y
periodos cerrados con la autorización correspondiente.

### 11.2 Preview obligatorio

Antes de confirmar, el sistema muestra:

- **Filas nuevas**, **filas idénticas** a lo existente y **filas en conflicto**
  con valor distinto, estas últimas listadas con valor anterior y valor nuevo.
- **Registros duplicados dentro del propio archivo**, con la línea donde apareció
  la primera vez.
- **Tipos de cambio en cero o ausentes**.
- **Precio implícito en moneda local**, para que el usuario confirme que la
  moneda declarada en la maestra es la correcta.
- **Cobertura resultante por instrumento**: fechas del rango obligatorio que
  quedan cubiertas y cuáles siguen faltando.

### 11.3 Clave única e idempotencia

La clave es `(fecha, isin)`. **La carga rechaza duplicados, no los suma.** Un
archivo con el mismo bloque de datos repetido es un caso real y se detecta.

Cada carga lleva una **clave de idempotencia derivada del contenido** del
archivo: cargar el mismo archivo dos veces no cambia nada.

Al confirmar, **la carga no dispara recálculo**: marca como desactualizadas las
fechas afectadas y actualiza el estado de los instrumentos.

### 11.4 Precio o tipo de cambio faltante

- **Tipo de cambio en cero, nulo o ausente:** arrastra el último valor hábil
  disponible para ese instrumento, sin límite de días, y **marca el dato como
  imputado**.
- **Precio ausente en una fecha vigente:** arrastra el último precio disponible
  hasta un máximo de `dias_max_arrastre` días y lo marca como imputado. Superado
  ese límite, la fecha queda en error y no se valoriza, con un mensaje que dice
  de qué fecha es el último precio y cuántos días atrás está.
- Los datos imputados se distinguen visualmente de los observados en toda la
  interfaz y en las exportaciones. **Un valor arrastrado nunca se presenta igual
  que un valor observado.**

### 11.5 Eliminación de precios

Un registro de precio individual puede eliminarse, con motivo obligatorio. Si la
fecha queda dentro del rango obligatorio del instrumento, este pasa a cobertura
parcial y aparece en la bandeja de pendientes. **No se sustituye en silencio por
un arrastre.**

### 11.6 Exportación

Cualquier vista se exporta a CSV o Excel, conservando la marca de dato imputado y
con el nombre del sistema en el encabezado del archivo.

---

## 12. Modelo de datos

Base **SQLite** en un único archivo, abrible con cualquier visor sin instalar el
sistema. Migraciones versionadas y reversibles; nada de cambios de esquema
manuales.

| Tabla | Contenido |
|---|---|
| `portafolio` | Nombre, moneda base, fecha de inicio |
| `parametro` | Parámetros por portafolio |
| `instrumento` | Maestra, con campos de eliminación lógica |
| `posicion` | Nominal y fecha de alta, con campos de eliminación lógica |
| `precio` | Serie de precios y tipos de cambio |
| `calendario_cupon` | Calendario derivado, materializado por instrumento |
| `version_calculo` | Eje `calculado_en` del modelo bitemporal |
| `valorizacion` | La grilla completa: entradas, intermedios, resultados, puente y T+0 |
| `reproceso` | Historial de ejecuciones con estado y duración |
| `reexpresion` | Reporte de reexpresión (append-only) |
| `bitacora` | Registro de cambios (append-only) |
| `fecha_desactualizada` | Cola de lo pendiente de recalcular |
| `periodo_cerrado` | Cierres y reaperturas con justificación |
| `carga` | Cargas de archivo con su clave de idempotencia |
| `migracion` | Versiones de esquema aplicadas |

**Índices:** único `(fecha, isin)` en `precio` sobre los registros no eliminados,
más índices de consulta en `(isin, fecha)` y `(fecha)`. Clave
`(fecha_valorizacion, isin, version_calculo)` en `valorizacion`, con índice por
`(version_calculo, fecha_valorizacion)`.

**Vista `valorizacion_vigente`:** resuelve la versión vigente por fecha.

---

## 13. API

REST versionada bajo `/api/v1`. El usuario se identifica con la cabecera
`X-Usuario`, que alimenta la bitácora. Errores de validación devuelven `422` con
el campo que los produjo; periodo cerrado devuelve `403`.

| Método | Ruta |
|---|---|
| `GET` | `/estado` |
| `PUT` | `/parametros` |
| `GET` | `/pendientes` |
| `GET` `POST` | `/instrumentos` |
| `POST` | `/instrumentos/calendario` |
| `GET` | `/instrumentos/{isin}/impacto-eliminacion` |
| `DELETE` | `/instrumentos/{isin}` |
| `POST` | `/instrumentos/{isin}/reactivar` |
| `POST` | `/posiciones` |
| `GET` | `/posiciones/{id}/impacto-eliminacion` |
| `DELETE` | `/posiciones/{id}` |
| `POST` | `/posiciones/{id}/reactivar` |
| `GET` | `/precios` |
| `POST` | `/precios/preview` · `/precios/confirmar` · `/precios/manual` |
| `DELETE` | `/precios/{id}` |
| `POST` | `/precios/purgar-huerfanos` |
| `GET` | `/reproceso/propuesta` |
| `POST` | `/reproceso/impacto` · `/reproceso` |
| `GET` | `/reproceso` · `/reproceso/{id}` · `/reproceso/{id}/reexpresion` |
| `GET` | `/valorizacion` · `/puente` · `/control` · `/validaciones` |
| `GET` | `/versiones` · `/comparar` · `/trazabilidad` · `/bitacora` |
| `GET` | `/periodos` |
| `POST` | `/periodos/cerrar` · `/periodos/{id}/reabrir` |
| `GET` | `/exportar/{vista}?formato=csv\|xlsx` |

Vistas exportables: `valorizacion`, `puente`, `consolidado`, `precios`.

---

## 14. Pruebas y cifras verificadas

132 pruebas automatizadas (`python3 run.py --pruebas`), con el peso en la base de
la pirámide.

| Capa | Qué cubre |
|---|---|
| Dominio | Filas de resultados esperados, consolidados, control T+0, caja, puente, las cuatro convenciones y los casos de borde |
| Integración | Carga con duplicados, tipo de cambio en cero y huecos; idempotencia; registro y eliminación; panel de validaciones; cola de trabajos; contrato de la API |
| Extremo a extremo | Reproceso retroactivo completo (siete pasos) y eliminación con reproceso (ocho pasos) |
| Regresión numérica | Corrida completa del periodo contra un archivo de referencia versionado |

Ninguna prueba compara montos por igualdad exacta: todas usan una tolerancia
declarada.

### Cifras reproducidas exactamente

| Comprobación | Valor |
|---|---|
| Portafolio al 31/05/2026 | 64,337,667.97 |
| Control T+0 al 31/05/2026 | 64,331,028.10 |
| Portafolio al 31/07/2026 | 63,212,688.76 |
| Control T+0 al 31/07/2026 | 63,206,499.83 |
| End MV con caja al 31/07/2026 | 114,413,367.76 |
| Efectivo al 31/07/2026 | 51,200,679.00 |
| Precio implícito en CAD al 31/05/2026 | 92.798 |
| Cupón de CA135087M276 el 01/06/2026 | 108,311.07 USD |
| Control del puente en 186 combinaciones | cero |
| 62 días como un día de devengo, residual máximo | 0.00 |
| Diferencia contra el valor de redención | 11,902.32 |
| Total tras el alta retroactiva | 63,212,688.76 |
| Begin MV al 31/05 sin la posición inicial | 50,783,915.44 |

### Las dos filas críticas

Ambas tienen la fecha de devengo cayendo exactamente sobre una fecha del
calendario, y son las que validan que la búsqueda estricta está bien
implementada.

| Fecha | ISIN | F. devengo | Últ. cupón | Próx. cupón | Días | Devengo x100 |
|---|---|---|---|---|---|---|
| 31/05/2026 | CA135087M276 | 01/06/2026 | 01/12/2025 | 01/06/2026 | 182 / 182 | **0.75000000** |
| 30/07/2026 | US91282CLB53 | 31/07/2026 | 31/01/2026 | 31/07/2026 | 181 / 181 | **2.18750000** |

Si el sistema devolviera 0 en cualquiera de las dos, estaría aplicando búsqueda
inclusiva. Si devolviera días del periodo en el orden de las decenas de miles,
una fecha de relleno se estaría filtrando al resultado.

---

## 15. Glosario

| Término | Significado |
|---|---|
| **Begin MV** | Valor de mercado al inicio del día: el End MV del día anterior |
| **End MV** | Valor de mercado al cierre del día |
| **Security MV** | Componente de precio del valor de mercado, sin devengo |
| **Devengo** | Interés corrido desde el último cupón hasta la fecha de devengo |
| **Devengo por 100** | Devengo expresado por cada 100 unidades de nominal |
| **Cupón por periodo** | `tasa_cupon / frecuencia`, en porcentaje |
| **Fecha de devengo** | Fecha de valorización más el desfase configurado |
| **Moneda base** | Moneda de consolidación del portafolio |
| **Precio en BASE** | El proveedor entrega el precio ya convertido a moneda base |
| **Precio implícito** | Precio reconstruido en la moneda del instrumento |
| **Dato imputado** | Valor arrastrado de una fecha anterior, no observado |
| **Quiebre** | Diferencia entre el control T+0 y la valorización del sistema |
| **Residual** | Quiebre más el devengo diario teórico; debe dar cero |
| **Reexpresión** | Cambio de un valor ya calculado y publicado |
| **Versión de cálculo** | Publicación completa de un rango de fechas en un instante |
| **Serie huérfana** | Precios de un instrumento eliminado, conservados como referencia |
| **Rango obligatorio** | De `fecha_alta` a `min(hoy, vencimiento)` |
