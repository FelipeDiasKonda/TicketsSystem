# Tickets System

Portal de tickets de suporte interno para a avaliação técnica de Full-Stack Developer.

## Escopo da v0

Estrutura inicial com React + TypeScript + Vite, FastAPI e MySQL. Inclui comunicação
frontend/API, verificação de saúde da API e do banco e configuração do ambiente.
Login, cadastro com perfil e sessões persistentes estão implementados.
As funcionalidades de tickets ainda não estão implementadas.

## Executar tudo com Docker

Pré-requisito: Docker Desktop instalado e iniciado, usando containers Linux e
Docker Compose. Não é necessário instalar Python, Node.js ou MySQL na máquina.

Na raiz do projeto, no PowerShell, gere as credenciais locais:

```powershell
.\scripts\Initialize-Env.ps1
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
As migrações criam as tabelas de usuários e sessões antes de iniciar a API.

As configurações do Docker vêm do `.env` da raiz; não é necessário copiar os
exemplos de `backend` e `frontend`. O script também sincroniza `backend/.env`
para execução local. O backend no Docker usa `db:3306` na rede interna e o
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
Os exemplos não contêm senhas. O script gera senhas aleatórias e mantém valores
já configurados. As variáveis de inicialização do MySQL só são aplicadas quando
o volume está vazio; para trocar senhas existentes use a rotação descrita abaixo.

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
.\scripts\Initialize-Env.ps1
if (!(Test-Path frontend/.env)) { Copy-Item frontend/.env.example frontend/.env }
docker compose up -d db
```

No primeiro terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
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
- Login e cadastro usam sessões no MySQL, cookie HttpOnly e senhas Argon2id.
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

## Login e cadastro

Após atualizar o código, reconstrua os serviços para instalar as novas dependências:

```powershell
docker compose up --build -d
```

O backend executa `alembic upgrade head` antes de iniciar o Uvicorn. Se uma migração
falhar, consulte `docker compose logs backend`; a API só inicia após a migração.
Os dados existentes do MySQL são preservados. Para novas migrações, reconstrua a
imagem; reinicie o backend para executar as migrações pendentes.

Abra http://localhost:5173 e clique em **Cadastre-se**. Informe nome, e-mail, senha
(de 12 a 128 caracteres), confirmação e perfil **Funcionário** ou **Suporte**.
O cadastro inicia a sessão automaticamente. Você também pode sair e entrar com
seu e-mail e senha. A sessão é restaurada ao recarregar a página e expira após
8 horas por padrão. Ainda não há telas de tickets nesta etapa.

A escolha livre de suporte é uma simplificação aprovada para este protótipo:
qualquer pessoa pode criar uma conta com esse perfil. Antes de uso real, a
atribuição desse perfil precisa ser controlada. Todos os usuários pertencem à
mesma empresa; não há entidade de empresa nem convites.

| Método | Rota | Resultado |
| --- | --- | --- |
| POST | `/api/auth/register` | Cria usuário no perfil escolhido e inicia sessão (201) |
| POST | `/api/auth/login` | Valida credenciais e inicia/renova sessão (200) |
| GET | `/api/auth/me` | Retorna o usuário autenticado (200 ou 401) |
| POST | `/api/auth/logout` | Revoga a sessão e remove o cookie (204) |

Cadastro recebe `name`, `email`, `password`, `password_confirmation` e `role`
(`employee` ou `support`). Login recebe `email` e `password`. E-mails são
normalizados para minúsculas e não podem repetir. Senhas e hashes não aparecem
nas respostas, inclusive nos erros de validação.

Requisições POST exigem o header `X-CSRF-Protection: 1`, também disponível nos
parâmetros do Swagger. O frontend já envia esse header e o cookie com
`credentials: include`. CORS aceita credenciais apenas das origens configuradas.
Use consistentemente **localhost** para frontend e API; não misture localhost
com 127.0.0.1, pois são hosts diferentes para cookies e SameSite.

`SESSION_HOURS=8` configura a duração da sessão. `COOKIE_SECURE=false` permite o
HTTP local; em produção com HTTPS use `COOKIE_SECURE=true`. Apenas o hash do token
fica no banco; logout revoga o acesso mesmo se o cookie antigo for reutilizado.
Sessões expiradas são rejeitadas; uma rotina periódica de limpeza pode ser
adicionada posteriormente.

Os módulos seguem a arquitetura existente: endpoints em `api/routes/endpoints/auth.py`,
contratos em `schemas/auth.py`, entidades em `models/auth.py`, regras em
`services/auth.py`, primitivas de segurança em `core/security.py` e dependências
de autenticação/perfil em `api/dependencies.py`. As permissões dos tickets serão
aplicadas quando os endpoints de tickets forem implementados.

A especificação aprovada está em `docs/specs/002-authentication.md`. Testes usam
SQLite isolado para os fluxos da API e para upgrade/downgrade das migrações; a
integração com MySQL deve ser validada com o Compose em execução. Recuperação de
senha, confirmação de e-mail, limitação de tentativas e controle da atribuição
de perfil são evoluções para uso real.

## Credenciais do banco

`.env.example` e `backend/.env.example` possuem senhas vazias. Não coloque senhas
reais nesses arquivos. O backend exige `DATABASE_PASSWORD` não vazia; não há
senha padrão no código. O Compose exige as duas senhas do MySQL.

Para a primeira configuração, execute na raiz:

```powershell
.\scripts\Initialize-Env.ps1
docker compose up --build -d
```

O script usa o gerador criptográfico do sistema para criar duas senhas independentes
de 256 bits no `.env` e sincroniza a conexão local em `backend/.env`. Não exibe
senhas e não troca valores já preenchidos. `.env`, `backend/.env` e arquivos
`.env.*` estão ignorados, com exceção dos `.env.example` versionados.

### Trocar credenciais de um banco existente

Mantenha o `.env` com as credenciais que ainda funcionam, abra o Docker Desktop
e inicie o banco existente antes de executar a rotação:

```powershell
docker compose up -d db
.\scripts\Rotate-DatabaseCredentials.ps1
docker compose up --build -d --force-recreate
Invoke-RestMethod http://localhost:8000/api/health/db
```

A rotação preserva o volume e os dados. Ela gera as próximas senhas em
`.env.rotation` (ignorado), atualiza as contas MySQL do usuário da aplicação e
root, verifica o acesso, e só então atualiza `.env` e `backend/.env`. O Compose
precisa recriar os containers para receber as novas variáveis de ambiente.
Durante esse intervalo a API pode ficar temporariamente sem acesso ao banco.

Se houver falha de acesso ao Docker, o `.env` ativo fica inalterado e as próximas
senhas permanecem em `.env.rotation`. Execute o mesmo script no seu terminal
quando o Docker estiver acessível. Não exclua o arquivo pendente até finalizar:
ele também permite retomar uma rotação interrompida após o MySQL aceitar as novas
senhas. O script não exibe senhas nem as envia como argumentos de processos.
Evite executar `docker compose config` sem `--quiet`, pois a saída completa
expõe os valores resolvidos do ambiente.

Senhas presentes em commits anteriores devem ser consideradas públicas. Um novo
commit não apaga esses commits; trocar as senhas invalida as credenciais antigas.
Não é necessário reescrever o histórico para concluir essa rotação. A especificação
da correção está em `docs/specs/003-database-credentials.md`.
