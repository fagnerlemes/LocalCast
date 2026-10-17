# Plano de testes no Windows e Chromecast 2

## Automação local

`scripts/test.ps1` executa HTTP real em loopback (200/206/416, GET/HEAD/OPTIONS, Range aberto/sufixo, CORS, concorrência e revogação), política de compatibilidade, chamadas Cast simuladas, erros LOAD e limpeza/seek. `-Integration` gera e converte MP4, MKV HEVC/EAC3, HEVC 4K/EAC3 e HDR sintético; verifica codecs/resolução/áudio com FFprobe e decodifica o HLS completo com FFmpeg. Sem ferramentas, os testes de integração aparecem como **skipped**, não como confirmação de transcodificação.

As chamadas Cast simuladas verificam o contrato do código, sem conectar a uma TV. Nenhum teste automatizado abaixo substitui aceitação física.

`test_tracks.py` cria um MKV original sintético com dois tons de áudio (220/880 Hz) e três legendas embutidas (SRT, ASS, PGS). Converte a segunda faixa, mede sua frequência e confere pixels antes/durante/depois da legenda, desde o começo e após seek para 3 e 6 segundos. O nome do arquivo contém acento, espaço, colchetes, vírgula e apóstrofo. O teste de desconexão simula o quit do receiver, com sucesso/falha, e verifica liberação do servidor; nenhuma chamada chega ao aparelho.

Os testes de Original recebem o corpo completo e um Range por HTTP real, verificando os bytes sem alteração e MIME de MP4/MKV; proíbem criação de encoder e verificam ausência de fallback após LOAD_FAILED. `test_launch.py` inicia e fecha uma GUI Qt offscreen por PowerShell/pythonw, confere ausência de console, argumentos/porta e fim do worker, em pasta com espaço, acento, colchetes e apóstrofo. A cópia temporária do launcher suprime diálogos de erro para automação; o aviso de abertura Python é conferido com MessageBox simulado.

## Aceitação física — preencher pelo usuário

Antes da TV, confirme o novo visual: Depuração começa fechada e abre pelo botão; Rede e conexão expande IPs; assinatura aparece no canto inferior; todos os controles de mídia permanecem acessíveis, inclusive por rolagem em janela pequena. Configure uma chave OMDb real para conferir a capa, correspondência do título/ano, elenco e notas. Teste Corrigir identificação e Atualizar; feche/troque o arquivo durante a consulta e confirme que uma resposta antiga não substitui o filme novo. Sem chave/Internet, a transmissão deve permanecer disponível.

Data: ______  PC/CPU: ______  Wi-Fi: ______  Chromecast modelo/firmware: ______

| Teste | Critério | Resultado |
|---|---|---|
| Descoberta | Chromecast listado com nome e IP | Pendente |
| MP4 direto | Imagem + áudio na TV, Default Media Receiver | Pendente |
| MP4 em Original | Arquivo enviado sem conversão; verificar reprodução e seek | Pendente |
| MKV em Original | Registrar aceitação/rejeição pelo receiver; nenhuma conversão automática | Pendente |
| Retorno à Automática | Após rejeição do Original, nova transmissão usa HLS | Pendente |
| Play/pause direto | TV acompanha os comandos | Pendente |
| Seek direto | Avança a 10 s e volta a 2 s; som sincronizado | Pendente |
| MP4 Forçar HLS | Manifesto/TS chegam e TV reproduz | Pendente |
| HLS pausa >30 s | Retoma sem erro de playlist; cache disponível | Pendente |
| MKV H.264/AAC | Conversão inicia sem cópia inteira prévia | Pendente |
| MKV HEVC 4K + EAC3 5.1 | Imagem ≤1080p, áudio estéreo, sem buffering prolongado | Pendente |
| Seek MKV fora do buffer | Nova carga inicia no tempo pedido, inclusive para trás | Pendente |
| Seek MKV pausado | Restaura pausa após nova carga | Pendente |
| Escolha de áudio do MKV | Idioma escolhido antes de Transmitir é audível | Pendente |
| Aplicar faixas durante reprodução | Troca áudio e legenda na posição atual; pausa restaurada | Pendente |
| SRT/ASS embutida | Acentos legíveis; aparece e apaga no tempo certo | Pendente |
| PGS embutida | Imagem da legenda visível e sincronizada | Pendente |
| Seek com legenda | Mantém faixa e sincronismo, inclusive no meio de uma fala | Pendente |
| Sem legenda / Sem áudio | Desativa conforme escolha após Aplicar faixas | Pendente |
| Arquivo longo real | ≥15 min sem perda de sync/buffer, CPU e disco aceitáveis | Pendente |
| HDR real (se aplicável) | Cores SDR aceitáveis, sem filtro faltando | Pendente |
| Stop/troca/fechamento | FFmpeg encerra; cache da sessão removido | Pendente |
| Desconectar após Parar | Chromecast retorna à tela ambiente; Buscar reconecta | Pendente |
| Conectar sem arquivo | Montagem LocalCast aparece e permanece pausada/sem som | Pendente |
| Espera por ≥20 min | Verificar permanência e possíveis limites de inatividade do receiver | Pendente |
| Transmitir após Conectar | Fundo é substituído pelo filme, preservando faixas e modo escolhido | Pendente |
| Parar durante filme | Volta ao fundo sem FFmpeg ativo | Pendente |
| Desconectar / fechar durante espera | Receiver libera a tela de espera e retorna ao modo ambiente | Pendente |
| Fechar durante reprodução / após Parar | Receiver do LocalCast encerra e retorna à tela ambiente | Pendente |
| iniciar.cmd | Qt fica aberto sem terminal persistente; fechar encerra corretamente | Pendente |
| iniciar-debug.cmd / diagnostico.cmd | Terminal visível para diagnóstico, saída/erro claros | Pendente |
| Wi-Fi desligado no meio | UI responde e diagnóstico mostra conexão/HTTP | Pendente |

Ordem obrigatória para diagnóstico: **MP4 direto → mesmo MP4 HLS → MKV H.264/AAC → MKV HEVC/EAC3 → arquivo 4K real**. Se uma etapa falhar, salve JSON, copie o log, anote estado e mensagem exata antes de avançar. Registre também se foram requisitados o manifesto e os segmentos. Uma falha de receiver não deve ser descrita apenas como “MKV não funciona”.

Se HLS for rejeitado apesar de bytes/manifesto válidos, o MVP ainda não passou a aceitação do recurso de conversão naquele firmware. Próximo trabalho é ajustar HLS/LOAD, comparar variantes ou avaliar um receiver customizado. Não pressupor que um player no PC implica suporte na TV.


## Aceitação adicional da 0.1.1 (pendente na TV)

| Teste | Critério | Resultado |
|---|---|---|
| Mesmo arquivo em CPU e GPU automática | Registrar encoder e verificar imagem/som | Pendente |
| Reserva padrão 90 s | Descanso próximo ao alvo e retomada próxima a 45 s, sem interrupção | Pendente |
| Pausa por dois minutos | Reserva estabiliza e reprodução retoma corretamente | Pendente |
| Seek e troca de faixas em GPU | Posição, idioma e legenda preservados | Pendente |
| Fechar enquanto encoder descansa | Processo próprio termina e receiver sai | Pendente |
