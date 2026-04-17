import os
import json
import requests
from datetime import datetime
import tweepy
from openai import OpenAI
import fal

print("🚀 BOT INICIADO COM SUCESSO!")
print("✅ Todos os imports carregados")

# ====================== CHAVES ======================
print("🔑 Verificando chaves...")
X_CONSUMER_KEY = os.getenv("X_CONSUMER_KEY")
X_CONSUMER_SECRET = os.getenv("X_CONSUMER_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GROK_API_KEY = os.getenv("GROK_API_KEY")
FAL_KEY = os.getenv("FAL_KEY")

print(f"X_CONSUMER_KEY: {'✅ OK' if X_CONSUMER_KEY else '❌ FALTA'}")
print(f"GROK_API_KEY: {'✅ OK' if GROK_API_KEY else '❌ FALTA'}")
print(f"FAL_KEY: {'✅ OK' if FAL_KEY else '❌ FALTA'}")

# ====================== CLIENTES ======================
print("🔌 Criando clientes...")
grok = OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")
fal.client = fal.Client(key=FAL_KEY)
print("✅ Clientes Grok e fal.ai criados")

# ====================== FUNÇÃO MÍNIMA PARA TESTE ======================
print("📖 Testando função de versículo...")

def pegar_versiculo_teste():
    try:
        r = requests.get("https://bible-api.com/data/almeida/random")
        data = r.json()
        ref = data["reference"]
        texto = data["text"]
        print(f"✅ Versículo obtido: {ref}")
        return ref, texto
    except Exception as e:
        print(f"❌ Erro ao pegar versículo: {e}")
        raise

# ====================== EXECUÇÃO ======================
if __name__ == "__main__":
    print("🔄 Iniciando execução principal...")
    try:
        ref, texto = pegar_versiculo_teste()
        print("✅ Teste finalizado com sucesso!")
        print("📌 O bot está funcionando. Próximo passo: adicionar o resto do código.")
    except Exception as e:
        print(f"💥 ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
