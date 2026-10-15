# KINETIX — Aprende inglés jugando

**KINETIX** es un prototipo educativo de escritorio en **Python + Pygame**. Practica vocabulario y gramática en inglés capturando respuestas con la cámara (reconocimiento de mano mediante MediaPipe) o con el ratón. Incluye monedas, tienda de mejoras, ajustes visuales y un **Tutor IA por voz** opcional.

> **¿Quieres jugar sin instalar Python?** Abre **[DESCARGAR APP](DESCARGAR_APP.md)**. GitHub Actions prepara versiones de prueba `KINETIX.exe` (Windows) y `KINETIX.app` (macOS Apple Silicon). Descárgalas solo cuando la compilación aparezca con marca verde; no son versiones firmadas ni probadas en dispositivos reales.

## Requisitos

- **Python 3.11 de 64 bits** recomendado para facilitar la instalación de cámara/audio.
- macOS (incluido Apple Silicon) o Windows (se requiere validar cada máquina). Linux: experimental.
- Cámara y micrófono opcionales según funciones; sin cámara hay controles con ratón.
- Internet para descargar los recursos del reconocimiento de mano la primera vez, las imágenes de emoji, el reconocimiento de voz, Google TTS y las consultas del Tutor IA.
- Una clave de API de OpenAI **solo si deseas usar el Tutor IA**. Cada usuario que lo configure necesitará su propia clave/cupo; una cuenta de ChatGPT no la sustituye.

## Descargar e iniciar — Mac

1. En GitHub, usa **Code → Download ZIP** y descomprime el repositorio (o clónalo con Git).
2. Abre **Terminal** en la carpeta que contiene `main.py` y `requirements.txt`.
3. Ejecuta:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Si `python3.11` no existe pero tienes Python 3.11 instalado, usa el comando de esa instalación. Si PyAudio no compila, instala PortAudio con `brew install portaudio` y vuelve a ejecutar `pip install -r requirements.txt`. macOS puede pedir permisos de Cámara y Micrófono para Terminal, Python o el entorno desde donde lo ejecutas.

**iPhone como cámara:** puedes seleccionarlo como cámara de continuidad en macOS (si está habilitado). El prototipo utiliza la cámara que OpenCV expone con índice 0; todavía **no incluye selector de cámara**. Para el micrófono, puedes elegir la entrada predeterminada de macOS o cambiarla desde Ajustes del juego.

## Descargar e iniciar — Windows

Instala Python 3.11 (64 bits). Después abre PowerShell en la carpeta del proyecto:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Si PowerShell no permite activar el entorno, abre CMD y usa `.venv\Scripts\activate.bat`, o ejecuta directamente `.venv\Scripts\python.exe main.py`. Da permisos de cámara y micrófono cuando los solicite el sistema.

### Si alguna dependencia de cámara o micrófono falla

Prueba primero el **modo básico con ratón**. Ejecuta estos comandos en un entorno virtual limpio:

```bash
python -m pip install -r requirements-minimos.txt
python main.py
```

En este modo no habrá detección de mano por cámara ni captura por micrófono, pero permite verificar la interfaz, preguntas, monedas y tienda. Si ya están instalados `cv2` o MediaPipe de manera parcial, pueden aparecer advertencias y el juego intentará utilizar los módulos disponibles.

## Cómo jugar

- Entra a **¡A JUGAR!**, lee las instrucciones y selecciona una modalidad desde **Temas de juego**.
- Controla al personaje moviendo la mano frente a la cámara; cierra el puño para atrapar respuestas.
- Sin cámara: mueve con el ratón y selecciona con clic.
- Obtén monedas y usa las mejoras en la tienda.
- Para consultar al Tutor IA: **mantén T** mientras hablas y **suelta T** para procesar la pregunta. También puedes mantener pulsado el botón **HABLAR**.
- En **Ajustes** puedes revisar la cámara y cambiar la entrada del micrófono, tema visual o calidad de imagen.

## Configurar Tutor IA de forma privada

**No subas tu clave a GitHub, capturas ni comentarios de código.** El juego intenta leer `OPENAI_API_KEY` de una variable de entorno, o de un archivo local `.openai_key` (ese archivo se ignora con `.gitignore`).

En macOS/Linux:

```bash
export OPENAI_API_KEY="PON_AQUI_TU_PROPIA_CLAVE"
python main.py
```

En PowerShell:

```powershell
$env:OPENAI_API_KEY="PON_AQUI_TU_PROPIA_CLAVE"
python main.py
```

Si no hay clave o cuota, el resto del juego se puede probar, pero el Tutor IA no podrá generar respuestas. Antes de distribuirlo masivamente, habría que rediseñar el acceso a la API (no distribuir una clave personal dentro de una aplicación pública).

## Recursos adicionales

`main.py` intenta descargar `hand_landmarker.task` si no existe y MediaPipe está instalado. La primera descarga requiere internet; si falla, comprueba la conexión y vuelve a iniciar. El juego descarga también imágenes para los emojis. La carpeta `emojis_cache/` no se sube al repositorio.

Estos sonidos son **opcionales** y no están incluidos porque no se recibieron los archivos `.wav` originales:

- `inicio_juego.wav`
- `sonido_agarrar_billete_moneda_diamante.wav`
- `sonido_metiorito_piedra.wav`
- `final_game_porcentaje.wav`

Si tienes derecho a usarlos, colócalos junto a `main.py`. Si faltan, el juego puede ejecutarse sin esos efectos.

## Pruebas en distintos equipos

Usa [`PRUEBAS.md`](PRUEBAS.md) para registrar el dispositivo, sistema, cámara, micrófono, rendimiento, errores y observaciones.

La automatización de GitHub Actions valida **solo la sintaxis y estructura del repositorio** en Mac, Windows y Linux: una verificación verde **no significa que la cámara, el audio o la interfaz estén probados físicamente**.

## Estado del prototipo

Versión inicial de pruebas, en repositorio público. No incluye versión web, Android ni instaladores autónomos. Por ahora no tiene una licencia abierta; la publicación del código no concede automáticamente permiso de reutilización.