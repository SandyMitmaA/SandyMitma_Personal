-- 001 esquema inicial
-- Nota de precision: SQLite es de tipado dinamico y convierte la afinidad
-- NUMERIC a REAL cuando el literal no es entero. Para no perder ni un digito,
-- todo monto, tasa, precio y tipo de cambio se almacena como TEXT con la
-- representacion decimal exacta, y se reconstruye con Decimal al leer.
-- Ningun valor monetario existe como FLOAT en ningun punto del sistema.

CREATE TABLE portafolio (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    moneda_base     TEXT NOT NULL,
    fecha_inicio    TEXT NOT NULL
);

CREATE TABLE parametro (
    portafolio_id   INTEGER NOT NULL REFERENCES portafolio(id),
    clave           TEXT NOT NULL,
    valor           TEXT NOT NULL,
    PRIMARY KEY (portafolio_id, clave)
);

CREATE TABLE instrumento (
    isin                TEXT PRIMARY KEY,
    descripcion         TEXT NOT NULL DEFAULT '',
    moneda              TEXT NOT NULL,
    tasa_cupon          TEXT NOT NULL,
    frecuencia          INTEGER NOT NULL,
    fecha_emision       TEXT NOT NULL,
    fecha_vencimiento   TEXT NOT NULL,
    convencion          TEXT NOT NULL,
    precio_expresado_en TEXT NOT NULL,
    valor_redencion     TEXT NOT NULL DEFAULT '100',
    creado_en           TEXT,
    creado_por          TEXT,
    eliminado_en        TEXT,
    eliminado_por       TEXT,
    motivo_eliminacion  TEXT
);

CREATE TABLE posicion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    portafolio_id       INTEGER NOT NULL REFERENCES portafolio(id),
    isin                TEXT NOT NULL REFERENCES instrumento(isin),
    nominal             TEXT NOT NULL,
    fecha_alta          TEXT NOT NULL,
    creado_en           TEXT,
    creado_por          TEXT,
    eliminado_en        TEXT,
    eliminado_por       TEXT,
    motivo_eliminacion  TEXT
);
CREATE INDEX ix_posicion_isin ON posicion(isin);

CREATE TABLE precio (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha               TEXT NOT NULL,
    isin                TEXT NOT NULL,
    precio              TEXT,
    tipo_cambio         TEXT,
    fuente              TEXT NOT NULL DEFAULT '',
    carga_id            INTEGER,
    cargado_en          TEXT,
    cargado_por         TEXT,
    eliminado_en        TEXT,
    eliminado_por       TEXT,
    motivo_eliminacion  TEXT
);
CREATE UNIQUE INDEX ux_precio_fecha_isin ON precio(fecha, isin) WHERE eliminado_en IS NULL;
CREATE INDEX ix_precio_isin_fecha ON precio(isin, fecha);
CREATE INDEX ix_precio_fecha ON precio(fecha);

CREATE TABLE calendario_cupon (
    isin    TEXT NOT NULL REFERENCES instrumento(isin),
    fecha   TEXT NOT NULL,
    PRIMARY KEY (isin, fecha)
);

CREATE TABLE version_calculo (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portafolio_id   INTEGER NOT NULL REFERENCES portafolio(id),
    reproceso_id    INTEGER,
    calculado_en    TEXT NOT NULL,
    calculado_por   TEXT,
    fecha_desde     TEXT,
    fecha_hasta     TEXT,
    publicada       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE valorizacion (
    fecha_valorizacion  TEXT NOT NULL,
    isin                TEXT NOT NULL,
    version_calculo     INTEGER NOT NULL REFERENCES version_calculo(id),
    posicion_id         INTEGER,
    nominal             TEXT,
    vigente             INTEGER,
    fecha_devengo       TEXT,
    ultimo_cupon        TEXT,
    proximo_cupon       TEXT,
    dias_transcurridos  INTEGER,
    dias_periodo        INTEGER,
    cupon_por_periodo   TEXT,
    devengo_por_100     TEXT,
    precio_proveedor    TEXT,
    precio_local        TEXT,
    tipo_cambio         TEXT,
    precio_imputado     INTEGER,
    tipo_cambio_imputado INTEGER,
    dias_arrastre_precio INTEGER,
    fecha_origen_precio TEXT,
    fecha_origen_tipo_cambio TEXT,
    security_mv_local   TEXT,
    devengo_local       TEXT,
    total_mv_local      TEXT,
    fx                  TEXT,
    security_mv_base    TEXT,
    devengo_base        TEXT,
    total_mv_base       TEXT,
    caja_origen         TEXT,
    caja_base           TEXT,
    begin_mv            TEXT,
    efecto_precio_fx    TEXT,
    devengo_dia         TEXT,
    cupon_pagado        TEXT,
    alta_posicion       TEXT,
    baja_vencimiento    TEXT,
    cobros_dia          TEXT,
    efecto_fx_caja      TEXT,
    end_mv              TEXT,
    control             TEXT,
    devengo_por_100_t0  TEXT,
    dias_transcurridos_t0 INTEGER,
    dias_periodo_t0     INTEGER,
    ultimo_cupon_t0     TEXT,
    proximo_cupon_t0    TEXT,
    security_mv_base_t0 TEXT,
    devengo_base_t0     TEXT,
    total_mv_base_t0    TEXT,
    quiebre_t0          TEXT,
    devengo_diario      TEXT,
    evento              TEXT,
    error               TEXT,
    PRIMARY KEY (fecha_valorizacion, isin, version_calculo)
);
CREATE INDEX ix_valorizacion_version_fecha ON valorizacion(version_calculo, fecha_valorizacion);
CREATE INDEX ix_valorizacion_isin ON valorizacion(isin, fecha_valorizacion);

CREATE VIEW valorizacion_vigente AS
SELECT v.*
FROM valorizacion v
JOIN (
    SELECT fecha_valorizacion AS f, isin AS i, MAX(version_calculo) AS m
    FROM valorizacion GROUP BY fecha_valorizacion, isin
) ult ON v.fecha_valorizacion = ult.f AND v.isin = ult.i AND v.version_calculo = ult.m;

CREATE TABLE reproceso (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    portafolio_id           INTEGER NOT NULL REFERENCES portafolio(id),
    fecha_desde             TEXT NOT NULL,
    fecha_hasta             TEXT NOT NULL,
    isines                  TEXT,
    disparador              TEXT,
    usuario                 TEXT,
    encolado_en             TEXT,
    iniciado_en             TEXT,
    terminado_en            TEXT,
    duracion_ms             INTEGER,
    estado                  TEXT NOT NULL,
    mensaje                 TEXT,
    version_calculo         INTEGER,
    valorizaciones_totales  INTEGER DEFAULT 0,
    valorizaciones_cambiadas INTEGER DEFAULT 0,
    forzado                 INTEGER DEFAULT 0
);

CREATE TABLE reexpresion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    reproceso_id        INTEGER NOT NULL REFERENCES reproceso(id),
    fecha_valorizacion  TEXT NOT NULL,
    isin                TEXT NOT NULL,
    campo               TEXT NOT NULL,
    valor_anterior      TEXT,
    valor_nuevo         TEXT,
    diferencia_absoluta TEXT,
    diferencia_relativa TEXT,
    causa               TEXT,
    usuario             TEXT,
    momento             TEXT
);
CREATE INDEX ix_reexpresion_reproceso ON reexpresion(reproceso_id);

CREATE TABLE bitacora (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    momento                 TEXT NOT NULL,
    usuario                 TEXT,
    accion                  TEXT NOT NULL,
    entidad                 TEXT,
    entidad_id              TEXT,
    detalle                 TEXT,
    rango_desde             TEXT,
    rango_hasta             TEXT,
    valorizaciones_cambiadas INTEGER
);
CREATE INDEX ix_bitacora_momento ON bitacora(momento);

CREATE TABLE fecha_desactualizada (
    portafolio_id   INTEGER NOT NULL REFERENCES portafolio(id),
    fecha           TEXT NOT NULL,
    isin            TEXT NOT NULL,
    motivo          TEXT,
    marcado_en      TEXT,
    PRIMARY KEY (portafolio_id, fecha, isin)
);

CREATE TABLE periodo_cerrado (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portafolio_id   INTEGER NOT NULL REFERENCES portafolio(id),
    fecha_desde     TEXT NOT NULL,
    fecha_hasta     TEXT NOT NULL,
    cerrado_en      TEXT,
    cerrado_por     TEXT,
    reabierto_en    TEXT,
    reabierto_por   TEXT,
    justificacion   TEXT
);

CREATE TABLE carga (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    clave_idempotencia  TEXT UNIQUE,
    nombre_archivo      TEXT,
    momento             TEXT,
    usuario             TEXT,
    filas_nuevas        INTEGER DEFAULT 0,
    filas_identicas     INTEGER DEFAULT 0,
    filas_conflicto     INTEGER DEFAULT 0,
    filas_rechazadas    INTEGER DEFAULT 0,
    resumen             TEXT
);
