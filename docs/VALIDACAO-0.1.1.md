# Validação da cópia 0.1.1 — 15/10/2026

**98 testes passaram em 95,53 s**, em Windows x64. Ruff E4/E7/E9/F/I
passou. A suíte rodou limitada a quatro núcleos do seu próprio processo; não
alterou afinidade, prioridade, estado ou arquivos do LocalCast 0.1.0 em uso.

## GPU e mídia

A validação local de GPU selecionou **NVIDIA NVENC**, com decodificação CUDA:

- H.264/MP4 e HEVC/MKV com EAC3, inclusive fonte 3840×2160 e HDR sintético.
- CUDA para decodificação; escala CUDA sem HDR/legenda; filtros CPU para HDR
  e texto, mantendo NVENC na saída.
- HLS MPEG-TS com H.264 8-bit, nível até 4.1, resolução até 1080p, AAC estéreo.
- Decodificação completa das playlists geradas, verificando áudio/vídeo reais.
- Áudio escolhido comprovado por frequência e SRT/ASS/PGS comprovadas por pixels,
  antes/durante/depois da fala e após seek.

Não se afirma funcionamento físico de Intel QSV ou AMD AMF: são alternativas
implementadas, dependentes de driver/equipamento. Falha inicial retorna às
alternativas e por fim à CPU; a CPU também foi validada.

## Reserva e processo

O teste real usa um vídeo sintético de **120 s**, com alvo reduzido para **30 s**
e retomada na metade, exercitando CPU, GPU e falha inicial de GPU seguida de CPU.
O encoder para de avançar antes de converter o filme inteiro. A amostra de
tempo de CPU do processo suspenso fica praticamente parada. Ao avançar o relógio
simulado, ele retoma, produz novos segmentos e volta a descansar.

O teste também simula perda do relógio, verifica retomada para evitar um processo
preso e encerra a sessão enquanto o processo está suspenso. Confere término do
PID próprio e remoção do cache. Falha de encoder gera HLS novo antes do LOAD,
com motivo de fallback preservado. Os limiares padrão **90/45 s** são cobertos
por testes determinísticos da mesma política.

A pausa/retomada GPU também foi repetida com o Python privado **3.15.0** desta
distribuição: **1 teste passou em 13,85 s**, com psutil nativo e mídia sintética.

## Interface e EXE

O EXE real **0.1.1**, com autoria **By Fagner Lemes**, foi compilado com Python
privado 3.15.0, PyInstaller 6.22.3, PySide6 6.12.0 e psutil 7.2.2. Abriu e fechou
em uma pasta contendo somente ele, nos modos **offscreen e nativo Windows**,
com PATH limitado ao Windows e dados em perfil de teste. Logo, espera,
FFmpeg/FFprobe e psutil estavam incluídos. O diagnóstico sem console passou.

A captura de [desempenho expandido](interface-desempenho-0.1.1.png) é da GUI Qt real,
sem simular conexão a uma TV nem consultar uma chave pessoal.

Tamanho e SHA256 do EXE desta cópia constam em
[BUILD-0.1.1.json](../BUILD-0.1.1.json).

## Limites da verificação

**Nenhum Chromecast físico foi buscado ou controlado.** A GPU é real, mas o
relógio de reprodução dos testes de reserva é simulado. O teste não comprova
que o receiver/firmware real envie os mesmos estados ou aceite esse HLS.

Não há promessa de uma porcentagem fixa de economia de CPU. HDR, legenda,
codec, driver, complexidade da imagem e outros programas influenciam a carga.
Também não é garantia de ausência de buffering numa LAN real.

Faça a comparação no aparelho após encerrar a sessão da versão estável,
seguindo [DESENVOLVIMENTO-0.1.1.md](DESENVOLVIMENTO-0.1.1.md).
