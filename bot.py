import os
import json
import requests
from datetime import datetime, timedelta
import tweepy
from openai import OpenAI
import fal

# ====================== CHAVES ======================
X_CONSUMER_KEY = os.getenv("X_CONSUMER_KEY")
X_CONSUMER_SECRET = os.getenv("X_CONSUMER_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GROK_API_KEY = os.getenv("GROK_API_KEY")
FAL_KEY = os.getenv("FAL_KEY")

# ====================== CLIENTES ======================
grok = OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")
fal.client = fal.Client(key=FAL_KEY)

# ====================== FUNÇÃO PÁSCOA (católica ocidental) ======================
def calcular_pascoa(ano):
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(ano, mes, dia).date()

# ====================== DIAS ESPECIAIS (atualizado para BR) ======================
def detectar_dia_especial(data):
    ano = data.year
    pascoa = calcular_pascoa(ano)
    especial = {
        # Fixos
        datetime(ano, 1, 1).date(): "Solenidade de Santa Maria, Mãe de Deus",
        datetime(ano, 2, 2).date(): "Apresentação do Senhor",
        datetime(ano, 3, 19).date(): "São José",
        datetime(ano, 6, 24).date(): "Natividade de São João Batista",
        datetime(ano, 6, 29).date(): "Santos Pedro e Paulo",
        datetime(ano, 8, 15).date(): "Assunção de Nossa Senhora",
        datetime(ano, 10, 12).date(): "Nossa Senhora Aparecida - Padroeira do Brasil",
        datetime(ano, 11, 1).date(): "Todos os Santos",
        datetime(ano, 12, 8).date(): "Imaculada Conceição",
        datetime(ano, 12, 25).date(): "Natal do Senhor",
        # Móveis (calculados)
        pascoa: "Páscoa da Ressurreição",
        pascoa - timedelta(days=46): "Quarta-feira de Cinzas",
        pascoa + timedelta(days=39): "Ascensão do Senhor",
        pascoa + timedelta(days=49): "Pentecostes",
        pascoa + timedelta(days=56): "Santíssima Trindade",
        pascoa + timedelta(days=60): "Corpus Christi",
    }
    return especial.get(data.date(), None)

# ====================== RESTO DO CÓDIGO (igual ao anterior, só com adaptação) ======================
def carregar_usados():
    try:
        with open("used_verses.json", "r") as f:
            return json.load(f)
    except:
        return []

def salvar_usado(versiculo):
    usados = carregar_usados()
    usados.append(versiculo)
    with open("used_verses.json", "w") as f:
        json.dump(usados[-500:], f)

def pegar_versiculo_tematico(tema_especial):
    prompt = f"""
    Hoje é {tema_especial or 'um dia normal no Tempo Comum'}.
    Escolha um versículo poderoso da Bíblia (Almeida) relacionado ao tema.
    Responda APENAS em JSON:
    {{"referencia": "João 3:16", "texto": "Porque Deus amou o mundo de tal maneira...", "reflexao": "Reflexão curta e profunda (3 frases no máximo, tom acolhedor)" }}
    """
    response = grok.chat.completions.create(
        model="grok-4.1-fast",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return json.loads(response.choices[0].message.content)

def gerar_prompt_imagem(referencia, texto, tema_especial):
    tema = tema_especial or "devocional sereno"
    return f"""
    Imagem bíblica cinematográfica, luz suave dourada, estilo artístico inspirador.
    Tema: {tema}. Inclua o versículo completo em português com tipografia elegante: "{referencia} - {texto}".
    Fundo sereno, elementos simbólicos católicos sutis, alta qualidade, 16:9.
    """

def gerar_imagem(prompt):
    handler = fal.run(
        "fal-ai/flux-pro",
        arguments={"prompt": prompt, "image_size": "landscape_16_9", "num_images": 1}
    )
    img_data = requests.get(handler["images"][0]["url"]).content
    with open("versiculo.png", "wb") as f:
        f.write(img_data)
    return "versiculo.png"

def postar_thread(ref, versiculo, reflexao, imagem_path, tema_especial):
    auth = tweepy.OAuth1UserHandler(X_CONSUMER_KEY, X_CONSUMER_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
    api_v1 = tweepy.API(auth)
    client = tweepy.Client(consumer_key=X_CONSUMER_KEY, consumer_secret=X_CONSUMER_SECRET,
                           access_token=X_ACCESS_TOKEN, access_token_secret=X_ACCESS_SECRET)

    media = api_v1.media_upload(imagem_path)
    post1 = client.create_tweet(
        text=f"📖 {ref}\n\n{versiculo}\n\n#{tema_especial.replace(' ', '') or 'Devocional'} #VersiculoDoDia",
        media_ids=[media.media_id]
    )
    client.create_tweet(text=reflexao, in_reply_to_tweet_id=post1.data.id)
    print(f"✅ Postado: {ref}")

# ====================== EXECUÇÃO ======================
if __name__ == "__main__":
    hoje = datetime.now()
    tema_especial = detectar_dia_especial(hoje)
    
    data = pegar_versiculo_tematico(tema_especial)
    ref = data["referencia"]
    versiculo = data["texto"]
    reflexao = data["reflexao"]
    
    prompt_img = gerar_prompt_imagem(ref, versiculo, tema_especial)
    imagem = gerar_imagem(prompt_img)
    
    postar_thread(ref, versiculo, reflexao, imagem, tema_especial)
    os.remove(imagem)
    salvar_usado(f"{ref}\n{versiculo}")
