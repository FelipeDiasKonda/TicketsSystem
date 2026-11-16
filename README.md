# Tickets System

## Como rodar

Tenha o Git e o Docker Desktop instalados, com o Docker iniciado em modo de
containers Linux. Não é necessário instalar Python, Node.js ou MySQL separadamente.
Os comandos abaixo usam PowerShell.

1. Clone o repositório e entre na pasta:

   ```powershell
   git clone https://github.com/FelipeDiasKonda/TicketsSystem.git
   cd TicketsSystem
   ```

2. Copie o arquivo de configuração:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Edite o `.env` da raiz e escolha o nome do banco, o usuário da aplicação
   (diferente de `root`) e as duas senhas:

   ```dotenv
   MYSQL_DATABASE=tickets_system
   MYSQL_USER=tickets_app
   MYSQL_PASSWORD=sua_senha_da_aplicacao
   MYSQL_ROOT_PASSWORD=sua_senha_do_root
   ```

   Substitua os valores de exemplo pelas suas credenciais. Para rodar com Docker,
   basta configurar esse `.env`; o backend recebe as mesmas credenciais automaticamente.
   Mantenha as demais chaves do exemplo: todas as configurações do backend vêm do
   ambiente. No Docker, `DATABASE_HOST=db` e `DATABASE_PORT=3306` apontam para o
   MySQL interno. Se mudar `FRONTEND_PORT`, ajuste também `CORS_ORIGINS`.
   `SEED_PASSWORD` pode ficar vazio enquanto o seed não for utilizado.

4. Inicie a aplicação:

   ```powershell
   docker compose up --build -d
   ```

   Aguarde a inicialização dos serviços. As tabelas são criadas pelas migrações
   automaticamente. A primeira execução pode demorar para baixar as dependências.

Os dados ficam em um volume persistente. As credenciais do `.env` inicializam o
MySQL somente quando esse volume está vazio; editar o arquivo depois não altera
as senhas já salvas no banco. Não versione o `.env` com suas credenciais.

## Como acessar

| Serviço | Endereço |
| --- | --- |
| Aplicação | http://localhost:5173 |
| Documentação da API | http://localhost:8000/docs |

Use **Cadastre-se** para criar uma conta de Funcionário ou Suporte, ou utilize
os dados de demonstração abaixo. Os endereços usam as portas padrão do `.env`.

## Dados de demonstração

O seed é opcional. Ele cria seis contas e três tickets, um para cada funcionário,
nas categorias TI, Instalações e RH.

Defina no `.env` da raiz uma senha de demonstração com 12 a 128 caracteres:

```dotenv
SEED_PASSWORD=sua_senha_de_demonstracao
```

Depois execute na raiz:

```powershell
docker compose up --build -d
docker compose exec backend python -m app.db.seed
```

| Perfil | E-mails |
| --- | --- |
| Funcionário | `funcionario1@gmail.com`, `funcionario2@gmail.com`, `funcionario3@gmail.com` |
| Suporte | `suporte1@gmail.com`, `suporte2@gmail.com`, `suporte3@gmail.com` |

Todas essas contas usam a senha definida em `SEED_PASSWORD`. Essa senha serve para
login na aplicação e é independente das senhas do MySQL.

O seed pode ser repetido sem duplicar os tickets. Ele restaura as seis contas de
demonstração e encerra suas sessões anteriores; os demais usuários e tickets são
preservados.

## Funcionalidades

- Cadastro e login com perfis de Funcionário e Suporte.
- Criação de tickets com título, descrição, categoria e prioridade por ambos os perfis.
- Funcionários visualizam seus próprios tickets; suporte visualiza todos.
- Visualizações em lista e quadro, com filtros por status, categoria e prioridade
  e ordenação por data ou prioridade.
- Suporte avança o status pelo seletor ou arrastando os cartões, seguindo o fluxo
  **Aberto → Em andamento → Resolvido → Fechado**, sem pular etapas ou voltar.
- Modal com detalhes completos, solicitante, responsável, comentários e histórico.
- Suporte pode atribuir tickets a si, a outro membro ativo ou remover a atribuição.
- Funcionários comentam nos próprios tickets; suporte comenta em qualquer ticket.
