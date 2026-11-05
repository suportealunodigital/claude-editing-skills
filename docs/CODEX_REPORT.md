# Relatório de adaptação para OpenAI Codex Cloud

Data: 4 de novembro de 2026. Repositório: suportealunodigital/claude-editing-skills.
Base analisada: `beff6b868a8c1bdfad8661bd8a298497e75568a3`.

## Resultado

As 11 skills foram preparadas para descoberta e uso pelo Codex, mantendo os
workflows e o suporte ao Claude. A descoberta nativa confirmou 11/11 habilitadas,
sem erros. Um template foi efetivamente renderizado; não foi validada a edição
completa de vídeos reais nos seis workflows com transcrição.

## Leitura e alterações

Foram examinados os 11 SKILL.md, README principal e guias de showcase/assets,
install.sh, kit/setup.sh, os módulos compartilhados, imports e resolução de caminhos
dos builders, manifests do plugin e dependências declaradas no setup e no código.
Não havia suíte própria de testes versionada na base.

- `.agents/skills/`: 11 links relativos versionáveis para as pastas canônicas em
  `skills/`. Nenhuma duplicação das instruções, templates ou código.
- `install-codex.sh`: instalação local ao checkout, opção `--skip-setup`, passagem
  de `--cutout`, reexecução segura e recusa de sobrescrever conteúdo existente.
- 11 SKILL.md: instruções de invocação no Codex e referência ao AGENTS.md. Nos seis
  originais, a localização do kit agora resolve o symlink da skill ANTES de subir
  dois diretórios. Isso também corrige o caso de instalação por links no Claude.
- `AGENTS.md`: setup Cloud, invocação de cada skill, versões distintas dos dois
  renderizadores, credenciais reais, mídia acessível no Cloud, rede, Chromium,
  testes, limites dos templates e critérios de entrega.
- `README.md`: seção de utilização no Codex; `.gitignore`: intermediários `work/`.
- `tests/test_codex.py`: cinco testes de descoberta e compatibilidade.

`install.sh`, `kit/`, todos os build.py, templates, assets e `.claude-plugin/`
permaneceram sem alterações no código versionado. Nenhuma configuração global de
Claude foi alterada. Na etapa original da adaptação não houve commit, push ou
publicação remota; o salvamento no GitHub é uma etapa posterior.

## Invocação das 11 skills

| Nome curto no Codex | Função |
|---|---|
| `$trial-reels` | Três versões de um mesmo clipe |
| `$behind-the-person` | Gráficos atrás da pessoa recortada |
| `$explainer` | Pessoa abaixo e explicação visual acima |
| `$split-screen` | Composição dividida em duas metades |
| `$ranking-list` | Ranking sincronizado com as palavras |
| `$storytelling` | Três cartões, título e legendas |
| `$shape-shift` | Match cuts de fotografias circulares |
| `$picture-stack` | Fotografias empilhadas com foco em uma delas |
| `$scene-switch` | Trocas de fundo atrás da pessoa |
| `$visual-notes` | Imagem inteira seguida por detalhe |
| `$orbit-reel` | Cartões em órbita 3D |

A consulta real `skills/list` deste cliente retornou os nomes com namespace
`editing-skills:`, associado ao manifest preservado. Neste cliente, use por exemplo
`$editing-skills:explainer /workspace/media/clip.mp4` e
`$editing-skills:orbit-reel skills/orbit-reel/example.json`.
Siga o nome exibido pelo catálogo da tarefa. Claude mantém `/nome-da-skill` e seu
plugin. Os caminhos precisam existir no ambiente Cloud; citar Downloads do laptop
não transfere um arquivo.

## Verificações executadas

| Comando/verificação | Resultado observado |
|---|---|
| `python3 -m unittest discover -s tests -v` | 5 testes aprovados na execução final |
| Testes de metadata, catálogo e importação dos builders por symlink | 11/11 pastas verificadas |
| Teste do instalador Codex | Reexecução, espaços no caminho, colisões e flags inválidas verificados |
| Teste do instalador Claude | 11 links e passagem de --cutout; setup substituído por stub apenas neste teste |
| `bash -n install.sh install-codex.sh kit/setup.sh` | Sem erro de sintaxe |
| `python3 -m compileall -q kit/*.py skills/*/build.py` | Sem erro de compilação |
| `git diff --check` | Sem problemas de whitespace |
| `bash install-codex.sh --skip-setup` | Executado no checkout; links reconhecidos |
| Codex app-server, initialize e `skills/list` com forceReload | 11 skills repo habilitadas, errors vazio |
| Cinco builders fotográficos com `--prepare-only` | Cinco composições HTML geradas com mídia e fontes |
| `kit/.venv/bin/python -m pip check` | No broken requirements found |
| `bash kit/setup.sh --cutout` | Exit 0; dependências Python e modelo disponíveis; aviso de falha no aquecimento HyperFrames 0.8.34 |
| CLI local HyperFrames `--version` | 0.8.214 confirmado |
| Picture Stack com CLI 0.8.214 e Chromium explícito | Check, render e decodificação ffmpeg concluídos |
| ffprobe do novo Picture Stack | H.264, 1080×1920, 30 fps, 126 frames, 4,2 s; sem áudio, conforme template |
| Folha de contato do novo MP4 | Gerada e visualmente examinada: pessoa contínua, cartões e transição de foco visíveis |
| frame/sheet e decodificação de amostra já incluída | Executados; não contados como renderização nova |
| cutout.py em trecho real de 0,3 s, reduzido para 270×480 | 9 frames segmentados em WebM; decode e alphaextract aprovados |
| --help de reel.py, transcribe.py e cutout.py | Executados sem erro |
| Comparação com a base de install.sh, kit e .claude-plugin | Nenhuma alteração versionada |

A consulta de descoberta usou um CODEX_HOME temporário em `work/`, porque o
CODEX_HOME padrão é somente leitura neste executor. Isso não criou credenciais.
Os testes de instalador usam diretórios temporários e não configuram serviços.
O teste reduzido de recorte comprova execução de ONNX e saída alfa, não qualidade
em resolução integral, cabelos, mãos ou clipes longos.

## Falhas observadas e recuperação

No sandbox padrão, chamadas npm/curl ao proxy falharam com EPERM/conexão recusada.
Uma tentativa npm com cache gravável expirou em 45 s. A verificação inicial do
HyperFrames falhou com `browser setup process exited without a result`, inclusive
com Chromium explícito e caches XDG graváveis. A execução ampliada autorizada pela
plataforma permitiu o Chromium e produziu o MP4. Não foi removida a política de rede
nem desativada a segurança para contornar o bloqueio.

A instalação do HyperFrames 0.8.34 também foi tentada com execução ampliada e cache
local. Terminou com exit 1; o log npm identifica falha no postinstall de
`onnxruntime-node@1.21.1`. O setup original suprime detalhes do aquecimento e
continua com aviso, portanto seu exit 0 não comprova esse renderizador operacional.
A versão 0.8.34 foi preservada; não houve atualização silenciosa dos workflows.

O check do Picture Stack reportou dois avisos de tweens GSAP sobrepostos, em #p0 e
#p2, entre 2,05 e 2,20 s. Não foram alteradas as animações originais. O check com
Chromium funcional permitiu a renderização. O doctor do HyperFrames retornou JSON
`ok: false` embora seu processo saísse com 0; apontou Docker e ferramentas opcionais
(whisper-cpp, Kokoro, MusicGen) ausentes. Elas não foram necessárias para o render
HTML/Chromium executado, e whisper-cpp não substitui automaticamente o Groq usado
pelos seis workflows deste repositório.

## Dependências e limitações restantes

- **GROQ_API_KEY ausente.** Nenhuma transcrição externa foi feita. Os seis workflows
  precisam de chave real e acesso a api.groq.com, ou de uma transcrição existente,
  verdadeira e com tempos por palavra. Nenhuma credencial ou transcrição fictícia
  foi criada. Disponibilidade do endpoint Groq autenticado permanece não testada.
- **HyperFrames 0.8.34 não operacionalmente confirmado.** Resolver seu postinstall
  de onnxruntime-node e repetir uma renderização antes de declarar os seis
  workflows aprovados de ponta a ponta.
- **Permissões do executor.** O navegador e os serviços locais do renderer precisam
  ser permitidos. Chromium instalado sozinho não basta, como a falha demonstrou.
- **Setup de ambiente novo não é integralmente reproduzido.** Já havia venv, GSAP e
  CLI 0.8.214 em cache. Foram usados de verdade, mas não se comprovou download do
  zero de todos os componentes. O modelo mobilenetv3 foi baixado nesta execução;
  resnet50 continua ausente e só é necessário se escolhido.
- Python 3.12.14, Node 24.22.1, ffmpeg/ffprobe 7.1.5, Chromium, groq, numpy,
  pillow e onnxruntime estão presentes. Os codecs libx264, AAC e libvpx-vp9 foram
  confirmados. Dependências Python do upstream continuam sem lock de versões.
- Os quatro outros templates fotográficos foram preparados, mas não renderizados
  novamente. Seus previews existentes não contam como testes de renderização.
- Não foram fornecidos vídeos reais do usuário. Os cinco estilos continuam sendo
  starters silenciosos de 4,2 s; cenas longas, áudio, crop, alinhamento de fotografias
  e novos recortes exigem edição e revisão. Não há rastreamento automático de rosto.
- As imagens de terceiros e a pessoa da amostra têm direitos separados da licença
  MIT do código. A demonstração gerada não deve ser apresentada como mídia própria.

## Entrega e reprodução

`claude-editing-skills-codex.tar.gz` contém o código adaptado, com os links simbólicos,
sem .git, credenciais, caches, venv ou modelos. `codex-cloud.patch` contém todas as
alterações, inclusive arquivos novos. Aplique na base indicada com `git apply` ou
extraia o arquivo completo em um diretório de trabalho. No Cloud, inicie nova tarefa
nesse checkout para atualizar o catálogo e siga AGENTS.md.

Os logs anexados preservam o resultado do setup, dos testes e do render. O MP4
anexado é o Picture Stack realmente gerado nesta execução, com mídia de exemplo.


## Evolução posterior: auto-reels

O relatório acima registra a etapa original de 4/11/2026. A coordenação automática,
Drive privado, runtime isolado, novos testes e limitações observadas em 5/11 estão
em [AUTO_REELS.md](AUTO_REELS.md) e [AUTO_REELS_TEST_REPORT.md](AUTO_REELS_TEST_REPORT.md).
A evolução adiciona uma skill coordenadora sem remover os onze tratamentos.
