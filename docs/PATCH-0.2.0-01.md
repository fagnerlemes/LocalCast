# LocalCast 0.2.0 — atualização 01

By Fagner Lemes. A versão permanece **0.2.0**. O identificador interno
`020-patch01`, visível no diagnóstico, distingue esta compilação da original.

## Instalar o patch

1. Feche o LocalCast pelo X e aguarde o encerramento.
2. Execute **LocalCast-Patch-0.2.0-01.exe**.
3. Confira a pasta da instalação. O padrão é
   `%LOCALAPPDATA%\Programs\LocalCast`; se instalou em outro lugar, selecione-o.
4. Aplique a atualização e abra pelo mesmo atalho.

Não é necessário desinstalar. O patch substitui apenas arquivos modificados,
confere os hashes de todos os componentes esperados e preserva o desinstalador
original. Histórico, chave OMDb, configurações e vídeos não fazem parte do patch.
Pode ser reaplicado à mesma instalação já atualizada. Uma instalação incompleta
ou diferente é recusada antes da cópia: nesse caso use o instalador completo
atualizado **LocalCast-Setup-0.2.0-patch01.exe**, na mesma pasta da entrega.

O patch é específico para a distribuição instalável 0.2.0 original e esta
atualização. Não se aplica ao executável único das versões 0.1.x. Não usa
diferenças binárias internas: distribui os arquivos inteiros que mudaram, sem
reenviar os componentes idênticos de Python, Qt e FFmpeg. Não cria um segundo
item para desinstalar e não altera o perfil pessoal.

## Mudanças

- **Volume de 0 a 100%** no rodapé do player. Controla o volume do Chromecast,
  acompanha alterações recebidas do aparelho e aceita mouse ou setas do teclado.
  Fica desativado quando desconectado. Aumentar um receiver em mudo também o
  desmuta. Comandos rápidos são agrupados e nunca são transferidos a outro aparelho.
- Texto discreto **ou arraste e solte**, ao lado de Abrir MP4 / MKV.
- Ao arrastar um vídeo local válido, a caixa Arquivo destaca **Solte aqui para
  abrir o vídeo**. Sair, cancelar ou soltar remove o destaque. A seleção continua
  limitada a um arquivo MP4/MKV; URLs e múltiplos arquivos não são aceitos.
- Janela padrão **1120 × 980**, limitada à área disponível do monitor. Em telas
  menores ou com painéis extras abertos a rolagem continua disponível para manter
  os controles acessíveis. Não é obrigatório maximizar a janela.
- **Parar** tenta voltar à arte de espera mesmo quando a conexão aparece
  momentaneamente indisponível; faz um STOP e depois reconecta/carrega. Falhas
  são apresentadas, em vez de simplesmente pular o carregamento.
- A espera tenta primeiro a arte **JPEG 1280 × 720** via HTTP LAN, com metadados
  de foto e stream NONE. Não exige conversão FFmpeg. Se o receiver rejeitar ou
  não confirmar em dez segundos, tenta o vídeo silencioso já existente e pausa-o.
  O diagnóstico informa `standby_format`: `image` ou `video-fallback`.
- **Capa e título nos controles Cast:** ao transmitir, usa os dados já carregados
  no painel Sobre o filme. Sem consulta, limpa o título a partir do nome do arquivo.
  A capa JPEG/PNG é servida na própria rede local, sem enviar a chave OMDb ao Cast;
  permanece disponível durante seek/troca de faixas e é liberada ao parar.
  A aparência final depende do Google Home/receiver. Aguarde a capa aparecer no
  LocalCast antes de iniciar; uma consulta concluída depois não interrompe nem
  recarrega o filme. Sem capa válida, a reprodução segue normalmente. Não há
  extração automática de frames nesta atualização.
- **Duração total:** envia o texto `Duração total: HH:MM:SS` nos metadados, para
  controles que exibem o subtítulo. Em reprodução direta também envia a duração
  numérica. Na conversão HLS, a barra da TV **ainda pode mostrar LIVE**.

O app continua usando o Default Media Receiver. O suporte geral do Google Cast
a JPEG/PNG e o limite recomendado de 1280 × 720 estão na
[documentação de mídia](https://developers.google.com/cast/docs/media#image_formats).
A aparência, os controles sobrepostos e a permanência da foto dependem do
receiver. Esta atualização usa foto para a espera; o seletor de filmes continua
MP4/MKV. **Desconectar** e fechar continuam encerrando a sessão, sem deixar a arte.

### Por que a barra da TV mostra LIVE?

A conversão publica uma playlist HLS EVENT crescente, e o Cast a recebe como LIVE.
O Google documenta que seu player usa a presença de `EXT-X-ENDLIST` para distinguir
um HLS concluído de um fluxo em andamento. Colocar esse marcador antes de terminar
ou apenas mudar para BUFFERED não oferece uma linha do tempo completa confiável.
Esta atualização preserva o fluxo funcional e mostra a duração no texto adicional,
quando o controle o utiliza. Esse texto é a duração total, não uma contagem regressiva.
O LocalCast no PC continua mostrando a posição e a duração completas.

Para substituir LIVE por uma barra completa durante a conversão, seria necessário
desenvolver e validar outro modo de servir o conteúdo sob demanda ou um receiver
próprio. Não foi implementado neste patch e não é necessário converter tudo antes
para continuar usando o modo atual.

Referências oficiais: [HLS no Cast](https://developers.google.com/cast/docs/media/streaming_protocols),
[metadados de filme](https://developers.google.com/cast/docs/reference/web_receiver/cast.framework.messages.MovieMediaMetadata).

## Validação e teste na TV

Foram aprovados **127 testes automatizados** de regressão, incluindo HTTP,
histórico, volume com receiver simulado, arraste, tamanho da janela, retorno da
espera, alternativa em vídeo e validação do manifesto do patch. Os 18 testes de
conversão foram excluídos desta rodada: os codecs e a geração FFmpeg não mudaram.
O pacote anterior já possuía testes sintéticos de CPU/GPU registrados na documentação.
Também foram verificados capa por HTTP, revogação da URL, manutenção da capa durante
seek/troca de faixas e contrato de metadados/duração sem alterar o modo HLS.

Uma instalação de teste isolada passou por atualização, reaplicação e desinstalação
com o desinstalador original. Histórico SQLite e configuração OMDb sintéticos foram
preservados. O patch recusou instalação ausente, arquivo incompatível e app em
execução antes de copiar os arquivos. O EXE atualizado abriu usando o Python/Qt e
FFmpeg empacotados. A instalação real do usuário não foi alterada.

A interface foi conferida no Qt com dados demonstrativos. A 1120 × 980, a coluna de controles
ficou sem rolagem no cenário verificado. Não houve controle da TV nos testes.

Roteiro no seu Chromecast:

1. Confira o tamanho ao abrir e o aviso ao arrastar um MKV.
2. Conecte, ajuste o volume e confira o nível no aparelho.
3. Reproduza um filme e clique Parar. Confira o retorno da arte.
4. Repita começando diretamente pelo filme, sem conectar antes à espera.
5. Confira se o histórico continua oferecendo Continuar.
6. Em Depuração → Salvar diagnóstico, consulte `standby_format` caso queira saber
   se o aparelho aceitou a imagem ou utilizou a alternativa em vídeo.
7. Aguarde a capa aparecer no app, transmita e abra Tocando agora no celular.
   Confira título e capa; `artwork.available` e `artwork.http` no diagnóstico ajudam
   a distinguir capa ausente de ausência de requisição do receiver/controle.
8. Confira a duração no texto adicional, se exibido. Em HLS, LIVE na barra ainda
   é esperado. Compare com MP4 H.264/AAC direto, que possui uma duração finita.

## Desenvolvimento

As instruções desta seção descrevem o código da atualização 01, preservado no
ZIP daquela entrega. No fonte atual, `gerar-patch.cmd` gera a
[atualização 02](PATCH-0.2.0-02.md).

`gerar-patch.cmd` recompila a pasta e prepara o patch usando
`installer/base-0.2.0.json`. Para usar uma pasta já compilada:
`scripts/installer.ps1 -SkipBuild -Patch`. Se houver arquivos adicionados ou
removidos da distribuição, a geração recusa o patch e pede o instalador completo.
`gerar-instalador.cmd` continua criando o instalador completo.

As duas skills de design foram consultadas. `design-taste-frontend` exclui telas
de aplicativos; aplicaram-se os princípios pertinentes de `emil-design-eng`,
preservando o tema existente e sem animações decorativas.

| Before | After | Why |
|---|---|---|
| Sem volume no player | Slider compacto com percentual e foco visível | Ajuste do receiver sem sair do app |
| Arraste sem indicação visual | Texto auxiliar e destaque durante arraste válido | Feedback imediato sem botão redundante |
| Altura inicial de 860 | Até 980, respeitando a tela | Enquadramento semelhante à referência |
