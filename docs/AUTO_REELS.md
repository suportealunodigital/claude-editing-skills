# Auto Reels privado no Codex Cloud

O comando `./auto-reels` recebe um MP4/MOV, transcreve a fala em português
brasileiro, escolhe um dos onze tratamentos e produz um MP4 1080×1920, 30 fps,
com voz, título e legendas sincronizadas. Os onze comandos originais continuam
existindo; `auto-reels` é a décima segunda skill de coordenação. Também funciona
no Claude com `/auto-reels` e o instalador original.

A escolha usa regras lexicais auditáveis em português e pré-condições de mídia.
Não é uma avaliação criativa por LLM. Sem imagens fornecidas, os cinco estilos
fotográficos ficam inelegíveis; não usamos fotos de terceiros como se fossem do
usuário. Não inventamos métricas, provas sociais, nomes ou tiers. Títulos e cartões
são trechos da transcrição. Rankings exigem um veredito de tier explícito.

## Instalação e descoberta no Codex Cloud

Neste fork, selecione o repositório `suportealunodigital/claude-editing-skills`,
branch `codex-editing-skills`, e execute a tarefa dentro do checkout. A `main`
original não contém a coordenação auto-reels. Se o clone buscar somente main:

```bash
git fetch origin refs/heads/codex-editing-skills:refs/remotes/origin/codex-editing-skills
git switch --no-track codex-editing-skills
# Se a branch local ainda não existir:
# git switch --no-track -c codex-editing-skills origin/codex-editing-skills
bash install-codex.sh --skip-setup
bash install-codex.sh --check
```

Compare `git rev-parse HEAD` com `git ls-remote origin refs/heads/codex-editing-skills`.
Para atualizar uma branch local sem alterações, use
`git merge --ff-only origin/codex-editing-skills` após o fetch. O instalador exige
as doze skills, verifica colisões antes de criar links e preserva diretórios
existentes. `--skip-setup` e `--check` não instalam Groq nem outros pacotes.
`--check` apenas verifica os links; não comprova atualização do catálogo.

A fonte fica em `skills/auto-reels/SKILL.md`; o link relativo versionado
`.agents/skills/auto-reels -> ../../skills/auto-reels` mantém os scripts e o kit
no mesmo checkout. Não copie apenas o SKILL.md. Dependências Python estão em
`kit/requirements-auto.txt`, renderer e lockfile em `kit/hyperframes-auto/`.
Os entrypoints são `auto-reels`, `skills/auto-reels/build.py` e `kit/auto_reels.py`;
os módulos ficam em `kit/autoreels/`.

Inicie **uma nova tarefa dentro deste checkout**, com essa branch selecionada,
para recarregar o catálogo. Confira `skills/list` quando disponível e invoque
`$auto-reels` (ou o nome qualificado exibido pelo cliente). Um catálogo vazio
na tarefa antiga não invalida os links, mas impede afirmar descoberta dinâmica.
Para testar somente invocação, use `$auto-reels apenas diagnóstico, sem editar`.
`./auto-reels --help` e `./auto-reels --doctor` não acionam setup nem edição.
Dependências ausentes continuam sendo um erro de runtime; descoberta não é render.

## 1. Preparar o ambiente publicado

Selecione no Codex o ambiente **claude-editing-skills** que você configurou e
inicie uma tarefa ligada a ele, nesta branch. Alterar/publicar uma configuração
não garante que uma tarefa já em execução receba novos segredos. O processo não
consegue selecionar um ambiente pelo nome. Confira a realidade desta tarefa:

```bash
./auto-reels --doctor
```

Esse diagnóstico mostra apenas presença de credenciais, ferramentas, modelo e
política de rede, nunca valores secretos. `groq_key_present` precisa ser `true`.
`GOOGLE_DRIVE_ACCESS_TOKEN` só é necessário para arquivos autenticados e envio.
Configure credenciais reais pelo mecanismo de segredos do ambiente, disponíveis
na fase de execução, sem colocá-las no código, Git, chat ou arquivos .env.

Na sessão de implementação de 5/11/2026, a observação corrente do executor
vinculado à tarefa não apresentou GROQ_API_KEY nem integração Drive, e sua
política não permitia os hosts abaixo. O nome do ambiente publicado não foi
exposto pelas ferramentas disponíveis; não se afirmou que essa sessão já usava
a configuração publicada. Esse estado é uma observação histórica, não a situação
de toda tarefa futura.

Permita, na configuração de rede, os destinos efetivamente usados:

- `api.groq.com`: Whisper.
- `drive.google.com` e `drive.usercontent.google.com`: links/downloads Drive.
- `www.googleapis.com`: Drive API autenticada e uploads resumíveis.
- Redirecionamentos `doc-….googleusercontent.com`, se retornados pelo Drive,
  precisam da autorização correspondente do ambiente. O código valida o domínio
  e não encaminha o bearer token a outro host.
- Setup: PyPI/files.pythonhosted.org, registry.npmjs.org, cdn.jsdelivr.net,
  GitHub releases para o modelo e os hosts de pacote que npm solicitar.

Não edite `/etc/codex/network-policy.json` para tentar liberar rede. Uma ausência
na política exige configuração do ambiente, não uma tentativa de contornar o
proxy. A autorização de domínio também não concede acesso ao arquivo.

O runtime automático precisa de Python 3.12+, Node 22+, FFmpeg/FFprobe com
libx264, AAC, libvpx-vp9 e libass, além de Chromium com suas bibliotecas Linux.
Uma vez, no setup do ambiente:

```bash
bash kit/setup-auto.sh --cutout
```

O launcher executa esse setup quando o runtime está ausente. Ele instala um
HyperFrames **0.8.214 isolado** em `kit/.hyperframes/`, sem lifecycle scripts npm;
a segmentação usa **ONNX Python na CPU**, não o postinstall Node que falhava no
0.8.34. O comando original `kit/setup.sh` e sua versão padrão não foram trocados.
As dependências Python automáticas estão em `kit/requirements-auto.txt`; o lockfile
do renderer está em `kit/hyperframes-auto/` e é aplicado por npm ci. Os seis builders
antigos também aceitam a opção HYPERFRAMES_CLI, sem trocar seu padrão: aponte-a
para `kit/.hyperframes/node_modules/hyperframes/dist/cli.js` para usar o runtime
automático com os comandos originais. A execução
verifica a versão do renderer; não declara o setup completo só por imprimir uma
versão. `HYPERFRAMES_BROWSER_PATH` seleciona um Chromium instalado; permissões de
subprocessos/serviços locais precisam permitir a renderização. Não são desativadas
as proteções do browser/plataforma pelo script.

## 2. Enviar o vídeo pelo Google Drive

Envie o arquivo pelo próprio Drive para uma pasta privada. Copie um link de arquivo
como `/file/d/ID/view`, `/open?id=ID` ou `/uc?id=ID&export=download` e disponibilize
o link à tarefa em **AUTO_REELS_INPUT_URL**, usando o mecanismo de entrada/segredos
do ambiente. Não coloque o link no repositório nem o imprima em logs.

```bash
./auto-reels --url-env AUTO_REELS_INPUT_URL
```

A skill `$auto-reels` ou `$editing-skills:auto-reels` executa esse mesmo comando.
Um arquivo realmente anexado/disponível no Cloud também pode ser usado:

```bash
./auto-reels /workspace/private/meu-video.mov
```

O fluxo não muda compartilhamento. Sem OAuth, tenta somente um download já
permitido pelo link existente; se vier uma tela de login/negação, para. Para
arquivos grandes, reconhece o formulário de confirmação de download do Drive;
não executa HTML/JavaScript nem transforma login em uma sessão autenticada.
Links compartilhados já acessíveis podem funcionar sem OAuth, mas você não deve
tornar um vídeo privado público para usá-los aqui.

Para arquivos privados autenticados, forneça **GOOGLE_DRIVE_ACCESS_TOKEN** real,
emitido por uma integração OAuth autorizada para a conta e os arquivos. Não há
login interativo, geração de credencial, captura de cookies ou refresh automático
no código. Uma conexão Drive de outro cliente não injeta necessariamente um token
neste executor. Use a integração autorizada se ela disponibilizar download/upload,
ou configure um token na execução por um mecanismo seguro. A API rejeita contas,
scopes ou arquivos sem permissão. Não há conector Drive ativo nesta sessão de
implementação; não foi afirmada uma conexão já existente.

Para ler arquivos arbitrários autorizados da conta, OAuth normalmente exige
`drive.readonly`; `drive.file` limita acesso aos arquivos explicitamente autorizados
para a aplicação (por exemplo, por um seletor). A escrita deve ter escopo adequado,
preferencialmente `drive.file` com a pasta escolhida autorizada. O consentimento,
renovação e disponibilização segura do token pertencem à integração autorizada.

## 3. Tamanho e ingestão

A transferência direta ao workspace não passa pela ferramenta de download de
anexos limitada a 32 MiB. Lê em blocos de 1 MiB, com limite padrão de **2 GiB**,
configurável até 8 GiB com `--max-mib`. O valor não representa garantia de quota
do Drive, limite de proxy, disco ou timeout de uma tarefa. Não é carregado o vídeo
inteiro na memória. O limite é aplicado com e sem Content-Length; downloads
incompletos/negados são removidos. `--sha256` permite verificar um hash conhecido.

São verificados container MP4/MOV, duração de 0,5 s a 2 h, uma trilha de vídeo e
uma de áudio, dimensões, taxa de frames e decodificação completa por FFmpeg.
Playlists/HTML não são aceitos como vídeo; protocolos remotos do FFmpeg ficam
bloqueados. Preserve espaço para entrada, vídeo preparado, alpha e frames de
renderização: o cache de frames pode ser muito maior que o MP4. O pipeline verifica
disco durante o download e limites de tempo; não promete processar 2 GiB com o
mesmo custo de um vídeo curto.

Na suíte foi transferido por HTTP mockado um MOV real de **34 MiB**, com streaming
e decodificação FFmpeg real. Isso prova a ausência do limite de 32 MiB na aplicação;
**não prova transferência de 34 MiB pelo Drive ou pelo proxy desta sessão**. Sem
link autorizado, credencial e domínios permitidos, esse teste externo fica pendente.

## 4. Edição automática

Groq Whisper `whisper-large-v3` recebe áudio mono 16 kHz em blocos de até dez minutos,
com cap de segurança de 24 MiB por envio, `language=pt`, prompt literal pt-BR e
marcação por palavra. A linguagem da API é `pt`, não `pt-BR`. Nenhum clone de voz,
dublagem ou troca de identidade é aplicado. O áudio da fonte é remuxado/reencodificado
em AAC a partir do mesmo trecho preparado usado no vídeo; a correlação de waveform
é conferida na entrega.

A seleção prefere trechos com começo de frase e sinais de gancho, tutorial,
história, comparação ou ranking; a edição padrão tem até 25 segundos, ajustável
por `--max-seconds` (até 60). Um título extrativo e legendas destacadas palavra a
palavra são gerados sem escrever JSON manualmente. Gráficos de comparação/lista
mostram apenas texto dito. Dados numéricos não são inferidos como analytics.

Opcionalmente forneça até doze imagens reais com `--images arquivo1.jpg ...`.
Os cinco templates fotográficos continuam limitados a 4,2 s e só entram na seleção
quando uma frase inteira cabe nessa janela e há imagens suficientes. Todos os
assets do template são substituídos pelas entradas; todo texto de demonstração é
removido antes do render. O recorte alpha é produzido a partir do próprio vídeo
quando o tratamento exige. Não há rastreamento automático de rosto, segmentação
sem falhas ou reconhecimento confiável do centro de objetos circulares; enquadramento,
cabelos, mãos e fotos precisam de inspeção quando usados em produção.

No fluxo automático, Trial Reels usa **v1** para entregar um MP4 único; o comando
original continua produzindo três versões. Os outros cinco builders originais e
os cinco HTMLs fotográficos são reutilizados, sem migração da lógica original.
A normalização inicial preserva proporções e usa padding para evitar cortar
arbitrariamente uma fonte horizontal; cada tratamento ainda tem seus próprios
recortes e pode exigir revisão visual.

## 5. Obter o resultado

O comando imprime o caminho real do MP4 e do relatório em:

```text
.autoreels/JOB/reel.mp4
.autoreels/JOB/report.json
.autoreels/JOB/contact-sheet.jpg
```

Essa pasta privada tem modo 0700 e está no .gitignore. O relatório não armazena
URL de entrada, bearer token ou sessão de upload. Transcrição, spec, logs privados
e imagens de conferência permanecem nessa pasta. Apague o job após a entrega se
não precisar conservá-lo. Não há serviço público, publicação ou upload GitHub.

O cliente pode expor arquivos como anexos da tarefa; nesse caso peça ao Codex para
anexar o arquivo real. **Não existe, nas ferramentas desta sessão, uma API genérica
de registro de artefatos**, portanto um caminho local não é automaticamente um
link de download. Se o cliente não oferecer anexos, use envio privado ao Drive:

```bash
./auto-reels --url-env AUTO_REELS_INPUT_URL --drive-folder-env AUTO_REELS_DRIVE_FOLDER_ID
```

Isso requer o OAuth acima e uma pasta de destino autorizada. O upload é resumível
em blocos de 8 MiB, com recuperação limitada de erros. A pasta é verificada; destinos
públicos ou cuja privacidade não pode ser confirmada são recusados. Nenhuma chamada
altera permissões. O arquivo herda o acesso da pasta escolhida, e o relatório retorna
o ID/link do Drive. Um token expirado ou quota excedida faz a transferência falhar;
o MP4 validado continua no job para uma tentativa de entrega posterior autorizada:

```bash
./auto-reels --deliver-job ID_DO_JOB --drive-folder-env AUTO_REELS_DRIVE_FOLDER_ID
```

Esse comando verifica novamente áudio, frames e hash antes de enviar; não exige
repetir a transcrição nem renderizar outra vez.

## 6. Qualidade e limites da validação

FFmpeg decodifica o resultado; FFprobe verifica 1080×1920, 30 fps, frames, duração,
trilha de áudio e alinhamento de timestamps. Áudio silencioso ou waveform divergente
é rejeitado. Título/legendas têm geometria medida por fonte e ficam dentro de
x=120..960, y=240..1460. O Chromium também mede os textos nativos dos templates em cada frame e rejeita
caixas fora de x=100..980, y=220..1500. A checagem não faz OCR de texto nas imagens.
A geometria não é uma prova de legibilidade em todos os
aparelhos nem de ausência de oclusão de rosto. Uma folha de contato de cinco frames
permite revisar pessoa, boca, títulos e gráficos. As áreas cobertas pelo Instagram
podem variar. Não se afirma aprovação visual se ninguém abriu a folha.

`--transcript arquivo.json` aceita uma transcrição verdadeira já existente e é
registrado como fonte fornecida, não como Groq testado. `--no-transcription` serve
apenas para teste explícito de render com áudio, sem legendas ou seleção por fala.
Nunca trate essas opções como confirmação da integração externa.

Execute os testes locais com:

```bash
kit/.venv/bin/python -m unittest discover -s tests -v
bash -n auto-reels install.sh install-codex.sh kit/setup.sh kit/setup-auto.sh
```

Consulte [AUTO_REELS_TEST_REPORT.md](AUTO_REELS_TEST_REPORT.md) para os testes
realmente executados nesta implementação e os serviços que ficaram pendentes.


Os testes de render com fala controlada podem ser repetidos, sem credenciais:

```bash
kit/.venv/bin/python tests/render_audio_smoke.py
kit/.venv/bin/python tests/render_audio_smoke.py --photo
```

Eles geram fala sintética conhecida com FFmpeg/flite e medem os timestamps pelos
samples PCM. São fixtures técnicas identificadas, não transcrição Groq, voz real
do apresentador ou validação de download externo. Requerem flite no FFmpeg e
permissão de executar Chromium; todas as mídias geradas permanecem ignoradas.
