import os
import logging
import requests
import tempfile
from datetime import datetime

import tweepy
from openai import OpenAI
import fal

# ====================== CONFIGURAÇÃO DE LOG ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

logger.info("🚀 BOT Palavra do Dia iniciado!")

# ====================== CHAVES ======================
X_CONSUMER_KEY = os.getenv("X_CONSUMER_KEY")
X_CONSUMER_SECRET = os.getenv("X_CONSUMER_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GROK_API_KEY = os.getenv("GROK_API_KEY")
FAL_KEY = os.getenv("FAL_KEY")

# Validação das chaves
missing = [k for k, v in {
    "X_CONSUMER_KEY": X_CONSUMER_KEY,
    "X_CONSUMER_SECRET": X_CONSUMER_SECRET,
    "X_ACCESS_TOKEN": X_ACCESS_TOKEN,
    "X_ACCESS_SECRET": X_ACCESS_SECRET,
    "GROK_API_KEY": GROK_API_KEY,
    "FAL_KEY": FAL_KEY
}.items() if not v]

if missing:
    logger.error(f"❌ Faltando chaves: {', '.join(missing)}")
    raise SystemExit(1)

logger.info("✅ Todas as chaves carregadas com sucesso")

# ====================== CLIENTES ======================
grok_client = OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")
fal_client = fal.Client(key=FAL_KEY)

logger.info("✅ Clientes Grok e fal.ai criados")

# ====================== FUNÇÕES ======================
def pegar_versiculo():
    """Pega um versículo aleatório da Bíblia (Almeida)"""
    try:
        r = requests.get("https://bible-api.com/data/almeida/random")
        r.raise_for_status()
        data = r.json()
        ref = data["reference"]
        texto =
