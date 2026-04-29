# Processo da Aplicacao de Controle de Ferias

Documento tecnico que descreve todo o fluxo da aplicacao, desde a sincronizacao da planilha ate a execucao final de bloqueio e desbloqueio no AD e no TOTVS.

---

## Visao Geral da Esteira

```
Planilha (SharePoint/OneDrive)
        ↓  sincronizacao
     Banco (SQLite/PostgreSQL)
        ↓  pre-lista
     Modulo Block
        ↓  check operacional (AD + TOTVS)
     Lista Final
        ↓  execucao
     AD  +  TOTVS  +  Notificacao WhatsApp
```

---

## 1. Sincronizacao da Planilha

### O que faz
Baixa a planilha de ferias do SharePoint/OneDrive e popula o banco local com os registros de colaboradores e suas ferias.

### Onde vive
- `apps/sync/` — tarefa de sincronizacao
- `apps/people/` — modelos `Colaborador`, `Ferias`, `Acesso`

### Como funciona
1. A task `run_spreadsheet_sync` e acionada pelo agendador (Django-Q) ou manualmente via bot com o comando `sincronizar`.
2. A planilha e baixada e lida. Cada linha vira um registro de `Ferias` ligado a um `Colaborador`.
3. O sistema faz `upsert`: atualiza quem ja existe e insere quem e novo.
4. O resultado (total inseridos, atualizados, removidos) e notificado via WhatsApp.

### Cache local
- A planilha baixada fica em cache por um numero de minutos configuravel em `OperationalSettings`.
- Enquanto o cache for valido, a proxima sync usa o arquivo local sem baixar novamente.
- O status do cache aparece na tela do modulo `block` e e exibido pelo bot.

### Campos sincronizados
| Campo          | Origem na planilha          |
|----------------|-----------------------------|
| nome           | Nome do colaborador         |
| email          | E-mail corporativo          |
| login_ad       | Login do Active Directory   |
| departamento   | Setor / area                |
| gestor         | Nome do gestor              |
| data_saida     | Data de inicio das ferias   |
| data_retorno   | Data de retorno das ferias  |

---

## 2. Pre-lista (Preview do Block)

### O que e
Uma visualizacao em tempo real de quem o sistema pretende bloquear ou desbloquear **hoje**, antes de qualquer acao ser executada.

### Onde vive
- `apps/block/preview_service.py` — `BlockPreviewService.previsualizar_verificacao_block()`
- `templates/block/index.html` — tela principal do modulo

### Regras da pre-lista
| Caso                       | Acao prevista |
|----------------------------|---------------|
| `data_saida <= hoje < data_retorno` | BLOQUEAR |
| `data_retorno <= hoje` e esta bloqueado | DESBLOQUEAR |
| Ja processado hoje com SUCESSO | Nao aparece |
| Status AD = `BLOQUEADO` e acao e bloqueio | IGNORAR |
| Status AD = `LIBERADO` e acao e desbloqueio | IGNORAR |

### Coluna TOTVS na pre-lista
A pre-lista exibe o status atual do TOTVS no banco (nao consulta a API neste momento). Os valores possiveis sao:
- `LIBERADO` — usuario ativo no TOTVS.
- `BLOQUEADO` — usuario inativo no TOTVS.
- `NP` — nao encontrado ou nao cadastrado.
- `NB` — nao verificado ainda.
- `-` — sem registro de TOTVS no banco.

### Bot
O comando `previsao` retorna a pre-lista formatada no WhatsApp.

---

## 3. Check Operacional

### O que e
Uma verificacao completa que consulta o **estado real** de cada usuario no **AD** e no **TOTVS**, compara com o banco local e decide quem realmente precisa de acao.

### Onde vive
- `apps/block/business_service.py` — `BlockBusinessService.processar_verificacao_operacional_block()`
- `apps/block/models.py` — `BlockVerificationRun`, `BlockVerificationItem`
- `integrations/ad/` — consulta ao Active Directory
- `apps/totvs/services.py` — `TotvsIntegrationService.consultar_usuarios_operacionais()`

### Fluxo do check

```
Pre-lista de candidatos
    ↓
Para cada candidato:
    ├─ Consulta AD em lote (consultar_usuarios_ad)
    └─ Consulta TOTVS em lote (TotvsIntegrationService.consultar_usuarios_operacionais)
    ↓
Para cada resultado:
    ├─ Compara status real do AD com o banco
    │    └─ Se divergiu → sincroniza o banco e notifica
    ├─ Compara status real do TOTVS com o banco
    │    └─ Se divergiu → sincroniza o banco
    ├─ Verifica se AD ja esta no estado desejado
    └─ Verifica se TOTVS ja esta no estado desejado
    ↓
Decide acao final:
    ├─ BLOQUEAR / DESBLOQUEAR → vai para a lista final
    ├─ IGNORAR (sincronizado) → banco atualizado, sem acao
    └─ IGNORAR (ja correto)  → sem acao necessaria
```

### O que fica salvo
Cada item do check e salvo como `BlockVerificationItem` com:
- `ad_status_banco_antes` / `ad_status_real` / `ad_status_banco_depois`
- `vpn_status_banco_antes` / `vpn_status_real` / `vpn_status_banco_depois`
- `totvs_status_banco_antes` / `totvs_status_real` / `totvs_status_banco_depois`
- `acao_inicial`, `acao_final`, `resultado_verificacao`, `motivo`

### Regras do TOTVS no check
| Status TOTVS real | Situacao              | Acao                        |
|-------------------|-----------------------|-----------------------------|
| `LIBERADO`        | Esperado `BLOQUEADO`  | Entra na lista final        |
| `BLOQUEADO`       | Esperado `LIBERADO`   | Entra na lista final        |
| `NP` (404)        | Nao existe no TOTVS   | Banco vira `NP`, sem acao   |
| `LIBERADO`        | Ja correto            | Removido da lista final     |
| `BLOQUEADO`       | Ja correto            | Removido da lista final     |

### Bot
O comando `verificacao` aciona o check operacional e retorna o resumo no WhatsApp.

---

## 4. Lista Final

### O que e
O resultado do check operacional: a lista curada de colaboradores que **realmente precisam** de acao (bloqueio ou desbloqueio) no AD e/ou no TOTVS.

### Onde vive
- `apps/block/preview_service.py` — `BlockPreviewService.ver_detalhes_verificacao_operacional()`
- `apps/block/models.py` — `BlockVerificationRun.items` com `acao_final IN ('BLOQUEAR', 'DESBLOQUEAR')`

### Estrutura da lista final
| Campo           | Descricao                                           |
|-----------------|-----------------------------------------------------|
| colaborador     | Nome do colaborador                                 |
| acao_final      | BLOQUEAR ou DESBLOQUEAR                             |
| sistemas        | AD e/ou TOTVS, dependendo do que ainda precisa acao |
| status reais    | AD, VPN, TOTVS consultados na hora                  |

### Bot
O comando `lista final` exibe o resumo da ultima verificacao operacional com os itens pendentes.

---

## 5. Execucao Final (Block/Desblock)

### O que faz
Executa de fato as acoes de bloqueio e desbloqueio no **AD** e no **TOTVS** para todos os usuarios da lista final.

### Onde vive
- `apps/block/business_service.py` — `BlockBusinessService.processar_verificacao_block()`
- `integrations/ad/executor.py` — `bloquear_usuarios_ad`, `desbloquear_usuarios_ad`
- `apps/totvs/services.py` — `bloquear_usuarios_operacionais`, `desbloquear_usuarios_operacionais`

### Fluxo da execucao

```
Lista final (BlockVerificationItems com acao_final != IGNORAR)
    ↓
Para cada candidato:
    ├─ precisa executar no AD?   → sim/nao (baseado no status atual AD)
    └─ precisa executar no TOTVS? → sim/nao (baseado no status atual TOTVS)
    ↓
Executa AD em lote (bloquear_usuarios_ad / desbloquear_usuarios_ad)
Executa TOTVS em lote (bloquear_usuarios_operacionais / desbloquear_usuarios_operacionais)
    ↓
Para cada resultado:
    ├─ Atualiza status no banco (AD, VPN, TOTVS)
    ├─ Salva em BlockProcessing (historico)
    └─ Acumula contadores (bloqueios, desbloqueios, erros, ignorados)
    ↓
Notifica resultado via WhatsApp
```

### Regras de execucao TOTVS
| Status TOTVS no banco | Acao esperada | Executa TOTVS? |
|-----------------------|---------------|----------------|
| `LIBERADO`            | BLOQUEIO      | Sim            |
| `NB` (nao verificado) | BLOQUEIO      | Nao*           |
| `NP` (nao encontrado) | Qualquer      | Nao            |
| `BLOQUEADO`           | DESBLOQUEIO   | Sim            |
| `BLOQUEADO`           | BLOQUEIO      | Nao (ja certo) |
| `LIBERADO`            | DESBLOQUEIO   | Nao (ja certo) |

> *`NB` nao entra na fila de execucao TOTVS porque nao ha certeza do estado real. O check operacional primeiro consulta e sincroniza o banco antes de executar.

### dry_run
Se `BlockConfig.dry_run = True`, o sistema simula as acoes sem executar nada de verdade. O historico e salvo com resultado `IGNORADO` e mensagem de simulacao.

### Historico
Cada execucao gera um registro em `BlockProcessing` com:
- `acao` (BLOQUEIO / DESBLOQUEIO)
- `resultado` (SUCESSO / ERRO / IGNORADO / SINCRONIZADO)
- `ad_status`, `vpn_status`, `totvs_status`
- `mensagem` com detalhe do que aconteceu

### Bot
O comando `executar block` aciona a execucao final. So funciona se ja existir uma verificacao operacional concluida hoje.

---

## 6. Modulo TOTVS

### O que e
Um modulo dedicado que gerencia toda a integracao com a API REST do TOTVS Protheus.

### Arquitetura

```
integrations/totvs/client.py       ← cliente HTTP puro (sem Django)
apps/totvs/credentials.py          ← cofre de credenciais (keyring)
apps/totvs/models.py               ← TotvsIntegrationConfig (banco)
apps/totvs/services.py             ← TotvsIntegrationService (logica)
apps/totvs/admin.py                ← interface admin do Django
apps/totvs/forms.py                ← formulario do admin
apps/totvs/management/commands/    ← comandos manage.py
```

### Configuracao (admin)
O admin do TOTVS (`/admin/totvs/totvs...`) permite:
- Informar a URL base do servidor TOTVS.
- Informar o `TenantId` (padrao `01,01`).
- Salvar usuario e senha no cofre seguro (keyring do Windows).
- Ver o status da ultima requisicao de teste.
- Desativar a integracao sem apagar a configuracao.

### Seguranca das credenciais
- O usuario e senha nunca sao gravados em texto puro no banco.
- Sao guardados no `keyring` do sistema operacional com uma chave gerada automaticamente (`totvs-<uuid>`).
- O admin exibe apenas o status: `"Credencial armazenada no cofre"` ou `"Referencia sem credencial no cofre"`.

### API utilizada
| Operacao      | Metodo | Endpoint                                     |
|---------------|--------|----------------------------------------------|
| Consultar     | GET    | `/rest/api/framework/v1/users/{login}`       |
| Bloquear      | PUT    | `/rest/api/framework/v1/users/{id}`          |
| Desbloquear   | PUT    | `/rest/api/framework/v1/users/{id}`          |
| Header fixo   | —      | `TenantId: 01,01`                            |
| Autenticacao  | —      | Basic Auth (usuario:senha)                   |

### Correcao do email vazio no PUT
O TOTVS exige que o campo `emails[0].value` (email primario) esteja preenchido no payload do PUT. Caso o GET retorne o email vazio, o sistema usa o email do banco local como fallback para nao quebrar a requisicao.

### Comandos manage.py disponiveis
| Comando                  | O que faz                                          |
|--------------------------|----------------------------------------------------|
| `test_totvs_api <login>` | Testa GET (e opcionalmente PUT) para um usuario    |
| `set_totvs_credentials`  | Salva usuario e senha no cofre via linha de comando|
| `sync_totvs_status`      | Sincroniza status TOTVS de todos os colaboradores  |

---

## 7. Integracao AD (Active Directory)

### O que e
Integracao com o Active Directory da empresa via script PowerShell ou ldap3, encapsulada em `integrations/ad/`.

### Operacoes disponiveis
| Funcao                  | O que faz                                  |
|-------------------------|--------------------------------------------|
| `consultar_usuario_ad`  | Retorna status atual (LIBERADO/BLOQUEADO)  |
| `consultar_usuarios_ad` | Consulta em lote (varios logins)           |
| `bloquear_usuario_ad`   | Desabilita conta no AD                     |
| `bloquear_usuarios_ad`  | Bloqueia em lote                           |
| `desbloquear_usuario_ad`| Habilita conta no AD                       |
| `desbloquear_usuarios_ad`| Desbloqueia em lote                       |

### Resultado padrao
Cada resultado AD retorna:
```python
{
    "success": True/False,
    "usuario_ad": "joao.silva",
    "ad_status": "BLOQUEADO",
    "vpn_status": "NP",
    "message": "...",
    "user_found": True,
    "is_enabled": False,
    "is_in_printi_acesso": False,
}
```

### VPN
O status VPN e derivado da pertenca ao grupo `printi-acesso` no AD. Se o usuario esta no grupo → `LIBERADA`. Se nao esta → `NP`.

---

## 8. Bot WhatsApp

### Comandos disponiveis

| Comando                          | O que faz                                         |
|----------------------------------|---------------------------------------------------|
| `buscar <nome/email/login>`      | Ficha do colaborador com status AD e VPN          |
| `gestor <nome/email>`            | Nome e email do gestor                            |
| `totvs <nome/email/login>`       | Consulta status real no TOTVS                     |
| `totvs bloquear <identificador>` | Bloqueia usuario no TOTVS                         |
| `totvs desbloquear <identificador>` | Desbloqueia usuario no TOTVS                  |
| `previsao`                       | Pre-lista do dia (quem sera bloqueado/desbloqueado)|
| `sincronizar`                    | Executa sync da planilha                          |
| `verificacao`                    | Executa o check operacional                       |
| `lista final`                    | Exibe a lista final da ultima verificacao         |
| `executar block`                 | Executa os bloqueios/desbloqueios da lista final  |
| `dashboard [mes]`                | Envia screenshot do dashboard como imagem         |
| `saidas hoje`                    | Quem comeca ferias hoje                           |
| `retornos hoje`                  | Quem volta de ferias hoje                         |
| `ausentes agora`                 | Quem esta de ferias agora                         |
| `agenda`                         | Proximas execucoes agendadas no Django-Q          |
| `ajuda` / `oi`                   | Menu interativo com botoes                        |

### Como o bot localiza um colaborador
1. Busca por `login_ad` (exato, case-insensitive).
2. Busca por `email` (exato, case-insensitive).
3. Busca por `nome` (icontains).
4. Usa o `login_ad` do colaborador encontrado para consultar o TOTVS.

### Resposta TOTVS no bot
```
🧾 Totvs - NOME DA PESSOA
STATUS: BLOQUEADO
```
ou `DESBLOQUEADO` ou `NAO ENCONTRADO`.

---

## 9. Agendamento (Django-Q)

### Tasks configuradas
| Task                           | Frequencia tipica | O que faz                    |
|--------------------------------|-------------------|------------------------------|
| Sincronizar planilha           | Diaria (manha)    | Atualiza banco com planilha  |
| Check operacional              | Diario (manha)    | Consulta AD e TOTVS          |
| Execucao de block/desblock     | Diario (pos check)| Bloqueia/desbloqueia         |
| Resumo diario (notificacao)    | Diario            | Envia resumo no WhatsApp     |

### Consultar no bot
O comando `agenda` lista todas as tasks agendadas e suas proximas execucoes.

---

## 10. Banco de Dados

### Tabelas principais

| Tabela                        | Modulo  | Descricao                                       |
|-------------------------------|---------|-------------------------------------------------|
| `people_colaborador`          | people  | Cadastro dos colaboradores                      |
| `people_ferias`               | people  | Registros de ferias por colaborador             |
| `people_acesso`               | people  | Status de acesso por sistema (AD, VPN, TOTVS)   |
| `block_configs`               | block   | Configuracao do modulo block (dry_run, etc)     |
| `block_processings`           | block   | Historico de todas as execucoes                 |
| `block_verification_runs`     | block   | Registros de cada check operacional             |
| `block_verification_items`    | block   | Itens de cada check com status AD e TOTVS       |
| `totvs_integration_configs`   | totvs   | Configuracao da integracao TOTVS                |

### Tabela `people_acesso`
Armazena o ultimo status conhecido de cada sistema para cada colaborador.

| Coluna      | Descricao                                         |
|-------------|---------------------------------------------------|
| colaborador | FK para Colaborador                               |
| sistema     | `"AD PRIN"`, `"VPN"`, `"TOTVS"`, `"Gmail"`, etc  |
| status      | `LIBERADO`, `BLOQUEADO`, `NP`, `NB`, etc          |
| updated_at  | Ultima atualizacao                                |

---

## 11. Fluxo Completo Resumido

```
1. SYNC        manage.py ou bot "sincronizar" ou agendador
               → baixa planilha → popula people_colaborador + people_ferias

2. PRE-LISTA   Tela do block ou bot "previsao"
               → quem sai/volta hoje com status banco atual

3. CHECK OP    manage.py ou bot "verificacao" ou agendador
               → consulta AD em lote + TOTVS em lote
               → sincroniza divergencias no banco
               → gera BlockVerificationRun com os itens da lista final

4. LISTA FINAL Tela do block ou bot "lista final"
               → mostra quem esta na lista curada pos-check

5. EXECUCAO    manage.py ou bot "executar block" ou agendador
               → bloqueia/desbloqueia no AD (ldap/PowerShell)
               → bloqueia/desbloqueia no TOTVS (API REST)
               → salva em BlockProcessing
               → notifica resultado no WhatsApp
```

---

## 12. Estados possiveis por sistema

### AD (campo `ad_status`)
| Valor      | Significado                          |
|------------|--------------------------------------|
| `LIBERADO` | Conta ativa no AD                    |
| `BLOQUEADO`| Conta desabilitada no AD             |
| `NP`       | Usuario nao encontrado no AD         |
| `ERRO`     | Falha de comunicacao ou permissao    |

### VPN (campo `vpn_status`)
| Valor      | Significado                          |
|------------|--------------------------------------|
| `LIBERADA` | Usuario esta no grupo `printi-acesso`|
| `NP`       | Usuario nao esta no grupo ou nao foi encontrado |

### TOTVS (campo `totvs_status`)
| Valor      | Significado                                      |
|------------|--------------------------------------------------|
| `LIBERADO` | `active=true` no TOTVS                           |
| `BLOQUEADO`| `active=false` no TOTVS                          |
| `NP`       | Usuario nao existe no TOTVS (404)                |
| `NB`       | Nao verificado (nunca consultou o TOTVS ainda)   |
| `ERRO`     | Falha ao consultar a API do TOTVS                |
