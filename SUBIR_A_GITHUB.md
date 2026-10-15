# Cómo publicar KINETIX en GitHub

## Desde la página web

1. Crea un repositorio llamado `KINETIX` en GitHub.
2. Elige **Private** si solo quieres pruebas con tu equipo (más adelante podrás decidir si hacerlo público).
3. Descomprime el ZIP de este proyecto. **No subas el ZIP entero como único archivo**: necesitas subir los archivos y carpetas descomprimidos para que GitHub muestre el código y lea la configuración.
4. En el repositorio, selecciona **Add file → Upload files** y arrastra `main.py`, `README.md`, `requirements.txt`, `PRUEBAS.md`, `.gitignore`, `.github/`, etc. Confirma que aparezcan los archivos ocultos `.gitignore` y `.github/workflows/comprobar.yml`.
5. Haz el commit de los cambios. Verifica que la sección **Actions** muestre la comprobación de sintaxis.
6. Comparte el enlace del repositorio con tus compañeros para que descarguen y prueben el juego siguiendo `README.md`.

### Alternativa desde Terminal (Mac)

Crea primero el repositorio vacío en GitHub. En Terminal, abre esta carpeta descomprimida:

```bash
git init
git add .
git commit -m "Primera version de KINETIX"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/KINETIX.git
git push -u origin main
```

Sustituye `TU_USUARIO` por tu nombre de usuario. GitHub pedirá autenticar la conexión según tu configuración. No pegues contraseñas ni claves en el código o repositorio.

**Nota:** GitHub Pages es para webs estáticas y no ejecutará directamente este Pygame de escritorio; eso requeriría portar el juego a web.