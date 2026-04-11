import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from openai import OpenAI

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

# Cargar FAQ (Estructura simple en Español)
def cargar_faq():
    try:
        with open('faq.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "es" in data:
                return data["es"].get("preguntas", [])
            return data.get("preguntas", data)  # Intenta formatos flexibles
    except FileNotFoundError:
        print("Error: ¡Archivo faq.json no encontrado!")
        return []

faq_preguntas = cargar_faq()

# Diccionario de mensajes del sistema (Solo ES)
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
    "sin_faq": "No encontré esa información en nuestro FAQ. Contacta a soporte@plataforma.com."
}

def crear_contexto_faq():
    """Transforma la lista de preguntas en un bloque de texto para el contexto de la IA"""
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
    """Consulta a OpenAI usando el contexto del FAQ"""
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

@bot.event
async def on_ready():
    print(f'✅ {bot.user} está en línea!')
    print(f'📚 FAQ cargado con {len(faq_preguntas)} preguntas.')
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
    async with ctx.typing():
        respuesta, exito = await obtener_respuesta_ia(pregunta)

        if exito:
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

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Responder a menciones
    if bot.user.mentioned_in(message):
        pregunta = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        if pregunta:
            async with message.channel.typing():
                respuesta, exito = await obtener_respuesta_ia(pregunta)
                if exito:
                    await message.reply(respuesta)
                else:
                    await message.reply(MENSAJES["error_ia"])
        return

    await bot.process_commands(message)

if __name__ == "__main__":
    if not DISCORD_TOKEN or not OPENAI_API_KEY:
        print("❌ ERROR: Verifica las claves DISCORD_TOKEN y OPENAI_API_KEY en el .env")
    else:
        bot.run(DISCORD_TOKEN)
