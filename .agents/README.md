# Guia Para Agentes de IA

Este projeto e um monorepo para capturar promocoes do Telegram, identificar links de marketplaces, salvar as postagens, chamar um webhook externo de afiliados, publicar no Telegram de destino e mostrar tudo no painel admin.

Use este arquivo como ponto de partida antes de editar o codigo. Ele resume o contexto que uma IA futura precisa para continuar o trabalho com seguranca.

## Estado Atual

- Backend: NestJS em `apps/api`.
- Frontend: Next.js em `apps/admin`.
- Banco: PostgreSQL via Prisma.
- Filas: Redis + BullMQ.
- Fluxo principal:
  1. Telegram envia ou a conta monitorada captura uma mensagem.
  2. `TelegramService` extrai URLs e joga um job em `process-promotion`.
  3. `ProcessPromotionProcessor` identifica marketplace, resolve URL final, cria `Promotion` como `PENDING`.
  4. O mesmo processor agenda um job em `publish-promotion`.
  5. `PublishPromotionProcessor` muda status para `PROCESSING`, chama o webhook/n8n, publica no Telegram quando configurado e grava `PublishLog`.
  6. Sucesso vira `PUBLISHED`; erro vira `FAILED` com detalhes em `PublishLog.details`.

## Diretorios Importantes

- `apps/api/src/modules/telegram`: captura, monitoramento e publicacao.
- `apps/api/src/modules/webhooks`: chamada ao webhook externo e resolucao de URL de produto.
- `apps/api/src/modules/promotions`: API de listagem, detalhe, paginacao e logs de postagens.
- `apps/api/src/modules/settings`: configuracao do webhook e marketplaces no painel.
- `apps/api/prisma/schema.prisma`: modelos, enums e relacoes do banco.
- `apps/admin/src/app/modules/promotions`: tela de postagens, paginacao e modal de logs.
- `apps/admin/src/app/modules/integrations`: configuracao visual de webhook e marketplaces.
- `apps/admin/src/app/modules/dashboard`: metricas do painel.

## Comandos

No Windows/PowerShell, prefira `npm.cmd` se `npm` falhar por execution policy.

```powershell
npm.cmd install
npm.cmd run prisma:generate -w apps/api
npm.cmd run prisma:migrate -w apps/api
npm.cmd run test -w apps/api
npm.cmd run build -w apps/api
npm.cmd run build -w apps/admin
npm.cmd run dev -w apps/api
npm.cmd run dev -w apps/admin
```

Comandos do root:

```powershell
npm.cmd run build
npm.cmd run test
npm.cmd run prisma:generate
npm.cmd run prisma:migrate
```

## Regras de Trabalho

- Nao reverta alteracoes existentes sem pedido explicito do usuario.
- Antes de mexer em fluxos de promocao, leia:
  - `apps/api/src/modules/telegram/application/process-promotion.processor.ts`
  - `apps/api/src/modules/telegram/application/publish-promotion.processor.ts`
  - `apps/api/src/modules/promotions/application/promotions.service.ts`
  - `apps/admin/src/app/modules/promotions/pages/promotions.page.tsx`
- Se alterar Prisma:
  - crie migration em `apps/api/prisma/migrations`.
  - rode `npm.cmd run prisma:generate -w apps/api`.
  - rode build/test da API.
- Se alterar contrato da API de postagens, atualize os tipos em `apps/admin/src/app/shared/types/admin.ts`.
- Se alterar listagem de postagens, confira tambem o dashboard, pois ele usa `listPromotions`.
- Evite bloquear o webhook do Telegram esperando n8n; publicacao externa deve continuar na fila `publish-promotion`.

## Decisoes Recentes

- O gargalo do n8n foi resolvido separando captura e publicacao em duas filas:
  - `process-promotion`: trabalho rapido de captura/normalizacao.
  - `publish-promotion`: trabalho lento de webhook/publicacao.
- Foi adicionado `PromotionStatus.PROCESSING`.
- `GET /promotions` agora retorna objeto paginado:

```ts
{
  items: Promotion[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}
```

- O admin abre o detalhe da postagem com `GET /promotions/:id` para carregar todos os logs.
- Falhas sao rastreadas em `PublishLog`, nao em arquivo local.
- Emojis da mensagem de publicacao ficam como emoji direto no codigo, nao escape unicode, exceto quando ja houver padrao local diferente.
- O monitoramento da conta Telegram usa evento realtime `NewMessage` e tambem polling periodico. O polling e importante porque alguns grupos podem permitir leitura historica mas nao entregar updates realtime de forma confiavel.

## Status e Logs

`Promotion.status`:

- `PENDING`: capturada e aguardando publicacao.
- `PROCESSING`: worker de publicacao pegou o job.
- `PUBLISHED`: webhook/publicacao concluiu.
- `FAILED`: ocorreu erro, ver `publishLogs`.

`PublishLog.status`:

- `SUCCESS`: resposta valida do webhook.
- `ERROR`: erro capturado. Detalhes podem incluir HTTP status, corpo de resposta do n8n, codigo de erro, tentativa e stack.

## Pontos de Cuidado

- `AFFILIATE_WEBHOOK_TIMEOUT_MS` tem default de 45s. Se o n8n demorar mais, ajuste env ou otimize o workflow.
- BullMQ faz retry; a tela pode mostrar logs de tentativas antigas em uma postagem que depois deu certo.
- `jobId` de publicacao usa `promotion-${promotionId}` para evitar duplicar publicacao da mesma promocao.
- O sistema nao faz backfill no restart/refresh. Mensagens antigas podem ser perdidas se a API estiver desligada.
- `TELEGRAM_USER_POLL_INTERVAL_MS=30000` faz a API varrer os grupos a cada 30s. O polling roda tambem uma vez logo ao iniciar.
- Se precisar reprocessar falhas manualmente, ainda falta endpoint/botao de reenvio.
- O admin usa CSS global em `apps/admin/app/styles.css` e overrides em `apps/admin/app/post-no-image.css`.
- Alguns arquivos antigos podem ter historico de encoding ruim; mantenha novos arquivos em UTF-8.

## Proximas Melhorias Recomendadas

- Botao "Reenviar" em postagens `FAILED`.
- Filtro por codigo HTTP no admin.
- Configuracao de concorrencia da fila `publish-promotion`.
- Job de limpeza/retencao de logs.
- Testes unitarios para `PublishPromotionProcessor`.
- Teste e2e leve para `GET /promotions` paginado.
