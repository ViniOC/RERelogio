"""Exporta o design para o firmware.

Gera:
  firmware/include/recursos.h  fontes (glifos), ícones, cores, temas e posições
  firmware/data/tema<N>.rgb    fundo 240x240 de cada tema, RGB565 little-endian

Uso: python3 -I design/gerar.py
Depois: cd firmware && uvx platformio run -e ota -t uploadfs   (fundos)
                       uvx platformio run -e ota -t upload     (firmware)
"""
import struct
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))
import glifos as G  # noqa: E402
import tela as T  # noqa: E402

RAIZ = PASTA.parent
CABECALHO = RAIZ / "firmware/include/recursos.h"
DADOS = RAIZ / "firmware/data"


def rgb565(c):
    r, g, b = c
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def empacota(valores, bpp):
    """Bits contíguos, mais significativo primeiro; completa o último byte."""
    saida, acc, n = [], 0, 0
    for v in valores:
        acc = (acc << bpp) | v
        n += bpp
        if n == 8:
            saida.append(acc)
            acc, n = 0, 0
    if n:
        saida.append(acc << (8 - n))
    return saida


def bytes_c(nome, dados):
    linhas = [", ".join(f"0x{b:02x}" for b in dados[i:i + 16])
              for i in range(0, len(dados), 16)]
    corpo = ",\n    ".join(linhas) if linhas else "0"
    return f"static const uint8_t {nome}[] PROGMEM = {{\n    {corpo}\n}};\n"


def fonte_c(nome):
    f = G.fonte(nome)
    dados, glifos = [], []
    for ch in sorted(f.glifos, key=ord):
        g = f.glifos[ch]
        glifos.append(f"    {{{g.cp}, {g.w}, {g.h}, {g.dx}, {g.dy}, {g.av}, {len(dados)}}},")
        dados += empacota(g.px, f.bpp)
    pref = f"F_{nome.upper()}"
    return (bytes_c(pref + "_px", dados)
            + f"static const Glifo {pref}_g[] PROGMEM = {{\n" + "\n".join(glifos) + "\n};\n"
            + f"static const Fonte {pref} = {{{pref}_g, {len(glifos)}, {pref}_px, {f.bpp}}};\n")


def icone_c(nome):
    w, h, px = G.ICONES[nome]
    pref = f"I_{nome.upper()}"
    return (bytes_c(pref + "_px", empacota(px, 1))
            + f"static const Icone {pref} = {{{w}, {h}, {pref}_px}};\n")


def gera_cabecalho():
    partes = [
        "// Gerado por design/gerar.py. Não editar à mão.\n#pragma once\n#include <Arduino.h>\n",
        "struct Glifo {\n  uint16_t cp;\n  uint8_t w, h;\n  int8_t dx, dy;\n"
        "  uint8_t av;\n  uint16_t ofs;\n};\n",
        "struct Fonte {\n  const Glifo *g;\n  uint8_t n;\n  const uint8_t *px;\n  uint8_t bpp;\n};\n",
        "struct Icone {\n  uint8_t w, h;\n  const uint8_t *px;\n};\n",
        "\n// Posições (y de texto = linha de base)\n",
        "".join(f"#define {k} {v}\n" for k, v in T.LAYOUT.items()),
        "\n// Cores\n",
    ]
    for nome in ["TEXTO", "TEXTO_2", "TRILHO", "LARANJA", "AMBAR", "VERMELHO", "AZUL", "CHUVA"]:
        partes.append(f"#define COR_{nome} 0x{rgb565(getattr(T, nome)):04x}\n")
    partes.append(f"#define COR_SOL 0x{rgb565(G.SOL):04x}\n")
    nomes = list(T.TEMAS)
    partes.append("\n// Temas: " + ", ".join(f"{i} {n}" for i, n in enumerate(nomes)) + "\n")
    partes.append(f"#define N_TEMAS {len(nomes)}\n")
    for campo in ["texto", "texto_2", "nuvem"]:
        valores = ", ".join(f"0x{rgb565(T.TEMAS[n][campo]):04x}" for n in nomes)
        partes.append(f"static const uint16_t TEMA_{campo.upper()}[] = {{{valores}}};\n")
    partes.append("\n// Fontes\n")
    partes += [fonte_c(n) for n in G.FONTES]
    partes.append("\n// Ícones (1 bit)\n")
    partes += [icone_c(n) for n in G.ICONES]
    CABECALHO.write_text("".join(partes))
    print("gerado:", CABECALHO.relative_to(RAIZ))


def gera_fundos():
    DADOS.mkdir(exist_ok=True)
    for i, nome in enumerate(T.TEMAS):
        img = T.fundo(nome)
        px = img.tobytes()
        dados = b"".join(struct.pack("<H", rgb565(px[k:k + 3]))
                         for k in range(0, len(px), 3))
        caminho = DADOS / f"tema{i}.rgb"
        caminho.write_bytes(dados)
        print(f"gerado: {caminho.relative_to(RAIZ)} ({nome}, {len(dados)} bytes)")


if __name__ == "__main__":
    gera_cabecalho()
    gera_fundos()
