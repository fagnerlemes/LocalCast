# Tela de espera — LocalCast 0.1.0

O fundo reúne capas reais de 24 filmes, obtidas pela integração OMDb, em uma montagem diagonal escurecida. A logo fica acima de **LocalCast** e a assinatura original **By Fagner Lemes** aparece menor abaixo. Inclui lançamentos de 2025/2026 e sucessos de outros anos. As fontes de cada capa estão em [fontes-filmes-espera.json](../assets/fontes-filmes-espera.json), sem chave de API.

Os filmes recentes incluem Avatar: Fire and Ash, Zootopia 2, Super Mario Galaxy, Toy Story 5 e Project Hail Mary. Os lançamentos/sucessos recentes foram conferidos em fontes dos estúdios, como [Disney](https://thewaltdisneycompany.com/box-office/) e [NBCUniversal](https://www.nbcuniversal.com/article/illumination-and-universal-pictures-super-mario-galaxy-becomes-first-1-billion-film-2026). A composição usa os arquivos de capa retornados pelo [OMDb](https://www.omdbapi.com/), com créditos dos filmes preservados nas imagens. Capas pertencem aos respectivos titulares; a integração do aplicativo é para uso pessoal/não comercial.

## Usar no Chromecast

1. Abra `iniciar.cmd` e clique **Buscar Chromecast**.
2. Escolha o aparelho e clique **Conectar**. O app envia a tela de espera mesmo sem abrir um vídeo.
3. Abra seu MP4/MKV, escolha as faixas e clique **Transmitir**. O vídeo substitui o fundo.
4. **Parar** encerra o filme e volta ao fundo quando a conexão está disponível.
5. **Desconectar** ou fechar o app libera a mídia local e solicita a saída do receiver.

Também continua sendo possível selecionar um arquivo e clicar **Transmitir** diretamente, sem usar Conectar antes. O aplicativo precisa permanecer aberto para servir a mídia pela rede.

## Funcionamento e limites do receptor

O [Default Media Web Receiver do Google](https://developers.google.com/cast/docs/web_receiver) não permite personalizar sua interface de espera. Por isso o app envia a arte como um pequeno MP4 local de imagem fixa e sem áudio: H.264 High nível 3.1, 1280×720, yuv420p, 1 fps e faststart. Após confirmação de reprodução, solicita pause, mantendo o quadro na tela. Não altera o modo ambiente do Chromecast nem instala outro receiver. Controles do receptor podem aparecer brevemente e o tempo que o aparelho mantém a sessão pausada depende de seu firmware; essa permanência precisa ser conferida na TV.

O vídeo do fundo vem pronto na pasta `assets`; não inicia FFmpeg nem consulta OMDb ao conectar. Ao começar um filme, o recurso do fundo é removido da lista HTTP. Abrir arquivos e buscar informações no painel não dispara automaticamente uma transmissão. A imagem não reaparece automaticamente ao terminar um filme; use **Parar** ou **Conectar** para voltar ao fundo.

Arquivos disponíveis:

- [PNG 2560×1440](../assets/localcast-espera-2560x1440.png), versão de maior resolução.
- [JPEG 1920×1080](../assets/localcast-espera-1920x1080.jpg), para outros usos em Full HD.
- [JPEG 1280×720](../assets/localcast-espera-1280x720.jpg), base da mídia enviada à TV.
- [MP4 da tela fixa](../assets/localcast-espera.mp4), sem áudio.

| Antes | Depois | Por quê |
|---|---|---|
| Transmitir é o primeiro contato com o receiver | Conectar permite mostrar a marca antes de abrir um arquivo | Atende à espera antes da reprodução |
| Parar deixa o receiver sem mídia | Parar volta à montagem se houver conexão | Mantém a identidade enquanto o usuário escolhe outro filme |
| Nome acompanhado pelas letras LC | Logo própria no cabeçalho e na janela | Une a identidade no PC e na TV |

As skills de design foram consultadas conforme as instruções do projeto. Após a rejeição da geração da montagem, o usuário escolheu explicitamente a composição com capas reais, sem geração de IA. Os cartazes foram montados com desenho nativo, preservando a logo gerada anteriormente e a assinatura fornecida pelo autor.

Nenhuma transmissão de teste foi feita a um Chromecast físico. A aceitação do vídeo de espera, a permanência após pause e a volta à tela ambiente devem ser confirmadas pelo usuário.
