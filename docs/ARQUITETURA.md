# Arquitetura

`ui_assets.py` resolve logo, assinatura e tela de espera no código-fonte, na pasta portátil ou nos recursos do PyInstaller. **Conectar** chama `PlaybackSession.show_standby`: registra o MP4 estático empacotado, carrega no receiver e solicita pause. `standby_active` é independente do modo de reprodução, de modo que seek/faixas/Play não tratam a imagem como um filme aberto. **Parar** usa `stop_to_standby`; as rotinas internas de stop, troca de arquivo e desconexão continuam liberando tokens/processos sem reabrir a tela. O filme e a espera usam o mesmo servidor LAN; só o recurso registrado está acessível.

```text
PySide6 GUI
  └─ fila serial / worker de comandos
      └─ PlaybackSession
          ├─ media.py / ffprobe → análise e escolha do modo
          ├─ subtitles.py → libass / overlay das legendas embutidas
          ├─ cast_client.py / PyChromecast → descoberta, LOAD e controle
          ├─ http_server.py → MP4 com Range ou playlist/segmentos HLS
          └─ transcoder.py / FFmpeg → H.264 + AAC / MPEG-TS

Chromecast → HTTP LAN do PC → arquivo selecionado ou cache HLS da sessão
Chromecast → MEDIA_STATUS / LOAD_FAILED → listener → snapshot → GUI
```

`gui.py` mantém a interface no thread Qt. Operações de descoberta, probe, conexão, LOAD e seek são serializadas num worker Python; sinais Qt entregam resultados no thread principal. HTTP atende requisições concorrentes; FFmpeg tem leitores separados para stdout de progresso e stderr. Não há integração com Chrome, extensão, DLNA ou espelhamento de tela.

`media.py` seleciona a primeira faixa de vídeo que não é capa e enumera todas as faixas de áudio/legenda, preservando índices globais, idioma, título, disposição padrão/forçada e ordinal de legenda. A faixa de áudio padrão (ou primeira) é a escolha inicial. `with_audio` valida o índice e produz a seleção; o ordinal de legenda é usado pelo filtro libass, enquanto o índice global é usado no map/overlay. O modo direto exige MP4 H.264 8-bit, perfil Baseline/Main/High, nível ≤4.1, até 1080p/30, AAC-LC mono/estéreo até 48 kHz ou sem áudio. Múltiplos áudios, mudança da faixa original, silêncio solicitado ou uma legenda selecionada exigem HLS. O teto de 12 Mb/s é uma política conservadora do MVP, não uma declaração de limite oficial do hardware. Entradas sem duração continuam reproduzíveis; seek é desativado.

`http_server.py` serve exclusivamente recursos registrados com token aleatório por sessão. Não expõe caminhos locais, listagem de pastas ou uploads. GET/HEAD suportam Range único, aberto e sufixo; múltiplos ranges são rejeitados com 416, sem multipart. OPTIONS e CORS habilitam o receiver. Playlists têm `no-store`; segmentos publicados pelo FFmpeg são imutáveis. `temp_file` impede servir segmentos parciais. O servidor escuta IPv4 em todas as interfaces; limite o acesso pelo firewall à LAN privada. Tokens reduzem exposição acidental, mas não equivalem a autenticação/HTTPS.

`transcoder.py` usa subprocesso sem shell. Arquivos com espaços/acentos são argumentos independentes. HLS: playlist mestre de uma variante, media playlist EVENT, TS muxado, segmentos de ~4 s, keyframes alinhados, High/4.1, VBV 6 Mb/s com buffer 12 Mb, AAC 192 kb/s. Aguarda pelo menos dois segmentos (~8 s), ou segmento único com ENDLIST num vídeo curto, antes do LOAD. A largura de banda de 7.5 Mb/s na playlist inclui margem. Não oferece ABR; 720p é uma escolha manual. A saída retém todos os segmentos até o fim da sessão, sem criar um MP4 intermediário.

`session.py` gerencia a propriedade dos recursos. MP4 usa Cast seek nativo; HLS usa `-ss` antes de `-i`, novo processo, diretório e URL a cada seek. Assim é possível pedir uma posição não convertida ainda. Durante a troca, o receiver perde a sessão e recebe outra; esse custo é aceito no MVP. O relógio da UI soma o offset da origem ao relógio relativo informado pelo receiver.

HLS em crescimento é carregado como `LIVE`, com `current_time=0`; ao terminar, FFmpeg publica ENDLIST. A TV pode mostrar duração/estado de live diferentes da UI. Essa combinação EVENT/LIVE precisa ser validada no Default Media Receiver do Chromecast 2 real. Se o mesmo MP4 direto funcionar e HLS falhar com HTTP 200, investigue formato do manifesto/segmento e comportamento do receiver antes de atribuir a falha à CPU ou ao MKV.

`paths.py` resolve ferramentas em variável de ambiente, `tools`, área do PyInstaller ou PATH, e mantém dados graváveis em `%LOCALAPPDATA%\LocalCastMVP`. `diagnostics.py` exporta um snapshot e mantém logs rotacionados. URLs de mídia com token não são incluídas no relatório exportado.

Na distribuição portátil, `runtime\python` contém Python oficial embeddable e dependências vendorizadas. O arquivo `python315._pth` usa caminhos relativos para a biblioteca padrão, `site-packages` e `src`, com isolamento dos pacotes globais. `iniciar.cmd` prefere esse runtime; não usa uma `.venv` copiada com caminhos absolutos. Os dados passam a `localcast-data` dentro da pasta, com a variável `LOCALCAST_DATA_DIR` disponível para sobrescrever o destino.

`preparar.cmd` apenas confere importações quando o runtime privado existe. No código-fonte sem Python, oferece baixar a distribuição privada fixada em `runtime-manifest.json`. `install-portable.ps1` confere hashes de Python/PyPI, extrai em uma pasta provisória curta, valida importações e só depois ativa `runtime\python`. Pip não é incluído no runtime embeddable. Desenvolvimento e PyInstaller continuam usando uma instalação completa de Python e `.venv` separada.

No Windows, o HTTP copia o conteúdo de playlists pequenas para memória e fecha o arquivo antes de enviar a resposta. Se FFmpeg registrar falha ao renomear `stream.m3u8.tmp`, o job tenta publicar esse arquivo concluído novamente, com prazo limitado; esse erro pode ocorrer mesmo com retorno 0 do FFmpeg. Vídeos e segmentos TS continuam sendo transmitidos do disco com Range.

## Modo Original e abertura sem console — versão 0.3

`PlaybackSession.start(original=True)` ignora a política conservadora, a opção Forçar HLS e a seleção de faixas, mantendo o `MediaInfo` do arquivo. Não cria `HlsJob`. HTTP registra exatamente o arquivo original: MP4 com `video/mp4`/`media.mp4`, MKV com `video/x-matroska`/`media.mkv`, ambos com Range. LOAD usa BUFFERED e seek usa o comando Cast. Uma rejeição preserva diagnóstico e não faz fallback oculto. A UI desabilita seletores de faixas e Forçar HLS; as seleções anteriores continuam disponíveis ao voltar a Automática. Mudanças do campo Conversão só entram em vigor ao Transmitir novamente.

`iniciar.cmd` inicia um helper PowerShell oculto que resolve o runtime e abre `pythonw.exe`; o helper termina depois da criação do processo. `ProcessStartInfo` trata o diretório literalmente (incluindo colchetes), usa argumentos com o caminho do script entre aspas e `CreateNoWindow`; a janela Qt continua visível. O servidor, controle Cast e FFmpeg pertencem ao processo Python, não ao terminal. `iniciar-debug.cmd` usa Python de console e aguarda a saída. Diagnóstico também usa console. `run_localcast.py` registra falhas de abertura e mostra um aviso no Windows quando não existe stderr. O fechamento continua passando por `PlaybackSession.close` para desconectar do Chromecast.

## Interface e informações de filmes — versão 0.1.0

`ui_layout.py` compõe os controles existentes e preserva seus nomes/callbacks; `ui_theme.py` aplica tema Fusion escuro, foco/estados e cantos arredondados. Seleção/seek continuam derivados dos widgets Qt nativos. A assinatura PNG original fica em `assets`, com fallback textual e `__author__` no código. Depuração apenas muda a visibilidade das mensagens/exportação; a coleta continua ativa.

`movie_info.py` contém queries/dados imutáveis, limpeza do nome, OMDb por HTTPS/urllib, respostas limitadas, mensagens sem chave, cache de sete dias e worker separado. A fila coalesce pedidos pendentes e sinais usam geração para rejeitar resultados antigos. O worker Cast não aguarda consultas de filmes. Imagens são bytes no worker e viram QPixmap na UI. `movie_panel.py` usa texto simples e configura/corrige identificação sem tocar no vídeo. Sem chave, nenhum pedido OMDb é enviado. Pacotes não incluem chaves/cache do usuário.

## Faixas embutidas e desconexão — versão 0.2

`subtitles.py` compõe a legenda no vídeo H.264. O filtro `subtitles`/libass lê a faixa de texto do próprio MKV, inclusive fontes ASS embutidas que o decoder conseguir usar. O caminho passa pelas duas camadas de escape do FFmpeg (opção e grafo), sem shell. Após `-ss`, o vídeo recebe o offset da origem antes do filtro e volta a timestamps relativos na saída. PGS/VobSub/DVB usam sub2video e `overlay` antes da escala; o decoder fornece transparência ao apagar uma legenda. As faixas desconhecidas são desabilitadas na UI. SRT, ASS e PGS foram testados com entrada real sintética, incluindo seek antes e dentro de uma fala; os outros formatos listados ainda precisam de amostras próprias.

`PlaybackSession.set_tracks` valida a seleção antes de interromper o vídeo, guarda posição absoluta e estado de pausa, revoga a URL/processo anteriores e cria a nova transmissão. `seek` mantém as mesmas faixas. Legendas incorporadas exigem conversão; desativá-las reinicia a sessão sem o filtro.

`stop` encerra a mídia e libera cache, mas mantém a propriedade do receiver para a próxima transmissão. `disconnect` e `close` executam stop, solicitam `Chromecast.quit_app(timeout=10)` e fecham descoberta, sockets e HTTP, inclusive se o quit falhar. A solicitação de quit só ocorre se o LocalCast iniciou a sessão e o app corrente ainda é `CC1AD845`. Aplicativos diferentes não recebem quit. Ao fechar a janela, a operação entra na mesma fila serial dos comandos anteriores; encerramento forçado não aciona esse fluxo.

## Evolução

SRT externo; WebVTT separado com seleção nativa no receiver; encoder NVENC/QSV com detecção e fallback; cache limitado com geração de segmentos solicitados; cancelamento imediato durante probe/LOAD; receiver customizado se o default não aceitar o fluxo esperado; instalador e assinatura; persistência de configurações. O suporte depende do caminho contêiner → codec → firmware/receiver → TV/HDMI, não da extensão do arquivo sozinha.

