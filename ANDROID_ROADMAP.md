# Plan de KINETIX para Android (APK)

## Meta
Crear una app **Android descargable** y un sitio web **informativo**, no intentar correr el archivo actual `main.py` desde el navegador.

### Qué existe
- KINETIX de escritorio escrito en Python/Pygame, con cámara por MediaPipe, preguntas, tienda, skins y tutor opcional.
- Página oficial en `docs/index.html`, sin enlaces falsos a aplicaciones no construidas.
- Todavía **no existe un APK de KINETIX**.

### Qué necesitamos desarrollar y probar
1. Crear interfaz jugable para pantallas táctiles y distintas resoluciones Android.
2. Reutilizar el banco de preguntas, dificultades, monedas y compras en la nueva app.
3. Agregar guardado de progreso y un tutorial para teléfono.
4. Añadir opcionalmente control por mano usando un componente compatible con Android y solicitar permiso de cámara **solo al usarlo**.
5. Separar y proteger la conexión del Tutor IA; **no incrustar nunca una clave OpenAI en el APK**. Para lanzarlo públicamente, hace falta un servicio backend con controles de uso y costos o desactivar temporalmente el tutor.
6. Configurar el proyecto y generar un APK firmado de prueba o distribución; instalarlo en teléfonos Android reales, revisar rendimiento, permisos, orientación, sonido y fallos.
7. Publicar en GitHub Releases un archivo `.apk` probado. La página detectará automáticamente un APK en la **última release** publicada.

### Alternativas técnicas
- **Flutter + Flame**: reimplementación del motor gráfico y entrada táctil con un proyecto multiplataforma que puede ampliarse a iPhone; integraciones de cámara, ML e IA se implementan por separado.
- **Kivy + Buildozer**: mantiene parte de Python, pero el juego actual usa Pygame, OpenCV, MediaPipe y PyAudio; requiere evaluar y portar dependencias antes de prometer un APK funcional. No es una conversión automática.

La ruta recomendada para una app Android estable es realizar una adaptación gradual con control táctil primero, conservando la edición de escritorio.

### Publicar página
Activar GitHub Pages mediante **Settings → Pages → Build and deployment → Source: GitHub Actions**. La acción `Publicar página KINETIX` sirve los archivos de `docs/`. Enlace esperado después de activarla:
https://aangelmanuel41-pixel.github.io/KINETIX/

### Descargas
El botón Android solo se habilita si la **última versión publicada** en GitHub Releases contiene un archivo con extensión `.apk`. Si no existe, aparece *APK en preparación*.
