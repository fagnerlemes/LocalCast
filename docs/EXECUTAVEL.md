# Instalador e código-fonte — 0.2.0

Para a atualização 01, há também um [patch menor](PATCH-0.2.0-01.md).
Use `gerar-patch.cmd` para recompilar e gerar o atualizador específico da 0.2.0.

By Fagner Lemes. O formato principal agora é **LocalCast-Setup-0.2.0.exe**.
Instala por usuário em `%LOCALAPPDATA%\Programs\LocalCast`, com Python,
dependências, ferramentas de mídia e recursos incluídos. Não exige Python global.
O atalho no menu Iniciar abre o aplicativo; o atalho de desktop é opcional.

## Editar e compilar

1. Edite a cópia do código 0.2.0, principalmente `src/localcast`.
2. Teste com `iniciar.cmd`; seu perfil fica em `localcast-dev-data`.
3. Execute `gerar-instalador.cmd`.
4. Use `dist/LocalCast-Setup-0.2.0.exe` para instalar ou atualizar.

O script usa o runtime privado ou a `.venv` preparada, gera `dist/LocalCast`
com PyInstaller e chama o Inno Setup 6.7.3. Na primeira vez, as ferramentas de
build são baixadas do PyPI e o compilador portátil vem do GitHub oficial de
JRSoftware. SHA256 e assinatura Authenticode de Pyrsys B.V. são conferidos.
O compilador fica em `.installer-tools`, sem instalação global.

Para compilar apenas a pasta: `scripts/build.ps1 -IncludeFFmpeg`.
Para compilar apenas o instalador após gerar a pasta:
`scripts/installer.ps1 -SkipBuild`.
Para o formato antigo de arquivo único, `gerar-exe.cmd` permanece opcional.

O executável instalado usa `_internal` ao lado. Copie/compacte a pasta inteira
se quiser uma distribuição ZIP sem instalador. Não mova somente esse EXE.
O código fonte não é necessário para executar o aplicativo instalado.

## Dados e atualizações

Dados do aplicativo instalado: `%LOCALAPPDATA%\LocalCast`. Não ficam na área
temporária do PyInstaller. Reinstalar ou substituir o programa preserva o banco
e a configuração OMDb. A desinstalação preserva esses dados deliberadamente.
Use Configurações → Armazenamento e privacidade para apagá-los antes de desinstalar.

O instalador impede atualização enquanto o novo LocalCast está aberto; não
encerra uma transmissão à força. O AppId fixo permite reconhecer futuras
atualizações. Não registra MP4/MKV como padrão nem altera o PATH ou firewall.
Se solicitado pelo Windows, permita a rede privada para transmitir na LAN.

Perfil de desenvolvimento é separado. `LOCALCAST_DATA_DIR` permite um perfil
explícito para testes ou uso portátil. Configurações antigas podem ser importadas
pelo seletor de `movie-settings.json`; não são incluídas na distribuição.

O programa/instalador do LocalCast não recebe assinatura digital de editor neste
build; o certificado do compilador Inno não assina os aplicativos que ele gera.

Detalhes funcionais em [VERSAO-0.2.0.md](VERSAO-0.2.0.md), validação em
[VALIDACAO-0.2.0.md](VALIDACAO-0.2.0.md). Os testes automatizados não controlam a TV.
