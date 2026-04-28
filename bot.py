import base64
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

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
XAI_IMAGE_API_URL = "https://api.x.ai/v1/images/generations"
XAI_IMAGE_MODEL = "grok-imagine-image"
XAI_IMAGE_ASPECT_RATIO = "1:1"
XAI_IMAGE_RESOLUTION = "1k"
XAI_IMAGE_RESPONSE_FORMAT = "b64_json"

# ====================== FUNÇÕES ======================
def ler_env(nome: str, default: Optional[str] = None) -> Optional[str]:
    valor = os.getenv(nome)
    if valor is None:
        return default

    valor = valor.strip()
    return valor or default


def carregar_variaveis():
    """Carrega e valida as chaves usadas pelo bot."""
    keys = {
        "X_CONSUMER_KEY": ler_env("X_CONSUMER_KEY"),
        "X_CONSUMER_SECRET": ler_env("X_CONSUMER_SECRET"),
        "X_ACCESS_TOKEN": ler_env("X_ACCESS_TOKEN"),
        "X_ACCESS_SECRET": ler_env("X_ACCESS_SECRET"),
        "XAI_API_KEY": ler_env("XAI_API_KEY"),
        "XAI_IMAGE_MODEL": ler_env("XAI_IMAGE_MODEL", XAI_IMAGE_MODEL),
        "XAI_IMAGE_ASPECT_RATIO": ler_env("XAI_IMAGE_ASPECT_RATIO", XAI_IMAGE_ASPECT_RATIO),
        "XAI_IMAGE_RESOLUTION": ler_env("XAI_IMAGE_RESOLUTION", XAI_IMAGE_RESOLUTION),
    }

    obrigatorias_x = (
        "X_CONSUMER_KEY",
        "X_CONSUMER_SECRET",
        "X_ACCESS_TOKEN",
        "X_ACCESS_SECRET",
    )
    missing = [name for name in obrigatorias_x if not keys.get(name)]
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


def montar_prompt_imagem(referencia: str, versiculo: str) -> str:
    return (
        "Crie uma ilustração cristã reverente, inspiradora e apropriada para uma postagem no X, "
        "baseada no significado espiritual do versículo abaixo. Prefira uma representação simbólica "
        "ou uma cena contemplativa, com luz suave, composição elegante e atmosfera de esperança. "
        "Nao inclua letras, palavras, versículos escritos, marcas d'agua, molduras ou assinaturas. "
        f"Referência bíblica: {referencia}. "
        f"Versículo: {versiculo}"
    )


def montar_alt_texto(referencia: str, versiculo: str) -> str:
    texto_base = (
        f"Ilustração inspirada no versículo {referencia}, com tema de fé, esperança e contemplação. "
        f"Versículo-base: {versiculo}"
    )
    return texto_base[:1000]


def detectar_extensao_imagem(conteudo: bytes) -> str:
    if conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"

    if conteudo.startswith(b"\xff\xd8\xff"):
        return ".jpg"

    if conteudo.startswith(b"RIFF") and conteudo[8:12] == b"WEBP":
        return ".webp"

    return ".jpg"


def criar_clientes_x(config):
    auth = tweepy.OAuth1UserHandler(
        config["X_CONSUMER_KEY"],
        config["X_CONSUMER_SECRET"],
        config["X_ACCESS_TOKEN"],
        config["X_ACCESS_SECRET"],
    )
    api_v1 = tweepy.API(auth)
    client_v2 = tweepy.Client(
        consumer_key=config["X_CONSUMER_KEY"],
        consumer_secret=config["X_CONSUMER_SECRET"],
        access_token=config["X_ACCESS_TOKEN"],
        access_token_secret=config["X_ACCESS_SECRET"],
    )
    return client_v2, api_v1


def gerar_imagem_post(config: dict[str, Optional[str]], referencia: str, versiculo: str) -> Path:
    if not config.get("XAI_API_KEY"):
        raise RuntimeError("XAI_API_KEY não configurada")

    prompt = montar_prompt_imagem(referencia, versiculo)
    payload = {
        "model": config["XAI_IMAGE_MODEL"],
        "prompt": prompt,
        "response_format": XAI_IMAGE_RESPONSE_FORMAT,
    }

    if config.get("XAI_IMAGE_ASPECT_RATIO"):
        payload["aspect_ratio"] = config["XAI_IMAGE_ASPECT_RATIO"]

    if config.get("XAI_IMAGE_RESOLUTION"):
        payload["resolution"] = config["XAI_IMAGE_RESOLUTION"]

    resposta = requests.post(
        XAI_IMAGE_API_URL,
        headers={
            "Authorization": f"Bearer {config['XAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    try:
        resposta.raise_for_status()
    except requests.HTTPError as e:
        detalhe = resposta.text.strip()
        raise RuntimeError(f"xAI retornou erro ao gerar imagem: {detalhe}") from e

    data = resposta.json()
    imagens = data.get("data")
    if not isinstance(imagens, list) or not imagens:
        raise RuntimeError("A xAI não retornou uma lista válida de imagens")

    imagem = imagens[0]
    if not isinstance(imagem, dict):
        raise RuntimeError("A xAI retornou um item de imagem inválido")

    logger.info("🧾 xAI respondeu com os campos: %s", ", ".join(sorted(imagem.keys())))

    if isinstance(imagem.get("b64_json"), str) and imagem["b64_json"].strip():
        conteudo = base64.b64decode(imagem["b64_json"])
    elif isinstance(imagem.get("url"), str) and imagem["url"].strip():
        download = requests.get(imagem["url"], timeout=60)
        download.raise_for_status()
        conteudo = download.content
    else:
        raise RuntimeError("A resposta da xAI não trouxe b64_json nem url da imagem")

    extensao = detectar_extensao_imagem(conteudo)
    with tempfile.NamedTemporaryFile(delete=False, suffix=extensao) as arquivo:
        arquivo.write(conteudo)
        caminho = Path(arquivo.name)

    logger.info("🖼️ Imagem gerada com sucesso via xAI em %s", caminho)
    return caminho


def upload_imagem_no_x(api_v1: tweepy.API, caminho_imagem: Path, alt_texto: str) -> str:
    with caminho_imagem.open("rb") as imagem:
        media = api_v1.media_upload(
            filename=caminho_imagem.name,
            file=imagem,
            media_category="tweet_image",
        )

    media_id_numerico = getattr(media, "media_id", None)
    if media_id_numerico is None:
        raise RuntimeError("O X não retornou um media_id válido")

    try:
        api_v1.create_media_metadata(media_id_numerico, alt_texto)
    except tweepy.TweepyException as e:
        logger.warning("⚠️ Não foi possível definir alt text da imagem no X: %s", e)

    media_id = getattr(media, "media_id_string", None) or str(media_id_numerico)
    logger.info("📤 Imagem enviada ao X com media_id=%s", media_id)
    return media_id


def publicar_no_x(cliente, texto, media_id: Optional[str] = None):
    try:
        kwargs = {"text": texto, "user_auth": True}
        if media_id:
            kwargs["media_ids"] = [media_id]

        resposta = cliente.create_tweet(**kwargs)
        data = resposta.data or {}
        tweet_id = data.get("id")
        logger.info("✅ Post publicado com sucesso. Tweet ID: %s", tweet_id)
        return resposta
    except tweepy.errors.Forbidden as e:
        detalhes = []

        api_errors = getattr(e, "api_errors", None)
        if api_errors:
            detalhes.append(f"api_errors={api_errors}")

        api_messages = getattr(e, "api_messages", None)
        if api_messages:
            detalhes.append(f"api_messages={api_messages}")

        response = getattr(e, "response", None)
        if response is not None and getattr(response, "text", None):
            detalhes.append(f"response={response.text}")

        sufixo = f" | {' | '.join(detalhes)}" if detalhes else ""
        logger.error(
            "❌ Erro ao publicar no X: 403 Forbidden. "
            "Verifique permissao Read and write, regeneracao do Access Token/Secret e restricoes da conta.%s",
            sufixo,
        )
        raise
    except tweepy.TweepyException as e:
        logger.error("❌ Erro ao publicar no X: %s", e)
        raise


def main():
    caminho_imagem: Optional[Path] = None
    try:
        config = carregar_variaveis()
        logger.info("✅ Variáveis carregadas com sucesso")

        referencia, versiculo = pegar_versiculo()
        logger.info("✅ Versículo carregado: %s", referencia)

        texto = montar_texto_postagem(referencia, versiculo)
        logger.info("📝 Texto pronto para postagem (%s caracteres)", len(texto))

        cliente_x, api_x_v1 = criar_clientes_x(config)
        media_id = None

        if config.get("XAI_API_KEY"):
            try:
                caminho_imagem = gerar_imagem_post(config, referencia, versiculo)
                media_id = upload_imagem_no_x(
                    api_x_v1,
                    caminho_imagem,
                    montar_alt_texto(referencia, versiculo),
                )
            except Exception as e:
                logger.exception("⚠️ Não foi possível gerar/anexar a imagem. O bot seguirá com texto apenas: %s", e)
        else:
            logger.warning("⚠️ XAI_API_KEY ausente. O bot vai publicar somente texto.")

        publicar_no_x(cliente_x, texto, media_id=media_id)
    except Exception as e:
        logger.exception("❌ Falha na execução do bot: %s", e)
        raise SystemExit(1) from e
    finally:
        if caminho_imagem and caminho_imagem.exists():
            caminho_imagem.unlink(missing_ok=True)
            logger.info("🧹 Arquivo temporário da imagem removido")


if __name__ == "__main__":
    main()
