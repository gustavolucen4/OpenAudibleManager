---
name: prompt-dev-antigravity
description: Use esta skill sempre que o usuário pedir ajuda para escrever, melhorar ou detalhar um prompt/encargo de desenvolvimento de código destinado ao Google Antigravity (IDE agent-first onde agentes autônomos planejam, escrevem, testam e verificam código) — ou, de forma mais ampla, sempre que o pedido de código do usuário for curto/vago e o contexto sugerir que ele vai delegar a tarefa a um agente autônomo em vez de escrever/revisar linha a linha. A skill analisa o contexto do projeto disponível (stack, arquivos, código existente, conversas anteriores) e devolve APENAS um prompt/missão detalhado e bem estruturado para colar no Antigravity — nunca escreve o código da tarefa em si nem tenta resolvê-la diretamente. Ative proativamente mesmo sem pedido explícito de "melhora esse prompt" — o gatilho é um encargo de código vago para um fluxo agent-first. NÃO ative se o usuário já escreveu um encargo completo (objetivo, escopo, critério de validação) ou se pediu explicitamente para você mesmo escrever/rodar o código aqui.
---

# Prompt de Desenvolvimento para Antigravity

Esta skill escreve o "encargo" (o prompt/missão) que o usuário vai colar no Google Antigravity para um agente autônomo executar. Ela serve para **qualquer tipo de tarefa de codificação** — criar funcionalidade nova, corrigir bug, refatorar, mexer em UI, escrever testes, configurar deploy, migrar dados, etc. — não é limitada a um tipo específico de pedido. Ela NUNCA escreve ou executa o código da tarefa — só prepara o pedido para que o agente do Antigravity trabalhe bem.

## Por que isso é diferente de um prompt de código comum

No Antigravity, o modelo de trabalho é **agent-first**: o usuário descreve o objetivo, e um ou mais agentes autônomos planejam, escrevem, rodam comandos no terminal, testam (inclusive via um subagente de navegador) e devolvem **Artifacts** (plano de implementação, lista de tarefas, diffs, capturas) para o usuário revisar — em vez de sugerir linha por linha enquanto o humano digita.

Isso muda o que faz um prompt "bom" aqui:
- Um prompt genérico ("faz uma tela de login") gera um Artifact genérico e o agente toma decisões de arquitetura sozinho, que podem não bater com o projeto real.
- Um prompt bem escrito para Antigravity funciona como um brief de projeto: dá contexto suficiente para o agente **planejar corretamente na primeira tentativa** e **validar sozinho que funcionou** (rodando testes, subindo o servidor local, conferindo no navegador) — sem precisar de várias idas e vindas.

Por isso o foco aqui não é só "adicionar adjetivos", é garantir que o encargo tenha os ingredientes que um agente autônomo precisa para planejar, executar e se auto-verificar.

## Quando ativar

Sinais de que o encargo precisa ser aprimorado (vale para qualquer tipo de tarefa — feature nova, bug, refatoração, UI, testes, deploy, migração, etc.):
- Pedido curto de código sem contexto de projeto ("cria um CRUD de usuários", "conserta esse bug de login", "refatora esse módulo", "sobe isso pra produção", "adiciona dark mode")
- Falta stack/arquitetura, escopo (o que mexer e o que não mexer), ou como validar que ficou certo
- Vai ser usado para delegar a tarefa inteira a um agente (não para pedir ajuda pontual em uma linha)

Sinais de que NÃO precisa ativar:
- O usuário já deu objetivo, contexto do projeto, escopo e critério de validação
- O usuário quer que você mesmo escreva/edite o código aqui na conversa
- É uma dúvida pontual de sintaxe/conceito, não um encargo para delegar

## Processo

### 1. Reúna o contexto do projeto
Antes de montar o encargo, veja o que já está disponível:
- Arquivos/repositório anexados ou mencionados — abra e leia antes de assumir a stack
- Mensagens anteriores sobre o projeto (linguagem, framework, convenções já estabelecidas)
- Se nada disso existir, não invente uma stack elaborada — pergunte apenas o essencial (ex: "é web, mobile ou backend? qual linguagem/framework?") antes de montar o prompt, já que sem isso o encargo fica genérico demais para ser útil.

### 2. Estruture o encargo com os ingredientes que um agente autônomo precisa
Um bom prompt para Antigravity normalmente cobre:

- **Objetivo**: o que deve existir/mudar ao final, em uma frase clara
- **Contexto do projeto**: stack, framework, estrutura de pastas relevante, convenções de código já usadas
- **Escopo**: quais arquivos/módulos mexer, e o que explicitamente NÃO deve ser tocado
- **Comportamento esperado**: regras de negócio, casos de borda, o que deve acontecer em cada cenário
- **Critério de validação**: como o próprio agente pode confirmar que funcionou — rodar testes existentes, escrever novos testes, subir o servidor local e checar uma rota/tela no navegador, etc. Isso é o que mais diferencia um prompt de Antigravity de um prompt genérico: o agente vai se auto-verificar, então dê a ele um jeito objetivo de saber se terminou certo.
- **Restrições técnicas**: versões de dependência, padrões de estilo, coisas que não pode instalar/mudar
- **Modo sugerido** (opcional, mas útil): para tarefas grandes/múltiplos arquivos, sugerir modo Plan (o agente monta um plano revisável antes de executar); para ajustes pequenos e diretos, modo Fast pode bastar

Nem toda tarefa precisa de todos os itens — inclua os que fazem diferença real dado o tamanho e risco da tarefa. Uma tarefa pequena e isolada não precisa do mesmo nível de detalhe que criar um módulo inteiro.

### 3. Preencha lacunas com suposições explícitas quando o contexto permitir
Se você já sabe a stack e convenções pelo contexto, assuma e escreva o encargo completo. Só pergunte ao usuário quando a lacuna for essencial e impossível de inferir (ex: linguagem/framework quando não há nenhum arquivo ou menção anterior) — nesse caso, uma pergunta objetiva é melhor do que um encargo com suposições erradas sobre a stack inteira.

### 4. Entregue APENAS o encargo pronto para colar no Antigravity
Sua resposta deve ser:

1. Uma frase curta (1–2 linhas) dizendo o que foi adicionado/esclarecido e por quê
2. O encargo completo, em um bloco de código (```) pronto para colar no Antigravity
3. Se fez suposições relevantes sobre a stack/arquitetura que podem estar erradas, mencione rapidamente quais foram

Não escreva o código da tarefa, não simule o que o agente do Antigravity faria, e não liste explicações longas categoria por categoria — o valor está no encargo pronto, não em uma aula sobre como escrevê-lo.

## Exemplo

**Input do usuário:** "cria um crud de produtos" (projeto já mencionado antes: API em Node.js com Express e Prisma, Postgres)

**Output esperado (formato):**

Adicionei escopo, regras de validação e critério de verificação, já que "CRUD de produtos" sozinho não diz como validar que ficou certo:

```
Implemente um CRUD completo de produtos na API existente (Node.js + Express + Prisma + Postgres).

Contexto: siga a estrutura de rotas/controllers/services já usada no projeto (pasta src/modules).
Não altere o schema de outras entidades já existentes no Prisma.

Escopo:
- Model Product no schema.prisma: nome (string, obrigatório), preço (decimal, > 0),
  estoque (int, >= 0), criadoEm (timestamp automático)
- Rotas REST: GET /products (lista, com paginação), GET /products/:id, POST /products,
  PUT /products/:id, DELETE /products/:id
- Validação de entrada: nome não pode ser vazio, preço e estoque não podem ser negativos
  (retornar 400 com mensagem clara nesses casos)

Critério de validação: escreva testes de integração cobrindo os 5 endpoints (casos de sucesso
e os 400 de validação), rode a suíte de testes existente para garantir que nada quebrou, e
confirme que a migration do Prisma roda sem erros.

Modo sugerido: Plan (várias partes: schema, rotas, validação, testes).
```
Assumi paginação simples na listagem e validação básica de negativos — ajuste se as regras de negócio forem outras.

## O que evitar
- Não escreva ou execute o código da tarefa — o usuário quer o encargo para o Antigravity, não o resultado
- Não invente uma stack/arquitetura do zero se o contexto já indicar outra — sempre confira arquivos/mensagens anteriores primeiro
- Não infle tarefas pequenas e bem definidas com estrutura desnecessária (nem todo encargo precisa de "modo Plan" ou de uma seção de restrições longa)
