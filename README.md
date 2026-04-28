# bible-bot-x-avancado

Bot simples para publicar um versículo aleatório da Bíblia no X uma vez por dia via GitHub Actions, com imagem gerada por IA via xAI quando a chave estiver configurada.

## Como funciona

O fluxo faz isto:

1. consulta primeiro um calendário diocesano local, se houver arquivo configurado
2. consulta o calendário litúrgico católico do Brasil
3. se houver uma celebração especial ou um tema litúrgico relevante do dia, usa esse contexto no post
4. quando o tema vier do calendário geral de fallback, tenta priorizar a leitura litúrgica correspondente
5. se o dia for ferial ou alguma consulta falhar, volta ao modo normal com versículo aleatório da API `bible-api.com`
6. monta um texto curto para postagem
7. gera uma imagem inspirada no versículo e, quando aplicável, no tema litúrgico do dia
8. publica no X usando OAuth 1.0a

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
- `BOT_TIMEZONE` (padrão: `America/Sao_Paulo`)
- `DIOCESAN_CALENDAR_FILE` (padrão: `diocesan_calendar.json`)

## Calendário diocesano

O repositório já traz um modelo em [diocesan_calendar.sample.json](/Users/ronaldodallevedovecardoso/Downloads/bible-bot-x-avancado-main/diocesan_calendar.sample.json:1).

Se você quiser ativar um calendário próprio da sua diocese, crie um arquivo `diocesan_calendar.json` na raiz do projeto seguindo esse formato:

```json
{
  "diocese": "Diocese de Exemplo",
  "celebrations": [
    {
      "month_day": "10-07",
      "name": "Nossa Senhora do Rosário",
      "type": "SOLEMNITY",
      "description": "Padroeira da diocese.",
      "reference": "Lucas 1:26-38"
    }
  ]
}
```

Campos aceitos em cada celebração:

- `month_day`: recorrência anual no formato `MM-DD`
- `date`: data fixa específica no formato `YYYY-MM-DD`
- `name`: nome da celebração
- `type`: `SOLEMNITY`, `FEAST`, `MEMORIAL`, `OPT_MEMORIAL`, `SUNDAY` ou `LITURGICAL_DAY`
- `description`: contexto usado no texto/imagem
- `quote`: opcional
- `reference`: passagem bíblica opcional para ser usada naquele dia

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
- depende também da disponibilidade das APIs públicas de calendário/leituras católicas
- o calendário brasileiro é obtido de uma fonte pública nacional; o calendário diocesano depende do arquivo local configurado no repositório
- a qualidade visual depende do prompt e do modelo configurado
- não possui testes automatizados
