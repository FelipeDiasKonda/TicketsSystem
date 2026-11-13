# Tickets System

Portal de tickets de suporte interno para a avaliação técnica de Full-Stack Developer.

## Escopo da v0

Estrutura inicial com React + TypeScript + Vite, FastAPI e MySQL. Inclui comunicação
frontend/API, verificação de saúde da API e do banco e configuração do ambiente.
As funcionalidades de tickets ainda não estão implementadas.

## Executar tudo com Docker

Pré-requisito: Docker Desktop instalado e iniciado, usando containers Linux e
Docker Compose. Não é necessário instalar Python, Node.js ou MySQL na máquina.

Na raiz do projeto, no PowerShell, copie o exemplo apenas se ainda não tiver `.env`:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
docker compose ps
```

O Compose inicia o MySQL, aguarda o banco ficar saudável, inicia a API e depois
o frontend. A primeira execução pode demorar para baixar imagens e dependências.

| Serviço | Endereço padrão |
| --- | --- |
| Frontend | http://localhost:5173 |
| Saúde da API | http://localhost:8000/api/health |
| Conexão com MySQL | http://localhost:8000/api/health/db |
| Documentação da API | http://localhost:8000/docs |
| MySQL pelo host | 127.0.0.1:3306 |

A tela inicial verifica a API. Para verificar também o banco, abra `/api/health/db`.
Nenhuma tabela é criada nesta etapa.

As configurações do Docker vêm do `.env` da raiz; não é necessário copiar os
exemplos de `backend` e `frontend`. O backend usa `db:3306` na rede interna e o
navegador acessa a API por `localhost`. Os arquivos `.env` locais não entram nas imagens.

Se ainda houver servidores locais rodando, encerre-os com `Ctrl+C` antes de subir
os containers. Se precisar mudar as portas, configure `BACKEND_PORT`, `FRONTEND_PORT`
ou `MYSQL_PORT` no `.env` da raiz e execute `docker compose up -d` novamente.
Por exemplo:

```dotenv
BACKEND_PORT=8001
FRONTEND_PORT=5174
MYSQL_PORT=3307
```

Nesse caso, abra http://localhost:5174 e http://localhost:8001/docs.
A comunicação interna com o MySQL continua usando a porta 3306.

## Desenvolvimento e comandos úteis

Alterações em `backend/app` e `frontend/src` são refletidas automaticamente pelos
servidores de desenvolvimento. A detecção de mudanças usa polling para funcionar
com os volumes no Windows. As dependências ficam nas imagens, separadas do
`node_modules` e do ambiente Python do Windows.

Depois de alterar dependências ou Dockerfiles, reconstrua as imagens:

```powershell
docker compose up --build -d
```

Mantenha `frontend/package-lock.json` atualizado junto com `frontend/package.json`.
O frontend instala dependências com `npm ci` durante o build.

Para acompanhar os logs ou parar os serviços:

```powershell
docker compose logs -f
docker compose down
```

O volume `mysql_data` preserva os dados entre reinicializações. Não use
`docker compose down -v` se quiser manter os dados.
As senhas do exemplo são exclusivamente para desenvolvimento local. As variáveis
de inicialização do MySQL só são aplicadas quando o volume está vazio; alterar
uma senha no `.env` não altera usuários já criados no banco.

## Verificações pelo Docker

Com os serviços em execução:

```powershell
docker compose exec backend python -m pytest
docker compose exec backend python -m ruff check .
docker compose exec frontend npm run build
```

Os testes cobrem a API de saúde e a resposta segura quando o banco está indisponível.
Para conferir a integração real com MySQL:

```powershell
Invoke-RestMethod http://localhost:8000/api/health/db
```

## Execução local opcional

Para executar Python e Node fora do Docker, use Python 3.14 e Node.js 22.12+.
Suba somente o banco e copie os exemplos locais apenas se os arquivos não existirem:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
if (!(Test-Path frontend/.env)) { Copy-Item frontend/.env.example frontend/.env }
docker compose up -d db
```

No primeiro terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

No segundo terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Nessa modalidade, mantenha as credenciais e a porta em `backend/.env` alinhadas
com o `.env` da raiz. Ajuste `frontend/.env` se mudar a porta da API.

## Estrutura

```text
backend/
  app/
    main.py         Factory, middleware e registro do router central
    api/routes/
      router.py     Agregador de routers
      endpoints/
        health.py   Endpoints de saude
    core/
      config.py     Configuracao por variaveis de ambiente
      lifespan.py   Ciclo de vida da aplicacao
    db/
      database.py   Engine SQLAlchemy e sessao por requisicao
  tests/
  Dockerfile
frontend/
  src/
    api.ts          Comunicação HTTP
    App.tsx         Tela inicial
  Dockerfile
compose.yaml        Frontend, API, MySQL e volume persistente
```

## Decisões e trade-offs

- Frontend e backend separados em um repositório simplificam a entrega.
- FastAPI fornece validação e documentação OpenAPI. SQLAlchemy prepara a camada
  de persistência sem acoplar as regras de negócio ao transporte HTTP.
- MySQL atende à persistência relacional de tickets e histórico.
- O acesso ao banco é síncrono, executado no thread pool do FastAPI.
- TypeScript ajuda a verificar contratos no frontend; a comunicação usa `fetch`.
- Docker Compose fornece um ambiente de desenvolvimento completo. Vite, reload
  do Uvicorn e dependências de teste estão incluídos; esta configuração é para
  desenvolvimento local. Uma implantação de produção requer outra configuração.
- Não há autenticação nesta v0.
- Dependências Python usam intervalos de versões; gerar um lock e automatizar CI
  são melhorias antes da entrega final. O frontend usa `package-lock.json` e `npm ci`.

## Próximas etapas

1. Modelar tickets e histórico de status, com migrações Alembic.
2. Criar tickets com título, descrição, categoria e prioridade.
3. Listar com filtros de status, categoria e prioridade e ordenação.
4. Exigir transições: Aberto → Em andamento → Resolvido → Fechado.
5. Exibir detalhes e histórico; testar regras e integração com MySQL.

## Arquitetura e fluxo SDD

O `main.py` registra o router central com prefixo `/api`. Cada funcionalidade
expõe um `APIRouter` em `api/routes/endpoints/`, reunido por `api/routes/router.py`.
Configuração e ciclo de vida ficam em `core/`; conexão e sessões ficam em `db/`.
Schemas Pydantic, modelos SQLAlchemy e serviços de negócio serão adicionados
conforme os requisitos de cada funcionalidade.

Seguimos SDD: requisito → especificação e plano com critérios de aceite → aprovação
do usuário → implementação → testes e revisão dos critérios. As orientações estão
em `AGENTS.md`, e a primeira refatoração está em `docs/specs/001-backend-architecture.md`.
