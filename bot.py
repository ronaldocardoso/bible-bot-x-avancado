import base64
import json
import logging
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
import tweepy
from PIL import Image, ImageDraw, ImageFont

# ====================== CONFIGURAÇÃO DE LOG ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

logger.info("🚀 BOT Palavra do Dia iniciado!")

BIBLE_RANDOM_API_URL = "https://bible-api.com/data/almeida/random"
BIBLE_PASSAGE_API_URL = "https://bible-api.com/"
LITURGICAL_CALENDAR_API_URL = "https://cpbjr.github.io/catholic-readings-api/liturgical-calendar"
LITURGICAL_READINGS_API_URL = "https://cpbjr.github.io/catholic-readings-api/readings"
BRAZIL_LITURGICAL_ICS_URL_TEMPLATE = "https://gcatholic.org/calendar/ics/{year}-pt-BR.ics?v=3"
ASSINATURA = "\n\n#Biblia #VersiculoDoDia"
MAX_TWEET_LEN = 280
DEFAULT_BOT_TIMEZONE = "America/Sao_Paulo"
XAI_IMAGE_API_URL = "https://api.x.ai/v1/images/generations"
XAI_IMAGE_MODEL = "grok-imagine-image"
XAI_IMAGE_ASPECT_RATIO = "1:1"
XAI_IMAGE_RESOLUTION = "1k"
XAI_IMAGE_RESPONSE_FORMAT = "b64_json"
IMAGE_SIGNATURE_TEXT = "@PalavraDoDiaBR"
TIPOS_CELEBRACAO_ESPECIAIS = {"SOLEMNITY", "FEAST", "MEMORIAL", "OPT_MEMORIAL"}
TIPOS_CELEBRACAO_PT = {
    "SOLEMNITY": "Solenidade",
    "FEAST": "Festa",
    "MEMORIAL": "Memória",
    "OPT_MEMORIAL": "Memória facultativa",
    "FERIA": "Dia ferial",
    "SUNDAY": "Domingo",
    "LITURGICAL_DAY": "Dia litúrgico",
}
SOURCE_BRAZIL_NATIONAL = "BRAZIL_NATIONAL"
SOURCE_DIOCESAN = "DIOCESAN"
SOURCE_GLOBAL_FALLBACK = "GLOBAL_FALLBACK"
ARQUIVO_CALENDARIO_DIOCESANO_PADRAO = "diocesan_calendar.json"

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
        "BOT_TIMEZONE": ler_env("BOT_TIMEZONE", DEFAULT_BOT_TIMEZONE),
        "DIOCESAN_CALENDAR_FILE": ler_env("DIOCESAN_CALENDAR_FILE", ARQUIVO_CALENDARIO_DIOCESANO_PADRAO),
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
        r = requests.get(BIBLE_RANDOM_API_URL, timeout=30)
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


def obter_data_postagem(config: dict[str, Optional[str]]) -> date:
    timezone_nome = config.get("BOT_TIMEZONE") or DEFAULT_BOT_TIMEZONE
    try:
        return datetime.now(ZoneInfo(timezone_nome)).date()
    except Exception as e:
        logger.warning(
            "⚠️ Fuso horário inválido em BOT_TIMEZONE (%s). Usando %s. Detalhe: %s",
            timezone_nome,
            DEFAULT_BOT_TIMEZONE,
            e,
        )
        return datetime.now(ZoneInfo(DEFAULT_BOT_TIMEZONE)).date()


def montar_url_endpoint(base_url: str, data_ref: date) -> str:
    return f"{base_url}/{data_ref.year}/{data_ref:%m-%d}.json"


def buscar_json(url: str) -> dict[str, Any]:
    resposta = requests.get(url, timeout=30)
    resposta.raise_for_status()
    data = resposta.json()
    if not isinstance(data, dict):
        raise ValueError(f"Resposta JSON inválida para {url}")
    return data


def normalizar_referencia_biblica(referencia: str) -> str:
    referencia = referencia.split("|", 1)[0].strip()
    referencia = re.sub(r"(?<=\d)([a-z]+)\b", "", referencia, flags=re.IGNORECASE)
    referencia = " ".join(referencia.split())
    return referencia


def pegar_passagem(referencia: str) -> tuple[str, str]:
    referencia_normalizada = normalizar_referencia_biblica(referencia)
    url = f"{BIBLE_PASSAGE_API_URL}{quote(referencia_normalizada)}?translation=almeida"

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            raise ValueError("Resposta da API bíblica não é um objeto JSON válido")

        ref, texto = extrair_referencia_e_texto(data)
        return ref, texto
    except requests.exceptions.RequestException as e:
        logger.error("❌ Erro ao buscar passagem bíblica (%s): %s", referencia_normalizada, e)
        raise
    except ValueError as e:
        logger.error("❌ Erro ao processar passagem bíblica (%s): %s", referencia_normalizada, e)
        raise


def traduzir_tipo_celebracao(tipo: str) -> str:
    return TIPOS_CELEBRACAO_PT.get(tipo, tipo)


def pegar_tema_liturgico_padrao(data_ref: date) -> Optional[dict[str, str]]:
    url = montar_url_endpoint(LITURGICAL_CALENDAR_API_URL, data_ref)
    try:
        data = buscar_json(url)
    except Exception as e:
        logger.warning("⚠️ Não foi possível consultar o calendário católico (%s): %s", data_ref.isoformat(), e)
        return None

    celebracao = data.get("celebration")
    if not isinstance(celebracao, dict):
        return None

    tipo = celebracao.get("type")
    nome = celebracao.get("name")
    if not isinstance(tipo, str) or not isinstance(nome, str) or not nome.strip():
        return None

    if tipo not in TIPOS_CELEBRACAO_ESPECIAIS:
        logger.info("ℹ️ Dia litúrgico sem celebração especial (%s)", tipo)
        return None

    tema = {
        "date": data_ref.isoformat(),
        "season": str(data.get("season", "")).strip(),
        "name": " ".join(nome.split()),
        "type": tipo,
        "type_pt": traduzir_tipo_celebracao(tipo),
        "description": " ".join(str(celebracao.get("description", "")).split()),
        "quote": " ".join(str(celebracao.get("quote", "")).split()),
        "source": SOURCE_GLOBAL_FALLBACK,
    }
    logger.info("✝️ Tema litúrgico detectado: %s (%s)", tema["name"], tema["type_pt"])
    return tema


def desenrolar_linhas_ics(texto: str) -> list[str]:
    linhas: list[str] = []
    for linha in texto.splitlines():
        if linha.startswith((" ", "\t")) and linhas:
            linhas[-1] += linha[1:]
        else:
            linhas.append(linha)
    return linhas


def parsear_eventos_ics(texto: str) -> list[dict[str, str]]:
    eventos: list[dict[str, str]] = []
    evento_atual: Optional[dict[str, str]] = None

    for linha in desenrolar_linhas_ics(texto):
        if linha == "BEGIN:VEVENT":
            evento_atual = {}
            continue

        if linha == "END:VEVENT":
            if evento_atual:
                eventos.append(evento_atual)
            evento_atual = None
            continue

        if evento_atual is None or ":" not in linha:
            continue

        chave, valor = linha.split(":", 1)
        evento_atual[chave] = valor

    return eventos


def desescapar_ics(texto: str) -> str:
    return (
        texto.replace("\\n", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def parsear_resumo_gcatholic(resumo: str) -> tuple[Optional[str], str]:
    resumo_limpo = desescapar_ics(resumo).strip()
    match = re.match(r"^\S+\s(?:\[(?P<grau>[SFMm])\]\s)?(?P<nome>.+)$", resumo_limpo)
    if not match:
        return None, resumo_limpo

    grau = match.group("grau")
    nome = " ".join(match.group("nome").split())
    return grau, nome


def extrair_descricao_gcatholic(descricao: str) -> str:
    primeira_linha = desescapar_ics(descricao).split("\n", 1)[0].strip()
    primeira_linha = primeira_linha.strip("() ")
    return " ".join(primeira_linha.split())


def nome_ferial_generico(nome: str) -> bool:
    if nome == "Nossa Senhora no Sábado":
        return True

    return bool(
        re.match(
            r"^(Segunda-Feira|Terça-Feira|Quarta-Feira|Quinta-Feira|Sexta-Feira|Sábado)\b",
            nome,
        )
    )


def tipo_por_resumo_gcatholic(grau: Optional[str], nome: str) -> Optional[str]:
    if grau == "S":
        return "SOLEMNITY"
    if grau == "F":
        return "FEAST"
    if grau == "M":
        return "MEMORIAL"
    if grau == "m":
        return "OPT_MEMORIAL"
    if nome.startswith("Domingo"):
        return "SUNDAY"
    if nome_ferial_generico(nome):
        return None
    return "LITURGICAL_DAY"


def pontuar_tema_gcatholic(tipo: Optional[str]) -> int:
    prioridades = {
        "SOLEMNITY": 500,
        "FEAST": 400,
        "SUNDAY": 350,
        "MEMORIAL": 300,
        "OPT_MEMORIAL": 200,
        "LITURGICAL_DAY": 100,
    }
    return prioridades.get(tipo or "", 0)


def carregar_eventos_calendario_brasileiro(ano: int) -> dict[str, list[dict[str, str]]]:
    url = BRAZIL_LITURGICAL_ICS_URL_TEMPLATE.format(year=ano)
    resposta = requests.get(url, timeout=45)
    resposta.raise_for_status()
    texto_ics = resposta.content.decode("utf-8", errors="replace")

    eventos_por_data: dict[str, list[dict[str, str]]] = {}
    for evento in parsear_eventos_ics(texto_ics):
        data_bruta = evento.get("DTSTART;VALUE=DATE")
        resumo = evento.get("SUMMARY")
        if not data_bruta or not resumo:
            continue

        if not re.match(r"^\d{8}$", data_bruta):
            continue

        data_iso = f"{data_bruta[0:4]}-{data_bruta[4:6]}-{data_bruta[6:8]}"
        grau, nome = parsear_resumo_gcatholic(resumo)
        tipo = tipo_por_resumo_gcatholic(grau, nome)
        descricao = extrair_descricao_gcatholic(evento.get("DESCRIPTION", ""))
        eventos_por_data.setdefault(data_iso, []).append(
            {
                "name": nome,
                "type": tipo or "FERIA",
                "type_pt": traduzir_tipo_celebracao(tipo or "FERIA"),
                "description": descricao,
                "quote": "",
                "source": SOURCE_BRAZIL_NATIONAL,
                "priority": str(pontuar_tema_gcatholic(tipo)),
            }
        )

    return eventos_por_data


def escolher_melhor_evento(eventos: list[dict[str, str]]) -> Optional[dict[str, str]]:
    if not eventos:
        return None

    melhor = max(eventos, key=lambda item: int(item.get("priority", "0")))
    if int(melhor.get("priority", "0")) <= 0:
        return None
    return melhor


def consultar_tema_liturgico_brasil(data_ref: date) -> tuple[Optional[dict[str, str]], bool]:
    try:
        eventos_por_data = carregar_eventos_calendario_brasileiro(data_ref.year)
    except Exception as e:
        logger.warning("⚠️ Não foi possível consultar o calendário católico brasileiro (%s): %s", data_ref.year, e)
        return None, False

    melhor = escolher_melhor_evento(eventos_por_data.get(data_ref.isoformat(), []))
    if not melhor:
        logger.info("ℹ️ Dia litúrgico brasileiro sem tema especial em %s", data_ref.isoformat())
        return None, True

    tema = dict(melhor)
    tema["date"] = data_ref.isoformat()
    logger.info("🇧🇷 Tema litúrgico brasileiro detectado: %s (%s)", tema["name"], tema["type_pt"])
    return tema, True


def carregar_calendario_diocesano(config: dict[str, Optional[str]]) -> dict[str, Any]:
    caminho = config.get("DIOCESAN_CALENDAR_FILE")
    if not caminho:
        return {}

    arquivo = Path(caminho)
    if not arquivo.exists():
        return {}

    try:
        data = json.loads(arquivo.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("⚠️ Não foi possível ler o calendário diocesano em %s: %s", arquivo, e)
        return {}

    return data if isinstance(data, dict) else {}


def pegar_tema_liturgico_diocesano(config: dict[str, Optional[str]], data_ref: date) -> Optional[dict[str, str]]:
    calendario = carregar_calendario_diocesano(config)
    celebracoes = calendario.get("celebrations")
    if not isinstance(celebracoes, list):
        return None

    alvo_iso = data_ref.isoformat()
    alvo_mes_dia = data_ref.strftime("%m-%d")
    diocese = " ".join(str(calendario.get("diocese", "")).split())

    for item in celebracoes:
        if not isinstance(item, dict):
            continue

        data_item = str(item.get("date", "")).strip()
        mes_dia = str(item.get("month_day", "")).strip()
        if data_item != alvo_iso and mes_dia != alvo_mes_dia:
            continue

        nome = " ".join(str(item.get("name", "")).split())
        if not nome:
            continue

        tipo = str(item.get("type", "SOLEMNITY")).strip() or "SOLEMNITY"
        tema = {
            "date": alvo_iso,
            "season": "",
            "name": nome,
            "type": tipo,
            "type_pt": traduzir_tipo_celebracao(tipo),
            "description": " ".join(str(item.get("description", "")).split()),
            "quote": " ".join(str(item.get("quote", "")).split()),
            "source": SOURCE_DIOCESAN,
            "diocese": diocese,
            "reference": " ".join(str(item.get("reference", "")).split()),
        }
        logger.info("⛪ Tema litúrgico diocesano detectado: %s (%s)", tema["name"], diocese or "diocese local")
        return tema

    return None


def resolver_tema_liturgico(config: dict[str, Optional[str]], data_ref: date) -> Optional[dict[str, str]]:
    tema_diocesano = pegar_tema_liturgico_diocesano(config, data_ref)
    if tema_diocesano:
        return tema_diocesano

    tema_brasil, consultado_brasil = consultar_tema_liturgico_brasil(data_ref)
    if consultado_brasil:
        return tema_brasil

    return pegar_tema_liturgico_padrao(data_ref)


def escolher_referencia_liturgica(readings: dict[str, Any]) -> Optional[str]:
    for chave in ("gospel", "firstReading", "secondReading", "psalm"):
        valor = readings.get(chave)
        if isinstance(valor, str) and valor.strip():
            return valor
    return None


def pegar_versiculo_liturgico(data_ref: date) -> Optional[tuple[str, str]]:
    url = montar_url_endpoint(LITURGICAL_READINGS_API_URL, data_ref)
    try:
        data = buscar_json(url)
    except Exception as e:
        logger.warning("⚠️ Não foi possível consultar as leituras católicas (%s): %s", data_ref.isoformat(), e)
        return None

    readings = data.get("readings")
    if not isinstance(readings, dict):
        return None

    referencia = escolher_referencia_liturgica(readings)
    if not referencia:
        return None

    try:
        return pegar_passagem(referencia)
    except Exception as e:
        logger.warning("⚠️ Não foi possível usar a leitura litúrgica do dia (%s): %s", referencia, e)
        return None


def preparar_conteudo_postagem(config: dict[str, Optional[str]]) -> tuple[Optional[dict[str, str]], str, str]:
    data_postagem = obter_data_postagem(config)
    logger.info("🗓️ Data da postagem considerada para o calendário católico: %s", data_postagem.isoformat())

    tema = resolver_tema_liturgico(config, data_postagem)
    if tema and tema.get("source") == SOURCE_DIOCESAN and tema.get("reference"):
        try:
            referencia, versiculo = pegar_passagem(tema["reference"])
            return tema, referencia, versiculo
        except Exception as e:
            logger.warning("⚠️ Não foi possível usar a referência bíblica diocesana configurada: %s", e)

    if tema and tema.get("source") == SOURCE_GLOBAL_FALLBACK:
        versiculo_liturgico = pegar_versiculo_liturgico(data_postagem)
        if versiculo_liturgico:
            return tema, versiculo_liturgico[0], versiculo_liturgico[1]

        logger.warning("⚠️ O tema litúrgico será mantido, mas o versículo cairá para o modo aleatório.")

    referencia, versiculo = pegar_versiculo()
    return tema, referencia, versiculo


def resumir_texto(texto: str, limite: int) -> str:
    if len(texto) <= limite:
        return texto

    return texto[: max(limite - 3, 0)].rstrip(" .,;:!?") + "..."


def montar_texto_postagem(referencia, versiculo, tema: Optional[dict[str, str]] = None):
    prefixo = "📖 Palavra do dia\n\n"
    if tema:
        tema_resumido = resumir_texto(tema["name"], 85)
        prefixo += f"Tema: {tema_resumido} ({tema['type_pt']})\n\n"

    prefixo += f"{referencia}\n"
    base = prefixo + versiculo
    limite = MAX_TWEET_LEN - len(ASSINATURA)

    if len(base) > limite:
        texto_maximo = max(limite - len(prefixo) - 3, 0)
        versiculo = versiculo[:texto_maximo].rstrip(" .,;:!?") + "..."
        base = prefixo + versiculo

    postagem = base + ASSINATURA
    if len(postagem) > MAX_TWEET_LEN:
        raise ValueError("Texto da postagem excede o limite de 280 caracteres")

    return postagem


def montar_prompt_imagem(referencia: str, versiculo: str, tema: Optional[dict[str, str]] = None) -> str:
    contexto_liturgico = ""
    if tema:
        partes = [
            f"Tema litúrgico do dia: {tema['name']}.",
            f"Tipo de celebração: {tema['type_pt']}.",
        ]
        if tema.get("diocese"):
            partes.append(f"Contexto diocesano: {tema['diocese']}.")
        if tema.get("season"):
            partes.append(f"Tempo litúrgico: {tema['season']}.")
        if tema.get("description"):
            partes.append(f"Contexto: {tema['description']}.")
        if tema.get("quote"):
            partes.append(f"Inspiração adicional: {tema['quote']}.")
        contexto_liturgico = " ".join(partes) + " "

    return (
        "Crie uma ilustração cristã reverente, inspiradora e apropriada para uma postagem no X, "
        "baseada no significado espiritual do versículo abaixo. "
        f"{contexto_liturgico}"
        "Prefira uma representação simbólica ou uma cena contemplativa, com luz suave, composição elegante "
        "e atmosfera de esperança. "
        "Nao inclua letras, palavras, versículos escritos, marcas d'agua, molduras ou assinaturas. "
        f"Referência bíblica: {referencia}. "
        f"Versículo: {versiculo}"
    )


def montar_alt_texto(referencia: str, versiculo: str, tema: Optional[dict[str, str]] = None) -> str:
    partes = []
    if tema:
        partes.append(f"Ilustração inspirada na celebração católica do dia: {tema['name']}.")
        if tema.get("diocese"):
            partes.append(f"Referência local: {tema['diocese']}.")
    else:
        partes.append("Ilustração inspirada em um versículo bíblico.")

    partes.append(f"Referência: {referencia}.")
    partes.append(f"Versículo-base: {versiculo}")
    texto_base = " ".join(partes)
    return texto_base[:1000]


def detectar_extensao_imagem(conteudo: bytes) -> str:
    if conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"

    if conteudo.startswith(b"\xff\xd8\xff"):
        return ".jpg"

    if conteudo.startswith(b"RIFF") and conteudo[8:12] == b"WEBP":
        return ".webp"

    return ".jpg"


def carregar_fonte_assinatura(tamanho: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", tamanho)
    except OSError:
        return ImageFont.load_default()


def assinar_imagem(caminho_imagem: Path, assinatura: str = IMAGE_SIGNATURE_TEXT) -> None:
    with Image.open(caminho_imagem) as imagem_original:
        imagem = imagem_original.convert("RGBA")

        largura, altura = imagem.size
        tamanho_fonte = max(18, min(largura, altura) // 28)
        margem = max(18, min(largura, altura) // 30)
        padding_x = max(10, tamanho_fonte // 2)
        padding_y = max(6, tamanho_fonte // 3)

        fonte = carregar_fonte_assinatura(tamanho_fonte)
        overlay = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        caixa_texto = draw.textbbox((0, 0), assinatura, font=fonte)
        largura_texto = caixa_texto[2] - caixa_texto[0]
        altura_texto = caixa_texto[3] - caixa_texto[1]

        x_texto = largura - largura_texto - margem - padding_x
        y_texto = altura - altura_texto - margem - padding_y
        caixa_fundo = (
            x_texto - padding_x,
            y_texto - padding_y,
            x_texto + largura_texto + padding_x,
            y_texto + altura_texto + padding_y,
        )

        draw.rounded_rectangle(caixa_fundo, radius=max(8, tamanho_fonte // 3), fill=(0, 0, 0, 90))
        draw.text((x_texto, y_texto), assinatura, font=fonte, fill=(255, 255, 255, 185))

        imagem_assinada = Image.alpha_composite(imagem, overlay)
        formato = imagem_original.format or "PNG"
        if formato.upper() in {"JPEG", "JPG"}:
            imagem_assinada = imagem_assinada.convert("RGB")

        imagem_assinada.save(caminho_imagem, format=formato)

    logger.info("✍️ Assinatura aplicada na imagem: %s", assinatura)


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


def gerar_imagem_post(
    config: dict[str, Optional[str]],
    referencia: str,
    versiculo: str,
    tema: Optional[dict[str, str]] = None,
) -> Path:
    if not config.get("XAI_API_KEY"):
        raise RuntimeError("XAI_API_KEY não configurada")

    prompt = montar_prompt_imagem(referencia, versiculo, tema=tema)
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

    assinar_imagem(caminho)
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

        tema, referencia, versiculo = preparar_conteudo_postagem(config)
        logger.info("✅ Conteúdo carregado: %s", referencia)

        texto = montar_texto_postagem(referencia, versiculo, tema=tema)
        logger.info("📝 Texto pronto para postagem (%s caracteres)", len(texto))

        cliente_x, api_x_v1 = criar_clientes_x(config)
        media_id = None

        if config.get("XAI_API_KEY"):
            try:
                caminho_imagem = gerar_imagem_post(config, referencia, versiculo, tema=tema)
                media_id = upload_imagem_no_x(
                    api_x_v1,
                    caminho_imagem,
                    montar_alt_texto(referencia, versiculo, tema=tema),
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
