import math
import os
from random import choice, randint, shuffle, uniform
import sys
import threading
import time
from io import BytesIO

# Al ejecutarse como app, guardar recursos y ajustes en una carpeta escribible.
if getattr(sys, "frozen", False):
    if sys.platform == "darwin":
        DIRECTORIO_JUEGO = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "KINETIX")
    elif os.name == "nt":
        DIRECTORIO_JUEGO = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")), "KINETIX")
    else:
        DIRECTORIO_JUEGO = os.path.join(os.path.expanduser("~"), ".local", "share", "KINETIX")
    os.makedirs(DIRECTORIO_JUEGO, exist_ok=True)
else:
    DIRECTORIO_JUEGO = os.path.dirname(os.path.abspath(__file__))

def ruta_juego(nombre):
    # Primero los archivos incluidos en PyInstaller y luego recursos personales.
    if getattr(sys, "frozen", False):
        empaquetado = os.path.join(getattr(sys, "_MEIPASS", ""), nombre)
        if os.path.isfile(empaquetado):
            return empaquetado
    return os.path.join(DIRECTORIO_JUEGO, nombre)
from gtts import gTTS
import numpy as np
import pygame
import requests

# === INTEGRACIÓN DE OPENAI ===
try:
    from openai import OpenAI, AuthenticationError, RateLimitError, APIConnectionError, BadRequestError
except ImportError:
    print("[Error] La librería 'openai' no está instalada. Ejecuta: pip install openai")
    sys.exit()

# CLAVE DE OPENAI
# Opción recomendada: variable de entorno OPENAI_API_KEY.
# Alternativa sencilla: crea un archivo llamado .openai_key junto a este .py
# y pega ahí SOLO la clave. No compartas ese archivo.
def cargar_clave_openai():
    clave = os.getenv("OPENAI_API_KEY", "").strip()
    if clave:
        return clave

    try:
        ruta_clave_local = os.path.join(
            DIRECTORIO_JUEGO, ".openai_key"
        )
        if os.path.exists(ruta_clave_local):
            with open(ruta_clave_local, "r", encoding="utf-8") as archivo:
                return archivo.read().strip()
    except Exception as e:
        print(f"[OpenAI Config] No se pudo leer .openai_key: {e}")

    return ""

OPENAI_API_KEY = cargar_clave_openai()
cliente_openai = None

if OPENAI_API_KEY:
    try:
        cliente_openai = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"[OpenAI Init Error] No se pudo inicializar el cliente: {e}")
else:
    print(
        "[OpenAI] No se encontró OPENAI_API_KEY ni .openai_key. "
        "El Tutor IA quedará desactivado hasta configurarla."
    )

# Intentar importar OpenCV y MediaPipe
try:
    import cv2
    import mediapipe as mp
    CAMARA_Y_MEDIAPIPE_DISPONIBLES = True
except ImportError:
    CAMARA_Y_MEDIAPIPE_DISPONIBLES = False
    print("[Advertencia] cv2 o mediapipe no están instalados. El juego funcionará con ratón.")

# Intentar importar SpeechRecognition
try:
    import speech_recognition as sr
    MICROFONO_DISPONIBLE = True
except ImportError:
    MICROFONO_DISPONIBLE = False
    print("[Advertencia] 'speech_recognition' no está instalado. Instálalo con: pip install SpeechRecognition pyaudio")

# Descarga automática del modelo de MediaPipe
RUTA_MODELO_MANO = ruta_juego("hand_landmarker.task")
if CAMARA_Y_MEDIAPIPE_DISPONIBLES and not os.path.exists(RUTA_MODELO_MANO):
    try:
        url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
        r = requests.get(url, timeout=15)
        with open(RUTA_MODELO_MANO, "wb") as f:
            f.write(r.content)
    except Exception as e:
        print(f"No se pudo descargar hand_landmarker.task automáticamente: {e}")

# 1. CONFIGURACIÓN E INICIALIZACIÓN DE GOOGLE TTS Y AUDIO
VOCES_GOOGLE = [
    ("us", "com", "Inglés EE.UU."),
    ("uk", "co.uk", "Inglés Británico"),
    ("au", "com.au", "Inglés Australiano"),
    ("ca", "ca", "Inglés Canadiense"),
]
indice_voz_actual = 0
reproduciendo_audio = False

def reproducir_voz(texto_a_hablar, lang="en"):
    """Genera el audio usando la API libre de Google TTS evitando acumular hilos."""
    global reproduciendo_audio
    def _hilo_reproduccion():
        global reproduciendo_audio
        try:
            reproduciendo_audio = True
            tld_actual = VOCES_GOOGLE[indice_voz_actual][1]
            tts = gTTS(text=texto_a_hablar, lang=lang, tld=tld_actual)
            buffer_audio = BytesIO()
            tts.write_to_fp(buffer_audio)
            buffer_audio.seek(0)
            sonido_generado = pygame.mixer.Sound(buffer_audio)
            canal = sonido_generado.play()
            while canal and canal.get_busy():
                pygame.time.wait(50)
        except Exception as error:
            print(f"[Google TTS Error] No se pudo reproducir el audio: {error}")
        finally:
            reproduciendo_audio = False
    # No iniciar voces nuevas mientras el usuario está grabando.
    if not grabacion_habilitada.is_set():
        threading.Thread(target=_hilo_reproduccion, daemon=True).start()

# 2. SISTEMA DE RECONOCIMIENTO DE VOZ (MICROFONO) Y TUTOR IA CON OPENAI
escuchando_mic = False
texto_escuchado = ""
respuesta_tutor = ""

def procesar_respuesta_tutor_ia(consulta_usuario):
    """Genera respuestas educativas del Tutor IA utilizando la API de OpenAI."""
    if cliente_openai is None:
        return (
            "El Tutor IA no está configurado. Define la variable "
            "OPENAI_API_KEY y reinicia el juego."
        )

    consulta_usuario = (consulta_usuario or "").strip()
    if not consulta_usuario:
        return "No recibí ninguna pregunta. Intenta hablar de nuevo."

    try:
        respuesta = cliente_openai.responses.create(
            model="gpt-6-luna",
            instructions=(
                "You are a friendly, encouraging English tutor for a game. "
                "Answer questions about English grammar, vocabulary, or translation "
                "briefly, in at most 2 sentences. Reply in Spanish when the user speaks "
                "Spanish and in English when the user speaks English."
            ),
            input=consulta_usuario,
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
            max_output_tokens=120,
        )

        texto_respuesta = (respuesta.output_text or "").strip()
        if not texto_respuesta:
            return "La IA no devolvió texto. Intenta de nuevo."

        return texto_respuesta

    except AuthenticationError as e:
        print(f"[OpenAI 401 - AUTENTICACIÓN] {e}")
        return "La clave de OpenAI no es válida o ya fue revocada."

    except RateLimitError as e:
        print(f"[OpenAI 429 - LÍMITE/CUOTA] {e}")
        return "La API alcanzó un límite de uso o la cuenta no tiene cuota disponible."

    except APIConnectionError as e:
        print(f"[OpenAI CONEXIÓN] {e}")
        return "No se pudo conectar con OpenAI. Revisa tu internet."

    except BadRequestError as e:
        print(f"[OpenAI 400 - SOLICITUD] {e}")
        return "OpenAI rechazó la solicitud. Revisa la configuración de la API."

    except Exception as e:
        status = getattr(e, "status_code", None)
        request_id = getattr(e, "request_id", None)
        print(
            f"[OpenAI ERROR] tipo={type(e).__name__} "
            f"status={status} request_id={request_id}: {e}"
        )
        return f"Error de OpenAI{f' ({status})' if status else ''}. Revisa la consola para ver el detalle."

# Micrófonos de entrada: no abrimos ninguno hasta mantener pulsado T o HABLAR.
def buscar_microfonos():
    """Detecta solo entradas de audio válidas; permite elegir la integrada de Mac."""
    opciones = [(None, "Predeterminado de macOS")]
    if not MICROFONO_DISPONIBLE:
        return opciones
    interfaz = None
    try:
        import pyaudio
        interfaz = pyaudio.PyAudio()
        for indice in range(interfaz.get_device_count()):
            info = interfaz.get_device_info_by_index(indice)
            if int(info.get("maxInputChannels", 0)) > 0:
                opciones.append((indice, str(info.get("name", f"Entrada {indice}"))))
    except Exception as error:
        print(f"[KINETIX MIC] No se pudieron listar entradas: {error}")
    finally:
        if interfaz is not None:
            interfaz.terminate()
    return opciones


opciones_microfonos = buscar_microfonos()
# Selección inicial: entrada elegida en macOS (puede ser el iPhone).
# KINETIX no fuerza el micrófono integrado del MacBook, ya que en algunos
# equipos no entrega muestras útiles aunque macOS indique que está activo.
# El usuario puede elegir manualmente otra entrada desde Ajustes.
indice_microfono = 0


def nombre_microfono_actual():
    return opciones_microfonos[indice_microfono][1]


def cambiar_microfono():
    global indice_microfono
    if escuchando_mic:
        return
    indice_microfono = (indice_microfono + 1) % len(opciones_microfonos)
    print(f"[KINETIX MIC] Elegido: {nombre_microfono_actual()}")


# Push-to-talk, sin límite de segundos ni detección automática de silencio.
grabacion_habilitada = threading.Event()
origen_grabacion = None
tecla_t_presionada = False
boton_mic_presionado = False
mic_listo = False
nivel_audio_entrada = 0
pico_audio_sesion = 0


def escuchar_microfono_async(origen="T"):
    """Graba mientras se sostiene T o el botón; informa fallos de entrada/STT/IA."""
    global escuchando_mic, texto_escuchado, respuesta_tutor, origen_grabacion
    global mic_listo, nivel_audio_entrada, pico_audio_sesion

    if escuchando_mic:
        return False
    if not MICROFONO_DISPONIBLE:
        texto_escuchado = "Falta SpeechRecognition o PyAudio. Revisa la Terminal."
        return False

    escuchando_mic = True
    origen_grabacion = origen
    grabacion_habilitada.set()
    mic_listo = False
    nivel_audio_entrada = 0
    pico_audio_sesion = 0
    respuesta_tutor = ""
    texto_escuchado = "Abriendo micrófono... espera a que indique GRABANDO."
    indice_dispositivo, nombre_dispositivo = opciones_microfonos[indice_microfono]
    print(f"[KINETIX MIC] Abriendo entrada: {nombre_dispositivo} (índice {indice_dispositivo})")

    def _hilo_mic():
        global escuchando_mic, texto_escuchado, respuesta_tutor, origen_grabacion
        global mic_listo, nivel_audio_entrada, pico_audio_sesion
        reconocedor = sr.Recognizer()
        partes = []
        try:
            # Al comenzar a hablar evitamos que los sonidos anteriores del juego
            # regresen al propio micrófono por los altavoces del Mac.
            try:
                pygame.mixer.stop()
            except Exception:
                pass

            with sr.Microphone(device_index=indice_dispositivo) as fuente:
                mic_listo = True
                texto_escuchado = "Grabando: habla y suelta T para enviar."
                print(f"[KINETIX MIC] Captura iniciada: {fuente.SAMPLE_RATE} Hz")
                while grabacion_habilitada.is_set():
                    datos = fuente.stream.read(fuente.CHUNK)
                    if not datos:
                        break
                    partes.append(datos)
                    # PyAudio usa PCM de 16 bits, como sr.Microphone.
                    muestras = np.frombuffer(datos, dtype=np.int16)
                    if muestras.size:
                        nivel = int(np.sqrt(np.mean(muestras.astype(np.float64) ** 2)))
                        nivel_audio_entrada = nivel
                        pico_audio_sesion = max(pico_audio_sesion, nivel)
                nivel_audio_entrada = 0
                if not partes:
                    texto_escuchado = "No se grabó nada. Mantén T durante unos segundos."
                    print("[KINETIX MIC] Grabación sin muestras")
                    return
                duracion = sum(len(p) for p in partes) / (fuente.SAMPLE_RATE * fuente.SAMPLE_WIDTH)
                audio = sr.AudioData(b"".join(partes), fuente.SAMPLE_RATE, fuente.SAMPLE_WIDTH)

            print(f"[KINETIX MIC] Grabados {duracion:.1f} s; nivel máximo RMS={pico_audio_sesion}")
            if duracion < 0.35:
                texto_escuchado = "Grabación muy corta. Mantén T y habla durante 2 o 3 segundos."
                return
            if pico_audio_sesion < 15:
                texto_escuchado = "No llega sonido. Ve a AJUSTES y cambia el micrófono."
                return

            texto_escuchado = "Audio recibido. Reconociendo palabras con Google..."
            try:
                consulta = reconocedor.recognize_google(audio, language="es-MX")
            except sr.UnknownValueError:
                consulta = reconocedor.recognize_google(audio, language="en-US")

            consulta = (consulta or "").strip()
            if not consulta:
                texto_escuchado = "No se reconocieron palabras. Habla más cerca del Mac."
                return
            texto_escuchado = f'Tú: "{consulta}"'
            print(f"[KINETIX MIC] Reconoció: {consulta}")
            respuesta_tutor = procesar_respuesta_tutor_ia(consulta)
            lang_voz = "es" if ("el" in respuesta_tutor.lower() or "la" in respuesta_tutor.lower() or "en" in respuesta_tutor.lower()) else "en"
            reproducir_voz(respuesta_tutor, lang=lang_voz)
        except sr.UnknownValueError:
            texto_escuchado = "Se captó audio, pero Google no entendió la frase."
        except sr.RequestError as error:
            texto_escuchado = "Audio captado, pero falló Google. Revisa internet."
            print(f"[KINETIX MIC] Error Google: {error}")
        except Exception as error:
            texto_escuchado = f"Error de entrada de audio: {str(error)[:110]}"
            print(f"[KINETIX MIC] Error {type(error).__name__}: {error}")
        finally:
            grabacion_habilitada.clear()
            mic_listo = False
            nivel_audio_entrada = 0
            origen_grabacion = None
            escuchando_mic = False

    threading.Thread(target=_hilo_mic, daemon=True).start()
    return True


def detener_grabacion_mic(origen=None):
    """Al soltar el control que inició la captura, deja de grabar."""
    if origen is None or origen_grabacion == origen:
        grabacion_habilitada.clear()

# 3. INICIALIZACIÓN DE PYGAME Y SISTEMA DE AUDIO
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
pygame.mixer.init()
pygame.mixer.set_num_channels(64)
screen_info = pygame.display.Info()
screen_width = screen_info.current_w
screen_height = screen_info.current_h
screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
fullscreen = True
pygame.display.set_caption("KINETIX | Aprende inglés jugando")

# 4. PALETAS DE COLORES Y ACCESIBILIDAD
PALETAS_COLOR = {
    "MODERNO": {
        "FONDO": (26, 29, 41),
        "PANEL": (38, 42, 60),
        "TEXTO": (236, 240, 241),
        "TEXTO_SEC": (170, 180, 200),
        "VERDE": (46, 204, 113),
        "NARANJA": (243, 156, 18),
        "ROJO": (231, 76, 60),
        "MORADO": (142, 68, 173),
        "BOTON": (79, 70, 229),
        "BOTON_HOVER": (99, 102, 241),
        "OSCURO": (18, 20, 29),
    },
    "DALTONICO_DEUTER": {
        "FONDO": (20, 25, 35),
        "PANEL": (35, 42, 58),
        "TEXTO": (240, 244, 248),
        "TEXTO_SEC": (180, 190, 210),
        "VERDE": (0, 114, 178),
        "NARANJA": (240, 228, 66),
        "ROJO": (230, 159, 0),
        "MORADO": (204, 121, 167),
        "BOTON": (86, 180, 233),
        "BOTON_HOVER": (120, 200, 245),
        "OSCURO": (14, 18, 26),
    },
    "DALTONICO_TRITER": {
        "FONDO": (22, 27, 34),
        "PANEL": (38, 45, 56),
        "TEXTO": (240, 242, 245),
        "TEXTO_SEC": (175, 185, 195),
        "VERDE": (0, 158, 115),
        "NARANJA": (230, 159, 0),
        "ROJO": (213, 94, 0),
        "MORADO": (204, 121, 167),
        "BOTON": (0, 114, 178),
        "BOTON_HOVER": (40, 140, 200),
        "OSCURO": (15, 19, 24),
    }
}
modo_color_nombre = "MODERNO"
c_theme = PALETAS_COLOR[modo_color_nombre]

# 5. CONFIGURACIÓN DE FUENTES DEL SISTEMA
try:
    fuente_pequena = pygame.font.SysFont("Arial", 22, bold=True)
    fuente_marcador = pygame.font.SysFont("Arial", 26, bold=True)
    fuente_opciones = pygame.font.SysFont("Arial", 36, bold=True)
    fuente_victoria = pygame.font.SysFont("Arial", 34, bold=True)
    fuente_titulo = pygame.font.SysFont("Arial", 48, bold=True)
except Exception:
    fuente_pequena = pygame.font.SysFont(None, 22)
    fuente_marcador = pygame.font.SysFont(None, 26)
    fuente_opciones = pygame.font.SysFont(None, 36)
    fuente_victoria = pygame.font.SysFont(None, 34)
    fuente_titulo = pygame.font.SysFont(None, 48)

# 6. CARGA DE EFECTOS DE SONIDO LOCALES
snd_inicio = None
snd_bueno = None
snd_malo = None
snd_final = None
snd_compra = None
try:
    if os.path.exists(ruta_juego("inicio_juego.wav")):
        snd_inicio = pygame.mixer.Sound(ruta_juego("inicio_juego.wav"))
    if os.path.exists(ruta_juego("sonido_agarrar_billete_moneda_diamante.wav")):
        snd_bueno = pygame.mixer.Sound(ruta_juego("sonido_agarrar_billete_moneda_diamante.wav"))
    if os.path.exists(ruta_juego("sonido_metiorito_piedra.wav")):
        snd_malo = pygame.mixer.Sound(ruta_juego("sonido_metiorito_piedra.wav"))
    if os.path.exists(ruta_juego("final_game_porcentaje.wav")):
        snd_final = pygame.mixer.Sound(ruta_juego("final_game_porcentaje.wav"))
        snd_compra = pygame.mixer.Sound(ruta_juego("final_game_porcentaje.wav"))
except Exception:
    pass

# 7. GESTOR DE EMOJIS
DIRECTORIO_EMOJIS = ruta_juego("emojis_cache")
os.makedirs(DIRECTORIO_EMOJIS, exist_ok=True)

def get_twemoji(emoji_char, size=(50,50)):
    if not emoji_char:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        return surf
    codes = [f"{ord(c):x}" for c in emoji_char if ord(c) != 0xFE0F]
    codepoint = "-".join(codes)
    ruta_local = os.path.join(DIRECTORIO_EMOJIS, f"{codepoint}.png")
    if os.path.exists(ruta_local):
        try:
            surf = pygame.image.load(ruta_local).convert_alpha()
            return pygame.transform.smoothscale(surf, size)
        except Exception:
            pass
    url = f"https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/72x72/{codepoint}.png"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        with open(ruta_local, "wb") as f:
            f.write(resp.content)
        surf = pygame.image.load(BytesIO(resp.content)).convert_alpha()
        return pygame.transform.smoothscale(surf, size)
    except Exception:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 200, 0), (size[0] // 2, size[1] // 2), size[0] // 2)
        return surf

EMOJIS_JUEGO = ["🪙", "🐱", "😺", "🙀", "🐶", "🐵", "👽", "⭐", "🤚", "✊", "🛒", "⏱️", "🧲", "🛡️"]
twemojis = {e: get_twemoji(e, (48, 48)) for e in EMOJIS_JUEGO}

# 8. DATOS DE PERSONAJES Y SKINS
SKINS_DATA = {
    "Gato": {"emojis": ["🐱", "😺", "🙀"], "precio": 0, "color": (60, 70, 90)},
    "Perro": {"emojis": ["🐶", "🐶", "🐶"], "precio": 100, "color": (50, 80, 60)},
    "Mono": {"emojis": ["🐵", "🐵", "🐵"], "precio": 200, "color": (90, 70, 50)},
    "Alien": {"emojis": ["👽", "👽", "👽"], "precio": 300, "color": (70, 50, 90)},
}
skins_compradas = ["Gato"]
skin_equipada = "Gato"
personaje_actual = SKINS_DATA[skin_equipada]["emojis"]

# 9. BANCO DE PREGUNTAS EDUCATIVAS
PREGUNTAS_VOC_FACIL = [
    ("Manzana en inglés", "Apple", ["Banana", "Orange", "Grape", "Melon"]),
    ("Gato en inglés", "Cat", ["Dog", "Bird", "Fish", "Mouse"]),
    ("Rojo en inglés", "Red", ["Blue", "Yellow", "Green", "Black"]),
    ("Libro en inglés", "Book", ["Pen", "Pencil", "Desk", "Chair"]),
    ("Agua en inglés", "Water", ["Fire", "Earth", "Wind", "Ice"]),
    ("Sol en inglés", "Sun", ["Moon", "Star", "Sky", "Cloud"]),
    ("Hermano en inglés", "Brother", ["Sister", "Father", "Mother", "Uncle"]),
    ("Feliz en inglés", "Happy", ["Sad", "Angry", "Tired", "Bored"]),
]
PREGUNTAS_GRAM_FACIL = [
    ("I ___ a student.", "am", ["is", "are", "be", "were"]),
    ("She ___ playing soccer.", "is", ["are", "am", "be", "was"]),
    ("They ___ happy today.", "are", ["is", "am", "was", "be"]),
    ("Do you ___ cats?", "like", ["likes", "liked", "liking", "to like"]),
    ("He does not ___ apples.", "like", ["likes", "liked", "liking", "to like"]),
    ("This is ___ book.", "my", ["me", "mine", "I", "myself"]),
    ("___ are you?", "How", ["Who", "What", "Where", "Why"]),
    ("We ___ going to the park.", "are", ["is", "am", "was", "be"]),
]
PREGUNTAS_VOC_MEDIO = [
    ("Siempre en inglés", "Always", ["Never", "Sometimes", "Often", "Rarely"]),
    ("Invierno en inglés", "Winter", ["Summer", "Spring", "Autumn", "Fall"]),
    ("Zapatos en inglés", "Shoes", ["Socks", "Pants", "Shirt", "Hat"]),
    ("Ciudad en inglés", "City", ["Town", "Village", "Country", "State"]),
    ("Pensamiento en inglés", "Thought", ["Think", "Thing", "Though", "Through"]),
    ("Desayuno en inglés", "Breakfast", ["Lunch", "Dinner", "Snack", "Meal"]),
    ("Cuchillo en inglés", "Knife", ["Fork", "Spoon", "Plate", "Glass"]),
    ("Enfermedad en inglés", "Illness", ["Health", "Doctor", "Hospital", "Medicine"]),
]
PREGUNTAS_GRAM_MEDIO = [
    ("I ___ to the store yesterday.", "went", ["go", "gone", "going", "goes"]),
    ("She has ___ her homework.", "done", ["do", "did", "doing", "does"]),
    ("They ___ sleeping when I called.", "were", ["was", "are", "is", "be"]),
    ("I have ___ to Paris.", "been", ["go", "went", "being", "was"]),
    ("I ___ buy a car tomorrow.", "will", ["would", "shall", "does", "did"]),
    ("___ she play the piano?", "Does", ["Do", "Is", "Are", "Has"]),
    ("She is taller ___ me.", "than", ["then", "that", "this", "there"]),
    ("I didn't ___ anything.", "see", ["saw", "seen", "seeing", "sees"]),
]
PREGUNTAS_VOC_DIFICIL = [
    ("Conocimiento en inglés", "Knowledge", ["Wisdom", "Learning", "Thought", "Mind"]),
    ("Desarrollo en inglés", "Development", ["Progress", "Growth", "Evolution", "Advance"]),
    ("Medio ambiente", "Environment", ["Nature", "World", "Earth", "Planet"]),
    ("Logro en inglés", "Achievement", ["Failure", "Goal", "Success", "Defeat"]),
    ("Comportamiento", "Behavior", ["Attitude", "Mood", "Action", "Thought"]),
    ("Reconocer en inglés", "Acknowledge", ["Ignore", "Deny", "Forget", "Refuse"]),
    ("Desafío en inglés", "Challenge", ["Easy", "Simple", "Basic", "Problem"]),
    ("Confiable en inglés", "Reliable", ["Fake", "False", "Liar", "Cheat"]),
]
PREGUNTAS_GRAM_DIFICIL = [
    ("If I ___ you, I would study.", "were", ["was", "am", "be", "are"]),
    ("By next year, I ___ graduated.", "will have", ["have", "had", "will", "would have"]),
    ("Hardly ___ I arrived when it rained.", "had", ["have", "did", "was", "do"]),
    ("I wish I ___ a car.", "had", ["have", "has", "having", "will have"]),
    ("The book was ___ by him.", "written", ["wrote", "write", "writing", "writes"]),
    ("He is used to ___ early.", "waking up", ["wake up", "woke up", "waken up", "wakes up"]),
    ("Neither John ___ Mary came.", "nor", ["or", "and", "but", "so"]),
    ("I would have gone if I ___ known.", "had", ["have", "has", "would", "did"]),
]

# 10. VARIABLES DE ESTADO Y CONFIGURACIÓN
tema_seleccionado = "MIXTO"
dificultad_seleccionada = "MEDIO"
pregunta_actual = ""
respuesta_correcta = ""
opciones_incorrectas = []
margen = 100
espacio_util = screen_width - (margen * 2)
num_carriles = 5
paso = espacio_util // (num_carriles - 1) if num_carriles > 1 else espacio_util
carriles_disponibles = [margen + paso * i for i in range(num_carriles)]
obstaculos = []
tiempo_restante = 60
estado_juego = "PORTADA"
MODO_ADMIN = False
contador_f_clostet = 0
monedas = 0
monedas_partida = 0
racha = 0
mejor_racha = 0
buff_tiempo_comprado = False
buff_iman_comprado = False
buff_escudo_comprado = False
habilidad_disponible = True
habilidad_activa = False
habilidades_tiempo_restante = 0.0
iman_activo = False
escudo_activo = False
cara_actual = personaje_actual[0]
tiempo_reaccion = 0
cooldown_pregunta = 0.0
puno_necesita_liberar = False
puno_anterior = False

# 11. CONFIGURACIÓN DE CÁMARA OPENCV Y MEDIAPIPE
camara_modo_hd = True
espejo_camara = True

def inicializar_camara(hd=True):
    if not CAMARA_Y_MEDIAPIPE_DISPONIBLES:
        return None
    try:
        cap_temp = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION) if sys.platform == "darwin" else cv2.VideoCapture(0)
        if hd:
            cap_temp.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap_temp.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        else:
            cap_temp.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap_temp.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap_temp.set(cv2.CAP_PROP_FPS, 30)
        cap_temp.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        if not cap_temp.isOpened():
            cap_temp.release()
            print("[KINETIX] No se pudo abrir la cámara. Puedes jugar con el ratón.")
            return None
        return cap_temp
    except Exception as e:
        print(f"Error al inicializar cámara: {e}")
        return None

# No solicitamos acceso a la cámara al abrir KINETIX.
# Se activa en AJUSTES (vista previa) y JUGANDO (control por mano).
cap = None
camara_intentada = False
current_hand_result = None


def sincronizar_camara_juego():
    """Activa la cámara en Ajustes y en partida; la libera al salir."""
    global cap, camara_intentada, current_hand_result, puno_anterior

    if estado_juego not in ("JUGANDO", "AJUSTES"):
        if cap is not None:
            cap.release()
            cap = None
        camara_intentada = False
        current_hand_result = None
        puno_anterior = False
        return

    # Una apertura por entrada a Ajustes, partida o reanudación; no intentar
    # reabrir 60 veces por segundo si faltan permisos o cámara.
    if not camara_intentada:
        camara_intentada = True
        current_hand_result = None
        cap = inicializar_camara(camara_modo_hd)
        if cap is None:
            print("[KINETIX] Sin acceso a la cámara. En el juego puedes usar ratón y clic.")

def hand_landmarker_result_callback(result, output_image, timestamp_ms):
    global current_hand_result
    current_hand_result = result

hands = None
if CAMARA_Y_MEDIAPIPE_DISPONIBLES and os.path.exists(RUTA_MODELO_MANO):
    try:
        BaseOptions = mp.tasks.BaseOptions
        HandLandmarker = mp.tasks.vision.HandLandmarker
        HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=RUTA_MODELO_MANO),
            running_mode=VisionRunningMode.LIVE_STREAM,
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.7,
            min_tracking_confidence=0.7,
            result_callback=hand_landmarker_result_callback
        )
        hands = HandLandmarker.create_from_options(options)
    except Exception as e:
        print(f"Error al inicializar HandLandmarker: {e}")

# 12. FUNCIONES DE LÓGICA DE JUEGO
def cargar_nueva_pregunta():
    """Selecciona una nueva pregunta del banco y la lee en voz alta."""
    global pregunta_actual, respuesta_correcta, opciones_incorrectas
    global cooldown_pregunta, puno_necesita_liberar
    pool = []
    if tema_seleccionado in ["VOCABULARIO", "MIXTO"]:
        if dificultad_seleccionada == "FACIL":
            pool.extend(PREGUNTAS_VOC_FACIL)
        elif dificultad_seleccionada == "MEDIO":
            pool.extend(PREGUNTAS_VOC_MEDIO)
        elif dificultad_seleccionada == "DIFICIL":
            pool.extend(PREGUNTAS_VOC_DIFICIL)
    if tema_seleccionado in ["GRAMATICA", "MIXTO"]:
        if dificultad_seleccionada == "FACIL":
            pool.extend(PREGUNTAS_GRAM_FACIL)
        elif dificultad_seleccionada == "MEDIO":
            pool.extend(PREGUNTAS_GRAM_MEDIO)
        elif dificultad_seleccionada == "DIFICIL":
            pool.extend(PREGUNTAS_GRAM_DIFICIL)
    if not pool:
        pool = PREGUNTAS_VOC_FACIL
        
    pregunta = choice(pool)
    pregunta_actual = pregunta[0]
    respuesta_correcta = pregunta[1]
    opciones_incorrectas = list(pregunta[2])
    cooldown_pregunta = 0.8
    puno_necesita_liberar = True
    lang_pregunta = "es" if "en inglés" in pregunta_actual.lower() else "en"
    reproducir_voz(pregunta_actual, lang=lang_pregunta)

def inicializar_obstaculos_educativo():
    """Genera las opciones flotantes en pantalla."""
    global obstaculos
    obstaculos.clear()
    opciones = [respuesta_correcta] + opciones_incorrectas[:4]
    shuffle(opciones)
    for idx, texto_opcion in enumerate(opciones):
        x = carriles_disponibles[idx % len(carriles_disponibles)]
        y = screen_height // 2
        obstaculos.append([x, y, 0, texto_opcion, 0])

def arrancar_juego_real():
    """Reinicia variables y da inicio a una partida."""
    global monedas_partida, tiempo_restante, estado_juego, cara_actual, tiempo_reaccion
    global habilidad_disponible, habilidad_activa, habilidades_tiempo_restante
    global iman_activo, escudo_activo, racha, puno_necesita_liberar
    
    monedas_partida = 0
    racha = 0
    tiempo_restante = 60 + (30 if buff_tiempo_comprado or MODO_ADMIN else 0)
    habilidad_disponible = buff_iman_comprado or buff_escudo_comprado or MODO_ADMIN
    habilidad_activa = False
    habilidades_tiempo_restante = 0.0
    iman_activo = False
    escudo_activo = False
    estado_juego = "JUGANDO"
    cara_actual = personaje_actual[0]
    tiempo_reaccion = 0
    puno_necesita_liberar = True
    cargar_nueva_pregunta()
    inicializar_obstaculos_educativo()

def puno_cerrado(hand_landmarks):
    """Detecta si la mano del usuario está cerrada (puño)."""
    wrist = hand_landmarks[0]
    tips = [8, 12, 16, 20]
    mcps = [5, 9, 13, 17]
    for tip, mcp in zip(tips, mcps):
        dist_tip = math.hypot(hand_landmarks[tip].x - wrist.x, hand_landmarks[tip].y - wrist.y)
        dist_mcp = math.hypot(hand_landmarks[mcp].x - wrist.x, hand_landmarks[mcp].y - wrist.y)
        if dist_tip > dist_mcp * 1.1:
            return False
    return True

# 13. DEFINICIÓN DE BOTONES DE INTERFAZ DE USUARIO
center_x = screen_width // 2
center_y = screen_height // 2

moneda_gigante = pygame.transform.smoothscale(get_twemoji("🪙", (140, 140)), (140, 140))
moneda_rect = pygame.Rect(center_x - 70, center_y - 40, 140, 140)
boton_jugar_rect = pygame.Rect(center_x - 140, screen_height - 380, 280, 55)
boton_tutor_ia_rect = pygame.Rect(center_x - 157, screen_height - 315, 315, 50)
boton_skins_rect = pygame.Rect(center_x - 140, screen_height - 255, 280, 50)
boton_tienda_p2w_rect = pygame.Rect(center_x - 140, screen_height - 195, 280, 50)
boton_closet_rect = pygame.Rect(center_x - 140, screen_height - 135, 280, 50)
boton_ajustes_rect = pygame.Rect(center_x - 140, screen_height - 75, 280, 50)
boton_listo_rect = pygame.Rect(center_x - 120, screen_height - 140, 240, 60)
boton_regresar_rect = pygame.Rect(25, screen_height - 65, 130, 45)
boton_pausa_rect = pygame.Rect(25, screen_height - 65, 110, 42)
boton_mic_game_rect = pygame.Rect(150, screen_height - 65, 160, 42)
boton_comprar_tiempo = pygame.Rect(center_x + 160, center_y - 110, 170, 42)
boton_comprar_iman = pygame.Rect(center_x + 160, center_y - 35, 170, 42)
boton_comprar_escudo = pygame.Rect(center_x + 160, center_y + 40, 170, 42)
boton_salir_rect = pygame.Rect(center_x - 100, center_y + 80, 200, 50)
boton_jugar_nuevo_rect = pygame.Rect(center_x - 140, center_y + 50, 280, 55)
boton_lobby_final_rect = pygame.Rect(center_x - 140, center_y + 120, 280, 55)
boton_activar_habilidad = pygame.Rect(screen_width - 190, 95, 160, 45)

caja_voc = pygame.Rect(center_x - 330, center_y - 110, 210, 90)
caja_gram = pygame.Rect(center_x - 105, center_y - 110, 210, 90)
caja_mixto = pygame.Rect(center_x + 120, center_y - 110, 210, 90)
caja_facil = pygame.Rect(center_x - 330, center_y + 50, 210, 90)
caja_medio = pygame.Rect(center_x - 105, center_y + 50, 210, 90)
caja_dificil = pygame.Rect(center_x + 120, center_y + 50, 210, 90)

# Botones Ajustes
btn_toggle_cam_hd = pygame.Rect(center_x - 220, center_y + 90, 210, 45)
btn_toggle_espejo = pygame.Rect(center_x + 10, center_y + 90, 210, 45)
btn_theme_moderno = pygame.Rect(center_x - 310, center_y + 190, 190, 45)
btn_theme_deuter = pygame.Rect(center_x - 95, center_y + 190, 190, 45)
btn_theme_triter = pygame.Rect(center_x + 120, center_y + 190, 190, 45)
btn_cambiar_voz_google = pygame.Rect(center_x - 150, center_y + 20, 300, 45)
btn_cambiar_microfono = pygame.Rect(center_x - 250, center_y - 45, 500, 45)

last_player_x = center_x
last_player_y = center_y
hay_puno = False
cuenta_regresiva_valor = 3
tiempo_inicio_cuenta = 0
pygame.time.set_timer(pygame.USEREVENT, 1000)
clock = pygame.time.Clock()

if snd_inicio:
    snd_inicio.play()

# 14. BUCLE PRINCIPAL DEL JUEGO
while True:
    dt = clock.tick(60) / 1000.0
    player_hand_x = None
    player_hand_y = None
    hay_puno = False
    frame_preview_surface = None

    # Cámara activa en Ajustes para verla y durante el juego para controlar
    # el personaje. Apagada en menús, Tutor IA, cuenta regresiva y pausa.
    sincronizar_camara_juego()
    if estado_juego in ("JUGANDO", "AJUSTES") and cap and cap.isOpened():
        ret, frame = cap.read()
        if ret:
            if espejo_camara:
                frame = cv2.flip(frame, 1)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if estado_juego == "AJUSTES":
                # Solo vista previa: no analizar manos mientras configuras.
                frame_resized = cv2.resize(frame_rgb, (260, 195))
                frame_preview_surface = pygame.surfarray.make_surface(np.rot90(frame_resized))
            elif hands:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                try:
                    current_timestamp = int(time.time() * 1000)
                    hands.detect_async(mp_image, current_timestamp)
                    if current_hand_result and current_hand_result.hand_landmarks:
                        for hand_landmarks in current_hand_result.hand_landmarks:
                            dedo_indice = hand_landmarks[8]
                            player_hand_x = int(dedo_indice.x * screen_width)
                            player_hand_y = int(dedo_indice.y * screen_height)
                            if puno_cerrado(hand_landmarks):
                                hay_puno = True
                except Exception:
                    pass

    puno_recien_cerrado = hay_puno and (not puno_anterior)
    puno_anterior = hay_puno

    if cooldown_pregunta > 0:
        cooldown_pregunta -= dt
        if cooldown_pregunta < 0:
            cooldown_pregunta = 0.0

    if not hay_puno:
        puno_necesita_liberar = False

    mouse_click_this_frame = False

    # PROCESAMIENTO DE EVENTOS
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            if cap:
                cap.release()
            if hands:
                hands.close()
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                fullscreen = not fullscreen
                screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN if fullscreen else 0)
            elif event.key == pygame.K_ESCAPE:
                if cap:
                    cap.release()
                if hands:
                    hands.close()
                pygame.quit()
                sys.exit()
            elif event.key == pygame.K_t and estado_juego in ("TUTOR_IA", "JUGANDO"):
                if not tecla_t_presionada:
                    tecla_t_presionada = True
                    escuchar_microfono_async("T")
            elif event.key == pygame.K_f and estado_juego == "PERSONAJES":
                contador_f_clostet += 1
                if contador_f_clostet >= 4:
                    MODO_ADMIN = not MODO_ADMIN
                    if MODO_ADMIN:
                        monedas = 9999
                        buff_tiempo_comprado = True
                        buff_iman_comprado = True
                        buff_escudo_comprado = True
                    else:
                        monedas = 0
                        buff_tiempo_comprado = False
                        buff_iman_comprado = False
                        buff_escudo_comprado = False
                    contador_f_clostet = 0

        # La tecla T debe soltarse para que se reconozca y envíe la pregunta.
        if event.type == pygame.KEYUP and event.key == pygame.K_t:
            tecla_t_presionada = False
            detener_grabacion_mic("T")

        # Si la ventana pierde el foco, no dejamos el micrófono abierto.
        if event.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
            tecla_t_presionada = False
            boton_mic_presionado = False
            detener_grabacion_mic()

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if boton_mic_presionado:
                boton_mic_presionado = False
                detener_grabacion_mic("BOTON")

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos_game = event.pos
            mouse_click_this_frame = True
            
            if estado_juego == "PORTADA":
                if moneda_rect.collidepoint(mouse_pos_game):
                    estado_juego = "INICIO"
            
            elif estado_juego == "INICIO":
                if boton_jugar_rect.collidepoint(mouse_pos_game):
                    estado_juego = "INSTRUCCIONES"
                elif boton_tutor_ia_rect.collidepoint(mouse_pos_game):
                    # Entrar al tutor no debe empezar a escuchar automáticamente.
                    estado_juego = "TUTOR_IA"
                elif boton_skins_rect.collidepoint(mouse_pos_game):
                    estado_juego = "TIENDA_SKINS"
                elif boton_tienda_p2w_rect.collidepoint(mouse_pos_game):
                    estado_juego = "TIENDA_P2W"
                elif boton_closet_rect.collidepoint(mouse_pos_game):
                    estado_juego = "PERSONAJES"
                    contador_f_clostet = 0
                elif boton_ajustes_rect.collidepoint(mouse_pos_game):
                    estado_juego = "AJUSTES"
                elif boton_regresar_rect.collidepoint(mouse_pos_game):
                    estado_juego = "PORTADA"
            
            elif estado_juego == "INSTRUCCIONES":
                if boton_listo_rect.collidepoint(mouse_pos_game):
                    cuenta_regresiva_valor = 3
                    estado_juego = "CUENTA_REGRESIVA"
                    tiempo_inicio_cuenta = pygame.time.get_ticks()
                elif boton_regresar_rect.collidepoint(mouse_pos_game):
                    estado_juego = "INICIO"
            
            elif estado_juego == "TUTOR_IA":
                if boton_regresar_rect.collidepoint(mouse_pos_game):
                    estado_juego = "INICIO"
                elif boton_mic_game_rect.collidepoint(mouse_pos_game) and not escuchando_mic:
                    # El botón también funciona al mantenerlo presionado.
                    boton_mic_presionado = escuchar_microfono_async("BOTON")
            
            elif estado_juego == "TIENDA_SKINS":
                if boton_regresar_rect.collidepoint(mouse_pos_game):
                    estado_juego = "INICIO"
                else:
                    start_y = 160
                    for idx, (nombre, data) in enumerate(SKINS_DATA.items()):
                        btn_accion = pygame.Rect(center_x + 110, start_y + (idx * 75) + 10, 150, 45)
                        if btn_accion.collidepoint(mouse_pos_game):
                            if nombre in skins_compradas:
                                skin_equipada = nombre
                                personaje_actual = SKINS_DATA[skin_equipada]["emojis"]
                            elif MODO_ADMIN or monedas >= data["precio"]:
                                if not MODO_ADMIN:
                                    monedas -= data["precio"]
                                skins_compradas.append(nombre)
                                skin_equipada = nombre
                                personaje_actual = SKINS_DATA[skin_equipada]["emojis"]
                                if snd_compra:
                                    snd_compra.play()
            
            elif estado_juego == "TIENDA_P2W":
                if boton_regresar_rect.collidepoint(mouse_pos_game):
                    estado_juego = "INICIO"
                elif not MODO_ADMIN:
                    if boton_comprar_tiempo.collidepoint(mouse_pos_game) and monedas >= 50 and not buff_tiempo_comprado:
                        monedas -= 50
                        buff_tiempo_comprado = True
                        if snd_compra:
                            snd_compra.play()
                    elif boton_comprar_iman.collidepoint(mouse_pos_game) and monedas >= 70 and not buff_iman_comprado:
                        monedas -= 70
                        buff_iman_comprado = True
                        if snd_compra:
                            snd_compra.play()
                    elif boton_comprar_escudo.collidepoint(mouse_pos_game) and monedas >= 80 and not buff_escudo_comprado:
                        monedas -= 80
                        buff_escudo_comprado = True
                        if snd_compra:
                            snd_compra.play()
            
            elif estado_juego == "AJUSTES":
                if boton_regresar_rect.collidepoint(mouse_pos_game):
                    estado_juego = "INICIO"
                elif btn_toggle_cam_hd.collidepoint(mouse_pos_game):
                    # Reiniciar captura para aplicar HD/SD a la vista previa.
                    camara_modo_hd = not camara_modo_hd
                    if cap is not None:
                        cap.release()
                        cap = None
                    camara_intentada = False
                    current_hand_result = None
                elif btn_toggle_espejo.collidepoint(mouse_pos_game):
                    espejo_camara = not espejo_camara
                elif btn_theme_moderno.collidepoint(mouse_pos_game):
                    modo_color_nombre = "MODERNO"
                    c_theme = PALETAS_COLOR[modo_color_nombre]
                elif btn_theme_deuter.collidepoint(mouse_pos_game):
                    modo_color_nombre = "DALTONICO_DEUTER"
                    c_theme = PALETAS_COLOR[modo_color_nombre]
                elif btn_theme_triter.collidepoint(mouse_pos_game):
                    modo_color_nombre = "DALTONICO_TRITER"
                    c_theme = PALETAS_COLOR[modo_color_nombre]
                elif btn_cambiar_microfono.collidepoint(mouse_pos_game):
                    cambiar_microfono()
                    texto_escuchado = f"Micrófono seleccionado: {nombre_microfono_actual()}"
                elif btn_cambiar_voz_google.collidepoint(mouse_pos_game):
                    indice_voz_actual = (indice_voz_actual + 1) % len(VOCES_GOOGLE)
                    reproducir_voz(f"Voice selected: {VOCES_GOOGLE[indice_voz_actual][2]}", lang="en")
            
            elif estado_juego == "JUGANDO":
                if boton_pausa_rect.collidepoint(mouse_pos_game):
                    estado_juego = "PAUSADO"
                elif boton_mic_game_rect.collidepoint(mouse_pos_game) and not escuchando_mic:
                    # El botón también funciona al mantenerlo presionado.
                    boton_mic_presionado = escuchar_microfono_async("BOTON")
                elif boton_activar_habilidad.collidepoint(mouse_pos_game) and habilidad_disponible:
                    habilidad_disponible = False
                    habilidad_activa = True
                    habilidades_tiempo_restante = 10.0
                    iman_activo = buff_iman_comprado or MODO_ADMIN
                    escudo_activo = buff_escudo_comprado or MODO_ADMIN
            
            elif estado_juego == "PAUSADO":
                boton_reanudar_rect = pygame.Rect(center_x - 120, center_y, 240, 55)
                boton_salir_pausa = pygame.Rect(center_x - 100, center_y + 70, 200, 50)
                if boton_reanudar_rect.collidepoint(mouse_pos_game):
                    estado_juego = "JUGANDO"
                elif boton_salir_pausa.collidepoint(mouse_pos_game):
                    estado_juego = "INICIO"
            
            elif estado_juego == "PERSONAJES":
                if caja_voc.collidepoint(mouse_pos_game):
                    tema_seleccionado = "VOCABULARIO"
                elif caja_gram.collidepoint(mouse_pos_game):
                    tema_seleccionado = "GRAMATICA"
                elif caja_mixto.collidepoint(mouse_pos_game):
                    tema_seleccionado = "MIXTO"
                elif caja_facil.collidepoint(mouse_pos_game):
                    dificultad_seleccionada = "FACIL"
                elif caja_medio.collidepoint(mouse_pos_game):
                    dificultad_seleccionada = "MEDIO"
                elif caja_dificil.collidepoint(mouse_pos_game):
                    dificultad_seleccionada = "DIFICIL"
                elif boton_regresar_rect.collidepoint(mouse_pos_game):
                    estado_juego = "INICIO"
            
            elif estado_juego == "FINAL":
                if boton_jugar_nuevo_rect.collidepoint(mouse_pos_game):
                    buff_tiempo_comprado = False
                    buff_iman_comprado = False
                    buff_escudo_comprado = False
                    cuenta_regresiva_valor = 3
                    estado_juego = "CUENTA_REGRESIVA"
                    tiempo_inicio_cuenta = pygame.time.get_ticks()
                elif boton_lobby_final_rect.collidepoint(mouse_pos_game):
                    buff_tiempo_comprado = False
                    buff_iman_comprado = False
                    buff_escudo_comprado = False
                    estado_juego = "INICIO"

        if event.type == pygame.USEREVENT and estado_juego == "JUGANDO":
            tiempo_restante -= 1
            if tiempo_restante <= 0:
                tiempo_restante = 0
                monedas += monedas_partida
                if racha > mejor_racha:
                    mejor_racha = racha
                estado_juego = "FINAL"
                if snd_final:
                    snd_final.play()

    # Libera la cámara al salir de Ajustes o de la partida, y al pausar.
    sincronizar_camara_juego()

    # RENDERIZADO DE PANTALLAS
    mouse_pos_game = pygame.mouse.get_pos()
    
    if estado_juego == "PORTADA":
        screen.fill(c_theme["FONDO"])
        pygame.draw.circle(screen, c_theme["PANEL"], (center_x, center_y - 30), 180)
        txt_titulo = fuente_titulo.render("KINETIX", True, c_theme["TEXTO"])
        screen.blit(txt_titulo, (center_x - txt_titulo.get_width() // 2, int(screen_height * 0.12)))
        txt_titulo2 = fuente_victoria.render("APRENDE INGLÉS JUGANDO", True, c_theme["BOTON"])
        screen.blit(txt_titulo2, (center_x - txt_titulo2.get_width() // 2, int(screen_height * 0.12) + 62))
        
        if moneda_rect.collidepoint(mouse_pos_game):
            moneda_hover = pygame.transform.smoothscale(get_twemoji("🪙", (160, 160)), (160, 160))
            screen.blit(moneda_hover, (center_x - 80, center_y - 50))
        else:
            screen.blit(moneda_gigante, moneda_rect.topleft)
            
        txt_click = fuente_victoria.render("Toca la moneda para entrar", True, c_theme["TEXTO_SEC"])
        screen.blit(txt_click, (center_x - txt_click.get_width() // 2, center_y + 130))

    elif estado_juego == "INICIO":
        screen.fill(c_theme["FONDO"])
        txt_titulo_principal = fuente_titulo.render("KINETIX", True, c_theme["TEXTO"])
        screen.blit(txt_titulo_principal, (center_x - txt_titulo_principal.get_width() // 2, 35))
        txt_menu = fuente_pequena.render("MENÚ PRINCIPAL", True, c_theme["TEXTO_SEC"])
        screen.blit(txt_menu, (center_x - txt_menu.get_width() // 2, 90))
        txt_banco = fuente_victoria.render(f"Monedas: {monedas}" + (" [ADMIN]" if MODO_ADMIN else ""), True, c_theme["VERDE"])
        screen.blit(txt_banco, (screen_width - txt_banco.get_width() - 40, 25))
        
        btns = [
            (boton_jugar_rect, "¡A JUGAR!", c_theme["BOTON"]),
            (boton_tutor_ia_rect, "TUTOR IA (MIC)", c_theme["VERDE"]),
            (boton_skins_rect, "PERSONAJES", c_theme["MORADO"]),
            (boton_tienda_p2w_rect, "TIENDA MEJORAS", c_theme["VERDE"]),
            (boton_closet_rect, "TEMAS DE JUEGO", c_theme["NARANJA"]),
            (boton_ajustes_rect, "AJUSTES Y CAMARA", c_theme["PANEL"]),
        ]
        for rect, txt, col in btns:
            color = c_theme["BOTON_HOVER"] if rect.collidepoint(mouse_pos_game) else col
            pygame.draw.rect(screen, color, rect, border_radius=16)
            t_surf = fuente_marcador.render(txt, True, c_theme["TEXTO"])
            screen.blit(t_surf, (rect.centerx - t_surf.get_width() // 2, rect.centery - t_surf.get_height() // 2))
            
        pygame.draw.rect(screen, c_theme["ROJO"], boton_regresar_rect, border_radius=12)
        txt_regresar = fuente_pequena.render("SALIR", True, c_theme["TEXTO"])
        screen.blit(txt_regresar, (boton_regresar_rect.centerx - txt_regresar.get_width() // 2, boton_regresar_rect.centery - txt_regresar.get_height() // 2))

    elif estado_juego == "TUTOR_IA":
        screen.fill(c_theme["FONDO"])
        tit_tutor = fuente_titulo.render("TUTOR IA DE INGLÉS", True, c_theme["TEXTO"])
        screen.blit(tit_tutor, (center_x - tit_tutor.get_width() // 2, 40))
        
        panel_t = pygame.Rect(center_x - 380, 120, 760, 360)
        pygame.draw.rect(screen, c_theme["PANEL"], panel_t, border_radius=20)
        pygame.draw.rect(screen, c_theme["BOTON"], panel_t, width=3, border_radius=20)
        
        st_color = c_theme["NARANJA"] if escuchando_mic else c_theme["VERDE"]
        if grabacion_habilitada.is_set():
            st_txt = "Grabando... suelta [T] o el botón para enviar" if mic_listo else "Preparando micrófono..."
        elif escuchando_mic:
            st_txt = "Procesando tu pregunta..."
        else:
            st_txt = "Mantén presionada [T] o el botón para hablar"
        txt_estado = fuente_marcador.render(st_txt, True, st_color)
        screen.blit(txt_estado, (center_x - txt_estado.get_width() // 2, panel_t.y + 25))
        
        estado_captura = texto_escuchado if texto_escuchado else "Pregunta algo sobre inglés..."
        while len(estado_captura) > 5 and fuente_pequena.size(estado_captura)[0] > panel_t.width - 60:
            estado_captura = estado_captura[:-4]
        if estado_captura != (texto_escuchado if texto_escuchado else "Pregunta algo sobre inglés..."):
            estado_captura += "..."
        txt_u = fuente_pequena.render(estado_captura, True, c_theme["TEXTO_SEC"])
        screen.blit(txt_u, (panel_t.x + 30, panel_t.y + 80))
        # Medidor real de señal: si no se mueve, el sistema no entrega audio.
        barra = pygame.Rect(panel_t.x + 35, panel_t.y + 118, 270, 12)
        pygame.draw.rect(screen, c_theme["OSCURO"], barra, border_radius=5)
        ancho_senal = min(barra.width, int(barra.width * nivel_audio_entrada / 1900))
        if grabacion_habilitada.is_set() and mic_listo and ancho_senal > 0:
            pygame.draw.rect(screen, c_theme["VERDE"], (barra.x, barra.y, ancho_senal, barra.height), border_radius=5)
        leyenda = "Señal de micrófono" if mic_listo else "Nivel de entrada"
        texto_senal = fuente_pequena.render(leyenda, True, c_theme["TEXTO_SEC"])
        screen.blit(texto_senal, (barra.right + 15, barra.y - 9))

        if respuesta_tutor:
            lbl_resp = fuente_marcador.render("Tutor IA dice:", True, c_theme["BOTON_HOVER"])
            screen.blit(lbl_resp, (panel_t.x + 30, panel_t.y + 140))
            words = respuesta_tutor.split(" ")
            line = ""
            y_offset = panel_t.y + 180
            for word in words:
                test_line = line + word + " "
                if fuente_pequena.size(test_line)[0] < 700:
                    line = test_line
                else:
                    t_line = fuente_pequena.render(line, True, c_theme["TEXTO"])
                    screen.blit(t_line, (panel_t.x + 30, y_offset))
                    line = word + " "
                    y_offset += 30
            if line:
                t_line = fuente_pequena.render(line, True, c_theme["TEXTO"])
                screen.blit(t_line, (panel_t.x + 30, y_offset))
                
        col_btn_mic = c_theme["ROJO"] if escuchando_mic else c_theme["VERDE"]
        pygame.draw.rect(screen, col_btn_mic, boton_mic_game_rect, border_radius=12)
        txt_mic = fuente_pequena.render("HABLAR", True, c_theme["TEXTO"])
        screen.blit(txt_mic, (boton_mic_game_rect.centerx - txt_mic.get_width() // 2, boton_mic_game_rect.centery - txt_mic.get_height() // 2))
        
        pygame.draw.rect(screen, c_theme["ROJO"], boton_regresar_rect, border_radius=12)
        txt_volver = fuente_pequena.render("VOLVER", True, c_theme["TEXTO"])
        screen.blit(txt_volver, (boton_regresar_rect.centerx - txt_volver.get_width() // 2, boton_regresar_rect.centery - txt_volver.get_height() // 2))

    elif estado_juego == "INSTRUCCIONES":
        screen.fill(c_theme["FONDO"])
        # EDITA AQUÍ los textos que aparecen antes de cada partida.
        instrucciones = [
            ("TU RETO", "¡Atrapa respuestas de inglés antes de que termine el tiempo!"),
            ("MUÉVETE", "Abre tu mano y guía al personaje frente a la cámara."),
            ("ATRAPA", "Cierra el puño sobre la respuesta que creas correcta."),
            ("GANA MÁS", "Suma monedas y encadena aciertos para subir tu premio."),
            ("POTÉNCIATE", "Canjea monedas por ventajas en la tienda."),
            ("TUTOR IA", "¿Tienes dudas? Mantén T para hablar y suéltala al terminar."),
            ("SIN CÁMARA", "También puedes moverte con ratón y elegir con clic."),
        ]
        panel_ancho = min(970, screen_width - 40)
        panel_y = max(48, int(screen_height * 0.09))
        altura_disponible = boton_listo_rect.top - panel_y - 22
        altura_panel = min(550, altura_disponible)
        panel = pygame.Rect(center_x - panel_ancho // 2, panel_y, panel_ancho, altura_panel)
        pygame.draw.rect(screen, c_theme["PANEL"], panel, border_radius=20)
        pygame.draw.rect(screen, c_theme["BOTON"], panel, width=3, border_radius=20)

        titulo_instrucciones = fuente_victoria.render("TU MISIÓN EN KINETIX", True, c_theme["BOTON_HOVER"])
        screen.blit(titulo_instrucciones, (panel.centerx - titulo_instrucciones.get_width() // 2, panel.y + 18))

        espacio_filas = min(52, (panel.height - 90) // len(instrucciones))
        y_pos = panel.y + 71
        for numero, (titulo_paso, descripcion) in enumerate(instrucciones, 1):
            # Las instrucciones usan números y texto, no dependen solo de colores.
            pygame.draw.circle(screen, c_theme["BOTON"], (panel.x + 40, y_pos + 13), 17)
            numero_img = fuente_pequena.render(str(numero), True, c_theme["TEXTO"])
            screen.blit(numero_img, (panel.x + 40 - numero_img.get_width() // 2, y_pos + 13 - numero_img.get_height() // 2))
            texto = f"{titulo_paso}: {descripcion}"
            fuente_fila = fuente_pequena
            ancho_max = panel.width - 108
            if fuente_fila.size(texto)[0] > ancho_max:
                # Ajustar frases largas a pantallas más estrechas.
                fuente_fila = pygame.font.SysFont("Arial", 19, bold=True)
            txt = fuente_fila.render(texto, True, c_theme["TEXTO"])
            screen.blit(txt, (panel.x + 75, y_pos + 1))
            y_pos += espacio_filas
            
        pygame.draw.rect(screen, c_theme["BOTON"], boton_listo_rect, border_radius=16)
        txt_listo = fuente_marcador.render("¡ENTENDIDO!", True, c_theme["TEXTO"])
        screen.blit(txt_listo, (boton_listo_rect.centerx - txt_listo.get_width() // 2, boton_listo_rect.centery - txt_listo.get_height() // 2))
        
        pygame.draw.rect(screen, c_theme["ROJO"], boton_regresar_rect, border_radius=12)
        txt_regresar = fuente_pequena.render("REGRESAR", True, c_theme["TEXTO"])
        screen.blit(txt_regresar, (boton_regresar_rect.centerx - txt_regresar.get_width() // 2, boton_regresar_rect.centery - txt_regresar.get_height() // 2))

    elif estado_juego == "CUENTA_REGRESIVA":
        screen.fill(c_theme["FONDO"])
        tiempo_transcurrido = pygame.time.get_ticks() - tiempo_inicio_cuenta
        segundos_pasados = tiempo_transcurrido // 1000
        cuenta_actual = 3 - segundos_pasados
        if cuenta_actual > 0:
            txt_cuenta = fuente_titulo.render(str(cuenta_actual), True, c_theme["BOTON"])
            screen.blit(txt_cuenta, (center_x - txt_cuenta.get_width() // 2, center_y - 50))
        else:
            txt_vamos = fuente_titulo.render("¡A JUGAR!", True, c_theme["VERDE"])
            screen.blit(txt_vamos, (center_x - txt_vamos.get_width() // 2, center_y - 50))
        if segundos_pasados >= 4:
            arrancar_juego_real()

    elif estado_juego == "AJUSTES":
        screen.fill(c_theme["FONDO"])
        titulo_ajustes = fuente_titulo.render("CONFIGURACIÓN Y CÁMARA", True, c_theme["TEXTO"])
        screen.blit(titulo_ajustes, (center_x - titulo_ajustes.get_width() // 2, 35))
        
        box_cam = pygame.Rect(center_x - 140, 110, 280, 210)
        pygame.draw.rect(screen, c_theme["PANEL"], box_cam, border_radius=14)
        if frame_preview_surface is not None:
            screen.blit(frame_preview_surface, (box_cam.x + 10, box_cam.y + 7))
        else:
            # Si no existe permiso o señal de cámara, no mostrar negro sin explicación.
            for i, linea_cam in enumerate(("SIN SEÑAL DE CÁMARA", "Comprueba la conexión", "y los permisos de macOS")):
                fuente_cam = fuente_pequena
                color_cam = c_theme["NARANJA"] if i == 0 else c_theme["TEXTO_SEC"]
                txt_cam = fuente_cam.render(linea_cam, True, color_cam)
                screen.blit(txt_cam, (box_cam.centerx - txt_cam.get_width() // 2, box_cam.y + 40 + i * 45))
        lbl_cam = fuente_pequena.render("Vista previa de cámara", True, c_theme["TEXTO_SEC"])
        screen.blit(lbl_cam, (box_cam.centerx - lbl_cam.get_width() // 2, box_cam.bottom + 8))
        
        col_hd = c_theme["VERDE"] if camara_modo_hd else c_theme["PANEL"]
        pygame.draw.rect(screen, col_hd, btn_toggle_cam_hd, border_radius=12)
        txt_hd = fuente_pequena.render("Calidad: HD (720p)" if camara_modo_hd else "Calidad: SD (480p)", True, c_theme["TEXTO"])
        screen.blit(txt_hd, (btn_toggle_cam_hd.centerx - txt_hd.get_width() // 2, btn_toggle_cam_hd.centery - txt_hd.get_height() // 2))
        
        col_esp = c_theme["VERDE"] if espejo_camara else c_theme["PANEL"]
        pygame.draw.rect(screen, col_esp, btn_toggle_espejo, border_radius=12)
        txt_esp = fuente_pequena.render("Modo Espejo: ON" if espejo_camara else "Modo Espejo: OFF", True, c_theme["TEXTO"])
        screen.blit(txt_esp, (btn_toggle_espejo.centerx - txt_esp.get_width() // 2, btn_toggle_espejo.centery - txt_esp.get_height() // 2))
        
        pygame.draw.rect(screen, c_theme["BOTON"], btn_cambiar_microfono, border_radius=12)
        nombre_mic_corto = nombre_microfono_actual()
        if len(nombre_mic_corto) > 30:
            nombre_mic_corto = nombre_mic_corto[:27] + "..."
        txt_sel_mic = fuente_pequena.render(f"Entrada de voz: {nombre_mic_corto}", True, c_theme["TEXTO"])
        screen.blit(txt_sel_mic, (btn_cambiar_microfono.centerx - txt_sel_mic.get_width() // 2, btn_cambiar_microfono.centery - txt_sel_mic.get_height() // 2))
        col_voz = c_theme["MORADO"]
        pygame.draw.rect(screen, col_voz, btn_cambiar_voz_google, border_radius=12)
        txt_voz = fuente_pequena.render(f"Voz: {VOCES_GOOGLE[indice_voz_actual][2]}", True, c_theme["TEXTO"])
        screen.blit(txt_voz, (btn_cambiar_voz_google.centerx - txt_voz.get_width() // 2, btn_cambiar_voz_google.centery - txt_voz.get_height() // 2))
        
        lbl_dalton = fuente_marcador.render("Accesibilidad Visual / Daltonismo", True, c_theme["TEXTO"])
        screen.blit(lbl_dalton, (center_x - lbl_dalton.get_width() // 2, center_y + 155))
        
        col_m1 = c_theme["BOTON"] if modo_color_nombre == "MODERNO" else c_theme["PANEL"]
        pygame.draw.rect(screen, col_m1, btn_theme_moderno, border_radius=12)
        txt_m1 = fuente_pequena.render("Modo Normal", True, c_theme["TEXTO"])
        screen.blit(txt_m1, (btn_theme_moderno.centerx - txt_m1.get_width() // 2, btn_theme_moderno.centery - txt_m1.get_height() // 2))
        
        col_m2 = c_theme["BOTON"] if modo_color_nombre == "DALTONICO_DEUTER" else c_theme["PANEL"]
        pygame.draw.rect(screen, col_m2, btn_theme_deuter, border_radius=12)
        txt_m2 = fuente_pequena.render("Protanopía / Deuter", True, c_theme["TEXTO"])
        screen.blit(txt_m2, (btn_theme_deuter.centerx - txt_m2.get_width() // 2, btn_theme_deuter.centery - txt_m2.get_height() // 2))
        
        col_m3 = c_theme["BOTON"] if modo_color_nombre == "DALTONICO_TRITER" else c_theme["PANEL"]
        pygame.draw.rect(screen, col_m3, btn_theme_triter, border_radius=12)
        txt_m3 = fuente_pequena.render("Tritanopía", True, c_theme["TEXTO"])
        screen.blit(txt_m3, (btn_theme_triter.centerx - txt_m3.get_width() // 2, btn_theme_triter.centery - txt_m3.get_height() // 2))
        
        pygame.draw.rect(screen, c_theme["ROJO"], boton_regresar_rect, border_radius=12)
        txt_volver = fuente_pequena.render("VOLVER", True, c_theme["TEXTO"])
        screen.blit(txt_volver, (boton_regresar_rect.centerx - txt_volver.get_width() // 2, boton_regresar_rect.centery - txt_volver.get_height() // 2))

    elif estado_juego == "TIENDA_SKINS":
        screen.fill(c_theme["FONDO"])
        titulo_skins = fuente_titulo.render("TIENDA DE PERSONAJES", True, c_theme["TEXTO"])
        screen.blit(titulo_skins, (center_x - titulo_skins.get_width() // 2, 35))
        txt_saldo = fuente_victoria.render(f"Saldo: {monedas} Monedas", True, c_theme["VERDE"])
        screen.blit(txt_saldo, (center_x - txt_saldo.get_width() // 2, 95))
        
        start_y = 160
        for idx, (nombre, data) in enumerate(SKINS_DATA.items()):
            caja_rect = pygame.Rect(center_x - 280, start_y + (idx * 75), 560, 65)
            pygame.draw.rect(screen, c_theme["PANEL"], caja_rect, border_radius=14)
            emoji_p = data["emojis"][0]
            if emoji_p in twemojis:
                screen.blit(twemojis[emoji_p], (caja_rect.x + 18, caja_rect.y + 8))
            
            txt_nombre = fuente_marcador.render(nombre, True, c_theme["TEXTO"])
            screen.blit(txt_nombre, (caja_rect.x + 80, caja_rect.y + 18))
            
            btn_accion = pygame.Rect(caja_rect.right - 170, caja_rect.y + 10, 150, 45)
            if nombre in skins_compradas:
                if skin_equipada == nombre:
                    pygame.draw.rect(screen, c_theme["VERDE"], btn_accion, border_radius=10)
                    t_btn = fuente_pequena.render("EQUIPADO", True, c_theme["TEXTO"])
                else:
                    pygame.draw.rect(screen, c_theme["BOTON"], btn_accion, border_radius=10)
                    t_btn = fuente_pequena.render("EQUIPAR", True, c_theme["TEXTO"])
            else:
                if monedas >= data["precio"] or MODO_ADMIN:
                    pygame.draw.rect(screen, c_theme["NARANJA"], btn_accion, border_radius=10)
                    t_btn = fuente_pequena.render(f"COMPRAR ({data['precio']})", True, c_theme["OSCURO"])
                else:
                    pygame.draw.rect(screen, c_theme["ROJO"], btn_accion, border_radius=10)
                    t_btn = fuente_pequena.render(f"FALTAN {data['precio'] - monedas}", True, c_theme["TEXTO"])
                    
            screen.blit(t_btn, (btn_accion.centerx - t_btn.get_width() // 2, btn_accion.centery - t_btn.get_height() // 2))
            
        pygame.draw.rect(screen, c_theme["ROJO"], boton_regresar_rect, border_radius=12)
        txt_volver = fuente_pequena.render("VOLVER", True, c_theme["TEXTO"])
        screen.blit(txt_volver, (boton_regresar_rect.centerx - txt_volver.get_width() // 2, boton_regresar_rect.centery - txt_volver.get_height() // 2))

    elif estado_juego == "TIENDA_P2W":
        screen.fill(c_theme["FONDO"])
        titulo_tienda = fuente_titulo.render("MEJORAS POR PARTIDA", True, c_theme["TEXTO"])
        screen.blit(titulo_tienda, (center_x - titulo_tienda.get_width() // 2, 35))
        txt_saldo = fuente_victoria.render(f"Saldo: {monedas} Monedas", True, c_theme["VERDE"])
        screen.blit(txt_saldo, (center_x - txt_saldo.get_width() // 2, 95))
        
        def dibujar_item(y, emoji, titulo, desc, rect, comprado, precio):
            pygame.draw.rect(screen, c_theme["PANEL"], (center_x - 340, y, 680, 65), border_radius=14)
            if emoji in twemojis:
                screen.blit(twemojis[emoji], (center_x - 320, y + 8))
            t = fuente_marcador.render(titulo, True, c_theme["TEXTO"])
            d = fuente_pequena.render(desc, True, c_theme["TEXTO_SEC"])
            screen.blit(t, (center_x - 260, y + 8))
            screen.blit(d, (center_x - 260, y + 35))
            
            if MODO_ADMIN:
                pygame.draw.rect(screen, c_theme["VERDE"], rect, border_radius=10)
                txt_b = fuente_pequena.render("ADMIN", True, c_theme["TEXTO"])
            elif comprado:
                pygame.draw.rect(screen, c_theme["OSCURO"], rect, border_radius=10)
                txt_b = fuente_pequena.render("COMPRADO", True, c_theme["TEXTO_SEC"])
            elif monedas >= precio:
                pygame.draw.rect(screen, c_theme["VERDE"], rect, border_radius=10)
                txt_b = fuente_pequena.render(f"Comprar ({precio})", True, c_theme["TEXTO"])
            else:
                pygame.draw.rect(screen, c_theme["ROJO"], rect, border_radius=10)
                txt_b = fuente_pequena.render(f"Faltan {precio - monedas}", True, c_theme["TEXTO"])
            screen.blit(txt_b, (rect.centerx - txt_b.get_width() // 2, rect.centery - txt_b.get_height() // 2))

        dibujar_item(center_y - 120, "⏱️", "Reloj Manipulado", "+30 segundos extra", boton_comprar_tiempo, buff_tiempo_comprado, 50)
        dibujar_item(center_y - 35, "🧲", "Imán de Respuestas", "Atrae la opción correcta", boton_comprar_iman, buff_iman_comprado, 70)
        dibujar_item(center_y + 40, "🛡️", "Escudo Libre", "Inmunidad al fallar", boton_comprar_escudo, buff_escudo_comprado, 80)
        
        pygame.draw.rect(screen, c_theme["ROJO"], boton_regresar_rect, border_radius=12)
        txt_volver = fuente_pequena.render("VOLVER", True, c_theme["TEXTO"])
        screen.blit(txt_volver, (boton_regresar_rect.centerx - txt_volver.get_width() // 2, boton_regresar_rect.centery - txt_volver.get_height() // 2))

    elif estado_juego == "JUGANDO":
        if player_hand_x is not None and player_hand_y is not None:
            mouse_x = player_hand_x
            mouse_y = player_hand_y
        else:
            mouse_x = mouse_pos_game[0]
            mouse_y = mouse_pos_game[1]
            
        last_player_x = mouse_x
        last_player_y = mouse_y
        player_y = mouse_y
        
        if tiempo_reaccion > 0:
            tiempo_reaccion -= 1
        else:
            cara_actual = personaje_actual[0]
            
        if habilidad_activa:
            habilidades_tiempo_restante -= dt
            iman_activo = buff_iman_comprado or MODO_ADMIN
            escudo_activo = buff_escudo_comprado or MODO_ADMIN
            if habilidades_tiempo_restante <= 0:
                habilidades_tiempo_restante = 0
                habilidad_activa = False
                iman_activo = False
                escudo_activo = False
                
        rect_jugador = pygame.Rect(mouse_x - 38, player_y - 38, 76, 76)
        screen.fill(c_theme["FONDO"])
        
        banner = pygame.Rect(center_x - 350, 18, 700, 68)
        pygame.draw.rect(screen, c_theme["PANEL"], banner, border_radius=14)
        pygame.draw.rect(screen, c_theme["BOTON"], banner, width=3, border_radius=14)
        txt_pregunta = fuente_victoria.render(pregunta_actual, True, c_theme["TEXTO"])
        screen.blit(txt_pregunta, (banner.centerx - txt_pregunta.get_width() // 2, banner.centery - txt_pregunta.get_height() // 2))
        
        puno_o_click = puno_recien_cerrado or mouse_click_this_frame
        puedes_interactuar = (cooldown_pregunta <= 0) and (not puno_necesita_liberar) and puno_o_click
        pregunta_resuelta = False
        
        for obs in obstaculos[:]:
            if obs[4] > 0:
                obs[4] = 1
                continue
            if iman_activo and str(obs[3]) == str(respuesta_correcta):
                if obs[0] < mouse_x: obs[0] += 4
                elif obs[0] > mouse_x: obs[0] -= 4
                if obs[1] > mouse_y: obs[1] -= 4
                elif obs[1] < mouse_y: obs[1] += 4
                
            ancho_txt = max(140, len(str(obs[3])) * 22)
            rect_obs = pygame.Rect(0, 0, ancho_txt, 75)
            rect_obs.center = (obs[0], obs[1])
            
            if rect_jugador.colliderect(rect_obs) and puedes_interactuar:
                puno_necesita_liberar = True
                cooldown_pregunta = 0.8
                if str(obs[3]) == str(respuesta_correcta):
                    if snd_bueno: snd_bueno.play()
                    reproducir_voz("Correct!", lang="en")
                    cara_actual = personaje_actual[1]
                    tiempo_reaccion = 40
                    puntos = 10 + (racha * 2)
                    monedas_partida += puntos
                    racha += 1
                    pregunta_resuelta = True
                    obstaculos.remove(obs)
                    break
                else:
                    if not escudo_activo:
                        if snd_malo: snd_malo.play()
                        reproducir_voz("Wrong answer", lang="en")
                        cara_actual = personaje_actual[2]
                        tiempo_reaccion = 40
                        monedas_partida = max(0, monedas_partida - 5)
                        racha = 0
            
            pygame.draw.rect(screen, c_theme["PANEL"], rect_obs, border_radius=16)
            pygame.draw.rect(screen, c_theme["TEXTO_SEC"], rect_obs, width=2, border_radius=16)
            txt_op = fuente_opciones.render(str(obs[3]), True, c_theme["TEXTO"])
            screen.blit(txt_op, (rect_obs.centerx - txt_op.get_width() // 2, rect_obs.centery - txt_op.get_height() // 2))
            
        if len(obstaculos) == 0 or pregunta_resuelta:
            cargar_nueva_pregunta()
            inicializar_obstaculos_educativo()
            
        pygame.draw.circle(screen, c_theme["PANEL"], (mouse_x + 24, player_y + 24), 38)
        col_anillo = c_theme["ROJO"] if hay_puno else c_theme["VERDE"]
        pygame.draw.circle(screen, col_anillo, (mouse_x + 24, player_y + 24), 38, 4)
        if cara_actual in twemojis:
            screen.blit(twemojis[cara_actual], (mouse_x, player_y))
            
        panel_marcador = pygame.Rect(screen_width - 310, 25, 285, 120)
        pygame.draw.rect(screen, c_theme["PANEL"], panel_marcador, border_radius=14)
        t_mon = fuente_marcador.render(f"Monedas: {monedas_partida}", True, c_theme["NARANJA"])
        t_tie = fuente_marcador.render(f"Tiempo: {tiempo_restante} s", True, c_theme["ROJO"] if tiempo_restante <= 10 else c_theme["TEXTO"])
        t_rac = fuente_marcador.render(f"Racha: {racha}", True, c_theme["VERDE"])
        screen.blit(t_mon, (panel_marcador.x + 15, panel_marcador.y + 10))
        screen.blit(t_tie, (panel_marcador.x + 15, panel_marcador.y + 45))
        screen.blit(t_rac, (panel_marcador.x + 15, panel_marcador.y + 80))
        
        if habilidad_disponible and (buff_iman_comprado or buff_escudo_comprado or MODO_ADMIN):
            pygame.draw.rect(screen, c_theme["MORADO"], boton_activar_habilidad, border_radius=10)
            txt_hab = fuente_pequena.render("ACTIVAR", True, c_theme["TEXTO"])
            screen.blit(txt_hab, (boton_activar_habilidad.centerx - txt_hab.get_width() // 2, boton_activar_habilidad.centery - txt_hab.get_height() // 2))
        elif habilidad_activa:
            pygame.draw.rect(screen, c_theme["VERDE"], (screen_width - 190, 95, 160, 45), border_radius=10)
            txt_hab = fuente_pequena.render(f"ACTIVA {int(habilidades_tiempo_restante)}s", True, c_theme["TEXTO"])
            screen.blit(txt_hab, (screen_width - 180, 105))
            
        pygame.draw.rect(screen, c_theme["BOTON"], boton_pausa_rect, border_radius=12)
        txt_pausa = fuente_pequena.render("PAUSA", True, c_theme["TEXTO"])
        screen.blit(txt_pausa, (boton_pausa_rect.centerx - txt_pausa.get_width() // 2, boton_pausa_rect.centery - txt_pausa.get_height() // 2))
        
        col_btn_mic_g = c_theme["ROJO"] if escuchando_mic else c_theme["VERDE"]
        pygame.draw.rect(screen, col_btn_mic_g, boton_mic_game_rect, border_radius=12)
        txt_mic_g = fuente_pequena.render("TUTOR (MIC)", True, c_theme["TEXTO"])
        screen.blit(txt_mic_g, (boton_mic_game_rect.centerx - txt_mic_g.get_width() // 2, boton_mic_game_rect.centery - txt_mic_g.get_height() // 2))
        # Mostrar mensajes del micrófono también durante la partida.
        if texto_escuchado and (escuchando_mic or texto_escuchado.startswith(("No ", "Error", "Audio", "Grabación", "Tú:", "Se ", "Micrófono"))):
            aviso = texto_escuchado
            while len(aviso) > 5 and fuente_pequena.size(aviso)[0] > screen_width - 350:
                aviso = aviso[:-4]
            if aviso != texto_escuchado:
                aviso += "..."
            texto_estado_mic = fuente_pequena.render(aviso, True, c_theme["TEXTO"])
            screen.blit(texto_estado_mic, (325, screen_height - 60))

    elif estado_juego == "PERSONAJES":
        screen.fill(c_theme["FONDO"])
        tit = fuente_titulo.render("TEMAS DE JUEGO", True, c_theme["TEXTO"])
        screen.blit(tit, (center_x - tit.get_width() // 2, 40))
        
        for caja, texto, valor in [(caja_voc, "VOCABULARIO", "VOCABULARIO"), (caja_gram, "GRAMATICA", "GRAMATICA"), (caja_mixto, "MIXTO", "MIXTO")]:
            col = c_theme["VERDE"] if tema_seleccionado == valor else c_theme["BOTON"]
            pygame.draw.rect(screen, col, caja, border_radius=16)
            t = fuente_marcador.render(texto, True, c_theme["TEXTO"])
            screen.blit(t, (caja.centerx - t.get_width() // 2, caja.centery - t.get_height() // 2))
            
        for caja, texto, valor in [(caja_facil, "FÁCIL", "FACIL"), (caja_medio, "MEDIO", "MEDIO"), (caja_dificil, "DIFÍCIL", "DIFICIL")]:
            col = c_theme["NARANJA"] if dificultad_seleccionada == valor else c_theme["BOTON"]
            pygame.draw.rect(screen, col, caja, border_radius=16)
            t = fuente_marcador.render(texto, True, c_theme["TEXTO"])
            screen.blit(t, (caja.centerx - t.get_width() // 2, caja.centery - t.get_height() // 2))
            
        pygame.draw.rect(screen, c_theme["ROJO"], boton_regresar_rect, border_radius=12)
        txt_reg = fuente_pequena.render("REGRESAR", True, c_theme["TEXTO"])
        screen.blit(txt_reg, (boton_regresar_rect.centerx - txt_reg.get_width() // 2, boton_regresar_rect.centery - txt_reg.get_height() // 2))

    elif estado_juego == "PAUSADO":
        panel_pausa = pygame.Rect(center_x - 180, center_y - 100, 360, 280)
        pygame.draw.rect(screen, c_theme["PANEL"], panel_pausa, border_radius=20)
        txt_pausa = fuente_titulo.render("PAUSADO", True, c_theme["TEXTO"])
        screen.blit(txt_pausa, (center_x - txt_pausa.get_width() // 2, center_y - 80))
        
        boton_reanudar_rect = pygame.Rect(center_x - 120, center_y, 240, 55)
        color_reanudar = c_theme["BOTON_HOVER"] if boton_reanudar_rect.collidepoint(mouse_pos_game) else c_theme["BOTON"]
        pygame.draw.rect(screen, color_reanudar, boton_reanudar_rect, border_radius=14)
        t_rea = fuente_marcador.render("REANUDAR", True, c_theme["TEXTO"])
        screen.blit(t_rea, (boton_reanudar_rect.centerx - t_rea.get_width() // 2, boton_reanudar_rect.centery - t_rea.get_height() // 2))
        
        boton_salir_pausa = pygame.Rect(center_x - 100, center_y + 70, 200, 50)
        color_salir = c_theme["ROJO"]
        pygame.draw.rect(screen, color_salir, boton_salir_pausa, border_radius=14)
        t_sal = fuente_marcador.render("SALIR", True, c_theme["TEXTO"])
        screen.blit(t_sal, (boton_salir_pausa.centerx - t_sal.get_width() // 2, boton_salir_pausa.centery - t_sal.get_height() // 2))

    elif estado_juego == "FINAL":
        screen.fill(c_theme["FONDO"])
        panel_final = pygame.Rect(center_x - 220, center_y - 190, 440, 400)
        pygame.draw.rect(screen, c_theme["PANEL"], panel_final, border_radius=25)
        txt_fin = fuente_titulo.render("¡TIEMPO AGOTADO!", True, c_theme["NARANJA"])
        screen.blit(txt_fin, (center_x - txt_fin.get_width() // 2, center_y - 170))
        
        t_gan = fuente_victoria.render(f"Monedas ganadas: {monedas_partida}", True, c_theme["VERDE"])
        t_rac = fuente_marcador.render(f"Mejor racha: {mejor_racha}", True, c_theme["TEXTO"])
        screen.blit(t_gan, (center_x - t_gan.get_width() // 2, center_y - 80))
        screen.blit(t_rac, (center_x - t_rac.get_width() // 2, center_y - 30))
        
        pygame.draw.rect(screen, c_theme["BOTON"], boton_jugar_nuevo_rect, border_radius=16)
        t_jn = fuente_marcador.render("JUGAR DE NUEVO", True, c_theme["TEXTO"])
        screen.blit(t_jn, (boton_jugar_nuevo_rect.centerx - t_jn.get_width() // 2, boton_jugar_nuevo_rect.centery - t_jn.get_height() // 2))
        
        pygame.draw.rect(screen, c_theme["MORADO"], boton_lobby_final_rect, border_radius=16)
        t_lf = fuente_marcador.render("IR AL MENÚ", True, c_theme["TEXTO"])
        screen.blit(t_lf, (boton_lobby_final_rect.centerx - t_lf.get_width() // 2, boton_lobby_final_rect.centery - t_lf.get_height() // 2))

    pygame.display.flip()