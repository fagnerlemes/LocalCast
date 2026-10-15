# Visual e informações de filmes — versão 0.1.0

By Fagner Lemes. A assinatura PNG foi fornecida pelo autor e incorporada sem alterar seus pixels/transparência. `src/localcast/__init__.py` registra `__author__ = "Fagner Lemes"`. A imagem fica em `assets/assinatura-fagner-lemes.png` e também entra na preparação do PyInstaller.

O visual usa fundo escuro, superfícies em cinza, amarelo nos destaques, cantos arredondados, campos com setas claras e foco visível. A referência é o IMDb; o aplicativo mantém sua própria marca. A assinatura fica no canto inferior. A ficha fica à direita, os controles à esquerda e a reprodução sempre abaixo. Painéis rolam quando a janela é menor.

| Antes | Depois | Por quê |
|---|---|---|
| Tela clara com formulário único | Tema escuro e áreas de arquivo, envio, filme e reprodução | Hierarquia que acompanha a tarefa |
| Depuração ocupa a parte inferior | Botão Depuração, recolhido por padrão | Mensagens e exportação continuam acessíveis |
| Campos de IP sempre visíveis | Rede e conexão, expansível | Mantém ajustes de LAN disponíveis |
| Setas do tema nativo pouco visíveis no escuro | Setas desenhadas sobre controles nativos | Preserva interação/teclado e melhora a descoberta |
| Textos longos empurram Aplicar faixas | Orientações curtas e dica no seletor de conversão | Mantém os controles visíveis na janela de referência |

As skills `design-taste-frontend` e `emil-design-eng` foram consultadas. A primeira exclui telas de aplicativos; não foram impostos fluxos de site ou animações. Os princípios de estados, foco, feedback e coerência da segunda guiaram os controles. As capturas são da interface Qt real em modo offscreen, não de um mockup HTML.

## Ativar as informações do filme

1. Abra **Configurar filmes** no canto superior direito.
2. Clique **Obter chave gratuita no OMDb** ou use [a página oficial](https://www.omdbapi.com/apikey.aspx). Selecione **FREE**. O plano publicado tem limite de 1.000 consultas diárias. O cadastro/ativação por e-mail é feito pelo usuário.
3. Cole a chave recebida no campo **Chave OMDb**, mantenha a consulta automática marcada e salve.
4. Abra seu MP4/MKV. O app tenta identificar título e ano pelo nome, removendo marcas como 1080p/HEVC/BluRay. Um ID `tt...` no nome tem preferência.
5. Se a identificação não corresponder ao arquivo, use **Corrigir identificação**: informe título/ano, ID IMDb ou link IMDb. O arquivo e sua reprodução não são modificados.

A ficha mostra capa, ano, duração, gênero, sinopse, elenco principal, direção e nota IMDb. Mostra a nota da crítica Rotten Tomatoes® quando ela existir no campo `Ratings` devolvido pelo OMDb. Uma nota ausente fica como **— / Não informado pela fonte**. Não promete nota de público/Popcornmeter, dados completos nem notas em tempo real. **Ver no IMDb** e **Consultar Rotten Tomatoes** abrem o navegador somente quando clicados. O segundo usa o endereço do filme se retornado, ou uma busca pelo título.

O serviço usado é [OMDb](https://www.omdbapi.com/), não a API oficial do IMDb/Rotten Tomatoes. Dados e imagens são atribuídos ao OMDb (CC BY-NC 4.0, uso pessoal/não comercial). OMDb não é afiliado ao IMDb. A [API oficial do IMDb](https://data.imdb.com/documentation/api-documentation/getting-access/) exige acesso por AWS; o [Rotten Tomatoes solicita acesso para integração](https://www.rottentomatoes.com/help_desk). Não há scraping desses sites no código. A presença atual da nota Rotten Tomatoes ainda precisa ser conferida com uma chave válida.

Sinopse/gêneros podem vir em inglês; nomes do elenco preservam a grafia da fonte. A capa usa a URL `Poster` da consulta comum quando retornada, não o Poster API premium. O nome do arquivo pode não conter o nome comercial do filme; a correção manual evita presumir uma correspondência certa.

## Independência da reprodução

A consulta roda em worker próprio, separado da fila Cast. Envia somente título/ano ou ID IMDb pela Internet, nunca vídeo, caminho completo, legenda ou faixa de áudio. Ausência de chave, falta de Internet, erro, resposta antiga e cota excedida não iniciam nem interrompem transmissão. A interface ignora resultados de um arquivo anterior. Sem chave, ela informa como configurar, mas a reprodução continua disponível.

Consultas/capas ficam em cache por até sete dias, em `localcast-data/movie-cache` na distribuição portátil. **Atualizar** consulta novamente, consumindo cota. A chave e a preferência ficam em `localcast-data/movie-settings.json`, fora do código-fonte e dos ZIPs. A chave não entra no diagnóstico exportado e não é impressa nas mensagens. A consulta automática pode ser desativada; Atualizar continua permitindo busca manual.

## Verificação

Consulte os resultados atuais em [VALIDACAO.md](VALIDACAO.md). A ficha completa depende de uma chave OMDb válida e dos dados retornados pelo serviço. As capturas demonstrativas são identificadas como tal.

[Interface com arquivo aberto e fonte não configurada](interface-cinema.png).
[Ficha demonstrativa](interface-cinema-demo.png): capa, filme, elenco e notas são fictícios e identificados como demonstração na imagem.
[Depuração expandida](interface-depuracao.png).
