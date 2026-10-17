# LocalCast 0.2.0 — instalador, retomada e dados locais

Esta documentação descreve a base 0.2.0. Veja também a
[atualização 01](PATCH-0.2.0-01.md), com volume, arraste visual, janela maior,
retorno à imagem de espera e patch para a instalação existente, e a
[atualização 02](PATCH-0.2.0-02.md), que corrige o progresso salvo.

Download público: [release 0.2.0](https://github.com/fagnerlemes/LocalCast/releases/tag/v0.2.0).
O instalador `LocalCast-Setup-0.2.0-patch02.exe` já inclui os dois patches.
O nome `LocalCast-Setup-0.2.0.exe` abaixo é o nome produzido pelo script de build.

By Fagner Lemes. Desenvolvido em cópia da 0.1.1, commit
`c8dd0cf793a5ecd6e4173d11e6cdbf91006e54ad`, branch `feature/resume-playback`.
A versão 0.1.0 publicada e as pastas anteriores permanecem independentes.

## Instalar e atualizar

Execute `LocalCast-Setup-0.2.0.exe`. O instalador é por usuário, para Windows
x64, e inclui Python, Qt, FFmpeg/FFprobe e recursos visuais. Cria um atalho no
menu Iniciar; o atalho na área de trabalho é opcional. Fecha-se o LocalCast
antes de atualizar. O aplicativo instalado usa os componentes da pasta,
sem extrair o pacote inteiro a cada abertura.

Local padrão: `%LOCALAPPDATA%\Programs\LocalCast`. Para abrir, use o atalho.
O executável dentro da instalação depende da pasta `_internal`; mova a pasta
completa se utilizar a distribuição ZIP. Não distribua apenas esse EXE.

Histórico, configurações, logs e caches ficam em `%LOCALAPPDATA%\LocalCast`.
Atualizar/reinstalar ou mover a pasta do programa preserva esses dados no mesmo
usuário do Windows. A desinstalação também preserva os dados. Para apagá-los,
use a restauração de fábrica antes de desinstalar.

O código-fonte é separado do programa instalado. `iniciar.cmd` usa o perfil
isolado `localcast-dev-data` da pasta de desenvolvimento. `LOCALCAST_DATA_DIR`
continua disponível como override explícito. Uma segunda instância não pode
abrir simultaneamente o mesmo perfil. A porta padrão desta versão é **8767**.

## Continuar um filme

Abra ou arraste um MP4/MKV. Se houver progresso salvo entre 30 segundos e o
limite de conclusão, aparecem a barra discreta, o horário e **Continuar**.
O botão ↺ tem tooltip **Começar do início**. Arquivo novo usa **Reproduzir**;
arquivo concluído usa **Assistir novamente**.

O ponto é registrado aproximadamente a cada dez segundos, a partir de amostras
recentes confirmadas pelo Chromecast. Pausar, parar, desconectar e fechar
salvam o último ponto válido. Buffering, tela de espera, status antigo e
estimativa do relógio local não avançam o registro. Em queda de energia ou
encerramento forçado, permanece o último checkpoint concluído; não se promete
recuperar exatamente o último segundo visto.

MP4 direto/Original pede a posição no LOAD; se necessário, tenta seek quando
o receiver declara suporte. HLS começa o FFmpeg no trecho salvo e soma esse
offset ao tempo confirmado do receiver. A reserva GPU de 90/45 s continua
relativa ao trecho novo. A aceitação e precisão real dependem do receiver.
Uma retomada não confirmada mostra erro e preserva o ponto anterior.

Um filme é concluído em 95%. Em vídeos de pelo menos 20 minutos, também vale
ter menos de três minutos restantes. Vídeos menores usam somente 95%, evitando
conclusão imediata em clipes curtos. Duração desconhecida não oferece retomada.

A identidade é derivada do caminho normalizado, tamanho e modificação em
nanosegundos quando disponível. Mesmo nome em pastas diferentes não compartilha
progresso. Mover, renomear ou modificar o arquivo cria outra identidade. Não há
fingerprint do conteúdo nem biblioteca de mídia nesta versão.

## Configurações, importação e privacidade

**Configurações → Informações dos filmes / OMDb** mantém os controles da fonte.
**Importar configuração anterior** permite escolher explicitamente o
`movie-settings.json` dentro de `localcast-data` da versão antiga. Importa apenas
a chave e a preferência de consulta automática; a origem é preservada. Não há
importação automática nem reaplicação depois de restaurar padrões.

**Armazenamento e privacidade** mostra o local dos dados, contagem do histórico
e tamanho de cada categoria. Todas as limpezas exigem confirmação e permitem
cancelar sem alterações:

- **Histórico:** remove registros e posições, preserva configuração OMDb.
- **Logs antigos:** preserva o log aberto na sessão atual.
- **Cache inativo:** remove capas/metadados e sessões HLS comprovadamente inativas.
- **Restaurar padrões:** remove histórico, configuração OMDb e dados descartáveis;
  redefine os controles. Um log novo pode ser criado para a execução atual.

Histórico e restauração exigem encerrar a reprodução/espera. Cache ativo nunca
é removido. Caches desconhecidos de versões antigas, arquivos bloqueados,
links/junções e conteúdo não reconhecido são preservados e a limpeza informa
o que não foi removido. Vídeos originais, executável e relatórios exportados
manualmente para outras pastas ficam fora da limpeza. A remoção lógica não é
um mecanismo de apagamento forense nem apaga backups externos.

## Arquitetura e limites

`history.py` contém SQLite transacional, identidade e política dos checkpoints.
`PlaybackSession` coordena um observador de status, independente da animação
do relógio da interface. Cada LOAD usa URL própria; serial/frescor e conteúdo
confirmado impedem eventos antigos de alterar a sessão atual.

`storage.py` limita limpeza a nomes/diretórios gerenciados, recusa reparse points
e usa marcadores com PID/data de criação para reconhecer caches. As consultas
de filme têm geração de gravação, bloqueando respostas antigas depois da limpeza.
`settings_panel.py` é uma janela não modal, com confirmações destrutivas.

`process_guard.py` usa Job Object Windows com kill-on-close: inicia o FFmpeg
suspenso, associa o filho ao job e o libera. Ao terminar o processo pai, o Windows
encerra seus filhos associados, inclusive se estavam descansando. Isso não
equivale a desconectar a TV após um crash: sem o app, o receiver pode permanecer
aberto até ser encerrado por outro comando/aplicativo.

Um banco indisponível preserva o arquivo e apresenta diagnóstico; a reprodução
continua disponível. A restauração explícita pode recriar um banco danificado.
Preferências de conversão continuam sendo ajustes da sessão; a configuração
OMDb e o histórico são persistentes.

Os limites de codecs, HDR, legendas e GPU permanecem descritos em
[DESENVOLVIMENTO-0.1.1.md](DESENVOLVIMENTO-0.1.1.md). Esta versão não acrescenta
saída 4K nem receiver próprio. **Nenhum teste físico no Chromecast é alegado.**

## Teste no Chromecast de 2ª geração

1. Feche a versão anterior. Instale a 0.2.0 e abra pelo atalho.
2. Reproduza MP4 H.264/AAC direto por pelo menos um minuto. Pause, desconecte e feche.
3. Abra novamente o mesmo arquivo: confira o horário e clique Continuar.
4. Repita com MKV HEVC/EAC3, GPU automática, áudio/legenda selecionados e reserva 90 s.
5. Avance para um trecho ainda não convertido; pause, feche e retome de novo.
6. Use Começar do início; depois feche e confirme que não reaparece o ponto antigo.
7. Teste arquivo homônimo em outra pasta e um vídeo curto. Teste a regra de conclusão.
8. Durante transmissão, limpe cache: confirme que o vídeo e a reserva continuam.
9. Desconecte, cancele uma limpeza e confira que nada mudou; depois confirme Limpar histórico.
10. Registre se áudio/legenda sincronizam após retomar e se há buffering. Exporte diagnóstico
    em Depuração se ocorrer falha; não publique o banco pessoal nem a chave OMDb.

## Interface

As skills `design-taste-frontend` e `emil-design-eng` foram consultadas. A primeira
exclui telas de app; manteve-se a identidade Qt, com foco/teclado e estados claros.

| Antes | Depois | Motivo |
|---|---|---|
| Transmitir sempre igual | Reproduzir / Continuar / Assistir novamente | A ação reflete o progresso salvo |
| Sem progresso persistente | Linha e barra discretas no cartão Arquivo | Contexto antes de iniciar |
| Sem reinício dedicado | Botão ↺ com tooltip e nome acessível | Alternativa ao ponto salvo |
| Configuração apenas de filmes | Configurações com armazenamento separado | Limpeza compreensível e confirmada |

Captura da UI real em cenário demonstrativo, sem receiver conectado:
[janela compacta](interface-compacta-0.2.0.png).
