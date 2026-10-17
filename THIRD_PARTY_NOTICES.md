# Créditos e componentes de terceiros

O código próprio é Copyright (c) 2026 Fagner Lemes, sob MIT. Essa licença não
substitui as condições de dependências, marcas e imagens.

## Software

- **psutil 7.2.2**, Giampaolo Rodola e colaboradores: gerenciamento do processo
  FFmpeg criado pelo próprio app. Licença original em `licenses/python-packages/`.
  <https://github.com/giampaolo/psutil>.

- **Python / CPython**, Python Software Foundation: PSF e avisos em
  `licenses/python/`. Fonte: <https://www.python.org/>.
- **PySide6 / Qt e Shiboken**, The Qt Company e colaboradores: componentes Qt
  for Python com licenças próprias. Avisos do pacote e LGPLv3 em `licenses/qt/`.
  Fontes/condições: <https://www.qt.io/qt-for-python> e
  <https://code.qt.io/pyside/pyside-setup.git/>. Usam-se módulos Qt Essentials.
  Bibliotecas permanecem componentes separados extraídos pelo PyInstaller.
- **PyChromecast** e dependências: avisos em `licenses/python-packages/`.
  Fontes: <https://github.com/home-assistant-libs/pychromecast>;
  versões e URLs da distribuição em `runtime-manifest.json`.
- **PyInstaller**: ferramenta de build, GPL com exceção do bootloader.
  <https://pyinstaller.org/en/stable/license.html>.
- **FFmpeg / FFprobe**: processos separados. O EXE usa **9.0.2 essentials,
  gyan.dev**, com GPL habilitada. GPLv3 e README original em `licenses/ffmpeg/`;
  origem, hashes e fonte em `licenses/ffmpeg/build-info.json`.
  <https://ffmpeg.org/legal.html> · <https://www.gyan.dev/ffmpeg/builds/>.

Binários de Python/Qt/FFmpeg não são versionados aqui. Os textos de licença são
preservados e incluídos no empacotamento. Ao redistribuir uma modificação,
preserve esses avisos e forneça fonte correspondente e condições de
substituição/recompilação exigidas pelas licenças aplicáveis. A MIT do LocalCast
não relicencia esses componentes. Scripts e manifests documentam o build.

## Filmes, marcas e arte de espera

Fichas e URLs de pôsteres vêm do **OMDb API**, serviço independente:
<https://www.omdbapi.com/>. O site atribui seu conteúdo a **CC BY-NC 4.0**:
<https://creativecommons.org/licenses/by-nc/4.0/>. Respeite as condições da fonte.
A integração é opcional e utiliza a chave pessoal do usuário.

A montagem usa pôsteres reais obtidos via OMDb. Títulos, IDs IMDb e URLs estão
em `assets/fontes-filmes-espera.json`. Pôsteres, personagens e marcas pertencem
aos respectivos titulares e **não são oferecidos sob MIT**. Esta publicação não
concede direitos comerciais sobre essas imagens nem indica endosso dos estúdios.

A logo foi criada para o projeto e a assinatura fornecida por Fagner Lemes.
Google Cast/Chromecast, IMDb e Rotten Tomatoes pertencem a seus titulares;
o LocalCast não é afiliado a esses serviços.
