# Conversor PDF a EPUB

Aplicacion de escritorio escrita en Python para convertir libros PDF que contienen texto en archivos EPUB con texto fluido. El formato EPUB generado permite a los lectores cambiar el tamaño del texto, ajustar la fuente y utilizar las funciones habituales de reflowable para mejorar la lectura.

La aplicacion conserva el nombre base de cada PDF en el archivo EPUB de salida y utiliza los metadatos disponibles del documento PDF, especialmente `title` y `author`. Si un PDF no tiene alguno de estos metadatos, se emplean valores predeterminados razonables: el nombre del archivo como titulo y "Autor desconocido" como autor.

## Funcionalidades implementadas

- **Estructura modular:** la lógica de análisis y conversión se encuentra en `conversor.py`, mientras que la interfaz gráfica se encuentra en `app_gui.py`.
- **Análisis automático de la carpeta de origen:** al seleccionar una carpeta, la aplicación busca los archivos PDF disponibles y lista los encontrados.
- **Clasificación visual de PDFs:** los documentos con texto seleccionable se muestran en verde y los que parecen escaneados o compuestos principalmente por imágenes se muestran en rojo.
- **Conversión por lotes:** convierte todos los PDFs de la carpeta de origen y crea un EPUB por archivo en la carpeta de destino.
- **Conservación del nombre base:** un PDF llamado `mi-libro.pdf` genera `mi-libro.epub`.
- **Conservación de metadatos:** el conversor intenta recuperar `title` y `author` de los metadatos del PDF y incorporarlos al EPUB.
- **Procesamiento sin bloqueo de la interfaz:** el análisis y la conversión se ejecutan en hilos separados, permitiendo que la ventana permanezca interactiva.
- **Registro de progreso y errores:** la interfaz muestra el avance, los archivos procesados y los problemas encontrados durante el análisis o la conversión.

## Limitación actual: OCR

El reconocimiento óptico de caracteres (OCR) para PDFs escaneados **todavía no está implementado**. La aplicación puede identificar documentos que parecen escaneados, pero no extrae ni convierte automáticamente el texto de sus imágenes. Incorporar OCR se considera una mejora futura.

## Requisitos

- Windows
- Python 3
- Las siguientes dependencias:
  - `pymupdf`
  - `ebooklib`
  - `pyinstaller`

## Instalacion en Windows

Abre PowerShell o Símbolo del sistema en la carpeta raíz del proyecto y crea un entorno virtual:

```powershell
py -m venv .venv
```

Activa el entorno virtual:

```powershell
.venv\Scripts\Activate.ps1
```

Si PowerShell impide la ejecución del script de activación, puedes usar Símbolo del sistema:

```bat
.venv\Scripts\activate.bat
```

Instala las dependencias dentro del entorno virtual:

```powershell
python -m pip install pymupdf ebooklib pyinstaller
```

## Uso

Con el entorno virtual activado, ejecuta la interfaz gráfica desde la raíz del proyecto:

```powershell
python app_gui.py
```

En la aplicación:

1. Selecciona la **carpeta de PDFs** de origen.
2. Espera el análisis automático. Los PDFs de texto aparecerán en verde y los escaneados en rojo.
3. Selecciona la **carpeta de EPUBs** de destino.
4. Pulsa **Convertir PDFs**.

Los EPUB generados se guardarán en la carpeta de destino con el mismo nombre base que los PDFs originales.

## Crear un ejecutable `.exe`

Con las dependencias instaladas y el entorno virtual activado, puedes generar un ejecutable con PyInstaller:

```powershell
pyinstaller --onefile --windowed app_gui.py
```

El ejecutable se generará normalmente en la carpeta `dist`. Para añadir un icono personalizado opcional, usa:

```powershell
pyinstaller --onefile --windowed --icon=ruta-al-icono.ico app_gui.py
```
