# Executável e código-fonte

**LocalCast.exe** é um arquivo único para Windows x64, com Python, PySide6, PyChromecast, FFmpeg/FFprobe, logo e tela de espera incluídos. Pode ser executado diretamente. O Windows não precisa ter Python instalado para abrir esse arquivo.

O código-fonte continua na pasta LocalCast, principalmente em `src/localcast`. O executável contém uma versão empacotada desse código; editar os arquivos não altera um EXE já gerado. Para testar edições diretamente, use **iniciar.cmd**. Para incorporá-las ao executável, use **gerar-exe.cmd**.

## Atualizar o executável

1. Feche o **LocalCast.exe** que estiver aberto.
2. Edite o código na pasta LocalCast e teste pelo **iniciar.cmd**.
3. Abra **gerar-exe.cmd** na pasta principal e espere terminar.
4. O arquivo novo fica em **LocalCast.exe** na pasta principal; uma cópia também fica em `dist/LocalCast.exe`.

Na primeira compilação, as ferramentas de empacotamento são baixadas do PyPI para `.build-tools`, na própria pasta. Versões e SHA256 estão fixados em `build-manifest.json`; hashes são conferidos antes de extrair. Não instala pacotes no Python global. O Python portátil do projeto pode gerar o EXE sem instalação global; uma `.venv` completa também é aceita. A pasta precisa ter o runtime/dependências preparados e `tools/ffmpeg.exe` + `tools/ffprobe.exe`.

`scripts/build.ps1` também mantém a opção de gerar uma pasta executável: execute com `-IncludeFFmpeg`, sem `-OneFile`. Nesse caso, preserve toda a pasta `dist/LocalCast`; o aplicativo é `dist/LocalCast/LocalCast.exe`.

## Configurações e arquivos

Ao abrir o EXE na sua pasta LocalCast atual, ele reutiliza a pasta **localcast-data** existente, incluindo sua configuração OMDb. A chave não está embutida no executável nem nos pacotes.

Se mover apenas o EXE para outra pasta que não tenha `localcast-data`, configurações, cache e logs ficam em `%LOCALAPPDATA%/LocalCastMVP`. Portanto continuam disponíveis após fechar o aplicativo. A chave OMDb deve ser configurada nesse perfil caso ele ainda não tenha a sua. O diretório temporário de extração do executável não é usado para salvar dados permanentes.

O arquivo único extrai suas dependências temporariamente a cada abertura; isso pode tornar a inicialização um pouco mais lenta. É o funcionamento documentado do [PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html). A logo, assinatura e fundo são recursos do programa e permanecem disponíveis sem acessar a Internet. Internet continua sendo usada somente nas consultas opcionais de filme.

**Conectar** mostra o fundo de filmes antes da reprodução; **Transmitir** abre o filme; **Parar** volta ao fundo se houver conexão; **Desconectar** ou fechar libera o receiver. Essa interação ainda exige validação física no Chromecast; o empacotamento não muda os limites dos codecs do aparelho.

## Verificação

Resultados do executável 0.1.0 em [VALIDACAO.md](VALIDACAO.md). O build deriva a versão das propriedades do Windows de `pyproject.toml`, preserva a autoria e inclui os avisos de licença. Nenhum teste automatizado conecta à TV.
