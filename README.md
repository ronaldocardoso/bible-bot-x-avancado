[README.md](https://github.com/user-attachments/files/26877147/README.md)
# bible-bot-x-avancado

Bot simples para publicar um versículo aleatório da Bíblia no X uma vez por dia via GitHub Actions.

## Como funciona

O fluxo atual faz apenas isto:

1. busca um versículo aleatório na API `bible-api.com`
2. monta um texto curto para postagem
3. publica no X usando OAuth 1.0a

## Secrets necessários no GitHub

Configure estas secrets em `Settings > Secrets and variables > Actions`:

- `X_CONSUMER_KEY`
- `X_CONSUMER_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_SECRET`

Mapeamento:

- `X_CONSUMER_KEY` = Consumer Key
- `X_CONSUMER_SECRET` = Consumer Secret
- `X_ACCESS_TOKEN` = Access Token
- `X_ACCESS_SECRET` = Access Token Secret

Importante:

- o app no X precisa estar com permissão `Read and write`
- `Bearer Token`, `Client ID` e `Client Secret` não são usados neste projeto

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
```

Execute:

```bash
python bot.py
```

## Workflow

O agendamento está em [`.github/workflows/daily.yml`](/Users/ronaldodallevedovecardoso/Downloads/bible-bot-x-avancado-main/.github/workflows/daily.yml:1) e também pode ser executado manualmente com `workflow_dispatch`.

## Limitações atuais

- depende da disponibilidade da API pública de versículos
- publica somente texto
- não possui testes automatizados
