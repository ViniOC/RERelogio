"""Lê o limite do Claude no ai-usagebar e envia para o relógio.

Envia só números: {"sessao": %, "reinicio": epoch, "semana": %, "idade": s}. O login do
Claude nunca sai do PC. Rodado a cada 2 min pelo timer do systemd (usuário).

Uso: python3 -I scripts/enviar_claude.py [--teste] [--relogio 192.168.1.5]
     --teste mostra o que seria enviado, sem enviar.
"""
import argparse
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AI_USAGEBAR = Path.home() / ".local/bin/ai-usagebar"
JANELA_SESSAO = 5 * 3600


def le_uso():
    saida = subprocess.run([str(AI_USAGEBAR), "usage", "--json"], capture_output=True,
                           text=True, timeout=60, check=True).stdout
    claude = next((e for e in json.loads(saida)["entries"] if e["id"] == "anthropic"), None)
    if claude is None or claude.get("error") or claude.get("status") != "ready":
        raise RuntimeError(f"ai-usagebar sem dados do Claude: {claude and claude.get('error')}")
    metricas = claude["metrics"]
    sessao = next(m for m in metricas if m.get("window_secs") == JANELA_SESSAO)
    semana = next(m for m in metricas if m["label"].startswith("Weekly"))
    reinicio = datetime.fromisoformat(sessao["reset_at"].replace("Z", "+00:00"))
    # idade: há quantos segundos o ai-usagebar leu (pode servir dado de cache)
    lido = datetime.fromisoformat(claude["fetched_at"][:26].rstrip("Z") + "+00:00")
    idade = max(0, int((datetime.now(timezone.utc) - lido).total_seconds()))
    return {"sessao": round(sessao["percent"]), "reinicio": int(reinicio.timestamp()),
            "semana": round(semana["percent"]), "idade": idade}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--relogio", default="192.168.1.5")
    p.add_argument("--teste", action="store_true")
    args = p.parse_args()
    dados = le_uso()
    if args.teste:
        print(json.dumps(dados))
        return
    req = urllib.request.Request(f"http://{args.relogio}/claude", data=json.dumps(dados).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        print(r.status, r.read().decode().strip(), json.dumps(dados))


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:  # o timer registra no journal; o relógio marca dado velho
        print(f"erro: {erro}", file=sys.stderr)
        sys.exit(1)
