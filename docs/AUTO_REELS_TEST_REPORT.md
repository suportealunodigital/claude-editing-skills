# Verificação do auto-reels — 5 de novembro de 2026

## Resultado e escopo

O código implementa ingestão privada pelo Drive/local, transcrição pt-BR no Groq,
seleção entre onze tratamentos, edição, render, QA e entrega local/Drive. A skill
`auto-reels` é descoberta junto às onze originais. Foram produzidos MP4s novos
com áudio, não apenas composições HTML ou verificação de versão.

**O percurso externo Drive → Groq → Drive não foi validado nesta tarefa.** A
observação atual do ambiente ligado à sessão não expõe GROQ_API_KEY nem token
Drive, e a política não permite api.groq.com, drive.google.com,
drive.usercontent.google.com ou www.googleapis.com. Não havia URL de vídeo
privado autorizada nem integração Drive ativa nas ferramentas. Não foi possível
confirmar pelo nome que este executor corresponde à configuração publicada
claude-editing-skills mencionada pelo usuário. O diagnóstico real prevalece sobre
a suposição de que uma configuração publicada já foi aplicada a esta tarefa.
Nenhuma credencial foi criada, procurada em arquivos secretos ou exposta.

## Testes executados

- `kit/.venv/bin/python -m unittest discover -s tests -v`: **25 testes aprovados**.
  Cobrem descoberta/metadata dos doze diretórios, instaladores Claude/Codex,
  resolução por symlink, imports, onze possibilidades de seleção, tiers sem
  provas, timestamps inválidos, pt-BR na chamada Whisper, geometria/escape de
  legendas e falha de renderer mesmo quando ele deixa um arquivo parcial.
- Transferência de **MOV real de 34 MiB** por stream HTTP mockado, com arquivo
  completo salvo e FFmpeg real validando o container/áudio/vídeo. Arquivos grandes
  usam blocos; a suíte também verifica interrupção por limite e limpeza de parcial.
  **O HTTP desse teste é simulado; não é um teste de quota/rede do Google Drive.**
- Protocolo Drive com HTTP mockado: confirmação de download grande, negação/login,
  bloqueio de host não autorizado, remoção de bearer em redirecionamento entre
  hosts, upload resumível em dois blocos e recusa de pasta pública. Nenhuma chamada
  muda compartilhamento. Não foram configuradas credenciais fictícias em serviços;
  strings de token de teste só existem nos transportes mockados da suíte.
- Testes reais de mídia: HTML e entrada sem áudio recusados; frame count, duração
  e áudio decodificados; substituição da waveform por outra frequência rejeitada.
- `bash -n auto-reels install.sh install-codex.sh kit/setup.sh kit/setup-auto.sh`:
  aprovado. `compileall` dos módulos/scripts: aprovado.
- `pip check` da venv: nenhuma dependência quebrada.
- `bash kit/setup-auto.sh --cutout`: setup isolado executado. HyperFrames 0.8.214
  instalado sem lifecycle scripts npm, Chromium do sistema, ONNX Python na CPU.
  O setup final usa o lockfile versionado em kit/hyperframes-auto/ e npm ci.
- Consulta real ao Codex app-server `skills/list`: **12/12 skills de repositório
  habilitadas, errors vazio**, incluindo editing-skills:auto-reels. O helper
  antigo apresentou timeout ao encerrar o processo depois de receber a resposta;
  o catálogo foi conferido no JSON recebido. Isso não é render/transcrição.
- ONNX real após a atualização: recorte de nove frames do arquivo técnico
  disponível, decode VP9 e alphaextract aprovados. Download de modelo agora usa
  arquivo temporário/rename e não deixa um modelo parcial com nome definitivo.

## Renderizações reais com áudio

As fixtures são explicitamente **sintéticas/controladas**: FFmpeg/flite gera cada
palavra, e os tempos são medidos nos samples PCM concatenados. O vídeo é um padrão
técnico de cores; não se atribui essa fala ao apresentador da amostra. Os timestamps
fornecidos não são reconhecimento Groq. Todas as mídias e transcrições ficam em
`.autoreels/`, ignoradas pelo Git.

| Tratamento escolhido automaticamente | MP4 final | Áudio × vídeo | Correlação com áudio de entrada | Legendas |
|---|---|---|---|---|
| Split Screen, sinais “primeiro”/“clique” | 1080×1920, 30 fps, 120 frames, 4,0 s | 4,0 s × 4,0 s | aproximadamente 0,995 | quatro eventos por palavra |
| Picture Stack, sinais “fotos”/“fotografias” | 1080×1920, 30 fps, 126 frames, 4,2 s | 4,2 s × 4,2 s | aproximadamente 0,996 | três eventos por palavra |
| Explainer, sinais “antes”/“depois”/“comparação” | 1080×1920, 30 fps, 96 frames, 3,2 s | 3,2 s × 3,2 s | aproximadamente 0,990 | três eventos por palavra |

Foram executados os scripts reprodutíveis:

```bash
kit/.venv/bin/python tests/render_audio_smoke.py
kit/.venv/bin/python tests/render_audio_smoke.py --photo
kit/.venv/bin/python tests/render_audio_smoke.py --explainer
```

O teste fotográfico usa explicitamente imagens já incluídas no repositório como
assets técnicos. Nenhum asset de demonstração é utilizado implicitamente pelo
fluxo de produção. A folha de contato foi aberta e inspecionada nos três casos;
ela mostra os textos, os cartões/transições e o padrão técnico. Isso não valida
qualidade de recorte em uma pessoa real, já que não havia fala original do usuário.

As caixas de título/legendas foram conferidas dentro de x=120..960, y=240..1460.
O auditor Chromium também executou os GSAPs e mediu texto DOM nativo por frame:
120 frames do Split Screen, 126 do Picture Stack e 96 do Explainer, sem caixas fora
da área x=100..980, y=220..1500. A medição do Explainer foi parte do pipeline final;
as outras composições renderizadas também foram auditadas diretamente. O template
fotográfico não manteve texto de demonstração, portanto tinha zero textos DOM;
seus títulos/legendas estão na trilha ASS validada separadamente.

## Falhas encontradas e tratadas

- O sandbox de execução padrão não permite certas operações do Chromium; renders
  e verificações de browser foram executados com a permissão normal ampliada da
  plataforma. Não se mudou política de rede nem se desativou a segurança no código.
- O Chromium bloqueia `file://` por política. O auditor usa servidor HTTP somente
  em loopback, restrito à composição, e bloqueia recursos externos; não há servidor
  público ou acesso irrestrito ao filesystem.
- O check do HyperFrames detectou o “?” decorativo do Explainer encoberto pelo
  cartão revelado. Uma primeira tentativa de escondê-lo na timeline era revertida
  pelo tween original; a correção final remove sua exibição no adaptador automático.
  O teste foi repetido até check, auditoria, render, decode e QA passarem. As
  tentativas que falharam continuam com status failed em seus jobs privados.
- O código legado considerava a existência do MP4 suficiente mesmo com exit não
  zero do renderer. Agora rejeita/remover o parcial nessa condição. Há teste de
  regressão. A seleção de CLI por HYPERFRAMES_CLI é opcional nos seis builders;
  sem ela o padrão legado permanece, preservando a configuração original.
- O launcher foi executado sem chave usando um MP4 técnico válido e falhou
  explicitamente em GROQ_API_KEY ausente. Não foi usado texto inventado como
  fallback de transcrição e não foi declarada uma chamada externa bem-sucedida.

## Pendências de produção

1. Iniciar uma tarefa ligada ao ambiente publicado correto, com GROQ_API_KEY real
   disponível na fase de execução. Confirmar presença com `./auto-reels --doctor`.
2. Autorizar os domínios reais Drive/Groq na configuração de rede desse ambiente.
   Um flag de domínio permitido não confirma autenticação nem quota do serviço.
3. Disponibilizar um link de arquivo privado autorizado e, se ele exigir login,
   GOOGLE_DRIVE_ACCESS_TOKEN real de uma integração OAuth consentida. O código
   não fornece login/refresh, não lê cookies de navegador e não muda permissões.
4. Para entrega Drive, autorizar uma pasta privada e token com escrita. Uploads
   herdariam as permissões da pasta; pastas públicas ou não verificáveis são recusadas.
5. Validar uma transferência real acima de 32 MiB pelo Drive/proxy, uma transcrição
   real pt-BR e o upload autorizado. O limite padrão de 2 GiB é da aplicação, não
   uma promessa sobre recursos, duração da tarefa ou quota do Google Drive.
6. Validar cortes, cabelos/mãos, face/boca, imagens e correção de transcrição com
   vídeo real. A geometria textual não faz OCR nem reconhecimento de rosto.
   Oito tratamentos têm cobertura de seleção/importação, mas não foram renderizados
   individualmente nesta etapa. A qualidade criativa é uma heurística básica.
7. Entrega como anexo depende de API/interface real do cliente. Não há API genérica
   de registro de artefatos nas ferramentas desta sessão; o fallback implementado
   é Drive privado autorizado, ainda sem credencial nesta tarefa. Não foi alegado
   que um caminho local já constitui um link de download externo.

As alterações de código, documentação, skill, testes e lockfile podem ser salvas
na branch codex-editing-skills. Inputs, MP4s, WAVs, transcrições, modelos, caches e
URLs/tokens não fazem parte do commit. Nenhum vídeo foi publicado em GitHub.
