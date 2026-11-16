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

## Decisões técnicas

| Escolha | Justificativa |
| --- | --- |
| React + TypeScript | Componentes reutilizáveis e contratos tipados para organizar a interface e detectar inconsistências durante o desenvolvimento. |
| FastAPI + Pydantic | Validação das entradas, contratos explícitos e documentação OpenAPI gerada pela API. |
| Separação em endpoints, services, schemas e models | Manter transporte HTTP, regras de negócio, validação e persistência com responsabilidades distintas, facilitando manutenção e testes. |
| MySQL + SQLAlchemy + Alembic | Modelar as relações entre usuários, tickets, comentários e histórico, com migrações versionadas para evoluir o banco. |
| Sessões no banco e cookie HttpOnly | Permitir revogação no logout sem disponibilizar o token ao JavaScript. As senhas usam Argon2id; as operações de escrita exigem proteção CSRF. |
| Filtros, ordenação e paginação no backend | Consultar somente os dados necessários e aplicar a visibilidade por perfil antes de retornar os resultados. |
| Configuração por ENV e erros centralizados | Separar configuração do código e manter respostas de erro consistentes. Logs estruturados incluem identificação da requisição e parâmetros permitidos. |
| Docker Compose | Reproduzir o ambiente completo com frontend, API e banco, reduzindo a configuração necessária para avaliar o desafio. |

## Trade-offs e suposições

- **Cadastro e perfis:** permitir que o usuário escolha Funcionário ou Suporte
  simplifica a demonstração dos dois fluxos. Essa escolha foi feita para o desafio;
  o controle administrativo de perfis fica como evolução para produção.
- **Fluxo de status:** interpretei a seta do requisito como um fluxo sequencial:
  **Aberto → Em andamento → Resolvido → Fechado**. Por isso, a implementação
  impede saltos, retornos e reabertura. Esse comportamento é uma suposição adotada
  para o desafio e precisaria ser confirmado com a área de negócio em um produto real.
- **Contexto organizacional:** considerei uma única organização. Funcionários
  acessam os próprios tickets e suporte acessa todos; não há isolamento por empresa.
- **Persistência e sessões:** o acesso síncrono ao banco simplifica a implementação,
  e as sessões persistidas facilitam a revogação. Em contrapartida, a autenticação
  depende de uma consulta ao banco; mudanças para atender outra carga exigiriam medição.
- **Ambiente de desenvolvimento:** o Compose usa recarregamento automático e um
  único arquivo de dependências, incluindo ferramentas de teste. Isso facilita
  a execução do desafio, mas aumenta a imagem e requer uma configuração própria
  para implantação em produção.

## Melhorias com mais tempo

- **Identidade e administração:** integrar autenticação com o e-mail corporativo
  e restringir a criação de usuários de suporte e a gestão de permissões a um
  administrador. Incluir edição e desativação de usuários existentes.
- **Internacionalização:** adotar i18next para suportar múltiplos idiomas,
  considerando o uso por equipes de uma empresa global.
- **Edição de tickets:** permitir corrigir título, descrição, categoria e
  prioridade depois da abertura, com regras de permissão e histórico das alterações.
  Essa funcionalidade não estava prevista nos requisitos, mas faz falta no uso diário.
- **Observabilidade:** ampliar a cobertura dos logs e dos códigos de erro já
  implementados, centralizar a coleta e adicionar métricas, alertas e rastreamento
  para facilitar a identificação e a resolução de problemas.
- **Qualidade e manutenção:** extrair hooks para reduzir a responsabilidade dos
  componentes maiores e ampliar os testes automatizados. Adicionar CI com testes
  de integração em MySQL, testes do frontend e dos fluxos no navegador.
- **Operação em produção:** preparar imagens com frontend compilado e API sem
  recarregamento automático, HTTPS, gestão de segredos e procedimentos de backup
  e restauração do banco.
