# RERelogio — continuidade

## Objetivo

Trocar o firmware de fábrica do relógio (ESP8266EX, flash 4 MB) por um firmware próprio,
com backup de fábrica confiável para poder voltar atrás.

Pronto quando: firmware novo rodando e restauração do backup testada/conhecida.

## Fatos do hardware (verificados)

- ESP8266EX, flash 4 MB, porta `/dev/ttyUSB0`; gravação e reset automáticos pelo USB.
- Firmware de fábrica em Arduino, arquivos em LittleFS.
- Ferramenta: `uvx esptool@5.6.0` (não instalado no sistema; roda via uv).
- Teste de upload de imagem pela rede: `scripts/relogio_teste.py` (IP fixo no script).

## Decisões

- `backup/` fica fora do git: contém senha do Wi-Fi e chave do OpenWeatherMap.

Sabatina de 2026-10-31:

1. Firmware próprio (não o de fábrica com imagens): hora e temperatura funcionam com o PC
   desligado; visual sob controle total.
2. Limite do Claude vem de `~/.local/bin/ai-usagebar usage --json` (entrada `anthropic`,
   métricas "Session (5h)" e "Weekly (7d)", com `percent` e `reset_at`). O PC envia só
   números; o login do Claude nunca vai para o relógio.
3. Na tela: sessão 5h (grande, com "reinicia em") e semanal (pequena). Fable e Codex fora.
4. Temperatura: Open-Meteo (sem chave), cidade configurada.
5. Layout C — Claude em destaque: hora e temperatura numa linha no topo; % da sessão
   enorme; barra; "reinicia em Xh Ym"; "semana NN%" embaixo.
6. Dado velho: >15 min sem atualização → % em cinza + "atualizado há X"; se `reset_at`
   da sessão já passou → "sessão renovada".
7. Cores: fundo preto, texto branco/cinza; destaque só na barra e no %: <60% laranja
   Claude #D97757, 60–85% âmbar, >85% vermelho.
8. Noite (23h–7h): brilho ~15%, tela acesa (relógio fica no quarto). Depende de a placa
   ter controle da luz de fundo.

Revisão do visual (2026-10-31, referência enviada pelo usuário — substitui o item 5):

- Layout da referência em pixel-art: dia da semana + data (esq.), temperatura + ícone
  (dir.), hora grande, cenário, cartão "Claude" (ícone, %, barra, "sessão 5h",
  "reinicia 3h31") e cartão "Semana" (ícone, barra azul, %).
- Tema muda sozinho com o horário: dia, pôr do sol, noite (principal) e minimalista
  (fundo preto, sem cenário).
- Fonte única: Jersey 10 (OFL, `design/fontes/`), nítida em múltiplos de 10 px, sem
  suavização. Pixelify e Press Start 2P foram descartadas (5 parecia S, C parecia O).
- Prévia exata 240×240: `python3 -I design/tela.py design/previa-temas.png`.
  Ajustar o visual ali antes de mexer no firmware.

Padrões técnicos (escolha do agente, sem objeção do usuário): Arduino via PlatformIO;
credenciais Wi-Fi em arquivo local ignorado pelo git; atualização por OTA depois da
primeira gravação; relógio anuncia `relogio.local` (mDNS); PC envia via timer do
systemd (usuário) a cada ~2 min.

Fora de escopo: Codex, Fable, outras IAs; previsão do tempo; configuração pela tela/web.

## Fases

- [x] **Backup de fábrica** — evidência (2026-10-31):
  - `backup/fabrica-4MB.bin` (1ª leitura) e `backup/fabrica-4MB-leitura2.bin` (2ª leitura);
    hashes em `backup/SHA256SUMS`.
  - `scripts/comparar_flash.py` entre as duas: 1021 de 1024 setores idênticos. Só mudaram
    0x3FD000, 0x3FE000 e 0x3FF000 (181, 31 e 4 bytes) — a área de configuração do SDK
    (Wi-Fi/parâmetros do sistema, gravada pelo próprio chip ao ligar). Firmware
    (0x0–0xF2000) e LittleFS idênticos nas duas leituras.
  - Conclusão: backup confiável. A diferença é o relógio regravando a configuração
    do Wi-Fi ao reiniciar, não erro de leitura.
- [x] **Decisões** — sabatina fechada (seção Decisões).
- [x] **F1 Hardware** — evidência (2026-10-31):
  - Tela ST7789 240×240, SPI modo 3, sem CS: MOSI GPIO13, SCLK GPIO14, DC GPIO0,
    RST GPIO2 (`firmware/platformio.ini`). Teste `firmware/src/main.cpp` gravado; usuário
    viu blocos vermelho/verde/azul na ordem certa e o texto legível.
  - Luz de fundo: GPIO5 com PWM, **invertida** (sinal baixo acende). Corrigido na F2: a
    F1 concluiu "polaridade normal" sem saber em qual dos 3 níveis a tela apagava; com
    255 fixo a tela ficou apagada, com 255 invertido acendeu (usuário viu). Usar
    `brilho()` em `firmware/src/main.cpp`. O firmware de fábrica também tem "Night
    brightness". Não confirmado: o nível bom para o modo noite.
  - Restauração do backup: `write-flash 0 backup/fabrica-4MB.bin` → hash verificado;
    relógio voltou ao Wi-Fi em 192.168.1.5, NTP ok, clima de minha cidade ok, HTTP 200.
  - Atenção: o firmware de fábrica imprime a senha do Wi-Fi na serial. Ao ler a serial
    com ele gravado, filtrar também `PSW`.
  - Estado do relógio ao fim da F1: firmware de fábrica (restaurado).
- [x] **F2 Firmware** — evidência (2026-10-31): Wi-Fi, NTP, Open-Meteo (temperatura +
  nascer/pôr do sol), OTA, visual pixel-art com 4 temas automáticos; usuário aprovou os
  4 temas no aparelho. Portão de revisão (revisor independente): nenhum defeito sério;
  2 de baixa severidade corrigidos (hora lida 1x por desenho; clima some após 1h sem
  atualizar e re-tenta a cada 1 min). Lição: se o Wi-Fi não conecta, conferir o nome
  exato da rede (maiúsc./`_`).
- [~] **F3 Dados do Claude** — provado (2026-10-31): `POST /claude` aceita
  `{sessao, reinicio, semana}` e recusa JSON inválido (HTTP 400);
  `scripts/enviar_claude.py` lê `ai-usagebar` (sessão = janela 18000 s; semana = rótulo
  "Weekly") e enviou 65%/39% (HTTP 200); timer `rerelogio-claude.timer` (usuário,
  2 min) ativo, cópia em `scripts/systemd/`. Falta: usuário confirmar números reais
  na tela; decidir uso no notebook do trabalho (mesma conta? mesmo SO?).
- [ ] **F4 Acabamento** — dado velho, sessão renovada, cores por faixa, brilho noturno.

## Agora

F3 no ar. Próximo passo exato: usuário confirmar na tela 65%/39% (ou o valor atual de
`python3 -I scripts/enviar_claude.py --teste`); responder se o notebook do trabalho usa
a mesma conta do Claude e qual SO. Depois F4 (dado velho, "sessão renovada").
Log do envio: `journalctl --user -u rerelogio-claude -n 20`.

Fluxo do visual: editar `design/tela.py` → `python3 -I design/tela.py design/previa-temas.png`
→ `python3 -I design/gerar.py` (gera `firmware/include/recursos.h` e `firmware/data/*.rgb`)
→ `cd firmware && uvx platformio run -e ota -t uploadfs --upload-port 192.168.1.5`
→ `uvx platformio run -e ota -t upload --upload-port 192.168.1.5`.
`relogio.local` às vezes não resolve (mDNS do ESP8266); usar o IP. Sugestão: reservar
192.168.1.5 para o MAC c4:d8:d5:35:15:b4 no roteador.
Luz de fundo invertida; serial pode dar I/O error — conferir pela rede (`/tema`).

## Como verificar

```bash
cd ~/Desenvolvimento/RERelogio
sha256sum -c backup/SHA256SUMS
python3 -I scripts/comparar_flash.py backup/fabrica-4MB.bin backup/fabrica-4MB-leitura2.bin
```

Restaurar o de fábrica (não testado):

```bash
uvx esptool@5.6.0 -p /dev/ttyUSB0 -b 460800 write-flash 0 backup/fabrica-4MB.bin
```

## Pendências e perguntas


- (resolvido) Nome fica RERelogio; repositório git local criado em 2026-10-31.
