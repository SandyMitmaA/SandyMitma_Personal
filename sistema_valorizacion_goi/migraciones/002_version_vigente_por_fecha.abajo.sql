DROP VIEW IF EXISTS valorizacion_vigente;

CREATE VIEW valorizacion_vigente AS
SELECT v.*
FROM valorizacion v
JOIN (
    SELECT fecha_valorizacion AS f, isin AS i, MAX(version_calculo) AS m
    FROM valorizacion GROUP BY fecha_valorizacion, isin
) ult ON v.fecha_valorizacion = ult.f AND v.isin = ult.i AND v.version_calculo = ult.m;
