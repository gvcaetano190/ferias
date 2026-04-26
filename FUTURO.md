# Visão Geral e Futuro do Sistema (Controle de Férias)

Este documento centraliza tudo o que conquistamos nesta fase de modernização do sistema e serve como uma bússola de ideias para melhorias e novas funcionalidades.

---

## 🚀 1. Resumo da Obra (O que fizemos)

Transformamos um script monolítico em uma arquitetura de software corporativa (Enterprise-grade).

* **Migração para Django Q2:** Substituímos agendadores arcaicos por um robusto gerenciador de tarefas em background (Q2). A aplicação web não fica mais "travada" esperando o banco de dados.
* **Limpeza Arquitetural (SOLID):** Desmembramos a God Class (`BlockService`) em Repositórios (banco de dados) e Regras de Negócio (`BlockBusinessService`).
* **Segurança e Idempotência:** Implementamos o conceito de *Preflight* (Pente Fino). O sistema agora "olha antes de pular", verificando o estado real do Active Directory (AD) para evitar sobreposição de comandos e sujeira nos logs.
* **Poder do "Batch" (Lote):** Reescrevemos a comunicação com o PowerShell. Consultas, bloqueios e desbloqueios agora enviam JSON com dezenas de usuários em uma única tacada, derrubando o tempo de execução de minutos para meros 2 a 3 segundos.
* **UI Transparente:** Interface reformulada dividindo a responsabilidade administrativa em 3 etapas claras:
  1. Sincronização.
  2. Verificação Operacional.
  3. Execução Controlada.
* **Auditoria de Pedra:** Cada respiração do sistema gera um registro (SUCESSO, ERRO, IGNORADO) na tabela `BlockProcessing`, impossibilitando as famosas dúvidas de T.I: "Quem cortou esse acesso?".

---

## 🛠 2. Oportunidades de Melhoria no Código Atual

A base agora é sólida, mas um sistema de alta performance sempre tem espaço para otimização contínua.


* **Limpeza Automática de Logs:** A tabela `BlockProcessing` e `BlockVerificationRun` vão crescer infinitamente. Podemos criar uma tarefa Q2 mensal que purgue (delete ou mova para arquivamento) logs mais velhos do que 6 meses para manter o SQLite rápido.
* **Testes de Integração (E2E):** Já temos 21 excelentes testes de negócio. O próximo passo seria adotar uma ferramenta como o *Playwright* ou *Selenium* para criar um robô que "clica nos botões" na tela para validar que a UI não quebre quando o HTML for alterado.
* **Mapeamento de Erros Finos no PS:** O PowerShell atualmente retorna apenas "Sucesso" ou "Erro". Poderíamos classificar melhor: *Timeout*, *Erro de Permissão*, *Credenciais Inválidas*, permitindo que o Python tome decisões automáticas baseadas no código do erro.

---

## ✨ 3. Novas Funcionalidades (O que seria legal trazer)

Agora que a casa está arrumada, podemos subir os andares do prédio!

### Botão de Emergência: Rollback (Desfazer)
* Se o RH enviou uma data errada na planilha e a pessoa foi bloqueada no meio do expediente, seria fantástico ter um botão vermelho "Desfazer" direto na tabela de auditoria que instantaneamente invertesse a ação (rodasse o desbloqueio ignorando as regras de calendário).

### Notificações Proativas (E-mail / Teams / Slack)
* O sistema poderia enviar uma mensagem automática ao gestor da área 1 dia antes: *"Amanhã os acessos de Joãozinho serão suspensos devido a férias"*.
* Uma notificação direta no Teams do time de Infraestrutura com o Resumo Diário: *"Hoje o robô executou 15 bloqueios com sucesso e houveram 2 falhas."*

### Dashboard Analítica (Gráficos)
* Usar bibliotecas como *Chart.js* na página inicial para criar gráficos de calor corporativo: "Quantas pessoas da empresa estarão de férias na semana do Natal?".
* Gráficos de barra de Saúde do Sistema: "Quantidade de erros x acertos na automação do AD por mês".

### Expansão: Além do Active Directory
* Já dominamos o Windows, mas os usuários também usam ferramentas de nuvem. No futuro, o mesmo clique de botão poderia bloquear contas no *Google Workspace*, revogar tokens na *AWS*, ou inativar licenças de softwares pagos (*Salesforce*, *Figma*, etc), economizando dinheiro real da empresa em licenças não utilizadas durante as férias.

### Painel de Controle Desktop (Executável)
* Substituir as telas pretas de terminal (`.bat` e `.sh`) por um pequeno programa com interface gráfica (um "Control Panel" estilo XAMPP).
* Esse executável teria botões simples: **"Iniciar Sistema"**, **"Pausar Sistema"**, **"Desligar"**, que gerenciariam o servidor Django e o worker do Q2 de forma limpa em segundo plano.
* Pode ser feito em Python puro usando *Tkinter/PyQt* ou empacotado como um aplicativo de bandeja (ícone perto do relógio do Windows). Isso torna a inicialização do sistema 100% amigável para qualquer analista rodar.
