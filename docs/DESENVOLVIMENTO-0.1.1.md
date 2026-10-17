# LocalCast 0.1.1 — GPU e reserva adiantada

By Fagner Lemes. Cópia isolada para desenvolvimento, iniciada em 15/10/2026 a
partir da tag `v0.1.0`. A branch local é `development/0.1.1`. Não substitui a
versão estável, o EXE em uso, o link público do Drive nem a release do GitHub.

## Usar esta cópia

Abra **LocalCast.exe** nesta pasta. Alternativa: **iniciar.cmd**, com o Python
privado incluído. A janela informa **0.1.1**. Em **Conversão e faixas → Desempenho
e reserva**, o padrão é **Automático — GPU quando disponível**, com **90 s**.

Os ajustes valem na próxima transmissão. Os modos Automática, 720p, Original e
Forçar HLS permanecem disponíveis. Original não utiliza encoder nem reserva.
Para comparar, use o mesmo arquivo com **CPU — compatibilidade** e depois
**Automático**. O status mostra o encoder realmente ativo, a velocidade e a
reserva. A tentativa de GPU que falhou fica no log/diagnóstico, sem ocultar o
fallback. No Gerenciador de Tarefas, veja também **GPU → Video Encode/Decode**.

Esta cópia usa a porta padrão **8766** e dados próprios. No EXE isolado, sem
`localcast-data` ao lado, usa `%LOCALAPPDATA%/LocalCast-0.1.1`. O Python privado
usa `localcast-data` desta pasta. A chave OMDb da instalação estável não foi
copiada. Configure-a aqui se quiser testar a ficha dos filmes.

Não conecte as duas versões ao mesmo Chromecast ao mesmo tempo: um novo LOAD
substitui a mídia do receiver. Os testes desta implementação usam apenas mídia
sintética e receptor simulado, sem interferir na sessão que já está em uso.

## Processamento

Automático tenta **NVIDIA NVENC**, depois **Intel Quick Sync**, depois **AMD AMF**,
quando o FFmpeg inclui esses encoders, e mantém **CPU x264** como alternativa.
Uma entrada na lista de encoders não prova que o driver funcione: a alternativa
só é aceita após o FFmpeg criar segmentos HLS utilizáveis da entrada real.
Se uma tentativa falhar antes do LOAD, seus arquivos parciais são removidos e
a seguinte recomeça no mesmo ponto. Não troca URLs silenciosamente depois do
LOAD; um erro durante a reprodução é diagnosticado e exige nova transmissão.

No caminho NVIDIA compatível, HEVC/H.264/VP9/AV1 podem usar CUDA para decodificar.
Sem HDR e sem legenda, a redução de resolução também usa CUDA. HDR e legenda
de texto usam filtros na CPU e codificação NVENC; legendas de imagem usam a
composição existente na CPU e NVENC. Portanto, **GPU não significa CPU zerada**.
Os alvos Cast permanecem H.264 8-bit nível 4.1, até 1080p/30 e AAC estéreo.

O HDR ainda utiliza zscale/tonemap em CPU. Não promete preservar Dolby Vision.
Intel/AMD dependem do equipamento/driver e não equivalem à validação NVIDIA
real desta máquina.

## Reserva e descanso

O início aguarda três segmentos de cerca de quatro segundos, ou a conclusão de
um vídeo mais curto. A reserva contabiliza somente segmentos já publicados,
não quadros ainda dentro do encoder. Ao atingir aproximadamente **90 s** à
frente do relógio do receiver, o app suspende apenas seu próprio processo FFmpeg.
Retoma em torno de **45 s**, mantendo margem antes de faltar conteúdo. Durante
pausa na TV, a reserva para de ser consumida e o encoder pode descansar.

O alvo pode ser ajustado entre **30 e 300 s**; o ponto de retomada é a metade,
com piso de 12 s. Há uma tolerância de segmentos/quadros em processamento.
A entrada é limitada a até 4× após um avanço inicial de 12 s, para conter
rajadas e a ultrapassagem do alvo. Isso não é uma porcentagem fixa de CPU.

O relógio é atualizado pelo Cast e consultado periodicamente. Status antigo,
conteúdo de uma sessão anterior ou perda de conexão não podem deixar FFmpeg
preso: sem relógio confiável após o início, o controle libera a conversão.
Seek e troca de faixas criam uma sessão nova com offset e reserva novos.
Parar, Desconectar e fechar retomam/encerram o processo antes de limpar o cache.
O controlador permanece ativo caso o encoder precise de fallback no início.

A reserva **não garante ausência de buffering**. Conversão sustentada abaixo
de 1×, Wi-Fi lento, erros do receiver ou disco insuficiente ainda podem causar
pausas. Aumentar a reserva oferece margem, mas não corrige CPU/GPU incapaz de
acompanhar o filme. Os segmentos já assistidos permanecem no cache até encerrar
a sessão; o alvo limita trabalho adiantado, não o tamanho total do cache.

## Validação

Resultados e escopo ficam em [VALIDACAO-0.1.1.md](VALIDACAO-0.1.1.md). Não há
teste físico no Chromecast realizado pelo agente. Para testar na TV, compare
MP4 direto, MP4 HLS, MKV HEVC, pausa longa, retomada, seek, troca de faixas e
desconexão, usando o [checklist existente](TESTES.md).

Referências técnicas: [NVIDIA/FFmpeg](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/ffmpeg-with-nvidia-gpu/index.html),
[controle de leitura FFmpeg](https://ffmpeg.org/ffmpeg.html#Main-options) e
[psutil](https://psutil.io/api/).

## Interface

As skills `design-taste-frontend` e `emil-design-eng` foram consultadas. A
primeira exclui telas de aplicativos; manteve-se a identidade Qt existente.

| Antes | Depois | Motivo |
|---|---|---|
| Conversão sem escolha de processamento | Desempenho e reserva, recolhido por padrão | Oferece controle sem ocupar a área principal |
| Velocidade agregada do FFmpeg | Encoder real, reserva e estado de descanso | Explica GPU, fallback e pausas intencionais |
| Diagnóstico de velocidade abaixo de 1× durante espera | Espera excluída da velocidade ativa | Evita confundir economia intencional com lentidão |
