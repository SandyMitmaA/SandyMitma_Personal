-- 002 La version vigente se resuelve por fecha, no por (fecha, isin).
--
-- Con la resolucion por (fecha, isin), una version que deja de publicar un
-- instrumento -por ejemplo porque su posicion fue eliminada- no lo retiraba:
-- la fila antigua seguia siendo el maximo para esa combinacion y sobrevivia al
-- reproceso. Cada version es ahora una publicacion completa de las fechas que
-- cubre, y un reproceso parcial arrastra sin tocar las filas que no recalcula.

DROP VIEW IF EXISTS valorizacion_vigente;

CREATE VIEW valorizacion_vigente AS
SELECT v.*
FROM valorizacion v
JOIN (
    SELECT fecha_valorizacion AS f, MAX(version_calculo) AS m
    FROM valorizacion GROUP BY fecha_valorizacion
) ult ON v.fecha_valorizacion = ult.f AND v.version_calculo = ult.m;
