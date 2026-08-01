# 🎧 OpenAudible Manager

> **Gerenciador Self-Hosted de Biblioteca & Autenticação Audible**  
> Aplicação moderna para sincronização, download e gerenciamento de acervos do Audible (com suporte nativo ao **Audible Brasil `audible.com.br`**).

![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📋 Sobre o Projeto

O **OpenAudible Manager** foi criado para resolver a necessidade de um serviço **self-hosted**, leve e flexível para autenticar contas do Audible (especialmente no marketplace brasileiro), sincronizar metadados da biblioteca e realizar downloads com conversão automática via **FFmpeg**.

Ele foi desenhado para rodar 24/7 em servidores domésticos, NAS e ecossistemas como **CasaOS**, **Portainer**, **Unraid**, **Raspberry Pi** e **Orange Pi**.

---

## ✨ Recursos Principais

* 🇧🇷 **Suporte Nativo ao Audible Brasil (`audible.com.br`)**: Além dos marketplaces internacionais (US, UK, etc.).
* ⚡ **Autenticação Facilitada 1-Clique**:
  * **Bookmarklet do Navegador (`⭐ Capturar Login Audible`)**: Conclui o login na Amazon com 1 clique direto da barra de favoritos.
  * **Botão Inline de Colar (`📋 Colar`)**: Captura automaticamente a URL da área de transferência com 1 clique.
* 🔐 **Login Persistente & Seguro**: Autentica **uma única vez** e armazena os tokens criptografados (`refresh_token`, `adp_token`). O serviço renova o acesso automaticamente em segundo plano.
* 🌙 **Dashboard Web em Dark Mode**: Interface responsiva e moderna para navegar pela biblioteca, acompanhar downloads e gerenciar configurações.
* 🎧 **Download & Conversão**: Integração com `python-audible` e `FFmpeg` para baixar e converter livros para formatos compatíveis.
* 🐳 **Pronto para Docker & CasaOS**: Imagem Docker leve com suporte a volumes de dados e mídia.

---

## 🚀 Como Rodar em um Servidor (Docker / CasaOS)

A forma recomendada para produção é utilizar **Docker** ou **Docker Compose**.

### 🏠 Opção A: Instalação no CasaOS

1. No painel do **CasaOS**, abra o **App Store**.
2. Clique no ícone **`+` (Custom Install / Instalação Personalizada)** no canto superior direito.
3. Escolha **`Importar Docker Compose`** e cole o seguinte conteúdo:

```yaml
version: '3.8'

services:
  openaudible-manager:
    image: gustavolucen4/openaudible-manager:latest # ou construa localmente
    container_name: openaudible-manager
    restart: unless-stopped
    ports:
      - "8085:8080"
    environment:
      - APP_NAME=OpenAudible Manager
      - ENV=production
      - HOST=0.0.0.0
      - PORT=8080
      - DATABASE_URL=sqlite:////app/data/auth.db
      - SECRET_KEY=sua_chave_secreta_aqui
      - DEFAULT_MARKETPLACE=br
    volumes:
      - /DATA/AppData/openaudible/data:/app/data
      - /DATA/Media/audiobooks:/app/downloads
```

4. Clique em **Submit/Instalar**. O serviço estará disponível em `http://ip-do-seu-servidor:8085`.

---

### 🐳 Opção B: Docker Compose Genérico (Linux / Raspberry Pi / NAS)

1. Clone o repositório:
   ```bash
   git clone https://github.com/gustavolucen4/OpenAudibleManager.git
   cd OpenAudibleManager/audible-auth-service
   ```

2. Suba o container com o Docker Compose:
   ```bash
   docker compose up -d
   ```

3. Acesse a aplicação no seu navegador: `http://localhost:8085`.

---

## 💻 Como Rodar Localmente (Ambiente de Desenvolvimento)

### Pré-requisitos
* **Python 3.12** ou superior.
* **FFmpeg** instalado no sistema (necessário para processamento de áudio).

### Passo a Passo

1. **Clonar o Repositório**:
   ```bash
   git clone https://github.com/gustavolucen4/OpenAudibleManager.git
   cd OpenAudibleManager/audible-auth-service
   ```

2. **Criar e Ativar o Ambiente Virtual (`venv`)**:
   * **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   * **Linux / macOS**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Instalar as Dependências**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Iniciar o Servidor em Modo de Desenvolvimento**:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8085 --reload
   ```

5. **Acessar a Aplicação**:
   * Dashboard & Autenticação: [http://localhost:8085/auth/login](http://localhost:8085/auth/login)
   * Documentação Swagger da API: [http://localhost:8085/docs](http://localhost:8085/docs)

---

## 🔑 Como Funciona a Autenticação no Audible

1. Acesse a tela de login (`/auth/login`).
2. Clique no botão **`1. Iniciar Login com Amazon Brasil`**. Uma nova aba será aberta no site da Amazon.
3. Conclua o login com suas credenciais da Amazon/Audible normalmente.
4. Quando a Amazon redirecionar para a página final (que dirá *"Procurando alguma coisa? Desculpe-nos..."*):
   * **Opção 1 (Bookmarklet - 1 Clique)**: Clique no favorito **`⭐ Capturar Login Audible`** que você arrastou para a sua barra do navegador. O login será finalizado sozinho!
   * **Opção 2 (Botão Inline `📋 Colar`)**: Copie a URL da barra do navegador, volte para a tela do OpenAudible Manager e clique no botão **`📋 Colar`** dentro do campo de texto.
5. Pronto! As chaves criptografadas serão salvas no banco SQLite (`auth.db`). Você não precisará repetir este processo.

---

## 🧪 Rodando os Testes Automatizados

O projeto conta com suíte de testes automatizados utilizando `pytest` e `httpx`:

```bash
cd audible-auth-service
.\venv\Scripts\python.exe -m pytest
```

---

## 📂 Estrutura do Projeto

```
OpenAudibleManager/
├── .gitignore
├── README.md
├── doc.md
└── audible-auth-service/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    ├── app/
    │   ├── main.py              # Entrypoint da aplicação FastAPI
    │   ├── config.py            # Configurações de ambiente (Pydantic Settings)
    │   ├── database.py          # Conexão e sessão do SQLite/SQLAlchemy
    │   ├── models.py            # Modelos ORM (User, Token, Book, Setting)
    │   ├── amazon.py            # Geração de URLs de OAuth PKCE do Audible
    │   ├── audible_client.py    # Integração com a biblioteca python-audible
    │   ├── routes/              # Endpoints da API (auth, library)
    │   ├── services/            # Camada de regras de negócio (Auth, Library, Download)
    │   └── templates/           # Interfaces HTML em Dark Mode (login, library)
    └── tests/                   # Suíte de testes automatizados
```

---

## 🔗 Integração com Audiobookshelf / Jellyfin

Se você utiliza o **Audiobookshelf** ou **Jellyfin**:
* Aponte o volume `/app/downloads` (ex: `/DATA/Media/audiobooks`) do **OpenAudible Manager** para a mesma pasta da sua biblioteca de audiolivros do Audiobookshelf.
* Assim que um download for concluído no OpenAudible Manager, o Audiobookshelf detectará o novo arquivo automaticamente!

---

## 📜 Licença

Este projeto é desenvolvido para fins educacionais e de uso pessoal sob a licença **MIT**. As marcas *Audible* e *Amazon* pertencem aos seus respectivos proprietários.
