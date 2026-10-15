# Diagnóstico por camada

| Sintoma | Evidência a conferir | Próximo teste |
|---|---|---|
| Nenhum aparelho na busca | Mesma LAN, UDP 5353, rede Privada, VPN/guest Wi-Fi | Informe o IP do Chromecast e repita a busca |
| Conexão falha antes de LOAD | TCP 8009, aparelho ligado, IP correto | `Test-NetConnection IP_DO_CHROMECAST -Port 8009` |
| LOAD timeout e nenhum GET | IP LAN anunciado, porta do PC, firewall | Abra `/health` em outro aparelho da LAN |
| HTTP 404/416 | Última URL foi revogada? Playlist referencia segmento existente? Range inválido? | Nova transmissão e diagnóstico; não reutilize URL de sessão antiga |
| MP4 direto funciona; HLS falha | HTTP de manifesto e segmentos, LOAD_FAILED/IDLE ERROR, FFmpeg sem erro | Mesmo MP4 com Forçar HLS; guarde relatório e firmware/modelo |
| Original falha | mode=original, MIME/contêiner/codecs do arquivo, LOAD_FAILED ou IDLE ERROR | Selecione Automática e Transmitir; Original não faz fallback |
| Campos de faixas cinza | Conversão selecionada como Original | As faixas dependem do receiver; volte a Automática e transmita novamente |
| App não abre sem terminal | startup.log / startup-launcher.log, runtime/python/pythonw.exe | Execute iniciar-debug.cmd para obter saída visível |
| HLS MP4 funciona; MKV HEVC trava | Velocidade FFmpeg, CPU, HDR, disco, áudio | 720p; amostra SDR; comparar arquivo real com amostra |
| Sem áudio / idioma errado | Campo Áudio, Sem áudio, índice no diagnóstico, AAC na saída, HDMI/volume | Escolha outra faixa e clique Aplicar faixas |
| Legenda ausente | Campo Legenda, tempo da fala, codec/faixa, stderr do FFmpeg | Escolha a faixa e Aplicar faixas; texto exige subtitles/libass, imagem exige overlay/decoder |
| Legenda errada após seek | Índice de legenda e offset no diagnóstico, timestamps do arquivo | Compare mesma fala desde o começo e por seek; salve diagnóstico/log |
| Legenda cinza na lista | Codec desconhecido | Formato ainda não suportado; tente uma faixa SRT/ASS/PGS do arquivo |
| Chromecast fica na tela do receiver | Usou Parar ou Desconectar? Conexão ativa? Quit confirmado no log? | Clique Desconectar; ao fechar normalmente o app também solicita a saída |
| Cores lavadas ou HDR falha | color_transfer/primaries e zscale/tonemap | Arquivo SDR, depois HDR; Dolby Vision não garantido |
| Pause funciona e Play falha | Receptor ainda tem sessão? acabou a mídia? conexões? | Recarregar arquivo e verificar estados |
| Porta já em uso | Erro ao criar servidor | Feche outra instância ou use `--port 8877` |

Um HTTP 200 apenas prova que o servidor entregou bytes. Um estado PLAYING recebido apenas prova que o receiver informou reprodução; a confirmação de imagem, som, sincronia e qualidade vem do teste físico. Não há introspecção de `CastReceiverContext.canDisplayType()` no Default Media Receiver neste sender Python.

HEVC é um limite de codec do Chromecast 2: trocar MKV por MP4 sem converter vídeo não o resolve. EAC3 pode depender de passthrough/TV/receiver; este MVP evita essa dependência convertendo a AAC estéreo. MKV não é usado como contêiner direto no receiver. HLS/MPEG-TS com H.264/AAC é uma escolha conservadora a testar no aparelho, não uma garantia baseada apenas na documentação de plataforma.

Na versão portátil, logs/cache ficam em `localcast-data\logs` e `localcast-data\cache` dentro da pasta do app. No desenvolvimento, a raiz padrão é `%LOCALAPPDATA%\LocalCastMVP`. Pode mudar a raiz com `LOCALCAST_DATA_DIR` antes de iniciar. O diagnóstico inclui índices de áudio/legenda e offset da sessão. O aplicativo não configura firewall, roteador ou TV automaticamente.

