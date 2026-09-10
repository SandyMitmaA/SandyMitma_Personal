#!/usr/bin/env python3
"""Parte una narración continua en los doce archivos por escena.

Uso:
    python3 tools/partir-audio.py grabacion.mp4 --voz camila
    python3 tools/partir-audio.py grabacion.wav --voz locutor --silencio 0.5

Pensado para cuando la voz llega como un único archivo en vez de doce.

Un umbral fijo de silencio no basta: la escena 5 enumera siete filtros y sus
pausas internas son tan largas como las que separan escenas, mientras que
algunas fronteras reales apenas superan los 0,7 s. Así que el script no elige
por duración, sino por **posición**: mide cuánta voz hay antes de cada pausa
candidata y busca las once que mejor encajan con las proporciones del guion
(escena 5 es larga, escena 1 es corta, etc.). Eso distingue una pausa interna
de una frontera aunque duren lo mismo.

La forma del guion se mide en caracteres pronunciados, no en palabras: una
sigla deletreada dura como varias palabras y descuadraba el ajuste.
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Forma del guion contra la que se alinea el audio: caracteres pronunciados por
# escena, NO palabras. Contar palabras falla porque una sigla deletreada («CSV»
# → «ce ese uve») dura como tres palabras, y la escena 8 lleva dos. Medido sobre
# esta narración, el modelo por caracteres deja las doce escenas dentro del 15%
# de la mediana; el de palabras las desviaba hasta un 25%.
CARACTERES = [107, 54, 90, 188, 118, 254, 70, 124, 95, 94, 87, 158]
N = len(CARACTERES)

MERGE_GAP = 0.35    # dos silencios separados por menos que esto son uno solo
AVISO_DESVIO = 4.0  # segundos de desajuste a partir de los cuales conviene revisar
FINO = 0.18         # umbral para medir voz neta: incluye las pausas entre frases


def ffmpeg(*args):
    return subprocess.run(["ffmpeg", *args], capture_output=True, text=True)


def duracion(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def silencios(path, min_dur, umbral_db, total, recortar_bordes=True):
    """Tramos de silencio, con los fragmentados por el detector ya unidos."""
    res = ffmpeg("-i", path, "-af", f"silencedetect=n={umbral_db}dB:d={min_dur}",
                 "-f", "null", "-")
    ini = [float(m) for m in re.findall(r"silence_start: (-?[\d.]+)", res.stderr)]
    fin = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", res.stderr)]
    crudos = sorted(zip(ini, fin))

    unidos = []
    for a, b in crudos:
        if unidos and a - unidos[-1][1] < MERGE_GAP:
            unidos[-1][1] = b
        else:
            unidos.append([a, b])
    if not recortar_bordes:
        return [(a, b) for a, b in unidos]
    # un silencio pegado al inicio o al final no separa dos escenas
    return [(a, b) for a, b in unidos if a > 0.25 and b < total - 0.25]


def voz_antes(t, finos):
    """Segundos de voz real transcurridos antes del instante t.

    Descuenta TODA pausa, no solo las largas. Medir el eje con un umbral y
    elegir las candidatas con otro era el error: las pausas entre frases
    inflaban la posición aparente y desplazaban las fronteras.
    """
    mudo = 0.0
    for a, b in finos:
        if b <= t:
            mudo += b - a
        elif a < t:
            mudo += t - a
            break
        else:
            break
    return t - mudo


def elegir_fronteras(cands, total_voz):
    """Escoge N-1 candidatas, en orden, que mejor sigan las proporciones del guion.

    Programación dinámica sobre (candidata, frontera): minimiza la suma de
    desajustes contra la posición esperada de cada frontera medida en voz
    acumulada, no en tiempo de archivo — así las pausas no distorsionan la
    comparación.
    """
    acum, s = [], 0
    for p in CARACTERES[:-1]:
        s += p
        acum.append(s)
    esperado = [total_voz * a / sum(CARACTERES) for a in acum]

    n, k = len(cands), len(esperado)
    if n < k:
        return None, None

    INF = float("inf")
    coste = [[INF] * (k + 1) for _ in range(n + 1)]
    origen = [[None] * (k + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        coste[i][0] = 0.0

    for i in range(1, n + 1):
        for j in range(1, k + 1):
            # no usar la candidata i
            if coste[i - 1][j] < coste[i][j]:
                coste[i][j], origen[i][j] = coste[i - 1][j], ("saltar", i - 1, j)
            # usarla como frontera j
            if coste[i - 1][j - 1] < INF:
                c = coste[i - 1][j - 1] + abs(cands[i - 1]["voz"] - esperado[j - 1])
                if c < coste[i][j]:
                    coste[i][j], origen[i][j] = c, ("usar", i - 1, j - 1)

    if coste[n][k] == INF:
        return None, None

    elegidas, i, j = [], n, k
    while j > 0:
        accion, pi, pj = origen[i][j]
        if accion == "usar":
            elegidas.append(cands[pi])
        i, j = pi, pj
    elegidas.reverse()
    return elegidas, esperado


def main():
    ap = argparse.ArgumentParser(description="Parte una narración continua en doce escenas.")
    ap.add_argument("archivo")
    ap.add_argument("--voz", required=True, help="carpeta destino bajo assets/audio/")
    ap.add_argument("--silencio", type=float, default=0.5)
    ap.add_argument("--umbral", type=float, default=-32)
    ap.add_argument("--forzar", action="store_true",
                    help="escribe aunque el ajuste sea dudoso")
    a = ap.parse_args()

    if not os.path.isfile(a.archivo):
        print(f"No existe {a.archivo}")
        return 1

    total = duracion(a.archivo)
    tramos = silencios(a.archivo, a.silencio, a.umbral, total)
    if not tramos:
        print("No detecté ningún silencio interno. ¿Es una grabación continua sin pausas?")
        return 2

    # el eje se mide con un umbral fino para que las pausas entre frases no
    # inflen la posición aparente de cada candidata
    finos = silencios(a.archivo, FINO, a.umbral, total, recortar_bordes=False)
    total_voz = total - sum(b - x for x, b in finos)

    cands = [{"ini": ini, "fin": fin, "corte": (ini + fin) / 2,
              "voz": voz_antes(ini, finos), "pausa": fin - ini}
             for ini, fin in tramos]

    print(f"Archivo: {os.path.basename(a.archivo)}  ·  {total:.1f}s "
          f"({total_voz:.1f}s de voz, {total - total_voz:.1f}s de pausas)")
    print(f"Pausas candidatas: {len(cands)}   ·   fronteras a encontrar: {N - 1}")

    elegidas, esperado = elegir_fronteras(cands, total_voz)
    if not elegidas:
        print(f"\nSolo hay {len(cands)} pausas y hacen falta {N - 1}.")
        print(f"Baja el mínimo:  --silencio {max(0.2, a.silencio - 0.2):.1f}")
        return 2

    desvios = [abs(e["voz"] - x) for e, x in zip(elegidas, esperado)]
    peor = max(desvios)

    limites = [0.0] + [e["corte"] for e in elegidas] + [total]
    print(f"\n{'escena':<8}{'inicio':>9}{'fin':>9}{'dur':>8}{'pausa previa':>14}{'desvío':>9}")
    for i in range(N):
        ini, fin = limites[i], limites[i + 1]
        pausa = f"{elegidas[i-1]['pausa']:.2f}s" if i > 0 else "—"
        desv = f"{desvios[i-1]:+.1f}s" if i > 0 else "—"
        print(f"esc{i:02d}{ini:>12.2f}{fin:>9.2f}{fin-ini:>8.2f}{pausa:>14}{desv:>9}")

    descartadas = [c for c in cands if c not in elegidas]
    if descartadas:
        print(f"\nPausas descartadas por no ser frontera ({len(descartadas)}): " +
              ", ".join(f"{c['ini']:.1f}s" for c in descartadas))

    print(f"\nPeor desajuste: {peor:.1f}s")
    if peor > AVISO_DESVIO and not a.forzar:
        print(f"\nSupera los {AVISO_DESVIO}s de tolerancia. No escribo nada: un corte")
        print("mal puesto desincroniza el video de ahí en adelante.")
        print("Revisa la tabla; si los cortes te parecen correctos, repite con --forzar.")
        return 3

    destino = os.path.join(ROOT, "assets", "audio", a.voz)
    os.makedirs(destino, exist_ok=True)
    print(f"\nEscribiendo en assets/audio/{a.voz}/")
    for i in range(N):
        ini, fin = limites[i], limites[i + 1]
        salida = os.path.join(destino, f"esc{i:02d}.wav")
        res = ffmpeg("-y", "-i", a.archivo, "-ss", f"{ini:.3f}", "-to", f"{fin:.3f}",
                     "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", salida)
        if res.returncode != 0:
            print(f"  ✗ esc{i:02d}: {res.stderr.strip().splitlines()[-1]}")
            return 1
        print(f"  ✓ esc{i:02d}.wav  ({fin - ini:.2f}s)")

    print(f"\nListo. Ahora:  python3 tools/sincronizar.py --voz {a.voz}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
