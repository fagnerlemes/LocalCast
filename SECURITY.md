# Dados locais e relatos

Use o LocalCast na rede local privada. Não publique sua porta HTTP na Internet.

`localcast-dev-data/` (fonte) e `%LOCALAPPDATA%/LocalCast` (instalado) podem conter
chave OMDb, histórico SQLite, cache, caminhos de arquivos e logs. Não integram
o repositório. `LOCALCAST_DATA_DIR` é um override explícito. Instalação, atualização
e desinstalação preservam o perfil. Use a limpeza confirmada no aplicativo para
remover seus dados. A limpeza não segue links/junções nem remove vídeos originais.

Revise o diagnóstico antes de anexá-lo a uma issue pública. Remova chave de API,
caminhos pessoais e endereços da rede que não queira divulgar. Informe modelo
do Chromecast, codecs, modo de conversão e erro, sem anexar o filme.

Para vulnerabilidades sensíveis, use **Security → Report a vulnerability**, se
disponível. Caso não esteja, peça um canal privado em uma issue sem publicar
detalhes de exploração ou credenciais.
