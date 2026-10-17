# Changelog

A [release 0.2.0](https://github.com/fagnerlemes/LocalCast/releases/tag/v0.2.0) reúne a base instalável e as atualizações 01 e 02. A numeração do aplicativo permanece 0.2.0.

## 0.2.0 — atualização 02 — 2026-10-16 (incluída no pré-lançamento)

- Painel de progresso salvo atualizado em segundo plano durante a reprodução.
- Continuar protegido contra recarregamento do mesmo filme na sessão ativa.
- Nova transmissão consulta o ponto persistido mais recente no momento do comando.
- Patch para a instalação 0.2.0 com atualização 01; dados pessoais preservados.

Veja o [guia da correção](docs/PATCH-0.2.0-02.md).

## 0.2.0 — atualização 01 — 2026-10-16 (incluída no pré-lançamento)

- Volume próprio do Chromecast de 0 a 100%, com sincronização do estado do aparelho.
- Aviso discreto e destaque na caixa Arquivo ao arrastar um MP4/MKV válido.
- Altura inicial de até 980 px, respeitando a área disponível do monitor.
- Retorno à espera após Parar com reconexão, JPEG estático e alternativa em vídeo.
- Capa OMDb já carregada e título identificado nos metadados Cast, com duração total
  como texto adicional. HLS em conversão continua LIVE; a barra da TV não foi alterada.
- Patch pequeno com validação da instalação e preservação de dados/desinstalador.
- Versão pública permanece 0.2.0; identificador interno `020-patch01`.

Veja o [guia da atualização](docs/PATCH-0.2.0-01.md).

## 0.2.0 — 2026-10-16 (base incluída no pré-lançamento)

- Instalador Windows por usuário, componentes em pasta e dados estáveis em LocalAppData.
- Histórico SQLite, retomada, reinício, conclusão e arrastar/soltar MP4/MKV.
- Armazenamento e privacidade, com confirmação e proteção de arquivos em uso.
- Importação explícita de configuração OMDb e proteção de processos FFmpeg em crashes.
- Mantém GPU, fallback, reserva e seleção de áudio/legendas da 0.1.1.

Veja o [guia da versão](docs/VERSAO-0.2.0.md).


## 0.1.1 — desenvolvimento local — 15/10/2026

- GPU automática: NVIDIA NVENC/CUDA, com alternativas Intel QSV, AMD AMF e CPU.
- Reserva de conversão adiantada de 30 a 300 s; padrão 90 s, retomada em 45 s.
- Descanso do processo FFmpeg próprio, sem limitar a CPU a uma porcentagem fixa.
- Diagnóstico do encoder real, fallback e reserva; pausa, seek e faixas preservados.
- Porta 8766 e perfil isolado da versão estável. Recursos incorporados à publicação 0.2.0; sem release 0.1.1 separada.

Detalhes em [DESENVOLVIMENTO-0.1.1.md](docs/DESENVOLVIMENTO-0.1.1.md).

## 0.1.0 — primeira versão pública — 14/10/2026

By Fagner Lemes.

- MP4/MKV no Chromecast via Default Media Receiver e HTTP com Range.
- Conversão HLS durante a reprodução, HEVC 4K/EAC3 para H.264 até 1080p/AAC estéreo.
- Áudio e legendas embutidas selecionáveis, inclusive durante a reprodução.
- Play, pausa, seek, Parar com retorno à espera e Desconectar.
- Modo Original, sem conversão e sem fallback automático.
- Interface escura, logo, assinatura, ficha OMDb e depuração recolhida.
- EXE único Windows x64, fonte editável e scripts de preparação/build.
- Documentação, testes locais, instruções Windows e licença MIT para o código.

Esta versão consolida o desenvolvimento anterior. Identificadores internos
0.1 a 0.5 anteriores à publicação não representam releases públicas.

### Limites conhecidos

- HLS e comandos Cast exigem validação no receiver/firmware real.
- Filmes longos dependem de CPU, rede e espaço para segmentos.
- Original pode falhar com MKV/HEVC/EAC3 no Chromecast 2.
- SRT externo ainda não tem seleção na interface; legendas embutidas são
  incorporadas ao vídeo durante a conversão.
- Dados/notas dependem do que o OMDb fornecer.
- Os testes locais não certificam reprodução física na TV.
