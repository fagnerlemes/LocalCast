# Contribuir com o LocalCast

By Fagner Lemes. Mudanças são recebidas por issues e pull requests.

## Ambiente de desenvolvimento

Use Windows x64, Python completo 3.11+ e FFmpeg/FFprobe em `tools/`.
Para pytest, use uma `.venv` completa; o runtime portátil serve para executar
e empacotar o app e não inclui ferramentas de teste.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m ruff check src tests scripts --select E4,E7,E9,F,I
.\.venv\Scripts\python.exe -m pytest -q -m 'not integration'
.\.venv\Scripts\python.exe -m pytest -q
```

O último comando inclui conversão. Sem FFmpeg, testes de mídia são pulados;
registre isso nos resultados. `scripts/test.ps1 -Integration` oferece a suíte
completa; sem o argumento, executa os testes sem integração.

Testes automatizados não devem controlar o Chromecast real. Use receiver
simulado e mídia sintética. Para aceitação na TV, preencha
[docs/TESTES.md](docs/TESTES.md), incluindo modelo e firmware.

## Alterações

Descreva o problema e o comportamento resultante. Para reprodução, confira
limpeza de processos, revogação de URLs, seek, pausa e erros. Operações lentas
devem ficar fora da thread da GUI. Preserve a assinatura, os avisos de licença,
texto da interface em português e a [arquitetura](docs/ARQUITETURA.md).

Não envie filmes pessoais, chave OMDb, logs brutos, runtime, EXEs ou caches.

## Preparar uma versão

Atualize `pyproject.toml` e `src/localcast/__init__.py` com a mesma versão,
registre o changelog, teste e gere o EXE no Windows. A versão nas propriedades
do Windows é derivada do `pyproject.toml` pelo spec do PyInstaller.
Confira o EXE isolado e registre seu SHA256.

Crie uma tag `vX.Y.Z`. Atualize o download do Drive e as notas da release em
conjunto, mantendo código e binário correspondentes. A automação não publica
executáveis nem utiliza chaves de API.
