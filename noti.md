# Bot de Consulta WhatsApp — Plano de Implementação

## Objetivo

Fazer o sistema **receber mensagens do WhatsApp** via Evolution API (webhook),
interpretar comandos em linguagem natural e responder com dados do banco.

Exemplo de uso:
```
Você:   quem sai de ferias hj
Bot:    📅 Saídas de hoje (27/04/2026):
        • Alice Santana — Tecnologia VII
        • Bruno Lima — Large Format I
        • Carla Matos — Packaging II
        Total: 3 pessoas
```

---

## O que já existe (não precisa criar)

| Componente | Arquivo | Status |
|---|---|---|
| Provider Evolution API | `apps/notifications/providers/evolution.py` | ✅ Pronto |
| Envio de texto WhatsApp | `apps/notifications/services.py` | ✅ Pronto |
| Config de provider no Admin | `NotificationProviderConfig` | ✅ Pronto |
| Modelos de férias/colaboradores | `apps/people/models.py` | ✅ Pronto |

---

## Arquitetura do Bot

```
WhatsApp → Evolution API → Webhook (POST /bot/webhook/) → Django
              ↑                                               ↓
              └──────────── Resposta (send_text) ←── BotService (interpreta + consulta)
```

### Fluxo completo:
1. Usuário manda mensagem no WhatsApp
2. Evolution API recebe e dispara um `POST` para o endpoint `/bot/webhook/`
3. Django processa o payload, extrai o texto e o número do remetente
4. `BotService` interpreta o comando (via match de palavras-chave)
5. Consulta o banco (models `Ferias`, `Colaborador`)
6. Formata a resposta e chama `EvolutionWhatsAppProvider.send_text()` de volta

---

## Comandos planejados

| Comando (exemplos) | Resposta |
|---|---|
| `quem sai de ferias hj` / `saidas hoje` | Lista de quem começa férias hoje |
| `quem volta hoje` / `retornos hj` | Lista de quem retorna hoje |
| `quem esta de ferias` / `ausentes agora` | Lista de quem está fora agora |
| `ferias de abril` / `ferias 04` | Resumo do mês solicitado |
| `ajuda` / `help` / `comandos` | Lista de comandos disponíveis |

---

## Etapas de Implementação

### Fase 1 — Webhook Receptor (1 arquivo novo)

**Novo:** `apps/bot/views.py`

```python
# Recebe o webhook da Evolution API
# Extrai: número do remetente + texto da mensagem
# Chama BotService.handle(sender, text)
# Retorna HTTP 200 sempre (Evolution API não espera conteúdo)
```

**Novo:** `apps/bot/urls.py`
```
POST /bot/webhook/  →  bot.views.webhook
```

**Registrar em:** `project/urls.py`

---

### Fase 2 — BotService (interpretador + executor)

**Novo:** `apps/bot/services.py`

```python
class BotService:
    def handle(self, sender: str, text: str) -> None:
        command = self.parse_command(text)
        response = self.execute(command)
        self.reply(sender, response)

    def parse_command(self, text: str) -> str:
        # Match por palavras-chave simples (sem IA)
        text_lower = text.lower().strip()
        if any(w in text_lower for w in ["sai", "saida", "saidah"]):
            if any(w in text_lower for w in ["hj", "hoje", "today"]):
                return "saidas_hoje"
        if any(w in text_lower for w in ["volta", "retorno"]):
            if any(w in text_lower for w in ["hj", "hoje"]):
                return "retornos_hoje"
        if any(w in text_lower for w in ["ausente", "ferias agora", "esta de ferias"]):
            return "ausentes_agora"
        if any(w in text_lower for w in ["ajuda", "help", "comandos"]):
            return "ajuda"
        return "desconhecido"

    def execute(self, command: str) -> str:
        # Chama BotQueryService para buscar no banco
        ...

    def reply(self, sender: str, text: str) -> None:
        # Usa o EvolutionWhatsAppProvider existente
        ...
```

---

### Fase 3 — BotQueryService (consultas ao banco)

**Novo:** `apps/bot/queries.py`

```python
class BotQueryService:
    def saidas_hoje(self) -> list[Colaborador]: ...
    def retornos_hoje(self) -> list[Colaborador]: ...
    def ausentes_agora(self) -> list[Colaborador]: ...
    def resumo_mes(self, month: int, year: int) -> dict: ...
```

Consultas diretas nos models `Ferias` e `Colaborador` já existentes.

---

### Fase 4 — Segurança (opcional mas recomendado)

Problema: qualquer pessoa que souber o URL do webhook pode mandar mensagens.

**Solução simples:** Whitelist de números no admin.

```python
class BotAllowedSender(models.Model):
    phone_number = models.CharField(max_length=30)
    label = models.CharField(max_length=100)  # ex: "Gabriel - Admin"
    enabled = models.BooleanField(default=True)
```

O webhook verifica se o número do remetente está na whitelist.
Se não estiver, responde "Acesso não autorizado." ou ignora silenciosamente.

---

### Fase 5 — Configuração na Evolution API

No painel da sua Evolution API, configurar o Webhook:

```
URL:    https://seu-dominio/bot/webhook/
Método: POST
Eventos: messages.upsert  (mensagem recebida)
```

Para teste local, usar **ngrok** para expor o Django:
```bash
ngrok http 8000
# URL gerada: https://xxxx.ngrok.io
# Webhook:    https://xxxx.ngrok.io/bot/webhook/
```

---

## Estrutura de arquivos novos

```
apps/
  bot/
    __init__.py
    apps.py
    urls.py
    views.py      ← webhook receptor
    services.py   ← interpretador de comandos
    queries.py    ← consultas ao banco
    models.py     ← BotAllowedSender (whitelist)
    admin.py      ← gerenciar whitelist pelo admin
    migrations/
```

---

## Payload do webhook da Evolution API

A Evolution API envia algo assim no POST:

```json
{
  "event": "messages.upsert",
  "data": {
    "key": {
      "remoteJid": "5511999999999@s.whatsapp.net",
      "fromMe": false
    },
    "message": {
      "conversation": "quem sai de ferias hj"
    }
  }
}
```

O `BotService` extrai:
- `sender` = `"5511999999999"` (remove o `@s.whatsapp.net`)
- `text`   = `"quem sai de ferias hj"`

E ignora mensagens onde `fromMe == true` (evita loop de resposta).

---

## Dependências

Nenhuma dependência nova necessária. Tudo que o bot precisa já está instalado:
- `requests` → para chamar a Evolution API de volta
- `django` → views, models, admin
- `apps.notifications.providers.evolution` → já tem o `send_text`

---

## Sequência de implementação sugerida

- [ ] Fase 1: Criar `apps/bot/` com webhook receptor básico (retorna 200)
- [ ] Testar recebimento com ngrok + Evolution API
- [ ] Fase 2: Adicionar `BotService` com parse de comandos
- [ ] Fase 3: Conectar `BotQueryService` ao banco
- [ ] Fase 4: Implementar whitelist de números
- [ ] Fase 5: Configurar webhook na Evolution API em produção

---

## Notas

- O bot **não precisa de IA** para os comandos iniciais — simples match de palavras-chave é suficiente e mais robusto para português informal.
- A infra de envio (`EvolutionWhatsAppProvider`) já está pronta e testada para **envio**. Este plano adiciona apenas o lado do **recebimento**.
- O número de destino para a resposta é o próprio `remoteJid` de quem enviou.
