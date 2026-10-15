# Registro histórico de desenvolvimento (antes da publicação)

Os números 0.1 a 0.5 abaixo eram internos. As condições e pendências descritas correspondem a cada etapa, não à versão pública atual. Consulte [a validação atual](../VALIDACAO.md).

# Validação executada — 14/10/2026

## Executável único da versão 0.5

O build foi executado no Windows com Python 3.15.0 privado, PyInstaller 6.22.3 e hooks 2026.8. **Sete testes específicos de GUI, launcher e caminhos do EXE passaram em 3,79 s**, incluindo persistência fora da extração temporária, reutilização de dados ao lado do EXE e localização de FFmpeg extraído.

O **EXE real** abriu a interface Qt e encerrou seus workers numa pasta que continha apenas esse arquivo, sem fonte/runtime/FFmpeg ao lado, com PATH limitado ao System32. Logo, ícone, tela de espera e dependências foram encontrados; FFmpeg e FFprobe executaram a partir da extração temporária. O relatório `--diagnose` funcionou sem console. O PE usa o subsistema GUI do Windows. O conflito de DLLs de outro software presente no PATH foi encontrado no teste inicial e corrigido antes da entrega. Nenhum teste conectou à TV. Consulte [EXECUTAVEL.md](../EXECUTAVEL.md).

As duas execuções do EXE passaram: Qt offscreen e janela nativa do Windows, com abertura/encerramento automático do teste e os mesmos recursos verificados. A captura da janela nativa está em [interface-executavel.png](../interface-executavel.png). Ela foi aberta sem dados/chave de filme no perfil isolado.

## Versão atual 0.5 — logo, montagem e espera no Chromecast

**73 testes passaram em 31,88 s no Python 3.15 portátil.** Incluem os fluxos anteriores de reprodução, HTTP, áudio/legenda, modo Original, abertura sem console e metadados, além da tela de espera. Os cinco testes novos verificam o transporte HTTP Range do vídeo estático, sua troca por filme e retorno após Parar, pausa após carregar, falha no carregamento/pause com liberação de recursos, imagem ausente sem interromper filme e codecs da mídia empacotada. O receptor foi simulado.

A nova mídia foi gerada e decodificada com FFmpeg/FFprobe: H.264 High 3.1, 1280×720, yuv420p limitado, 1 fps, 60 segundos, sem áudio, faststart e cerca de 826 KiB. O primeiro quadro decodificado foi conferido visualmente. Logo PNG com transparência e ICO em sete resoluções carregam no Qt. A GUI real foi capturada offscreen com a marca no cabeçalho e o botão Conectar; os workers encerraram. Ruff passou. O ícone está definido no projeto PyInstaller; a validação do EXE foi realizada na etapa descrita acima.

Após ajustar o espaço dos controles no cartão Chromecast, o teste de GUI passou novamente em 0,66 s e uma nova captura confirmou o botão Aplicar faixas visível na janela de referência 1120×880.

Nesta atualização houve consultas **reais** ao OMDb com a chave já salva pelo usuário no aplicativo: 24 fichas/capas foram obtidas para compor a montagem. A chave não foi mostrada, modificada ou incluída nas fontes/arte/pacotes. A consulta de nota Rotten Tomatoes e a escolha automática de título a partir de um arquivo real não foram o objetivo dessa verificação.

**Nenhuma transmissão de teste foi feita a uma TV ou Chromecast físico.** A permanência do quadro pausado, controles sobrepostos do receiver e a volta à tela ambiente precisam ser conferidos no aparelho. Consulte [TELA-DE-ESPERA.md](../TELA-DE-ESPERA.md).

## Histórico da versão 0.4 — visual, ficha e assinatura

**68 testes passaram em 29,47 s no Python 3.15 portátil**, incluindo mídia/HTTP/Cast anteriores e dez verificações de informações de filme. Após acabamento, quatro testes de GUI/launcher passaram em 3,66 s e dez testes de filmes em 0,25 s; não foi repetida a conversão após alterações apenas em interface/cache. Ruff passou.

A GUI foi capturada offscreen com depuração recolhida/aberta e ambos os workers encerraram. Foram verificados seletores/fluxos existentes, título/ano/ID, ausência de dados, cache sem chave no conteúdo, cota inválida, consulta não bloqueante, resultados antigos ignorados e configuração JSON corrompida. A assinatura fornecida tem transparência, foi copiada sem edição e conferida no canto inferior. O PyInstaller passou a incluir assets, mas não houve novo build .exe.

A consulta OMDb foi simulada; uma requisição HTTPS sem chave recebeu a rejeição de acesso prevista. **Não há chave real configurada: não foi obtida ficha/capa ao vivo nem confirmada a presença atual da nota Rotten Tomatoes.** Capturas demonstrativas têm dados fictícios explicitamente marcados. A reprodução mantém o código anterior; a nova apresentação ainda precisa ser conferida pelo usuário junto à TV. Consulte [FILMES-E-VISUAL.md](../FILMES-E-VISUAL.md).

## Histórico da versão 0.3 — Original e abertura sem terminal

**58 testes do aplicativo passaram na validação combinada com Python 3.15 privado:** os 55 testes de aplicativo/HTTP/conversão/faixas passaram na execução geral; os três testes de abertura passaram em 2,37 s após corrigir caminhos com colchetes no launcher. Não foi repetida a conversão depois dessa correção isolada do launcher.

O modo Original foi validado com MP4/MKV fora da política automática, recebendo bytes completos e parciais por HTTP, sem encoder e sem fallback após rejeição simulada. A escolha de faixas é bloqueada nesse modo. A GUI Qt offscreen foi aberta e fechada pelo launcher real em pasta com espaço, acento, colchetes e apóstrofo. Pythonw ficou sem console; o processo de GUI encerrou seu worker. A alternativa com console preservou os argumentos e também encerrou corretamente. Falha de abertura gerou log e aviso Windows simulado. O teste revelou que Push-Location e Start-Process podiam interpretar colchetes como curingas; o launcher usa localização literal e criação nativa de processo com diretório literal.

Captura da interface com a opção selecionada: [interface-original.png](../interface-original.png). Nenhum teste conectou a uma TV ou Chromecast físico. Reprodução original, inclusive uma possível rejeição de MKV/HEVC no Chromecast 2, permanece uma verificação do usuário.

## Histórico da versão 0.2 — áudio, legenda e desconexão

**52 testes do aplicativo passaram em 26,67 s usando o Python 3.15.0 privado da distribuição portátil**, com FFmpeg/FFprobe 9.0.2, PySide6-Essentials 6.12.0 e PyChromecast 14.0.10. Os quatro testes do instalador convencional também passaram na execução com Python completo 3.12 durante esta atualização. Ruff E4/E7/E9/F/I passou.

Além da conversão/HTTP/GUI já cobertos, a validação atual verificou:

- MKV sintético original com dois áudios de idiomas distintos e SRT, ASS e PGS embutidas. A frequência do áudio decodificado confirma a segunda faixa, em vez de somente conferir o map do comando.
- Legenda ausente antes, presente durante e apagada depois da fala, conferindo pixels do HLS decodificado. Seek para 3 s (dentro de uma fala) e 6 s (antes da próxima), mantendo áudio e sincronismo.
- Arquivo com acento, espaço, colchetes, apóstrofo e vírgula no nome; caminho escapado sem shell.
- Troca de faixas na posição atual, restauração de pausa, desativação de legenda/áudio e preservação da seleção no próximo seek. Índices inválidos são rejeitados antes de interromper a sessão ativa.
- Quit do receiver simulado ao Desconectar e ao fechar, inclusive depois de Parar. Falha de quit ainda libera servidor e conexões locais; aplicativos Cast diferentes não recebem quit.
- Campos de áudio/legenda na GUI, formatos desconhecidos desabilitados, estado do botão Aplicar faixas e encerramento do worker. Captura da interface real Qt em modo offscreen: [interface-faixas.png](../interface-faixas.png). O plugin offscreen não descobre fontes do Windows; a captura carregou Segoe UI instalada, sem mudar a fonte do aplicativo.

O usuário relatou que a versão anterior do LocalCast funcionou perfeitamente. Esse é um relato de uso, sem detalhes por arquivo/codec; não é um teste físico realizado pelo agente. **Áudio/legendas e desconexão da versão 0.2 ainda precisam de confirmação na TV.** VobSub/DVD, DVB e outros formatos de texto listados na interface não tiveram amostras específicas nesta rodada. A nova validação não realizou descoberta nem transmissão a um aparelho real.

## Histórico da primeira versão

O registro abaixo documenta as etapas anteriores. Os resultados atuais são os da versão 0.4 acima.

**Resultado inicial: 37 testes passaram em 17,41 s**, executados localmente no Windows. Nenhum Chromecast foi buscado, conectado ou usado durante essa validação inicial.

Ambiente de teste:

- Python 3.12.14 x64, Windows 11.
- PySide6 6.12.0 e PyChromecast 14.0.10 (versões fixadas nas dependências).
- FFmpeg/FFprobe 9.0.2, build Windows essentials de gyan.dev, indicado pela página de downloads do FFmpeg.
- pytest 9.1.1.
- Dependências instaladas numa pasta de teste isolada do projeto. A execução usa Python fornecido no ambiente de trabalho; isso não elimina a necessidade de instalar Python/FFmpeg seguindo o README em outra máquina.

Verificações concluídas:

| Área | Verificação |
|---|---|
| HTTP real em loopback | GET/HEAD/OPTIONS, 200/206/416, Content-Length/Content-Range, ranges abertos/sufixo, CORS |
| Acesso a arquivos | Nome com acentos/espaços, token revogado, bloqueio de traversal, arquivos privados e `.tmp` |
| Concorrência | Oito leituras de Range simultâneas; arquivo vazio |
| Compatibilidade | MP4 elegível; MKV/HEVC/EAC3/10-bit/HDR/resolução/fps incompatíveis acionam conversão |
| Análise | Ignora capa e seleciona faixa padrão; duração e fps com valores ausentes |
| Cast simulado | LOAD com MIME e streamType, posição inicial zero; LOAD_FAILED propagado; listener antigo ignorado |
| Sessão simulada | Seek HLS reinicia no offset, revoga URL anterior, restaura pausa e limpa recursos; falha de LOAD preserva diagnóstico |
| Conversão real MP4 | HLS EVENT/ENDLIST, MPEG-TS, H.264 nível ≤4.1 e AAC estéreo |
| Conversão real MKV | Entrada HEVC + EAC3 5.1 → saída H.264 + AAC estéreo |
| Conversão real 4K | Entrada HEVC 3840×2160/EAC3 → saída ≤1920×1080 |
| Conversão HDR sintética | HEVC 10-bit BT.2020/PQ passa por zscale/tonemap e gera H.264 yuv420p |
| HLS local | Manifesto/segmentos obtidos por HTTP; FFprobe confere faixas; FFmpeg decodifica playlist completa sem erro |
| GUI | Janela PySide6 inicializa em modo offscreen; botão MP4/MKV; encerramento assíncrono termina o worker |
| Diagnóstico | `python -m localcast --diagnose` concluiu com código 0; FFmpeg e FFprobe `ok: true` |
| Scripts | Cinco scripts PowerShell analisados pelo parser, sem erro de sintaxe |
| Código | Ruff (E4/E7/E9/F/I) passou; formatação aplicada |

Tentativas iniciais no ambiente restrito falharam por bloqueio de diretório temporário e de sockets loopback. Os testes foram executados novamente com diretório temporário no workspace e permissão de rede local; o resultado final acima é dessa execução. Os erros iniciais eram restrições do ambiente de teste, não foram contados como sucesso nem omitidos como testes de TV.

**Ainda não verificado:** descoberta mDNS numa LAN real, firewall do usuário, LOAD no receiver físico, aceitação do HLS EVENT/LIVE pelo firmware do Chromecast 2, imagem/som na TV, desempenho e sincronismo em um filme longo, HDR real/Dolby Vision, geração e execução do `.exe` por PyInstaller, instalação em um Windows limpo.

Os testes de codecs e HLS são locais e usam vídeos sintéticos curtos. Não são certificação Google Cast. Play/pause/seek de TV e compatibilidade de receiver devem ser preenchidos em [TESTES.md](../TESTES.md). Na primeira versão, SRT permanecia uma etapa futura; a versão 0.2 implementou as legendas embutidas descritas acima.

## Correção do preparar.cmd — 14/10/2026

A primeira versão exigia o launcher `py` e selecionava Python 3.11 especificamente. Após o erro relatado no Windows do usuário, a preparação passou a detectar Python 3.11+ 64 bits no PATH, registro, pastas convencionais e, como alternativa, launcher existente. Atalhos WindowsApps não são executados. Um caminho explícito continua disponível por `-Python`; `-CheckOnly` verifica a detecção sem instalar dependências.

**Quatro testes adicionais do instalador passaram em 1,85 s**: caminho explícito válido sem launcher, caminho ausente com mensagem útil, rejeição de atalho da Store e descoberta em pasta convencional fora do PATH. Seis scripts PowerShell passaram na análise de sintaxe. A cópia `Desktop\LocalCast` recebeu os três arquivos de preparação corrigidos, com backup dos arquivos substituídos.

A verificação automática nessa etapa confirmou que nenhum Python convencional utilizável foi encontrado. A mensagem corrigida solicitava a instalação do Python, em vez de exibir `CommandNotFoundException`. A etapa seguinte resolveu isso com o runtime privado na própria pasta; o modo `-CheckOnly` não instala nada. Os quatro testes do instalador eram adicionais aos 37 testes do aplicativo, sem repetição de testes de TV.

## Distribuição portátil — 14/10/2026

Foi montado um runtime privado com **Python 3.15.0 x64**, embeddable do site oficial, mais 12 pacotes do PyPI. O SHA256 do Python e os hashes de todos os wheels foram confrontados com os metadados publicados pelos fornecedores. A distribuição inclui as licenças fornecidas nos pacotes. PySide6-Essentials 6.12.0 fornece os módulos Qt usados pelo app; não há pip ou instalação global na versão portátil.

**39 testes do aplicativo passaram em 16,77 s usando esse Python 3.15 privado**, incluindo GUI offscreen, HTTP Range, contrato Cast simulado, conversão real de MP4/MKV/HEVC4K/EAC3/HDR, limpeza e duas regressões de leitura/publicação de playlists. **Os quatro testes do instalador convencional também passaram**, em 2,74 s, com o Python completo de testes 3.12.

A validação revelou que o Windows podia bloquear o rename de uma playlist aberta e o FFmpeg podia finalizar com retorno 0 sem publicar ENDLIST. O servidor agora fecha o snapshot de playlists antes da resposta HTTP e o job recupera a publicação do arquivo `.tmp` concluído com retries limitados. A regressão simula um bloqueio real de arquivo e verifica a publicação após liberar o leitor. A repetição da integração confirmou ENDLIST e decodificação das quatro amostras.

A pasta inteira foi movida para outro caminho com espaços, mantendo `._pth` relativo. O diagnóstico confirmou Python/Qt/Cast e FFmpeg/FFprobe locais, com PATH sem Python e PYTHONPATH apontando para um caminho inexistente. Uma janela Qt foi criada e encerrada offscreen na pasta movida. Logs e cache foram direcionados a `localcast-data` nessa pasta. Os atalhos `.cmd` usam o caminho nativo do Windows PowerShell, sem depender da presença dele no PATH.

Isso valida independência de Python global nesta máquina; não equivale a testes em todos os Windows, em um pendrive ou no Chromecast físico. Nenhuma descoberta ou transmissão real à TV foi feita. A versão completa portátil permite abrir `iniciar.cmd` diretamente; `preparar.cmd` passa a conferir os arquivos locais. Sem runtime e sem Python completo, oferece baixar/preparar o runtime privado a partir do manifesto fixado.

