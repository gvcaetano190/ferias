# Plano Completo - App de Notificacoes Plug and Play

## Objetivo

Criar um app novo de notificacoes para o sistema Django atual, com foco inicial em WhatsApp via Evolution API, de forma:

- plug and play
- configuravel pelo admin
- reutilizavel em qualquer parte do sistema
- desacoplada da logica de block/sync
- preparada para crescer para outros canais no futuro

O primeiro caso de uso sera:

- detectar divergencias entre planilha e AD
- corrigir o status interno com base na verdade operacional
- notificar os responsaveis por WhatsApp

---

## Base encontrada no sistema legado

O repositório legado `gvcaetano190/controle-ferias` ja tem uma base funcional que devemos reaproveitar conceitualmente.

### 1. Cliente Evolution API

Arquivo:

- `C:\ferias\_tmp_legacy_controle_ferias\integrations\evolution_api.py`

Pontos importantes:

- existe uma classe `EvolutionAPI`
- recebe:
  - `url`
  - `numero`
  - `api_key`
- envia mensagem via `requests.post`
- suporta numero individual e grupo
- formata numero automaticamente
- aceita `apikey` no header
- ja possui metodos utilitarios como:
  - `enviar_mensagem`
  - `enviar_mensagem_sync`
  - `enviar_mensagem_teste`

Referencias:

- `integrations/evolution_api.py:24`
- `integrations/evolution_api.py:41`

### 2. Configuracoes legadas

Arquivo:

- `C:\ferias\_tmp_legacy_controle_ferias\config\settings.py`

Chaves ja usadas no legado:

- `EVOLUTION_API_URL`
- `EVOLUTION_NUMERO`
- `EVOLUTION_API_KEY`
- `EVOLUTION_ENABLED`
- `SYNC_NOTIF_HOUR`
- `SYNC_NOTIF_MINUTE`
- `SYNC_NOTIF_ENABLED`
- `EVOLUTION_NUMERO_SYNC`

Referencias:

- `config/settings.py:41`
- `config/settings.py:61`

### 3. Tela de configuracoes legada

Arquivo:

- `C:\ferias\_tmp_legacy_controle_ferias\frontend\modules\configuracoes.py`

O legado ja organizava:

- habilitar/desabilitar notificacao
- horario de sync com notificacao
- minuto
- numero/grupo do WhatsApp
- endpoint da Evolution
- api key
- botao para executar sync com notificacao manualmente

Referencias:

- `frontend/modules/configuracoes.py:119`
- `frontend/modules/configuracoes.py:152`
- `frontend/modules/configuracoes.py:159`

### 4. Jobs legadas com notificacao

Arquivo:

- `C:\ferias\_tmp_legacy_controle_ferias\scheduler\jobs.py`

O legado ja tinha:

- notificacao em sync automatica
- numero especifico para sync
- controle de horarios
- separacao entre sync normal e sync com notificacao

Referencias:

- `scheduler/jobs.py:135`
- `scheduler/jobs.py:159`

---

## Leitura do sistema atual

O sistema atual em Django ja tem uma base excelente para absorver isso do jeito certo:

### 1. Configuracao operacional central

Arquivos:

- [apps/core/models.py](/C:/ferias/apps/core/models.py)
- [apps/core/admin.py](/C:/ferias/apps/core/admin.py)

Hoje ja existe um singleton operacional (`OperationalSettings`) no admin.

Isso mostra dois caminhos possiveis:

1. colocar tudo dentro de `OperationalSettings`
2. criar um app proprio `notifications` com modelos proprios e integra-lo ao admin

Minha recomendacao:

- criar app proprio `notifications`
- manter `OperationalSettings` apenas como configuracao operacional geral

Motivo:

- deixa notificacao realmente plugavel
- evita inflar o model central
- facilita reuso em outros modulos
- deixa o dominio de notificacoes autocontido

### 2. Pontos de integracao reais no sistema atual

Os pontos mais importantes para integrar notificacao sao:

- [apps/shared/services/sync.py](/C:/ferias/apps/shared/services/sync.py)
- [apps/block/business_service.py](/C:/ferias/apps/block/business_service.py)
- [apps/block/preview_service.py](/C:/ferias/apps/block/preview_service.py)

Regra recomendada:

- a sync pode detectar suspeita
- o check operacional confirma a realidade
- a notificacao so deve sair depois da divergencia ser validada pelo AD

Isso evita alerta prematuro.

---

## Decisao de arquitetura

## Escolha recomendada

Criar um novo app:

- `apps.notifications`

Esse app sera responsavel por:

- configuracao de provedores
- configuracao de destinos
- templates de mensagens
- envio
- logs de entrega
- deduplicacao
- gatilhos internos

### Vantagem

Qualquer modulo podera usar esse app depois:

- sync
- block
- kanbanize
- passwords
- scheduler
- auditoria

---

## Estrutura proposta do app

### App

- `apps/notifications/apps.py`
- `apps/notifications/models.py`
- `apps/notifications/admin.py`
- `apps/notifications/services.py`
- `apps/notifications/providers/`
- `apps/notifications/repositories.py`
- `apps/notifications/templates.py`
- `apps/notifications/tests/`

### Providers

Primeiro provider:

- `apps/notifications/providers/evolution.py`

Interface futura:

- `apps/notifications/providers/base.py`

Objetivo:

- esconder detalhes da Evolution API
- permitir no futuro:
  - email
  - webhook
  - Teams
  - Slack

---

## Modelagem recomendada

## 1. NotificationProviderConfig

Representa a configuracao do canal.

Campos sugeridos:

- `name`
- `provider_type`
  - `EVOLUTION`
- `enabled`
- `endpoint_url`
- `api_key`
- `default_instance_name` ou `instance_slug` se necessario
- `timeout_seconds`
- `created_at`
- `updated_at`

Observacao:

No seu caso, pela imagem, o endpoint completo ja parece incluir a rota final.

Entao podemos suportar os dois formatos:

1. `endpoint_url` completo
2. opcionalmente `base_url + route_template`

Para o primeiro milestone, eu recomendo:

- armazenar o endpoint completo mesmo

Isso deixa a configuracao plug and play.

## 2. NotificationTarget

Representa para onde mandar a mensagem.

Campos sugeridos:

- `name`
- `channel`
  - `WHATSAPP`
- `target_type`
  - `PERSONAL`
  - `GROUP`
- `destination`
  - ex: `120363020985287866@g.us`
- `enabled`
- `is_default`
- `description`
- `created_at`
- `updated_at`

Exemplos:

- Grupo RH
- Grupo Operacoes
- Numero pessoal Gabriel
- Grupo divergencias sync

## 3. NotificationEventRule

Define quando e para quem notificar.

Campos sugeridos:

- `event_key`
  - `sync.divergence.detected`
  - `sync.completed`
  - `block.execution.error`
- `enabled`
- `provider`
- `target`
- `send_once_per_key`
- `cooldown_minutes`
- `template_key`
- `severity`
- `created_at`
- `updated_at`

Isso deixa o app plugavel.

## 4. NotificationDelivery

Log de envio.

Campos sugeridos:

- `event_key`
- `dedupe_key`
- `provider_type`
- `target_destination`
- `payload_snapshot`
- `message_preview`
- `status`
  - `PENDING`
  - `SENT`
  - `FAILED`
  - `SKIPPED_DUPLICATE`
- `provider_response`
- `error_message`
- `sent_at`
- `created_at`

## 5. NotificationDivergenceAudit

Modelo especifico para o primeiro caso de uso.

Campos sugeridos:

- `colaborador_id`
- `usuario_ad`
- `email`
- `sistema`
- `sheet_status`
- `real_status`
- `internal_status_after_sync`
- `divergence_type`
- `source_module`
  - `SYNC`
  - `BLOCK_OPERATIONAL_CHECK`
- `dedupe_key`
- `notified_at`
- `resolved_at`
- `active`
- `details`
- `created_at`
- `updated_at`

Esse modelo resolve governanca e evita spam.

---

## Admin - desenho plug and play

Voce pediu algo igual ao modelo das imagens, com configuracao direta no admin.

Minha recomendacao e dividir em 3 areas no admin:

## 1. Provider de WhatsApp (Evolution API)

Sessao:

- `Notifications > Provider Config`

Campos:

- `Habilitar Evolution API`
- `URL Completa do Endpoint`
- `API Key`
- `Timeout`
- `Destino padrao`

Visual semelhante ao da imagem:

- bloco unico
- campos claros
- acao de teste

Botao extra no admin:

- `Enviar mensagem de teste`

## 2. Destinos

Sessao:

- `Notifications > Targets`

Campos:

- nome amigavel
- numero/grupo
- tipo do destino
- ativo
- padrao

Exemplos:

- RH - Divergencias
- Operacoes - Sync
- Grupo Block

## 3. Regras de envio

Sessao:

- `Notifications > Event Rules`

Campos:

- evento
- provider
- target
- cooldown
- deduplicacao
- template
- ativo

Isso torna o sistema plugavel de verdade.

---

## UX do admin recomendada

Para ficar no nivel que voce quer, eu faria:

### No `OperationalSettings`

Adicionar um link ou botao:

- `Abrir configuracoes de notificacao`

### No app `notifications`

Criar um `change_form_template` do admin com:

- card "Evolution API (WhatsApp)"
- card "Destino padrao"
- card "Regras de divergencia"
- botao de teste
- botao de teste de divergencia fake

---

## Contrato plugavel do app

Quero deixar o desenho do app muito claro:

### Interface de alto nivel

Servico:

- `NotificationService`

Metodos sugeridos:

- `notify(event_key, context, dedupe_key=None)`
- `notify_divergence(...)`
- `send_test_message(...)`
- `resolve_target(...)`
- `resolve_provider(...)`

### Provider interface

Classe base:

- `BaseNotificationProvider`

Metodos:

- `send_text(destination, text, metadata=None)`
- `healthcheck()`
- `format_destination(raw_destination)`

### Provider Evolution

Classe:

- `EvolutionWhatsAppProvider`

Responsabilidade:

- reaproveitar a logica do legado
- fazer POST no endpoint
- colocar `apikey` no header
- validar numero/grupo
- devolver payload normalizado

---

## Fluxo de divergencia recomendado

## Regra funcional

1. planilha entra no sistema
2. sync identifica status fraco ou suspeito
3. check operacional consulta o AD
4. AD confirma realidade
5. sistema corrige o banco interno
6. sistema registra divergencia
7. sistema dispara WhatsApp para o destino configurado
8. divergencia fica auditada e deduplicada

## Importante

Nao recomendo disparar a notificacao na sync bruta.

Recomendo disparar:

- no momento em que a divergencia estiver validada operacionalmente

Ou seja:

- `apps/block/business_service.py`
- ou um ponto de reconciliacao chamado pela sync apenas quando tiver certeza operacional

### Melhor trigger inicial

O melhor trigger para o primeiro milestone e:

- quando o check operacional detectar que a planilha dizia uma coisa
- mas o AD mostrou outra
- e o sistema sincronizou o status interno automaticamente

Esse e o evento mais confiavel para notificar.

---

## Evento inicial recomendado

### `sync.divergence.validated`

Contexto:

- usuario
- sistema
- status_planilha
- status_real_ad
- status_interno_corrigido
- data_saida
- data_retorno
- origem

Template base:

> Divergencia detectada: o usuario [NOME] consta com [SISTEMA]=[STATUS_PLANILHA] na planilha, mas o AD confirmou [STATUS_REAL]. O sistema ja normalizou o status interno para [STATUS_INTERNO]. Favor ajustar a planilha conforme a realidade.

### Exemplo especifico VPN

> Divergencia detectada: o usuario [NOME] consta com VPN liberada na planilha, mas o acesso nao existe no AD/Printi_Acesso. O sistema ja normalizou o status interno para NP. Favor ajustar a planilha conforme a realidade.

---

## Auditoria de grupo VPN

Voce destacou o `Printi_Acesso`, e isso faz todo sentido.

Plano:

1. expandir a consulta do AD atual
2. retornar explicitamente:
   - `is_in_printi_acesso`
3. incluir isso no resultado operacional
4. mapear:
   - planilha `LIBERADO`
   - AD fora do grupo
   - status interno final `NP`
5. gerar divergencia notificada

Essa checagem deve ficar centralizada na camada de integracao com AD, nao espalhada pela UI.

---

## Ordem segura de implementacao

## Fase 1 - Fundacao do app

1. criar `apps.notifications`
2. adicionar no `INSTALLED_APPS`
3. criar models:
   - `NotificationProviderConfig`
   - `NotificationTarget`
   - `NotificationEventRule`
   - `NotificationDelivery`
4. registrar admin
5. criar migrations

## Fase 2 - Provider Evolution

1. portar a logica do legado de `integrations/evolution_api.py`
2. adaptar para Django
3. remover dependencias do estilo legado/streamlit
4. criar:
   - `BaseNotificationProvider`
   - `EvolutionWhatsAppProvider`
5. criar teste de envio fake com mock de `requests.post`

## Fase 3 - Servico plugavel

1. criar `NotificationService`
2. resolver provider ativo
3. resolver target por regra
4. montar template
5. enviar
6. registrar `NotificationDelivery`
7. implementar deduplicacao

## Fase 4 - Configuracao no admin

1. criar telas admin elegantes
2. adicionar botao `Enviar mensagem de teste`
3. adicionar botao `Testar divergencia fake`
4. permitir configurar:
   - habilitado
   - endpoint
   - api key
   - numero/grupo
   - horario de sync com notificacao

## Fase 5 - Divergencia operacional

1. criar modelo de auditoria de divergencia
2. disparar evento apenas quando AD validar conflito
3. atualizar status interno
4. registrar auditoria
5. disparar notificacao

## Fase 6 - Reuso no scheduler e outros modulos

1. migrar notificacoes de sync para usar `NotificationService`
2. migrar notificacoes futuras do block
3. permitir uso por outros apps

---

## Regras de deduplicacao

Para evitar spam no WhatsApp:

### Chave recomendada

- `usuario_ad + sistema + divergence_type + data_retorno`

### Regras

- se a mesma divergencia ja foi notificada e continua ativa, nao reenviar
- reenviar apenas se:
  - a divergencia foi resolvida e reapareceu
  - ou passou do cooldown configurado

### Status do ciclo

- `ACTIVE`
- `NOTIFIED`
- `RESOLVED`
- `REOPENED`

---

## Onde integrar no sistema atual

## Ponto 1 - check operacional do block

Arquivo principal:

- [apps/block/business_service.py](/C:/ferias/apps/block/business_service.py)

Melhor local logico:

- no trecho em que o sistema identifica `OUTCOME_SYNCED`
- porque ali o AD ja validou a verdade

Quando isso acontecer:

1. registrar divergencia
2. corrigir o status interno
3. disparar `NotificationService.notify(...)`

## Ponto 2 - sync

Arquivo:

- [apps/shared/services/sync.py](/C:/ferias/apps/shared/services/sync.py)

Nesse ponto eu recomendo:

- apenas registrar suspeita
- nao disparar WhatsApp ainda

Motivo:

- a sync so olha dado importado
- o check operacional e quem confirma a divergencia real

## Ponto 3 - scheduler

Arquivo futuro de uso:

- task de sync
- task operacional

Estratégia:

- o scheduler nao envia direto via Evolution
- ele chama `NotificationService`

Assim o canal fica desacoplado da job.

---

## Compatibilidade com o legado

O que reaproveitar:

- formato do endpoint completo
- header `apikey`
- formatacao de numero/grupo
- rotina de teste de envio
- ideia de numero/grupo alternativo para notificacoes
- ideia de horario de sync com notificacao

O que NAO copiar literalmente:

- persistencia em `.env`
- acoplamento direto em scheduler/jobs
- logica espalhada em frontend Streamlit

No Django atual, o ideal e:

- persistir no banco
- configurar no admin
- usar services desacoplados

---

## Modelo de configuracao no admin

### Provider

- Nome: `Evolution API (WhatsApp)`
- Habilitado: `true/false`
- URL Completa do Endpoint
- API Key
- Timeout
- Observacoes

### Destino

- Nome: `Grupo RH Divergencias`
- Canal: `WhatsApp`
- Tipo: `Grupo`
- Destino: `120363020985287866@g.us`
- Ativo
- Padrao

### Regra

- Evento: `sync.divergence.validated`
- Provider: `Evolution API`
- Destino: `Grupo RH Divergencias`
- Deduplicar: `sim`
- Cooldown: `1440`
- Ativo

---

## Casos de teste recomendados

## 1. Provider

- envia texto com sucesso
- falha por URL vazia
- falha por API key invalida
- falha por timeout
- formata grupo corretamente
- formata numero pessoal corretamente

## 2. Admin

- salva provider
- salva target
- salva rule
- botao de teste envia mensagem

## 3. Dedupe

- mesma divergencia nao envia duas vezes
- divergencia resolvida e reaberta envia novamente

## 4. Fluxo operacional

- planilha diz `LIBERADO`
- AD diz `fora do grupo`
- sistema muda para `NP`
- cria auditoria
- envia WhatsApp
- nova sync igual nao reenvia spam

## 5. Integracao funcional

- provider habilitado
- destino ativo
- regra ativa
- evento emitido
- mensagem entregue e logada

---

## Resultado esperado

Ao final dessa implementacao, o sistema tera:

1. um app de notificacoes reutilizavel
2. configuracao plug and play no admin
3. envio via WhatsApp reaproveitando a base do legado
4. auditoria completa de entregas e divergencias
5. desacoplamento entre scheduler, sync, block e canal de notificacao
6. uma base pronta para plugar notificacao em qualquer fluxo futuro

---

## Recomendacao final

Se a meta e fazer direito e sem criar um monolito de excecoes, a melhor abordagem e:

- criar `apps.notifications`
- portar a Evolution API para provider Django
- configurar tudo no admin
- disparar notificacao apenas depois da validacao operacional do AD
- deixar sync e scheduler consumirem esse app, e nao enviarem WhatsApp por conta propria

Esse e o caminho mais limpo, escalavel e seguro para o que voce quer construir.
