import sys
import logging
import threading
import discord
from discord.ext import commands
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from webserver import keep_alive

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO)

# Cargar variables de entorno
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Configurar intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Crear bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Cliente OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Palabras clave para detectar preguntas técnicas
PALABRAS_TECNICAS = [
    # LLMs y Transformers
    "llm", "large language model", "transformer", "attention mechanism", "bert", "gpt",
    # Redes neuronales
    "red neuronal", "neural network", "cnn", "rnn", "lstm", "convolucional", "recurrente",
    # Aprendizaje por refuerzo
    "reinforcement learning", "aprendizaje por refuerzo", "reward", "policy", "q-learning",
    # Fine-tuning y transfer learning
    "fine-tuning", "fine tuning", "transfer learning", "ajuste fino",
    # Embeddings y bases vectoriales
    "embedding", "vector", "base de datos vectorial", "pinecone", "faiss", "chroma",
    # MLOps y pipelines
    "mlops", "pipeline", "entrenamiento", "training pipeline", "mlflow", "kubeflow",
    # Inferencia y edge
    "inferencia", "edge device", "on-device", "tflite", "onnx",
    # Hardware
    "gpu", "tpu", "npu", "cuda", "tensor core",
    # Cuantización
    "cuantización", "quantization", "pruning", "optimización de modelos",
    # Kubernetes y orquestación
    "kubernetes", "k8s", "docker", "contenedor", "orquestación",
    # Agentes y multi-agente
    "agente autónomo", "multi-agente", "multi agente", "autonomous agent",
    # RAG
    "rag", "retrieval augmented", "retrieval-augmented",
    # Computer vision
    "computer vision", "visión por computadora", "detección de objetos", "segmentación", "yolo",
    # Generación de contenido
    "generación de imágenes", "stable diffusion", "dall-e", "text to image", "generación de video",
    # Copilots
    "copilot", "asistente de código", "code assistant", "github copilot",
    # Seguridad IA
    "prompt injection", "jailbreak", "jailbreaking", "adversarial",
    # Bias y fairness
    "bias", "fairness", "sesgo", "discriminación algorítmica",
    # Interpretabilidad
    "xai", "explainability", "interpretabilidad", "shap", "lime",
    # Alineación
    "ai alignment", "alineación de ia", "rlhf", "constitutional ai",
    # Deepfakes
    "deepfake", "contenido sintético", "detección de deepfakes",
    # Multimodal
    "multimodal", "vision language model", "vlm",
    # Robótica
    "robótica", "drone", "robot", "autonomous vehicle",
    # Computación cuántica
    "computación cuántica", "quantum computing", "qubit",
    # Open source vs propietario
    "llama", "mistral", "open source model", "modelo open source",
    # Tool calling
    "tool calling", "function calling", "herramientas externas",
    # Automatización y no-code/low-code
    "n8n", "automatización", "automatizar", "automation", "zapier", "make", "integromat",
    "workflow", "flujo de trabajo", "trigger", "webhook", "integración", "no-code", "low-code",
    "robotic process automation", "rpa", "airflow", "prefect", "dagster",
    # Términos generales de programación
    "programación", "código", "codificar", "framework", "librería", "library",
    "api rest", "backend", "frontend", "base de datos", "sql", "python", "javascript",
    "java", "c++", "react", "node", "django", "flask", "fastapi", "algoritmo",
    "debugging", "deploy", "deployment", "servidor", "cloud", "aws", "azure", "gcp",
]

HISTORIAL_FILE = 'historial.json'

def cargar_historial():
    if not os.path.exists(HISTORIAL_FILE):
        return []
    try:
        with open(HISTORIAL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def guardar_registro(pregunta, tipo, usuario):
    historial = cargar_historial()
    historial.append({
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario": str(usuario),
        "pregunta": pregunta,
        "tipo": tipo  # "respondida", "tecnica", "sin_faq"
    })
    with open(HISTORIAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)

def es_pregunta_tecnica(texto):
    texto_lower = texto.lower()
    return any(palabra in texto_lower for palabra in PALABRAS_TECNICAS)

# Cargar FAQ
def cargar_faq():
    try:
        with open('faq.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            preguntas = []
            for seccion, contenido in data.items():
                if seccion == "config":
                    continue
                if isinstance(contenido, dict):
                    items = contenido.get("preguntas_respuestas", contenido.get("preguntas", []))
                    for item in items:
                        if "pregunta" in item and "respuesta" in item:
                            if "categoria" not in item:
                                item["categoria"] = seccion.replace("_", " ").title()
                            preguntas.append(item)
                elif isinstance(contenido, list):
                    for item in contenido:
                        if "pregunta" in item and "respuesta" in item:
                            preguntas.append(item)
            return preguntas
    except FileNotFoundError:
        print("Error: ¡Archivo faq.json no encontrado!")
        return []

faq_preguntas = cargar_faq()

# Diccionario de mensajes del sistema
MENSAJES = {
    "ayuda_titulo": "🤖 Bot de Soporte con IA",
    "ayuda_desc": "¡Utilizo GPT-4 para responder tus dudas basándome en nuestro FAQ!",
    "cmd_preguntar": "!preguntar <tu pregunta>",
    "cmd_preguntar_desc": "Haz una pregunta de forma natural y te respondo usando el FAQ.",
    "cmd_lista": "!lista",
    "cmd_lista_desc": "Ver las categorías disponibles en el FAQ.",
    "cmd_categoria": "!categoria <nombre>",
    "cmd_categoria_desc": "Ver preguntas de una categoría específica.",
    "cmd_buscar": "!buscar <término>",
    "cmd_buscar_desc": "Buscar por palabras clave específicas.",
    "footer_ayuda": "💡 ¡También puedes mencionarme directamente en el chat!",
    "error_ia": "Lo siento, ocurrió un error al procesar tu respuesta. Inténtalo de nuevo más tarde.",
    "sin_faq": "No encontré esa información en nuestro FAQ. Por favor contacta a soporte escribiendo a contacto-one@aluracursos.com o contacta directamente con CMs Leti Farias o WarCap en el servidor de Discord.",
    "pregunta_tecnica": "¡Hola! 👋 Soy el asistente del programa **Oracle Next Education (ONE)** y estoy especializado en responder dudas sobre el programa, la fase de inmersión, certificados y acceso a la plataforma. Para consultas técnicas sobre programación, IA o tecnología en general, te recomiendo explorar los canales especializados del servidor o preguntar en la comunidad. Si tienes alguna duda específica sobre el programa ONE, ¡con gusto te ayudo! 😊",
}

def crear_contexto_faq():
    contexto = "# BASE DE CONOCIMIENTO DE LA PLATAFORMA\n\n"
    categorias = {}
    for item in faq_preguntas:
        cat = item.get('categoria', 'General')
        if cat not in categorias:
            categorias[cat] = []
        categorias[cat].append(item)
    for categoria, items in categorias.items():
        contexto += f"## Categoría: {categoria}\n"
        for item in items:
            contexto += f"P: {item['pregunta']}\nR: {item['respuesta']}\n\n"
    return contexto

async def obtener_respuesta_ia(pregunta_usuario):
    try:
        contexto = crear_contexto_faq()
        system_prompt = f"""RESPONDE SIEMPRE EN ESPAÑOL. Eres un asistente de soporte especializado.

{contexto}

INSTRUCCIONES:
1. Usa ÚNICAMENTE la información anterior para responder.
2. Sé amigable, educado y usa emojis con moderación.
3. Si la información no está en el texto, usa la frase: "{MENSAJES['sin_faq']}"
4. Responde de forma concisa (máximo 2-3 párrafos).
5. Usa negrita para destacar puntos importantes.
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pregunta_usuario}
            ],
            temperature=0.5
        )
        return response.choices[0].message.content, True
    except Exception as e:
        print(f"Error OpenAI: {e}")
        return None, False

def tiene_rol_admin(member):
    return any(role.name.lower() == "admin" for role in member.roles) or member.guild_permissions.administrator

@bot.event
async def on_ready():
    logging.info(f'Bot online: {bot.user}')
    logging.info(f'FAQ cargado con {len(faq_preguntas)} preguntas.')
    await bot.change_presence(activity=discord.Game(name="!ayuda | Soporte ES 🇪🇸"))

@bot.command(name='ayuda')
async def ayuda(ctx):
    embed = discord.Embed(
        title=MENSAJES["ayuda_titulo"],
        description=MENSAJES["ayuda_desc"],
        color=discord.Color.blue()
    )
    embed.add_field(name=MENSAJES["cmd_preguntar"], value=MENSAJES["cmd_preguntar_desc"], inline=False)
    embed.add_field(name=MENSAJES["cmd_lista"], value=MENSAJES["cmd_lista_desc"], inline=False)
    embed.add_field(name=MENSAJES["cmd_categoria"], value=MENSAJES["cmd_categoria_desc"], inline=False)
    embed.add_field(name=MENSAJES["cmd_buscar"], value=MENSAJES["cmd_buscar_desc"], inline=False)
    embed.set_footer(text=MENSAJES["footer_ayuda"])
    await ctx.send(embed=embed)

@bot.command(name='preguntar')
async def preguntar(ctx, *, pregunta: str):
    if es_pregunta_tecnica(pregunta):
        guardar_registro(pregunta, "tecnica", ctx.author)
        await ctx.send(MENSAJES["pregunta_tecnica"])
    else:
        async with ctx.typing():
            respuesta, exito = await obtener_respuesta_ia(pregunta)

            if exito:
                if MENSAJES['sin_faq'] in respuesta:
                    guardar_registro(pregunta, "sin_faq", ctx.author)
                else:
                    guardar_registro(pregunta, "respondida", ctx.author)

                embed = discord.Embed(
                    title="🤖 Respuesta de la IA",
                    description=respuesta,
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"Respondiendo a {ctx.author.display_name} • GPT-4o-mini")
                await ctx.send(embed=embed)
            else:
                await ctx.send(MENSAJES["error_ia"])

@bot.command(name='lista')
async def lista(ctx):
    categorias = sorted(list(set([p.get('categoria', 'General') for p in faq_preguntas])))
    embed = discord.Embed(title="📚 Categorías del FAQ", color=discord.Color.purple())
    for cat in categorias:
        count = len([p for p in faq_preguntas if p.get('categoria') == cat])
        embed.add_field(name=cat, value=f"{count} preguntas. Usa `!categoria {cat}`", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='categoria')
async def categoria(ctx, *, nombre: str):
    items = [p for p in faq_preguntas if p.get('categoria', '').lower() == nombre.lower()]
    if not items:
        return await ctx.send(f"❌ Categoría `{nombre}` no encontrada.")
    embed = discord.Embed(title=f"📁 Categoría: {nombre}", color=discord.Color.gold())
    for i, item in enumerate(items[:10], 1):
        embed.add_field(name=f"{i}. {item['pregunta']}", value="Puedes preguntar los detalles usando `!preguntar`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='buscar')
async def buscar(ctx, *, termino: str):
    resultados = [p for p in faq_preguntas if termino.lower() in p['pregunta'].lower() or termino.lower() in p['respuesta'].lower()]
    if not resultados:
        return await ctx.send(f"🔍 Ningún resultado para `{termino}`.")
    embed = discord.Embed(title=f"🔍 Resultados para: {termino}", color=discord.Color.blue())
    for p in resultados[:5]:
        embed.add_field(name=p['pregunta'], value=p['respuesta'][:150] + "...", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='informe')
async def informe(ctx, desde: str = None, hasta: str = None):
    if not tiene_rol_admin(ctx.author):
        await ctx.send("❌ No tienes permiso para usar este comando.")
        return

    historial = cargar_historial()

    # Filtrar por fechas si se pasan
    if desde or hasta:
        try:
            fecha_desde = datetime.strptime(desde, "%Y-%m-%d") if desde else datetime.min
            fecha_hasta = datetime.strptime(hasta, "%Y-%m-%d").replace(hour=23, minute=59, second=59) if hasta else datetime.max
            historial = [
                r for r in historial
                if fecha_desde <= datetime.strptime(r["fecha"], "%Y-%m-%d %H:%M:%S") <= fecha_hasta
            ]
        except ValueError:
            await ctx.send("❌ Formato de fecha inválido. Usa `YYYY-MM-DD`. Ejemplo: `!informe 2026-05-01 2026-05-11`")
            return

    total = len(historial)
    respondidas = sum(1 for r in historial if r["tipo"] == "respondida")
    tecnicas = sum(1 for r in historial if r["tipo"] == "tecnica")
    sin_faq = sum(1 for r in historial if r["tipo"] == "sin_faq")
    preguntas_sin_faq = [r for r in historial if r["tipo"] == "sin_faq"]

    periodo = ""
    if desde and hasta:
        periodo = f" ({desde} → {hasta})"
    elif desde:
        periodo = f" (desde {desde})"
    elif hasta:
        periodo = f" (hasta {hasta})"

    embed = discord.Embed(
        title=f"📊 Informe del Bot{periodo}",
        color=discord.Color.blurple()
    )
    embed.add_field(name="📨 Total de preguntas", value=str(total), inline=True)
    embed.add_field(name="✅ Respondidas correctamente", value=str(respondidas), inline=True)
    embed.add_field(name="🔧 Preguntas técnicas", value=str(tecnicas), inline=True)
    embed.add_field(name="❓ Sin respuesta (sin_faq)", value=str(sin_faq), inline=True)

    if preguntas_sin_faq:
        lista_sin_faq = "\n".join(
            f"• [{r['fecha'][:10]}] {r['pregunta'][:80]}{'...' if len(r['pregunta']) > 80 else ''}"
            for r in preguntas_sin_faq[:10]
        )
        embed.add_field(
            name="📝 Preguntas sin respuesta (para alimentar FAQ)",
            value=lista_sin_faq,
            inline=False
        )
        if len(preguntas_sin_faq) > 10:
            embed.set_footer(text=f"Mostrando 10 de {len(preguntas_sin_faq)} preguntas sin respuesta.")

    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    logging.info(f'Mensaje de {message.author}: {message.content[:80]}')

    # Detectar menciones de usuario o de rol del bot
    bot_mencionado = bot.user.mentioned_in(message)
    if not bot_mencionado and message.guild:
        bot_member = message.guild.get_member(bot.user.id)
        if bot_member:
            bot_mencionado = any(role in message.role_mentions for role in bot_member.roles)

    # Responder a menciones
    if bot_mencionado:
        pregunta = message.content
        for mention in message.mentions:
            pregunta = pregunta.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        for role in message.role_mentions:
            pregunta = pregunta.replace(f'<@&{role.id}>', '')
        pregunta = pregunta.strip()

        if pregunta:
            if es_pregunta_tecnica(pregunta):
                guardar_registro(pregunta, "tecnica", message.author)
                await message.reply(MENSAJES["pregunta_tecnica"])
            else:
                async with message.channel.typing():
                    respuesta, exito = await obtener_respuesta_ia(pregunta)
                    if exito:
                        if MENSAJES['sin_faq'] in respuesta:
                            guardar_registro(pregunta, "sin_faq", message.author)
                        else:
                            guardar_registro(pregunta, "respondida", message.author)
                        await message.reply(respuesta)
                    else:
                        await message.reply(MENSAJES["error_ia"])
        return

    await bot.process_commands(message)

if __name__ == "__main__":
    if not DISCORD_TOKEN or not OPENAI_API_KEY:
        print("❌ ERROR: Verifica las claves DISCORD_TOKEN y OPENAI_API_KEY en el .env")
    else:
        keep_alive()
        bot.run(DISCORD_TOKEN)
