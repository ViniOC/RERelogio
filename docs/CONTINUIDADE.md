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
- [ ] **F1 Hardware** — descobrir controlador e pinos da tela e da luz de fundo (backup +
  comunidade GeekMagic/SmallTV); gravar firmware mínimo que escreve na tela; **restaurar o
  de fábrica e confirmar que volta** (prova do caminho de volta); gravar o mínimo de novo.
- [ ] **F2 Firmware** — Wi-Fi, NTP (America/Sao_Paulo), Open-Meteo, layout C com dados
  fixos de teste, OTA.
- [ ] **F3 Dados do Claude** — endpoint no relógio + script no PC lendo `ai-usagebar` +
  timer systemd.
- [ ] **F4 Acabamento** — dado velho, sessão renovada, cores por faixa, brilho noturno.

## Agora

Decisões fechadas. Próximo passo exato: F1 — identificar controlador/pinos da tela.

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
