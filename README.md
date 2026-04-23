# Django App

Base inicial da migração do projeto para Django, reaproveitando o banco existente `data/database_v2.sqlite`.

## O que já ficou pronto

- projeto Django isolado em `django_app/`
- banco próprio clonado em `django_app/data/controle_ferias_django.sqlite`
- `Django Admin` como central de configuração
- models mapeando as tabelas legadas `colaboradores`, `ferias`, `acessos`, `sync_logs` e `password_links`
- módulo de sincronização que baixa a planilha do Google Sheets, processa as abas e grava no mesmo banco
- módulo de senhas com integração OneTimeSecret
- dashboard inicial com `Django Templates + HTMX`
- visual inicial com Tailwind via CDN para acelerar a primeira etapa
- camada base de `shared/repositories` e `shared/services` para concentrar regras de negócio

## Estrutura

```text
django_app/
  apps/
    core/        # configuração operacional no admin
    people/      # tabelas existentes do banco atual
    sync/        # download + tratamento + persistência da planilha
    passwords/   # geração e histórico de links OneTimeSecret
    dashboard/   # dashboard inicial com HTMX
    shared/      # repositories e services reutilizáveis
  project/
  templates/
  static/
```

## Como rodar

```bash
cd /Users/gabriel.caetano/Documents/controle-ferias/django_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Fluxo recomendado

1. Entrar no `/admin/`
2. Abrir `Configurações operacionais`
3. Confirmar URL da planilha e credenciais do OneTimeSecret
4. Voltar ao dashboard
5. Rodar a sincronização manual

## Arquitetura

- `apps/.../views.py`: entrada HTTP
- `apps/.../forms.py`: validação de formulário
- `apps/shared/services/`: regras de negócio e orquestração
- `apps/shared/repositories/`: acesso aos dados via ORM
- `apps/.../models.py`: mapeamento de tabelas

O objetivo daqui para frente é que módulos novos nasçam seguindo esse fluxo, sem depender dos módulos legados fora da pasta `django_app`.

## Observações

- o banco padrão da nova app aponta para `django_app/data/controle_ferias_django.sqlite`
- esse banco é um clone do estado atual do `database_v2.sqlite`, incluindo tabelas do Django/Admin
- a partir daqui, a ideia é evoluir só esse banco do projeto novo
- o CSS está usando Tailwind CDN nesta primeira etapa para acelerar a migração; depois podemos trocar para pipeline local com build
