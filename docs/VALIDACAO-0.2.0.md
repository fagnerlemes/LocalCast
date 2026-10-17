# Validação local — LocalCast 0.2.0

Data: 16/10/2026. Base: 0.1.1, commit
`c8dd0cf793a5ecd6e4173d11e6cdbf91006e54ad`. Trabalho local na branch
`feature/resume-playback`, sem publicação de release.

## Resultados

| Verificação | Resultado |
|---|---|
| Suíte automatizada completa | **131 testes aprovados em 97,28 s** |
| Análise estática Ruff (E4, E7, E9, F, I) | Aprovada |
| Histórico, exclusividade de perfil e encerramento de filhos no Python privado 3.15 | 22 testes aprovados |
| FFmpeg real, CPU e NVIDIA NVENC | 18 testes de integração aprovados; também incluídos na suíte completa |
| Executável instalado, sem Python/FFmpeg no PATH | Inicialização e ferramentas integradas aprovadas |
| Interface Qt nativa do Windows e offscreen | Aprovadas; ícone, logo, fundo e depuração oculta presentes |
| Instalação por usuário em pasta de teste | Aprovada |
| Reinstalação do mesmo pacote | Histórico SQLite e configuração de teste preservados |
| Desinstalação | Programa removido; dados do perfil de teste preservados |
| Script de criação do instalador | Compilação validada com Inno Setup 6.7.3 |
| Chromecast físico / televisão | **Não testado** |

O conjunto de integração usa vídeos sintéticos e processos iniciados pelo teste.
Verifica conversão H.264/AAC, alternativas de CPU/GPU, controle da reserva,
áudio, legendas e encerramento. Não representa uma medição de CPU ou buffering
do filme do usuário. O instalador foi exercitado em pasta e perfil isolados;
as instalações portáteis anteriores não foram atualizadas.

O teste de reinstalação utiliza novamente a 0.2.0, com histórico e configuração
sintéticos. Não afirma validar uma migração de banco de uma versão futura.
Nenhuma chave pessoal foi incorporada ao código ou instalador.

## Comportamentos cobertos

- Identidade por caminho, tamanho e modificação; arquivos homônimos e modificados.
- Persistência SQLite entre execuções e após encerramento abrupto do processo.
- Posições efetivas do receiver, amostras antigas, zero transitório, pausa,
  buffering, reinício, conclusão e regras para vídeos curtos.
- Retomada direta, Original e HLS, usando receiver simulado; falha de confirmação
  mantém o ponto anterior.
- Confirmação e cancelamento das limpezas, restauração de padrões, preservação
  de arquivos externos, cache ativo e junções do Windows.
- Bloqueio de respostas antigas de metadados após limpeza e de gravações de
  histórico de uma sessão anterior à limpeza.
- Exclusividade de acesso ao perfil e recuperação do bloqueio após crash.
- Encerramento real do processo filho quando o pai termina inesperadamente.
- HTTP com Range e funcionalidades anteriores de conversão/controle.

## Arquivos e arquitetura

Módulos novos: `history.py` (SQLite e checkpoints), `storage.py` (perfil e
limpezas), `process_guard.py` (Job Object do Windows) e `settings_panel.py`
(configurações). `cast_client.py` separa status bruto e relógio de exibição;
`session.py` coordena retomada e gravação. A interface, os caminhos, o cache de
filmes e o encerramento do transcodificador foram integrados a esses módulos.

Os testes novos ficam em `tests/test_history.py`, `test_resume_session.py`,
`test_resume_gui.py`, `test_storage.py`, `test_profile_lease.py` e
`test_process_guard.py`. O instalador está em `installer/LocalCast.iss`, com
entrada `gerar-instalador.cmd` e automação `scripts/installer.ps1`.

## Reprodução dos testes

Em um ambiente Python de desenvolvimento preparado com as dependências de
`pyproject.toml`, a partir da raiz do projeto:

```powershell
python -m pip install -e '.[dev]'
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest -q
python -m ruff check src tests --select E4,E7,E9,F,I
```

Para incluir os casos opcionais de integração de GPU:

```powershell
$env:LOCALCAST_TEST_GPU = '1'
python -m pytest -q
```

FFmpeg/FFprobe devem estar em `tools` ou nos caminhos configurados. Os testes de
GPU requerem hardware/driver compatível; outros ambientes podem pular casos
opcionais. Os comandos de instalação de dependências destinam-se ao ambiente
de desenvolvimento, não ao usuário do instalador.

O roteiro de aceitação na televisão está em
[VERSAO-0.2.0.md](VERSAO-0.2.0.md#teste-no-chromecast-de-2ª-geração).
O procedimento de empacotamento está em [EXECUTAVEL.md](EXECUTAVEL.md).
As versões, tamanhos e hashes do pacote estão em [BUILD-0.2.0.json](../BUILD-0.2.0.json).
