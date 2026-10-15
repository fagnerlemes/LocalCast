# Histórico de versões

## 0.1.0 — primeira versão pública — 14/10/2026

By Fagner Lemes.

- MP4/MKV no Chromecast via Default Media Receiver e HTTP com Range.
- Conversão HLS durante a reprodução, HEVC 4K/EAC3 para H.264 até 1080p/AAC estéreo.
- Áudio e legendas embutidas selecionáveis, inclusive durante a reprodução.
- Play, pausa, seek, Parar com retorno à espera e Desconectar.
- Modo Original, sem conversão e sem fallback automático.
- Interface escura, logo, assinatura, ficha OMDb e depuração recolhida.
- EXE único Windows x64, fonte editável e scripts de preparação/build.
- Documentação, testes locais, instruções Windows e licença MIT para o código.

Esta versão consolida o desenvolvimento anterior. Identificadores internos
0.1 a 0.5 anteriores à publicação não representam releases públicas.

### Limites conhecidos

- HLS e comandos Cast exigem validação no receiver/firmware real.
- Filmes longos dependem de CPU, rede e espaço para segmentos.
- Original pode falhar com MKV/HEVC/EAC3 no Chromecast 2.
- SRT externo ainda não tem seleção na interface; legendas embutidas são
  incorporadas ao vídeo durante a conversão.
- Dados/notas dependem do que o OMDb fornecer.
- Os testes locais não certificam reprodução física na TV.
