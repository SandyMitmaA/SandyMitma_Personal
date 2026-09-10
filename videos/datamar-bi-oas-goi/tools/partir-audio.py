#!/usr/bin/env python3
"""Parte una narración continua en los doce archivos por escena.

Uso:
    python3 tools/partir-audio.py grabacion.wav --voz camila
    python3 tools/partir-audio.py grabacion.wav --voz locutor --silencio 0.7 --umbral -34

Pensado para cuando la voz llega como un único archivo en vez de doce. Detecta
los silencios entre frases con ffmpeg y corta ahí, escribiendo
`assets/audio/<voz>/esc00.wav` … `esc11.wav`.

Necesita encontrar exactamente once silencios largos, uno por frontera de
escena. Si encuentra otra cantidad no adivina: informa lo que halló y sugiere
cómo ajustar los parámetros, porque un corte mal puesto desincroniza todo el
video a partir de ahí.
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N_ESCENAS = 12


def ffmpeg(*args):
    return subprocess.run(["ffmpeg", *args], capture_output=True, text=True)


def duracion(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def silencios(path, min_dur, umbral_db):
    """Devuelve [(inicio, fin)] de cada tramo de silencio detectado."""
    res = ffmpeg("-i", path, "-af", f"silencedetect=n={umbral_db}dB:d={min_dur}",
                 "-f", "null", "-")
    inicios = [float(m) for m in re.findall(r"silence_start: (-?[\d.]+)", res.stderr)]
    finales = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", res.stderr)]
    return list(zip(inicios, finales))


def main():
    ap = argparse.ArgumentParser(description="Parte una narración continua en doce escenas.")
    ap.add_argument("archivo", help="la grabación completa")
    ap.add_argument("--voz", required=True, help="nombre de la carpeta destino bajo assets/audio/")
    ap.add_argument("--silencio", type=float, default=0.6,
                    help="duración mínima de silencio que cuenta como corte (s)")
    ap.add_argument("--umbral", type=float, default=-32,
                    help="por debajo de estos dB se considera silencio")
    a = ap.parse_args()

    if not os.path.isfile(a.archivo):
        print(f"No existe {a.archivo}")
        return 1

    total = duracion(a.archivo)
    tramos = silencios(a.archivo, a.silencio, a.umbral)
    # un silencio al inicio o al final no separa dos escenas
    internos = [(i, f) for i, f in tramos if i > 0.25 and f < total - 0.25]

    print(f"Archivo: {os.path.basename(a.archivo)}  ·  {total:.1f} s")
    print(f"Silencios internos de ≥{a.silencio}s por debajo de {a.umbral}dB: {len(internos)}")

    if len(internos) != N_ESCENAS - 1:
        print(f"\nEsperaba {N_ESCENAS - 1} cortes y encontré {len(internos)}. No voy a adivinar:")
        print("un corte mal puesto desincroniza el video de ahí en adelante.\n")
        if len(internos) > N_ESCENAS - 1:
            print("Hay más cortes de la cuenta — está partiendo dentro de las frases.")
            print(f"  Prueba a subir el mínimo:  --silencio {a.silencio + 0.3:.1f}")
        else:
            print("Hay menos cortes de la cuenta — las pausas no llegan al umbral.")
            print(f"  Prueba a bajarlo:  --silencio {max(0.2, a.silencio - 0.2):.1f}")
            print(f"  o a subir el umbral:  --umbral {a.umbral + 6:.0f}")
        if internos:
            print("\n  Cortes detectados (s):")
            for i, (ini, fin) in enumerate(internos, 1):
                print(f"    {i:>2}.  {ini:>7.2f} → {fin:>7.2f}   (pausa de {fin - ini:.2f}s)")
        print("\nSi no logras un corte limpio, entrégame los doce archivos por separado.")
        return 2

    # corta por el punto medio de cada silencio, para no comer aire de ninguna escena
    limites = [0.0] + [(i + f) / 2 for i, f in internos] + [total]

    destino = os.path.join(ROOT, "assets", "audio", a.voz)
    os.makedirs(destino, exist_ok=True)

    print(f"\nEscribiendo en assets/audio/{a.voz}/")
    for n in range(N_ESCENAS):
        ini, fin = limites[n], limites[n + 1]
        salida = os.path.join(destino, f"esc{n:02d}.wav")
        res = ffmpeg("-y", "-i", a.archivo, "-ss", f"{ini:.3f}", "-to", f"{fin:.3f}",
                     "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", salida)
        if res.returncode != 0:
            print(f"  ✗ esc{n:02d}: {res.stderr.strip().splitlines()[-1]}")
            return 1
        print(f"  ✓ esc{n:02d}.wav   {ini:>7.2f} → {fin:>7.2f}   ({fin - ini:.2f}s)")

    print(f"\nListo. Ahora:  python3 tools/sincronizar.py --voz {a.voz}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
