"""Interfaz gráfica para convertir carpetas de PDF a EPUB."""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from conversor import analizar_carpeta_pdfs, convertir_carpeta


class ConversorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Conversor PDF a EPUB")
        self.root.minsize(640, 420)

        self.carpeta_origen = tk.StringVar()
        self.carpeta_destino = tk.StringVar()
        self._id_analisis = 0
        self._ultima_ruta_solicitada: str | None = None

        marco = ttk.Frame(root, padding=16)
        marco.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        marco.columnconfigure(1, weight=1)

        ttk.Label(marco, text="Carpeta de PDFs (origen)").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 8)
        )
        self.entrada_origen = ttk.Entry(marco, textvariable=self.carpeta_origen)
        self.entrada_origen.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        self.entrada_origen.bind("<Return>", self._analizar_origen_evento)
        self.entrada_origen.bind("<FocusOut>", self._analizar_origen_evento)
        ttk.Button(
            marco,
            text="Examinar...",
            command=lambda: self._examinar(
                self.carpeta_origen, "Selecciona la carpeta de PDFs"
            ),
        ).grid(row=0, column=2, padx=(8, 0), pady=(0, 8))

        ttk.Label(marco, text="Carpeta de EPUBs (destino)").grid(
            row=1, column=0, sticky="w", padx=(0, 12), pady=(0, 12)
        )
        ttk.Entry(marco, textvariable=self.carpeta_destino).grid(
            row=1, column=1, sticky="ew", pady=(0, 12)
        )
        ttk.Button(
            marco,
            text="Examinar...",
            command=lambda: self._examinar(
                self.carpeta_destino, "Selecciona la carpeta de EPUBs"
            ),
        ).grid(row=1, column=2, padx=(8, 0), pady=(0, 12))

        self.boton_convertir = ttk.Button(
            marco, text="Convertir PDFs", command=self._iniciar_conversion
        )
        self.boton_convertir.grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=(0, 12)
        )

        ttk.Label(marco, text="Registro de progreso").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        self.registro = scrolledtext.ScrolledText(
            marco, wrap=tk.WORD, state=tk.DISABLED, height=12
        )
        self.registro.tag_configure("texto", foreground="#1e7e34")
        self.registro.tag_configure("escaneado", foreground="#b02a37")
        self.registro.tag_configure("info", foreground="#6c757d")
        self.registro.tag_configure("error", foreground="#d97706")
        self.registro.grid(row=4, column=0, columnspan=3, sticky="nsew")
        marco.rowconfigure(4, weight=1)

    def _examinar(self, variable: tk.StringVar, titulo: str) -> None:
        carpeta = filedialog.askdirectory(parent=self.root, title=titulo)
        if carpeta:
            variable.set(carpeta)
            if variable is self.carpeta_origen:
                self._analizar_origen(forzar=True)

    def _analizar_origen_evento(self, _evento: tk.Event) -> None:
        self._analizar_origen()

    def _limpiar_registro(self) -> None:
        self.registro.configure(state=tk.NORMAL)
        self.registro.delete("1.0", tk.END)
        self.registro.configure(state=tk.DISABLED)

    def _insertar_registro(self, mensaje: str, etiqueta: str) -> None:
        self.registro.configure(state=tk.NORMAL)
        self.registro.insert(tk.END, mensaje + "\n", etiqueta)
        self.registro.see(tk.END)
        self.registro.configure(state=tk.DISABLED)

    def _analizar_origen(self, forzar: bool = False) -> None:
        origen = self.carpeta_origen.get().strip()
        if not origen:
            if self._ultima_ruta_solicitada is not None:
                self._ultima_ruta_solicitada = None
                self._id_analisis += 1
                self._limpiar_registro()
            return

        ruta = Path(origen)
        clave_ruta = str(ruta.resolve()) if ruta.is_dir() else origen
        if not forzar and clave_ruta == self._ultima_ruta_solicitada:
            return

        self._ultima_ruta_solicitada = clave_ruta
        self._id_analisis += 1
        id_analisis = self._id_analisis
        self._limpiar_registro()

        if not ruta.is_dir():
            self._insertar_registro(
                f"La carpeta de origen no existe o no es válida: {origen}",
                "error",
            )
            return

        self._insertar_registro(f"Analizando carpeta: {ruta}", "info")
        hilo = threading.Thread(
            target=self._analizar_en_hilo,
            args=(str(ruta), id_analisis),
            daemon=True,
        )
        try:
            hilo.start()
        except RuntimeError as exc:
            self._insertar_registro(f"No se pudo iniciar el análisis: {exc}", "error")

    def _analizar_en_hilo(self, origen: str, id_analisis: int) -> None:
        try:
            resultados = analizar_carpeta_pdfs(origen)
        except Exception as exc:
            self.root.after(
                0, self._mostrar_error_analisis, id_analisis, str(exc)
            )
            return

        self.root.after(
            0, self._mostrar_resultados_analisis, id_analisis, origen, resultados
        )

    def _mostrar_error_analisis(self, id_analisis: int, error: str) -> None:
        if id_analisis != self._id_analisis:
            return
        self._limpiar_registro()
        self._insertar_registro(f"Error al analizar la carpeta: {error}", "error")

    def _mostrar_resultados_analisis(
        self,
        id_analisis: int,
        origen: str,
        resultados: list[dict[str, str | int]],
    ) -> None:
        if id_analisis != self._id_analisis:
            return

        total = len(resultados)
        cantidad_texto = sum(resultado["tipo"] == "texto" for resultado in resultados)
        cantidad_escaneados = sum(
            resultado["tipo"] == "escaneado" for resultado in resultados
        )
        cantidad_errores = total - cantidad_texto - cantidad_escaneados

        self._limpiar_registro()
        self._insertar_registro(f"Análisis de carpeta: {origen}", "info")
        self._insertar_registro(
            f"{total} PDF(s): {cantidad_texto} de texto, "
            f"{cantidad_escaneados} escaneado(s), {cantidad_errores} con error.",
            "info",
        )

        for resultado in resultados:
            tipo = resultado["tipo"]
            paginas_texto = resultado["paginas_texto"]
            total_paginas = resultado["total_paginas"]
            linea = f"({paginas_texto}/{total_paginas} págs. con texto)"
            if tipo == "texto":
                self._insertar_registro(
                    f"[TEXTO] {resultado['nombre_archivo']} {linea}", "texto"
                )
            elif tipo == "escaneado":
                self._insertar_registro(
                    f"[ESCANEADO] {resultado['nombre_archivo']} {linea}",
                    "escaneado",
                )
            else:
                detalle = resultado["detalle"]
                self._insertar_registro(
                    f"[ERROR] {resultado['nombre_archivo']} {linea} - {detalle}",
                    "error",
                )

    def _agregar_log(self, mensaje: str) -> None:
        self.registro.configure(state=tk.NORMAL)
        self.registro.insert(tk.END, mensaje + "\n")
        self.registro.see(tk.END)
        self.registro.configure(state=tk.DISABLED)

    def _registrar_log(self, mensaje: str) -> None:
        self.root.after(0, self._agregar_log, mensaje)

    def _iniciar_conversion(self) -> None:
        origen = self.carpeta_origen.get().strip()
        destino = self.carpeta_destino.get().strip()

        if not origen or not destino:
            messagebox.showwarning(
                "Faltan carpetas",
                "Selecciona las carpetas de origen y destino.",
                parent=self.root,
            )
            return

        ruta_origen = Path(origen)
        ruta_destino = Path(destino)
        if not ruta_origen.is_dir():
            messagebox.showerror(
                "Origen no válido",
                f"La carpeta de origen no existe o no es una carpeta:\n{origen}",
                parent=self.root,
            )
            return
        if ruta_destino.exists() and not ruta_destino.is_dir():
            messagebox.showerror(
                "Destino no válido",
                f"La ruta de destino no es una carpeta:\n{destino}",
                parent=self.root,
            )
            return

        self.boton_convertir.configure(state=tk.DISABLED)
        hilo = threading.Thread(
            target=self._convertir_en_hilo,
            args=(origen, destino),
            daemon=True,
        )
        try:
            hilo.start()
        except RuntimeError as exc:
            self.boton_convertir.configure(state=tk.NORMAL)
            messagebox.showerror(
                "No se pudo iniciar",
                f"No se pudo iniciar la conversión:\n{exc}",
                parent=self.root,
            )

    def _convertir_en_hilo(self, origen: str, destino: str) -> None:
        try:
            convertir_carpeta(origen, destino, callback_log=self._registrar_log)
        except Exception as exc:
            mensaje = f"Error al procesar las carpetas: {exc}"
            self.root.after(0, self._agregar_log, mensaje)
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Error de conversión", mensaje, parent=self.root
                ),
            )
        finally:
            self.root.after(
                0, lambda: self.boton_convertir.configure(state=tk.NORMAL)
            )


def main() -> None:
    root = tk.Tk()
    ConversorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
