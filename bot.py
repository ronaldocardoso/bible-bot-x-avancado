import logging
import os
from typing import Any

import requests
import tweepy

# ====================== CONFIGURAÇÃO DE LOG ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

logger.info("🚀 BOT Palavra do Dia iniciado!")

BIBLE_API_URL = "https://bible-api.com/data/almeida/random"
ASSINATURA = "\n\n#Biblia #VersiculoDoDia"
MAX_TWEET_LEN = 280

# ====================== FUNÇÕES ======================
def carregar_variaveis():
    """Carrega e valida apenas as chaves realmente usadas pelo bot."""
    keys = {
        "X_CONSUMER_KEY": os.getenv("X_CONSUMER_KEY"),
        "X_CONSUMER_SECRET": os.getenv("X_CONSUMER_SECRET"),
        "X_ACCESS_TOKEN": os.getenv("X_ACCESS_TOKEN"),
        "X_ACCESS_SECRET": os.getenv("X_ACCESS_SECRET"),
    }

    missing = [name for name, value in keys.items() if not value]
    if missing:
        raise RuntimeError(f"Faltando variáveis de ambiente: {', '.join(missing)}")

    return keys


def validar_campo_texto(data: dict[str, Any], campo: str) -> str:
    valor = data.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"Campo inválido na resposta da API: {campo}")
    return " ".join(valor.split())


def extrair_referencia_e_texto(data: dict[str, Any]) -> tuple[str, str]:
    """Aceita tanto payloads antigos quanto o formato atual com `random_verse`."""
    if "reference" in data and "text" in data:
        return validar_campo_texto(data, "reference"), validar_campo_texto(data, "text")

    verso = data.get("random_verse")
    if not isinstance(verso, dict):
        raise ValueError("Resposta da API sem `reference` e sem objeto `random_verse`")

    livro = validar_campo_texto(verso, "book")
    texto = validar_campo_texto(verso, "text")
    capitulo = verso.get("chapter")
    versiculo = verso.get("verse")

    if not isinstance(capitulo, int) or not isinstance(versiculo, int):
        raise ValueError("Campos inválidos na resposta da API: chapter/verse")

    referencia = f"{livro} {capitulo}:{versiculo}"
    return referencia, texto


def pegar_versiculo():
    """Pega um versículo aleatório da Bíblia (Almeida)"""
    try:
        r = requests.get(BIBLE_API_URL, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            raise ValueError("Resposta da API não é um objeto JSON válido")

        ref, texto = extrair_referencia_e_texto(data)
        return ref, texto
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Erro ao buscar versículo: {e}")
        raise
    except ValueError as e:
        logger.error(f"❌ Erro ao processar resposta da API: {e}")
        raise


def montar_texto_postagem(referencia, versiculo):
    base = f"📖 Palavra do dia\n\n{referencia}\n{versiculo}"
    limite = MAX_TWEET_LEN - len(ASSINATURA)

    if len(base) > limite:
        texto_maximo = max(limite - len(f"📖 Palavra do dia\n\n{referencia}\n") - 3, 0)
        versiculo = versiculo[:texto_maximo].rstrip(" .,;:!?") + "..."
        base = f"📖 Palavra do dia\n\n{referencia}\n{versiculo}"

    postagem = base + ASSINATURA
    if len(postagem) > MAX_TWEET_LEN:
        raise ValueError("Texto da postagem excede o limite de 280 caracteres")

    return postagem


def criar_cliente_x(config):
    return tweepy.Client(
        consumer_key=config["X_CONSUMER_KEY"],
        consumer_secret=config["X_CONSUMER_SECRET"],
        access_token=config["X_ACCESS_TOKEN"],
        access_token_secret=config["X_ACCESS_SECRET"],
    )


def publicar_no_x(cliente, texto):
    try:
        resposta = cliente.create_tweet(text=texto)
        data = resposta.data or {}
        tweet_id = data.get("id")
        logger.info("✅ Post publicado com sucesso. Tweet ID: %s", tweet_id)
        return resposta
    except tweepy.TweepyException as e:
        logger.error("❌ Erro ao publicar no X: %s", e)
        raise


def main():
    try:
        config = carregar_variaveis()
        logger.info("✅ Variáveis carregadas com sucesso")

        referencia, versiculo = pegar_versiculo()
        logger.info("✅ Versículo carregado: %s", referencia)

        texto = montar_texto_postagem(referencia, versiculo)
        logger.info("📝 Texto pronto para postagem (%s caracteres)", len(texto))
        cliente_x = criar_cliente_x(config)
        publicar_no_x(cliente_x, texto)
    except Exception as e:
        logger.exception("❌ Falha na execução do bot: %s", e)
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
