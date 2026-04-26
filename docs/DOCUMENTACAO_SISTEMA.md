# Documentação Técnica e Funcional: Controle de Férias

## 1. Visão Geral do Sistema
O **Sistema de Controle de Férias** é uma aplicação web monolítica moderna projetada para gerenciar, auditar e automatizar o bloqueio e desbloqueio de acessos (VPN e Active Directory) de colaboradores que entram ou retornam de férias.

Nascida de uma migração de uma antiga base em *Streamlit*, a aplicação agora repousa sobre uma infraestrutura robusta em **Django**, proporcionando interfaces ricas via **HTMX**, agendamento resiliente de tarefas em segundo plano via **Django Q2**, e persistência de dados em **SQLite**.

---

## 2. Arquitetura Tecnológica
O projeto utiliza um padrão de arquitetura em camadas (Layered Architecture) inspirado em princípios SOLID:

*   **Apresentação (Frontend)**: Construído com HTML renderizado no servidor (Django Templates), estilizado de forma fluída com **Tailwind CSS**, e utilizando **HTMX** para interações dinâmicas (modais, filtros, loaders) sem requerer uma Single Page Application (SPA) complexa.
*   **Controle (Views)**: Camada fina que apenas orquestra o tráfego de requisições HTTP para os serviços de negócio.
*   **Negócios (Services)**: Onde a inteligência reside. Dividido estritamente para manter a Responsabilidade Única (ex: *PreviewService* apenas empacota dados para leitura, *BusinessService* toma as decisões de bloqueio).
*   **Integração (External)**: Camada de comunicação com o ecossistema Windows corporativo, utilizando chamadas seguras (Subprocessos) para executar rotinas PowerShell no Active Directory.
*   **Persistência (Repositories/Models)**: Abstrações do Django ORM interagindo com o banco SQLite local.
*   **Background / Mensageria**: **Django Q2** atua como o agendador de tarefas cron e processador de filas assíncronas, utilizando o próprio ORM do Django como *Broker*.

---

## 3. Principais Módulos da Aplicação

### 3.1. Dashboard (`apps/dashboard`)
Fornece métricas e alertas sobre o estado atual dos usuários em férias. Utiliza dados cacheados e agregados para montagem de gráficos e totalizadores rápidos de acessos bloqueados ou pendentes.

### 3.2. Sync (`apps/sync`)
Responsável por garantir que o Banco de Dados local seja o reflexo fiel da planilha-mestre do RH (Google Sheets/Excel).
*   **O que faz**: Efetua o download da planilha, aplica higienização, descobre novos colaboradores, e sincroniza as datas de férias.
*   **Como opera**: Através do agendamento periódico no Django Q2 chamando o `SpreadsheetSyncService`.

### 3.3. Block (`apps/block`)
O módulo mais vital do sistema. Responsável por garantir as travas de segurança do Active Directory baseadas no calendário de férias.

---

## 4. O Fluxo de Execução (Deep Dive no Módulo Block)

O processo de verificação e bloqueio é dividido em etapas de salvaguarda para evitar bloqueios acidentais e melhorar o desempenho:

### Etapa 1: Pré-visualização (Preview)
Quando um administrador ou o robô avalia a situação do dia, o sistema passa pela fase de *Preview* (leitura passiva):
1. Cruza os dados da tabela de `Pessoas` com as datas da tabela de `Férias`.
2. Identifica quem sai de férias **hoje** (Candidato a Bloqueio).
3. Identifica quem volta de férias **hoje** (Candidato a Desbloqueio).
4. Verifica na tabela `BlockProcessing` se essa ação já foi feita hoje com sucesso (Prevenção de dupla-execução).
5. Retorna o lote (Batch) de alvos. **Nenhuma alteração é feita no banco neste momento.**

### Etapa 2: Preflight (Verificação Operacional)
Antes de enviar dezenas de comandos lentos para a rede corporativa, o sistema prepara uma fila (Verificação Operacional):
1. O sistema se comunica com o Active Directory via `executor.py` fazendo uma checagem em lote (Read-Only) para saber o Status Real da VPN e do Usuário na nuvem atual.
2. Compara o Banco de Dados Local com a Realidade do AD.
3. **Decisão Autônoma**: Se o sistema ia "Bloquear" o Usuário X, mas descobre que no AD ele *já está bloqueado*, a ação do usuário passa de `BLOQUEAR` para `IGNORAR` e o banco local é **Sincronizado** passivamente, poupando a rede corporativa e evitando erros.
4. Gera um histórico transitório chamado `BlockVerificationRun`.

### Etapa 3: Execução Crítica (Integração AD)
Com a fila limpa (contendo apenas usuários que *realmente precisam* de bloqueio/desbloqueio físico):
1. O `BlockBusinessService` itera sobre os colaboradores.
2. Invoca o script `AD_block.ps1` através do interpretador PowerShell do Windows, injetando os parâmetros do usuário.
3. O script injeta o comando na infraestrutura da T.I e retorna um payload JSON contendo `success`, `message` e o novo `status`.
4. O Django intercepta o JSON.

### Etapa 4: Auditoria e Salvamento (BlockProcessing)
Para cada resposta do PowerShell:
1. O Django ORM atualiza a tabela corporativa de `Acessos` (status da VPN, status AD) daquele funcionário.
2. Insere uma linha imutável na tabela de Auditoria (`BlockProcessing`) contendo: Ação tentada, resultado (SUCESSO/ERRO), data de férias referente e as mensagens técnicas.

---

## 5. Tarefas Agendadas e Tolerância a Falhas

Todo o fluxo acima não necessita de interação humana. O **Django Q2** foi integrado para atuar como guardião:
*   As *tasks* como `run_block_verification()` e `run_spreadsheet_sync()` estão cadastradas no painel do Django Admin (`/admin/`).
*   Se a rede corporativa cair e o PowerShell falhar, o Django Q intercepta a falha e o `BlockBusinessService` gravará na auditoria o resultado como `ERRO`.
*   Na próxima janela do agendamento (ou dia seguinte), a regra de negócio notará que a rodada anterior deu `ERRO` e tentará bloqueá-lo novamente, conferindo total resiliência ao sistema.

---

## Conclusão
Esta infraestrutura garante alto nível de isolamento entre o "O que o usuário vê", "As regras do RH", e "A T.I pesada do Windows". Adições futuras podem ser focadas puramente na extensão de módulos (como revogar senhas ou suspender contas de email do Google Workspace) apenas plujando novos *scripts* de integração no final da esteira.
