# bible-bot-x-avancado

Bot simples para publicar um versículo aleatório da Bíblia no X uma vez por dia via GitHub Actions, com imagem gerada por IA via xAI quando a chave estiver configurada.

## Como funciona

O fluxo faz isto:

1. busca um versículo aleatório na API `bible-api.com`
2. monta um texto curto para postagem
3. gera uma imagem inspirada no versículo com a xAI
4. publica no X usando OAuth 1.0a

## Secrets necessários no GitHub

Configure estas secrets em `Settings > Secrets and variables > Actions`:

- `X_CONSUMER_KEY`
- `X_CONSUMER_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_SECRET`
- `XAI_API_KEY`

Mapeamento:

- `X_CONSUMER_KEY` = Consumer Key
- `X_CONSUMER_SECRET` = Consumer Secret
- `X_ACCESS_TOKEN` = Access Token
- `X_ACCESS_SECRET` = Access Token Secret
- `XAI_API_KEY` = chave de API gerada em `console.x.ai`

Importante:

- o app no X precisa estar com permissão `Read and write`
- `Bearer Token`, `Client ID` e `Client Secret` não são usados neste projeto
- se `XAI_API_KEY` não estiver configurada, o bot continua funcionando, mas publica somente texto
- a geração da imagem usa a API da xAI; para aproveitar o ecossistema X/xAI, vincule sua conta/time da xAI ao X Developer Console e confira os créditos disponíveis
- os tokens do X API e a chave `XAI_API_KEY` continuam sendo configurações separadas

## Variáveis opcionais para imagem

Você pode configurar estas `Repository variables` no GitHub para ajustar a imagem:

- `XAI_IMAGE_MODEL` (padrão: `grok-imagine-image`)
- `XAI_IMAGE_ASPECT_RATIO` (padrão: `1:1`)
- `XAI_IMAGE_RESOLUTION` (padrão: `1k`)

## Execução local

Instale as dependências:

```bash
pip install -r requirements.txt
```

Exporte as variáveis de ambiente:

```bash
export X_CONSUMER_KEY="..."
export X_CONSUMER_SECRET="..."
export X_ACCESS_TOKEN="..."
export X_ACCESS_SECRET="..."
export XAI_API_KEY="..."
```

Execute:

```bash
python bot.py
```

## Workflow

O agendamento está em [`.github/workflows/daily.yml`](/Users/ronaldodallevedovecardoso/Downloads/bible-bot-x-avancado-main/.github/workflows/daily.yml:1) e também pode ser executado manualmente com `workflow_dispatch`.

## Limitações atuais

- depende da disponibilidade da API pública de versículos
- a qualidade visual depende do prompt e do modelo configurado
- não possui testes automatizados
