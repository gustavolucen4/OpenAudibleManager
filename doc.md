# OpenAudible Manager

Serviço self-hosted para gerenciamento de biblioteca Audible.

## Status do projeto

🚧 MVP - Fase 1: Autenticação Audible

Objetivo atual:

* autenticar uma conta Audible;
* suportar marketplace Brasil (`audible.com.br`);
* capturar e armazenar sessão;
* preparar base para sincronização da biblioteca.

---

# Motivação

Ferramentas existentes como Libation resolvem grande parte do problema de gerenciamento Audible, porém o fluxo de autenticação pode apresentar limitações dependendo do marketplace.

Este projeto tem como objetivo criar uma camada própria de autenticação mais flexível, especialmente para ambientes self-hosted como Orange Pi, Raspberry Pi e servidores domésticos.

---

# Arquitetura inicial

```
Usuário
   |
   |
Web Browser
   |
   |
Authentication Service
   |
   |
Amazon Login
   |
   |
Audible Marketplace
   |
   |
Token/Sessão
   |
   |
Database
```

---

# Objetivos do MVP

## Autenticação

* [ ] Abrir fluxo de login Amazon
* [ ] Suportar Audible Brasil
* [ ] Capturar callback
* [ ] Armazenar sessão
* [ ] Renovar autenticação

## Segurança

* [ ] Não armazenar senha
* [ ] Criptografar tokens
* [ ] Utilizar variáveis de ambiente
* [ ] Separar configuração de código

---

# Tecnologias

## Backend

* Python 3.12
* FastAPI
* Uvicorn
* SQLAlchemy
* Pydantic

## Banco

Inicial:

* SQLite

Futuro:

* PostgreSQL

## Infraestrutura

* Docker
* Docker Compose
* Nginx
* Redis

---

# Estrutura futura

```
OpenAudible Manager

API
 |
Authentication Service
 |
Audible Client
 |
Library Manager
 |
Download Worker
 |
Storage
```

---

# Próximas fases

## Fase 1 - Authentication

Objetivo:

Login funcional.

Entrega:

* endpoint `/login`
* endpoint `/callback`
* sessão persistente

---

## Fase 2 - Biblioteca

Implementar:

* listar audiobooks;
* sincronizar metadados;
* salvar biblioteca local.

---

## Fase 3 - Downloads

Implementar:

* fila;
* worker;
* download automático;
* conversão.

---

## Fase 4 - Interface Web

Dashboard:

* biblioteca;
* downloads;
* configurações;
* logs.

---

# Requisitos de hardware

Suportado:

* Orange Pi
* Raspberry Pi
* Servidor Linux

Recomendado:

* 2GB RAM ou mais
* Docker instalado
* armazenamento externo para audiobooks

---

# Princípios do projeto

1. O usuário é dono dos próprios dados.
2. Nunca armazenar senha Amazon.
3. Toda autenticação deve ser transparente.
4. O sistema deve funcionar offline após autenticação.
5. O projeto deve ser compatível com ARM.
