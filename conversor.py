"""Convierte PDFs con texto a libros EPUB de texto fluido."""

import html
import re
import uuid
from pathlib import Path
from typing import Callable, Optional

import fitz
from ebooklib import epub


LogCallback = Optional[Callable[[str], None]]


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

            capitulos = []
            for i, pagina in enumerate(doc):
                texto = pagina.get_text("text").strip()
                parrafos = [
                    re.sub(r"\s+", " ", parrafo).strip()
                    for parrafo in re.split(r"\n\s*\n", texto)
                    if parrafo.strip()
                ]
                contenido = "".join(
                    f"<p>{html.escape(parrafo)}</p>" for parrafo in parrafos
                )

                titulo_capitulo = f"Página {i + 1}"
                capitulo = epub.EpubHtml(
                    title=titulo_capitulo,
                    file_name=f"capitulo_{i + 1}.xhtml",
                    lang="es",
                )
                capitulo.content = (
                    f"<h1>{html.escape(titulo_capitulo)}</h1>{contenido}"
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
