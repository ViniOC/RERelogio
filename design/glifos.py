"""Tabelas de glifos e ícones compartilhadas pela prévia e pelo firmware.

O firmware desenha texto glifo a glifo, a partir destas tabelas, com o mesmo
algoritmo de `desenha_texto` abaixo. Assim a prévia é fiel ao relógio.
"""
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DIR_FONTES = Path(__file__).resolve().parent / "fontes"
DIGITOS = "0123456789"

# Textos possíveis em cada fonte pequena (define o conjunto de caracteres)
TEXTOS_PEQ = ["janela 5h", "reinicia 3h31", "Semana 7d", "sem dados",
              "atualizado há 12 min", "sessão renovada", "Claude: sem dados"]

# nome: (arquivo, tamanho em px, bits por pixel, caracteres)
FONTES = {
    "hora": ("Jersey10.ttf", 80, 1, DIGITOS + ":-"),
    "grande": ("Jersey10.ttf", 30, 1, DIGITOS + "°-SEGTRQUAIXÁBDOM"),
    "data": ("Jersey10.ttf", 20, 1, DIGITOS + " JANFEVMRBIUOLGSTDZ"),
    "titulo": ("Montserrat-SemiBold.otf", 15, 4, "Claude"),
    "pct": ("Montserrat-SemiBold.otf", 16, 4, DIGITOS + "%-"),
    "peq": ("Montserrat-Medium.otf", 12, 4, DIGITOS + "%-:" + "".join(TEXTOS_PEQ)),
}


@dataclass
class Glifo:
    cp: int
    w: int
    h: int
    dx: int   # deslocamento do canto esquerdo em relação à origem
    dy: int   # topo em relação à linha de base (negativo = acima)
    av: int   # avanço horizontal
    px: list  # intensidades 0..(2^bpp - 1), linha a linha


@dataclass
class Fonte:
    nome: str
    bpp: int
    glifos: dict

    @property
    def maximo(self):
        return (1 << self.bpp) - 1


def monta_fonte(nome):
    arq, tam, bpp, chars = FONTES[nome]
    f = ImageFont.truetype(str(DIR_FONTES / arq), tam)
    maximo = (1 << bpp) - 1
    glifos = {}
    for ch in sorted(set(chars)):
        l, t, r, b = f.getbbox(ch, anchor="ls")
        w, h = max(r - l, 0), max(b - t, 0)
        px = []
        if w and h:
            img = Image.new("L", (w, h), 0)
            d = ImageDraw.Draw(img)
            d.fontmode = "1" if bpp == 1 else "L"
            d.text((-l, -t), ch, font=f, fill=255, anchor="ls")
            px = [round(v * maximo / 255) for v in img.getdata()]
        glifos[ch] = Glifo(ord(ch), w, h, l, t, round(f.getlength(ch)), px)
    return Fonte(nome, bpp, glifos)


_cache = {}


def fonte(nome):
    if nome not in _cache:
        _cache[nome] = monta_fonte(nome)
    return _cache[nome]


def largura(nome, s):
    return sum(fonte(nome).glifos[c].av for c in s)


def mistura(fundo, cor, a):
    return tuple(round(fundo[i] + (cor[i] - fundo[i]) * a) for i in range(3))


def desenha_texto(img, nome, x, y, s, cor, alinha="e"):
    """y é a linha de base. alinha: e (esquerda), d (direita), c (centro)."""
    f = fonte(nome)
    if alinha == "d":
        x -= largura(nome, s)
    elif alinha == "c":
        x -= largura(nome, s) // 2
    for ch in s:
        g = f.glifos[ch]
        for i, v in enumerate(g.px):
            if v:
                px, py = x + g.dx + i % g.w, y + g.dy + i // g.w
                if 0 <= px < img.width and 0 <= py < img.height:
                    a = v / f.maximo
                    img.putpixel((px, py), cor if a == 1 else
                                 mistura(img.getpixel((px, py)), cor, a))
        x += g.av


# ---------- ícones (máscaras de 1 bit, uma cor) ----------

SOL = (255, 204, 64)


def _mascara(w, h, desenho):
    img = Image.new("L", (w, h), 0)
    desenho(ImageDraw.Draw(img))
    return w, h, [1 if v >= 128 else 0 for v in img.getdata()]


def _sol(d):
    d.ellipse((4, 4, 15, 15), fill=255)
    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
        px, py = 9 + dx * 9, 9 + dy * 9
        d.rectangle((px, py, px + 1, py + 1), fill=255)


def _lua(d):
    d.ellipse((2, 2, 17, 17), fill=255)
    d.ellipse((7, -1, 22, 14), fill=0)


def _nuvem(d):
    for x0, y0, x1, y1 in [(0, 6, 9, 13), (5, 1, 16, 12), (12, 5, 21, 13)]:
        d.ellipse((x0, y0, x1, y1), fill=255)
    d.rectangle((4, 9, 17, 13), fill=255)


def _gotas(d):
    for x in (5, 10, 15):
        d.line((x, 15, x - 2, 19), fill=255)


def _claude(d):
    cx = cy = 6  # asterisco de 8 pontas, traço de 2 px
    for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
        for k in range(-6, 7):
            px, py = cx + dx * k, cy + dy * k
            d.rectangle((px, py, px + 1, py + 1), fill=255)


def _calendario(d):
    d.rectangle((0, 2, 11, 12), outline=255)
    d.rectangle((0, 2, 11, 4), fill=255)
    d.point([(3, 0), (3, 1), (8, 0), (8, 1)], fill=255)
    d.rectangle((3, 7, 5, 9), fill=255)


ICONES = {
    "sol": _mascara(20, 20, _sol),
    "lua": _mascara(20, 20, _lua),
    "nuvem": _mascara(22, 20, _nuvem),
    "gotas": _mascara(22, 20, _gotas),
    "claude": _mascara(14, 14, _claude),
    "calendario": _mascara(12, 13, _calendario),
}


def desenha_icone(img, nome, x, y, cor):
    w, h, px = ICONES[nome]
    for i, v in enumerate(px):
        if v:
            img.putpixel((x + i % w, y + i // w), cor)
