# Roadmap: Orquestração de Conformidade e Alertas de Divergência

Este documento foca exclusivamente no próximo grande marco do sistema: garantir que a planilha externa reflita a realidade operacional do AD através de notificações automatizadas.

### 🧠 Princípios do Fluxo
1.  **A "Verdade" é o AD**: Estabelece-se uma hierarquia clara. Se houver conflito entre a planilha e o Check Operacional (robô) no Active Directory, o sistema sempre confia no AD.
2.  **Sistema Auto-Corretivo**: Se o AD indicar que o usuário já está desbloqueado (e a data de retorno confirma isso), o sistema atualiza o banco de dados interno automaticamente.
3.  **Vigia Silencioso**: O Dashboard permanece limpo e focado em ação. As divergências são tratadas via notificações externas (WhatsApp).
4.  **Ação Reversa**: O sistema força a correção da fonte (planilha) através de alertas diretos aos responsáveis.

---

### 🛠️ Plano de Implementação (Passo a Passo)

#### 1. Auditoria de Grupos de VPN (Printi_Acesso)
*   **Ação**: Expandir o `Check Operacional` para verificar se o usuário está dentro do grupo de segurança `Printi_Acesso` no AD.
*   **Lógica**: Se a planilha marcar `LIBERADO` mas o usuário não estiver no grupo no AD, o sistema altera o status interno para `NP` (Não Presente) ou `NB` automaticamente.

#### 2. Integração com Microserviço de WhatsApp
*   **Base Tecnológica**: Utilizar a lógica de envio já funcional do projeto legado: [Controle de Férias Legado](https://github.com/gvcaetano190/controle-ferias).
*   **Template de Alerta**: 
    > *"⚠️ **Divergência Detectada**: O usuário **[NOME]** consta com VPN na planilha, mas o acesso não existe no AD. O sistema já normalizou o status interno para garantir a segurança, favor ajustar a planilha conforme a realidade."*

#### 3. Gatilho de Notificação (Divergência)
*   **Momento**: O disparo ocorre no serviço de sincronização (`apps/shared/services/sync.py`) quando a reconciliação detecta que o status da planilha é "fraco" ou incorreto comparado ao status validado pelo AD.
*   **Frequência**: Um alerta por divergência detectada para evitar spam, mantendo a planilha sempre higienizada.

#### 4. Manutenção do Front-End Clean
*   Não adicionar colunas de erro no dashboard.
*   Manter apenas o status efetivo na tela, movendo a complexidade da "briga" entre planilha vs AD para os bastidores e para o WhatsApp.

---

### 🚀 Impacto Esperado
*   **Governança Ativa**: O RH/Gestores são notificados em tempo real sobre erros de preenchimento.
*   **Segurança**: Garantia de que nenhum acesso de VPN fique aberto por erro de digitação na planilha.
*   **Integridade**: A planilha do Google Sheets deixará de ser um "cemitério de dados" e passará a ser um espelho fiel da infraestrutura.
