# LocalCast 0.2.0 — atualização 02

By Fagner Lemes. Mantém a versão **0.2.0**, com identificação interna `020-patch02`.

## Correção do progresso salvo

O painel Arquivo mantinha o ponto carregado ao abrir/iniciar o vídeo. O histórico
continuava recebendo gravações, mas o painel não o consultava durante a reprodução.
O botão Continuar utilizava essa cópia antiga e podia recarregar o mesmo filme dali.

- A interface consulta o histórico a cada cinco segundos, em segundo plano, sem
  bloquear o player. Mostra o ponto efetivamente gravado, não uma estimativa do relógio.
- Na transmissão do mesmo arquivo para o mesmo aparelho, o botão principal mostra
  **Em reprodução** e fica desativado, inclusive em pausa. Use Play/Pause para
  controlar a sessão e Ir para/barra inferior para mudar a posição.
  Para mudar conversão ou qualidade, pare e transmita novamente; a seleção de
  áudio/legenda durante a reprodução continua no botão Aplicar faixas.
- A proteção também vale para chamadas diretas do comando; o botão de recomeçar
  continua explícito e disponível quando há progresso salvo.
- Uma nova transmissão lê o banco novamente imediatamente antes de iniciar.
  Uma cópia antiga do texto da interface não determina a posição de retomada.
- Respostas atrasadas de outro arquivo ou anteriores à limpeza do histórico são
  descartadas. Falha de leitura em segundo plano não interrompe a reprodução.

A gravação continua usando posições confirmadas pelo Chromecast, normalmente em
intervalos de dez segundos, além de pausas/paradas. Portanto uma pequena diferença
entre a barra de reprodução e a barra salva é esperada. A regra anterior de marcar
como concluído a partir de 95%, ou nos últimos três minutos de filmes longos, foi
mantida. Agora esse estado também conserva a indicação visual do último ponto salvo.

## Instalação

1. Feche o LocalCast e aguarde o encerramento.
2. Execute **LocalCast-Patch-0.2.0-02.exe**.
3. Confira a pasta da instalação e conclua. Abra pelo atalho habitual.

Este patch é para a **0.2.0 com atualização 01 já aplicada**; também aceita sua própria
reaplicação. Não desinstale antes. Histórico, chave OMDb e configurações são preservados.
Se o patch recusar a base, use `LocalCast-Setup-0.2.0-patch02.exe`, escolhendo a
mesma pasta de instalação. No pacote local ele está em `instalador-completo`.
Os dois instaladores também estão na [release 0.2.0](https://github.com/fagnerlemes/LocalCast/releases/tag/v0.2.0).

O código editável está neste repositório e, na entrega local, em `codigo-fonte`
na pasta principal do projeto. Os pacotes anteriores foram preservados.
Os manifestos de build registram a validação e a entrega local originais;
a publicação posterior está descrita nas notas da release.

## Validação

- 128 testes automatizados aprovados; 18 testes de conversão não repetidos porque
  o pipeline de FFmpeg não mudou.
- O teste Qt reproduz painel antigo e banco avançado, acompanha a leitura real
  assíncrona, verifica a barra e impede recarregamento acidental em play e pause.
- Verifica retomada a partir do registro mais recente, reinício explícito, seleção
  de outro arquivo, limpeza de histórico, conclusão e falha de consulta.
- Atualização, reaplicação, validação de base e desinstalação verificadas numa pasta
  isolada, preservando dados sintéticos. A instalação em uso não foi modificada.
- Sem comandos enviados à TV e sem teste físico de reprodução nesta correção.

## Teste no seu aparelho

1. Reproduza um filme com ponto salvo. O botão deve mostrar Em reprodução.
2. Aguarde de 10 a 20 segundos. Confira a atualização de Progresso salvo.
3. Pause, avance para outro ponto e aguarde a confirmação do Chromecast.
4. Pare, feche e reabra o programa. Abra o mesmo arquivo e confira Continuar.
5. Use o botão de recomeçar somente quando quiser voltar ao início.

Para gerar novamente: `gerar-patch.cmd`, ou `scripts/installer.ps1 -SkipBuild -Patch`
após compilar a pasta. O padrão é a atualização 02, baseada em
`installer/base-0.2.0-patch01.json`. O instalador completo continua sendo gerado por
`gerar-instalador.cmd`.

## Revisão da interação

As skills design-taste-frontend e emil-design-eng foram consultadas. A primeira
exclui telas de aplicativos; foram aplicados os princípios de estado e feedback
da segunda, preservando o visual existente e sem animações adicionais.

| Before | After | Why |
|---|---|---|
| Ponto carregado uma vez | Consulta periódica do registro salvo | O painel reflete a persistência real |
| Continuar podia recarregar a sessão ativa | Em reprodução, desativado para o mesmo filme/aparelho | Evita voltar acidentalmente a um ponto antigo |
| Nova sessão usava a cópia do painel | Consulta ao banco no momento do comando | Retomada usa o dado mais recente |
