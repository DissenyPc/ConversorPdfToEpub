"""Convierte PDFs con texto a libros EPUB de texto fluido."""

import html
import mimetypes
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Callable, Optional

import fitz
from ebooklib import epub


LogCallback = Optional[Callable[[str], None]]


def _normalizar_texto(texto: str) -> str:
    """Normaliza mayúsculas y tildes para comparar encabezados."""
    texto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def _es_titulo_de_seccion(linea: str) -> bool:
    """Indica si una línea contiene un título o número de capítulo/sección."""
    texto = _normalizar_texto(linea.strip())
    if not texto:
        return False

    if re.match(r"^(?:capitulo|chapter)\b", texto):
        return True
    if re.match(
        r"^(?:prologo|prologue|agradecimientos?|"
        r"acknowledg(?:e)?ments?|thanks|epilogo|epilogue)\b",
        texto,
    ):
        return True
    return bool(
        re.match(r"^(?:\d{1,3}|[ivxlcdm]{1,8})[.)]?$", texto)
        or re.match(r"^(?:\d{1,3}|[ivxlcdm]{1,8})[.)]\s+\S", texto)
    )


def _detectar_seccion(texto: str) -> Optional[str]:
    """Detecta secciones especiales o encabezados que terminan una sección."""
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]
    if not lineas:
        return None

    encabezado = lineas[0]
    normalizado = _normalizar_texto(encabezado)
    if re.match(r"^(?:capitulo|chapter)\b", normalizado):
        return "capitulo"
    if re.match(r"^(?:prologo|prologue)\b", normalizado):
        return "prologo"
    if re.match(r"^(?:agradecimientos?|acknowledg(?:e)?ments?|thanks)\b", normalizado):
        return "agradecimientos"
    if re.match(r"^(?:epilogo|epilogue)\b", normalizado):
        return "epilogo"
    if _es_titulo_de_seccion(encabezado):
        return "capitulo"

    encabezado_generico = re.match(
        r"^(?:introduccion|indice|contenido|prefacio|dedicatoria|"
        r"bibliografia|referencias|conclusion|anexos?|"
        r"introduction|contents|foreword|preface|references|conclusion|appendix)\b",
        normalizado,
    )
    letras = [caracter for caracter in encabezado if caracter.isalpha()]
    es_mayusculas = bool(letras) and all(caracter.isupper() for caracter in letras)
    if encabezado_generico or (
        len(encabezado) <= 80 and es_mayusculas
        and not re.search(r"[.!?…]$", encabezado)
    ):
        return "otra"
    return None


def _termina_en_punto(linea: str) -> bool:
    """Comprueba el punto final sin interpretar abreviaturas frecuentes como fin."""
    texto = linea.rstrip()
    texto_sin_cierre = re.sub(r"""["'»”’)\]}]+$""", "", texto)
    if not re.search(r"(?:\.|…)$", texto_sin_cierre):
        return False
    if re.search(
        r"(?:^|\s)(?:sr|sra|srta|dr|dra|ud|uds|etc|num|pag|pags|"
        r"vol|aprox|art|fig|ej|[a-z])\.$",
        _normalizar_texto(texto_sin_cierre),
    ):
        return False
    return True


def _convertir_saltos_de_linea(
    texto: str,
    seccion_actual: Optional[str],
) -> tuple[str, Optional[str]]:
    """Une líneas en prosa salvo tras una frase completa o un encabezado."""
    lineas = texto.split("\n")
    resultado = []
    for indice, linea in enumerate(lineas):
        seccion_detectada = _detectar_seccion(linea)
        if seccion_detectada == "otra":
            seccion_actual = None
        elif seccion_detectada is not None:
            seccion_actual = seccion_detectada

        resultado.append(linea)
        if indice == len(lineas) - 1:
            continue
        conservar_salto = (
            seccion_actual is None
            or _termina_en_punto(linea)
            or _es_titulo_de_seccion(linea)
            or _es_titulo_de_seccion(lineas[indice + 1])
        )
        resultado.append("\n" if conservar_salto else " ")
    return "".join(resultado), seccion_actual


def analizar_pdf(
    ruta_pdf: str | Path,
    umbral_caracteres: int = 40,
) -> dict[str, str | int]:
    """Clasifica un PDF según la cantidad de texto seleccionable de sus páginas."""
    ruta = Path(ruta_pdf)
    resultado: dict[str, str | int] = {
        "nombre_archivo": ruta.name,
        "ruta": str(ruta),
        "tipo": "error",
        "paginas_texto": 0,
        "total_paginas": 0,
        "detalle": "",
    }

    try:
        with fitz.open(ruta_pdf) as doc:
            total_paginas = len(doc)
            resultado["total_paginas"] = total_paginas
            if total_paginas == 0:
                resultado["detalle"] = "El PDF no contiene páginas."
                return resultado

            paginas_texto = 0
            paginas_con_imagenes = 0
            for pagina in doc:
                texto = pagina.get_text("text").strip()
                if len(texto) >= umbral_caracteres:
                    paginas_texto += 1
                    resultado["paginas_texto"] = paginas_texto
                if pagina.get_images(full=True):
                    paginas_con_imagenes += 1

            if paginas_texto / total_paginas >= 0.5:
                resultado["tipo"] = "texto"
                resultado["detalle"] = (
                    f"{paginas_texto} de {total_paginas} páginas tienen texto "
                    "seleccionable suficiente."
                )
            else:
                resultado["tipo"] = "escaneado"
                detalle = (
                    f"Solo {paginas_texto} de {total_paginas} páginas tienen "
                    "texto seleccionable suficiente."
                )
                if paginas_con_imagenes:
                    detalle += (
                        f" Se detectaron imágenes en {paginas_con_imagenes} "
                        "páginas; podría ser un documento escaneado."
                    )
                else:
                    detalle += " Podría ser un documento escaneado."
                resultado["detalle"] = detalle
    except Exception as exc:
        resultado["detalle"] = f"No se pudo analizar el PDF: {exc}"

    return resultado


def analizar_carpeta_pdfs(carpeta_entrada: str | Path) -> list[dict[str, str | int]]:
    """Analiza los archivos PDF de una carpeta y devuelve sus resultados."""
    entrada = Path(carpeta_entrada)
    if not entrada.is_dir():
        raise NotADirectoryError(
            f"La carpeta de entrada no existe o no es una carpeta: {entrada}"
        )

    archivos_pdf = sorted(
        (
            archivo
            for archivo in entrada.iterdir()
            if archivo.is_file() and archivo.suffix.lower() == ".pdf"
        ),
        key=lambda archivo: archivo.name.lower(),
    )
    return [analizar_pdf(archivo) for archivo in archivos_pdf]


def _registrar(mensaje: str, callback_log: LogCallback) -> None:
    if callback_log is None:
        print(mensaje)
    else:
        callback_log(mensaje)


def convertir_pdf_a_epub(
    ruta_pdf: str | Path,
    ruta_epub: str | Path,
    callback_log: LogCallback = None,
) -> bool:
    """Convierte un PDF en un EPUB. Devuelve False si el archivo no se pudo convertir."""
    ruta_pdf = Path(ruta_pdf)
    ruta_epub = Path(ruta_epub)

    try:
        with fitz.open(ruta_pdf) as doc:
            metadatos = doc.metadata or {}
            titulo = (metadatos.get("title") or "").strip() or ruta_pdf.stem
            autor = (metadatos.get("author") or "").strip() or "Autor desconocido"

            libro = epub.EpubBook()
            libro.set_identifier(str(uuid.uuid4()))
            libro.set_title(titulo)
            libro.set_language("es")
            libro.add_author(autor)

            try:
                if len(doc) == 0:
                    raise ValueError("El PDF no contiene páginas.")
                portada = doc[0].get_pixmap(dpi=150).tobytes("png")
                libro.set_cover("cover.png", portada)
            except Exception as exc:
                _registrar(f"Aviso: no se pudo generar la portada: {exc}", callback_log)

            capitulos = []
            imagenes_por_xref: dict[int, str] = {}
            xrefs_fallidos: set[int] = set()
            seccion_actual: Optional[str] = None
            for numero_pagina, pagina in enumerate(doc, start=1):
                texto = pagina.get_text("text").strip()
                parrafos = [
                    parrafo.strip()
                    for parrafo in re.split(r"\n\s*\n", texto)
                    if parrafo.strip()
                ]
                parrafos_html = []
                for parrafo in parrafos:
                    texto_html, seccion_actual = _convertir_saltos_de_linea(
                        parrafo, seccion_actual
                    )
                    parrafos_html.append(
                        html.escape(texto_html).replace("\n", "<br />")
                    )
                contenido = "".join(
                    f"<p>{parrafo_html}</p>" for parrafo_html in parrafos_html
                )

                imagenes_pagina = []
                xrefs_pagina = set()
                for imagen in pagina.get_images(full=True):
                    xref = imagen[0]
                    if xref in xrefs_pagina or xref in xrefs_fallidos:
                        continue
                    xrefs_pagina.add(xref)

                    if xref not in imagenes_por_xref:
                        try:
                            datos_imagen = doc.extract_image(xref)
                            contenido_imagen = datos_imagen["image"]
                            extension = re.sub(
                                r"[^a-z0-9]",
                                "",
                                str(datos_imagen.get("ext") or "png").lower(),
                            ) or "bin"
                            nombre_imagen = f"images/image_{xref}.{extension}"
                            media_type = (
                                mimetypes.guess_type(nombre_imagen)[0]
                                or f"image/{extension}"
                            )
                            recurso_imagen = epub.EpubImage(
                                uid=f"image_{xref}",
                                file_name=nombre_imagen,
                                media_type=media_type,
                                content=contenido_imagen,
                            )
                            libro.add_item(recurso_imagen)
                            imagenes_por_xref[xref] = nombre_imagen
                        except Exception as exc:
                            xrefs_fallidos.add(xref)
                            _registrar(
                                f"Aviso: no se pudo extraer la imagen {xref} "
                                f"de la página {numero_pagina}: {exc}",
                                callback_log,
                            )
                            continue

                    ruta_imagen = html.escape(imagenes_por_xref[xref], quote=True)
                    imagenes_pagina.append(
                        f'<img src="{ruta_imagen}" alt="Imagen extraída del PDF" '
                        'style="max-width: 100%; height: auto;" />'
                    )

                capitulo = epub.EpubHtml(
                    title="Contenido",
                    file_name=f"capitulo_{numero_pagina}.xhtml",
                    lang="es",
                )
                capitulo.content = (
                    f'<section data-pdf-page="{numero_pagina}">'
                    f"{contenido}{''.join(imagenes_pagina)}</section>"
                )
                libro.add_item(capitulo)
                capitulos.append(capitulo)

            libro.toc = tuple(capitulos)
            libro.add_item(epub.EpubNcx())
            libro.add_item(epub.EpubNav())
            libro.spine = ["nav", *capitulos]

            epub.write_epub(str(ruta_epub), libro)

        _registrar(f"Convertido: {ruta_pdf.name} -> {ruta_epub.name}", callback_log)
        return True
    except Exception as exc:
        _registrar(f"Error al convertir {ruta_pdf.name}: {exc}", callback_log)
        return False


def convertir_carpeta(
    carpeta_entrada: str | Path,
    carpeta_salida: str | Path,
    callback_log: LogCallback = None,
) -> None:
    """Convierte todos los PDF de una carpeta a EPUB."""
    entrada = Path(carpeta_entrada)
    salida = Path(carpeta_salida)

    if not entrada.exists() or not entrada.is_dir():
        mensaje = f"Error: la carpeta de entrada no existe o no es una carpeta: {entrada}"
        _registrar(mensaje, callback_log)
        raise NotADirectoryError(mensaje)

    salida.mkdir(parents=True, exist_ok=True)
    archivos_pdf = sorted(
        (archivo for archivo in entrada.iterdir()
         if archivo.is_file() and archivo.suffix.lower() == ".pdf"),
        key=lambda archivo: archivo.name.lower(),
    )

    if not archivos_pdf:
        _registrar(f"No se encontraron archivos PDF en: {entrada}", callback_log)
        return

    for ruta_pdf in archivos_pdf:
        ruta_epub = salida / f"{ruta_pdf.stem}.epub"
        _registrar(f"Procesando: {ruta_pdf.name}", callback_log)
        convertir_pdf_a_epub(ruta_pdf, ruta_epub, callback_log)
