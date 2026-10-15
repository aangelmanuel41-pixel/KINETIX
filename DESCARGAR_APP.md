# Descargar KINETIX como aplicación

No necesitas instalar Python, VS Code ni abrir el archivo `main.py`.

## Descargar app para Windows o Mac

1. Abre [Actions](https://github.com/aangelmanuel41-pixel/KINETIX/actions/workflows/compilar-apps.yml).
2. Selecciona una ejecución de **Compilar aplicaciones KINETIX** que haya terminado correctamente (marca verde).
3. Al final de la ejecución, en **Artifacts**, descarga el archivo correspondiente:
   - **Windows:** `KINETIX-windows-latest` → contiene `KINETIX-Windows.zip` con `KINETIX.exe`.
   - **Mac:** `KINETIX-macos-15-arm64` → contiene `KINETIX-macOS.zip` con `KINETIX.app`.
4. Extrae el ZIP y abre la aplicación.

**Nota:** GitHub requiere iniciar sesión para descargar artifacts. Los archivos temporales caducan; para un botón de descarga público sin cuenta en el futuro, hay que publicar una **Release**. Los archivos de Windows y macOS son diferentes.

### macOS
La aplicación no está firmada ni certificada ante Apple. Gatekeeper puede bloquear una app desconocida. Prueba únicamente aplicaciones de fuentes de confianza y revisa las advertencias del sistema. Mac pedirá autorización para cámara y micrófono.

### Windows
Windows puede mostrar una advertencia porque la app no está firmada. Para pruebas, comprueba que el ejecutable proviene de este repositorio. No desactives la protección del equipo.

### Funciones y límites
- Cámara: requiere permisos. En macOS se usa la cámara que OpenCV presenta como número 0; todavía no incluye selector de cámara.
- Tutor IA: requiere conectividad y una clave API propia configurada mediante `OPENAI_API_KEY` o `.openai_key` local. **Nunca compartas ni incluyas claves en el repositorio.**
- El modelo de mano viene incluido en la descarga; los emojis pueden requerir internet durante el primer uso.
- Sonidos adicionales: si no se proporcionaron archivos originales .wav, el juego funciona sin ellos.
- La compilación automatizada no garantiza el funcionamiento físico de cámara, micro y pantalla; por favor registra tus pruebas en `PRUEBAS.md`.
- En macOS los recursos de usuario se guardan en `~/Library/Application Support/KINETIX`; en Windows, en `%LOCALAPPDATA%\\KINETIX`.

## Estado de publicación

Esta es una **versión de pruebas**, no un instalador firmado de producción. Si un trabajo de compilación falla, revisa el log del trabajo y compártelo para corregir dependencias.
