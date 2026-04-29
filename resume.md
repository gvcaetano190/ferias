# Resumo da implantacao TOTVS e integracao com o bot

## Objetivo

Implantar a integracao com o TOTVS para:

1. Consultar usuario por login.
2. Bloquear e desbloquear usuario via API.
3. Sincronizar o status real do TOTVS no banco.
4. Integrar o TOTVS ao fluxo do modulo `block`.
5. Expor consulta, bloqueio e desbloqueio do TOTVS no bot/WhatsApp.

---

## Regras fechadas

### API TOTVS

- Consulta por `GET /rest/api/framework/v1/users/{login ou id}`.
- Atualizacao por `PUT /rest/api/framework/v1/users/{id}`.
- Header obrigatorio: `TenantId: 01,01`.
- Autenticacao: `Basic Auth`.

### Seguranca

- Usuario e senha do TOTVS nao ficam em texto puro no banco.
- As credenciais ficam no cofre do sistema via `keyring`.
- O admin guarda apenas a configuracao e a referencia da credencial.

### Regra funcional

- Se o usuario existir no TOTVS, o sistema usa o status real.
- Se a consulta retornar `404`, o status local do TOTVS vira `NP`.
- `NP` nao deve inflar a pre-lista antiga.
- O TOTVS deve atuar daqui para frente apenas no lote corrente.
- O check operacional consulta primeiro o AD e depois o TOTVS.
- A execucao final age apenas em quem realmente ainda precisa de acao.

---

## O que foi implantado

## 1. Novo modulo TOTVS

Foi criado um modulo dedicado para a integracao com o TOTVS.

### O que ele faz

- Guarda configuracao da integracao no admin.
- Guarda usuario/senha no cofre do Windows.
- Consulta usuario no TOTVS.
- Atualiza `active=true/false`.
- Sincroniza status real no banco local.
- Oferece comandos de teste e sincronizacao.

### Arquivos criados ou alterados

- [apps/totvs/apps.py](/C:/ferias/apps/totvs/apps.py:1)
- [apps/totvs/models.py](/C:/ferias/apps/totvs/models.py:1)
- [apps/totvs/admin.py](/C:/ferias/apps/totvs/admin.py:1)
- [apps/totvs/forms.py](/C:/ferias/apps/totvs/forms.py:1)
- [apps/totvs/credentials.py](/C:/ferias/apps/totvs/credentials.py:1)
- [apps/totvs/services.py](/C:/ferias/apps/totvs/services.py:1)
- [apps/totvs/tests/test_client.py](/C:/ferias/apps/totvs/tests/test_client.py:1)
- [apps/totvs/migrations/0001_initial.py](/C:/ferias/apps/totvs/migrations/0001_initial.py:1)
- [apps/totvs/management/commands/test_totvs_api.py](/C:/ferias/apps/totvs/management/commands/test_totvs_api.py:1)
- [apps/totvs/management/commands/set_totvs_credentials.py](/C:/ferias/apps/totvs/management/commands/set_totvs_credentials.py:1)
- [apps/totvs/management/commands/sync_totvs_status.py](/C:/ferias/apps/totvs/management/commands/sync_totvs_status.py:1)
- [integrations/totvs/client.py](/C:/ferias/integrations/totvs/client.py:1)
- [project/settings.py](/C:/ferias/project/settings.py:1)

### Validacoes feitas

- `GET` funcionando.
- `PUT` funcionando.
- `TenantId` confirmado.
- Credencial salva no cofre confirmada.

---

## 2. Correcao importante no payload do PUT

Durante os testes apareceu um caso real em que o usuario existia no TOTVS, mas o `GET` devolvia o e-mail primario vazio:

- usuario: `pedro.furtado`
- erro no PUT: `E-mail primário não enviado`

Foi corrigido o cliente do TOTVS para:

- reutilizar o payload do `GET`
- e preencher `emails[0].value` com o e-mail do banco local quando o TOTVS devolver o e-mail vazio

### Arquivos alterados

- [integrations/totvs/client.py](/C:/ferias/integrations/totvs/client.py:1)
- [apps/totvs/services.py](/C:/ferias/apps/totvs/services.py:1)
- [apps/totvs/tests/test_client.py](/C:/ferias/apps/totvs/tests/test_client.py:1)

### Resultado

- `pedro.furtado` passou a aceitar `PUT` normalmente.

---

## 3. Integracao do TOTVS com o fluxo do block

O TOTVS foi acoplado ao fluxo completo do modulo `block`.

### O que mudou

- A pre-lista agora mostra coluna de status TOTVS.
- O check operacional consulta AD e depois TOTVS.
- A fila final considera AD e TOTVS.
- O historico de processamentos passa a guardar `status_totvs`.
- A verificacao operacional passa a guardar:
  - `totvs_status_banco_antes`
  - `totvs_status_real`
  - `totvs_status_banco_depois`

### Regra final adotada

- O TOTVS nao reabre fila antiga sozinho.
- O TOTVS nao infla a pre-lista so porque esta `NP`.
- O TOTVS atua apenas sobre o lote corrente.
- O check sincroniza o banco quando encontra divergencia.

### Arquivos alterados

- [apps/block/models.py](/C:/ferias/apps/block/models.py:1)
- [apps/block/repositories.py](/C:/ferias/apps/block/repositories.py:1)
- [apps/block/preview_service.py](/C:/ferias/apps/block/preview_service.py:1)
- [apps/block/business_service.py](/C:/ferias/apps/block/business_service.py:1)
- [apps/block/migrations/0006_blockprocessing_totvs_status_and_more.py](/C:/ferias/apps/block/migrations/0006_blockprocessing_totvs_status_and_more.py:1)
- [templates/block/index.html](/C:/ferias/templates/block/index.html:1)
- [templates/block/partials/preview_modal.html](/C:/ferias/templates/block/partials/preview_modal.html:1)
- [templates/block/partials/verification_modal.html](/C:/ferias/templates/block/partials/verification_modal.html:1)
- [apps/block/tests/helpers.py](/C:/ferias/apps/block/tests/helpers.py:1)
- [apps/block/tests/test_block_business_rules.py](/C:/ferias/apps/block/tests/test_block_business_rules.py:1)

### Ajuste funcional posterior

Depois da primeira integracao, a pre-lista ficou inflada porque o TOTVS estava puxando casos antigos com `NP/NB`.

A regra foi corrigida para:

- deixar a pre-lista mostrar apenas o lote real do momento
- deixar o TOTVS atuar dentro do `check operacional` e da `execucao final`

---

## 4. Ajustes de front

Foram feitos dois movimentos no front do modulo `block`:

1. Inclusao inicial de explicacao visual da esteira AD + TOTVS.
2. Remocao posterior dessa area porque o layout ficou poluido e o usuario nao gostou.

O estado final ficou:

- tela mais limpa
- historico com coluna de `Status TOTVS`
- modais de preview e verificacao mostrando TOTVS
- secao explicativa removida da home do `block`

### Arquivos alterados

- [templates/block/index.html](/C:/ferias/templates/block/index.html:1)
- [templates/block/partials/preview_modal.html](/C:/ferias/templates/block/partials/preview_modal.html:1)
- [templates/block/partials/verification_modal.html](/C:/ferias/templates/block/partials/verification_modal.html:1)

---

## 5. Integracao do TOTVS com o bot/WhatsApp

Foi adicionado suporte no bot para consultar, bloquear e desbloquear usuarios no TOTVS.

### Comandos implantados

- `totvs nome`
- `totvs email`
- `totvs login`
- `totvs bloquear nome/email/login`
- `totvs desbloquear nome/email/login`
- `totvs desbloquar nome/email/login`

### Resposta curta adotada

Consulta:

```text
🧾 Totvs - NOME DA PESSOA
STATUS: BLOQUEADO
```

ou

```text
🧾 Totvs - NOME DA PESSOA
STATUS: DESBLOQUEADO
```

ou

```text
🧾 Totvs - NOME DA PESSOA
STATUS: NAO ENCONTRADO
```

### Como a busca funciona

- o bot primeiro localiza o colaborador no banco
- aceita:
  - nome
  - e-mail
  - login
- depois usa preferencialmente o `login_ad` para consultar ou atualizar no TOTVS

### Arquivos alterados

- [apps/bot/services.py](/C:/ferias/apps/bot/services.py:1)
- [apps/bot/queries.py](/C:/ferias/apps/bot/queries.py:1)
- [apps/bot/tests.py](/C:/ferias/apps/bot/tests.py:1)

### Ajustes no menu do bot

O menu de ajuda tambem foi atualizado para incluir:

- consultar TOTVS
- bloquear no TOTVS
- desbloquear no TOTVS

---

## 6. Arquivos alterados nesta entrega

### Modulo TOTVS

- [apps/totvs/apps.py](/C:/ferias/apps/totvs/apps.py:1)
- [apps/totvs/models.py](/C:/ferias/apps/totvs/models.py:1)
- [apps/totvs/admin.py](/C:/ferias/apps/totvs/admin.py:1)
- [apps/totvs/forms.py](/C:/ferias/apps/totvs/forms.py:1)
- [apps/totvs/credentials.py](/C:/ferias/apps/totvs/credentials.py:1)
- [apps/totvs/services.py](/C:/ferias/apps/totvs/services.py:1)
- [apps/totvs/tests/test_client.py](/C:/ferias/apps/totvs/tests/test_client.py:1)
- [apps/totvs/migrations/0001_initial.py](/C:/ferias/apps/totvs/migrations/0001_initial.py:1)
- [apps/totvs/management/commands/test_totvs_api.py](/C:/ferias/apps/totvs/management/commands/test_totvs_api.py:1)
- [apps/totvs/management/commands/set_totvs_credentials.py](/C:/ferias/apps/totvs/management/commands/set_totvs_credentials.py:1)
- [apps/totvs/management/commands/sync_totvs_status.py](/C:/ferias/apps/totvs/management/commands/sync_totvs_status.py:1)
- [integrations/totvs/client.py](/C:/ferias/integrations/totvs/client.py:1)

### Modulo block

- [apps/block/models.py](/C:/ferias/apps/block/models.py:1)
- [apps/block/repositories.py](/C:/ferias/apps/block/repositories.py:1)
- [apps/block/preview_service.py](/C:/ferias/apps/block/preview_service.py:1)
- [apps/block/business_service.py](/C:/ferias/apps/block/business_service.py:1)
- [apps/block/migrations/0006_blockprocessing_totvs_status_and_more.py](/C:/ferias/apps/block/migrations/0006_blockprocessing_totvs_status_and_more.py:1)
- [apps/block/tests/helpers.py](/C:/ferias/apps/block/tests/helpers.py:1)
- [apps/block/tests/test_block_business_rules.py](/C:/ferias/apps/block/tests/test_block_business_rules.py:1)

### Front block

- [templates/block/index.html](/C:/ferias/templates/block/index.html:1)
- [templates/block/partials/preview_modal.html](/C:/ferias/templates/block/partials/preview_modal.html:1)
- [templates/block/partials/verification_modal.html](/C:/ferias/templates/block/partials/verification_modal.html:1)

### Bot

- [apps/bot/services.py](/C:/ferias/apps/bot/services.py:1)
- [apps/bot/queries.py](/C:/ferias/apps/bot/queries.py:1)
- [apps/bot/tests.py](/C:/ferias/apps/bot/tests.py:1)

### Projeto

- [project/settings.py](/C:/ferias/project/settings.py:1)

### Banco local de desenvolvimento

- `data/controle_ferias_django.sqlite`

---

## 7. Validacoes executadas

### TOTVS

- `manage.py test apps.totvs.tests`
- `manage.py test_totvs_api infra-teste --show-body`
- `manage.py test_totvs_api infra-teste --set-active true --show-body`
- `manage.py test_totvs_api infra-teste --set-active false --show-body`
- `manage.py test_totvs_api pedro.furtado --set-active true --show-body`

### Block

- `manage.py test apps.block.tests`
- `manage.py migrate block`
- `manage.py check`

### Bot

- `manage.py test apps.bot.tests`
- `manage.py check`

---

## 8. Observacoes finais

- O `requirements.txt` nao foi atualizado nesta entrega para registrar `keyring`, porque o arquivo do repositório ja estava com problema de codificacao antes.
- O fluxo do TOTVS ficou funcional no admin, no backend, no modulo `block` e no bot.
- A regra final combinada foi manter o passado como esta e corrigir progressivamente os proximos lotes.
