> Este registro corresponde à versão estável 0.1.0. A cópia atual é 0.1.1; veja [a validação da 0.1.1](VALIDACAO-0.1.1.md).

# Validação — LocalCast 0.1.0

Publicação preparada em **14/10/2026**, no Windows x64. By Fagner Lemes.

## Código e reprodução local

**80 testes passaram em 33,72 s**, com Python 3.12.14, PySide6 6.12.0,
PyChromecast 14.0.10 e FFmpeg/FFprobe 9.0.2. Nenhum teste foi pulado nessa
execução. Ruff E4/E7/E9/F/I também passou para `src`, `tests` e `scripts`.

Foram exercitados:

- HTTP real em loopback: Range, GET/HEAD/OPTIONS, concorrência, revogação,
  proteção de caminhos e transporte sem alterar bytes no modo Original.
- Política de codecs, MKV/HEVC/EAC3, HLS MPEG-TS, 4K e HDR sintético, com análise
  FFprobe e decodificação FFmpeg das saídas.
- Seleção de áudio comprovada por frequência decodificada e legendas SRT/ASS/PGS
  comprovadas por pixels, inclusive após seek.
- Sessão Cast simulada: LOAD, play/pausa/seek, troca de faixas, Original sem
  fallback, espera, retorno após Parar, desconexão e limpeza após erros.
- Interface Qt offscreen, launcher Windows com/sem console, configuração/cache
  OMDb, detecção de Python e diretórios persistentes do EXE.

## Executável real

Build com Python privado **3.15.0**, PyInstaller **6.22.3** e hooks **2026.8**.
As propriedades do Windows informam **FileVersion/ProductVersion 0.1.0** e
**By Fagner Lemes**.

O EXE foi copiado para uma pasta contendo somente ele, sem código-fonte,
runtime ou ferramentas ao lado e com PATH limitado ao System32. Abriu e fechou
corretamente em **Qt offscreen e interface nativa Windows**. Logo, ícone e
espera estavam disponíveis; FFmpeg/FFprobe executaram a partir da extração do
próprio EXE. O diagnóstico confirmou `localcast: 0.1.0`, sem console obrigatório.
A captura é [interface-executavel.png](interface-executavel.png).

Tamanho e SHA256 do arquivo distribuído estão em
[RELEASE-0.1.0.json](../RELEASE-0.1.0.json). A chave OMDb e o perfil pessoal não
integram o build nem o código público.

## O que exige teste no aparelho

**Não foi buscado nem controlado um Chromecast físico nesta validação.**
Os testes não comprovam descoberta mDNS na LAN do usuário, regras do firewall,
aceitação de HLS pelo firmware, imagem/som na TV, sincronismo em filme longo,
desempenho de conversão 4K ou HDR/Dolby Vision real. Windows limpo/SmartScreen e
outros computadores também não foram usados nesta rodada.

Siga [TESTES.md](TESTES.md) na ordem MP4 direto → MP4 HLS → MKV H.264/AAC →
MKV HEVC/EAC3 → arquivo 4K real. Registre modelo/firmware e mensagem exata.
Abrir um HLS no PC não confirma que o receiver o aceite.

O [registro histórico](historico/VALIDACAO-DESENVOLVIMENTO.md) preserva as
etapas anteriores, com seus números internos e limitações da época.
