import json  # Serializa eventos estructurados de forma legible.
import logging  # Proporciona el sistema estándar de registros.
from logging.handlers import RotatingFileHandler  # Limita el tamaño.
from pathlib import Path  # Construye rutas multiplataforma.

from nivel_experto.tutor_multiagente.config import (
    RUTA_DIRECTORIO_LOGS,
)


# Utiliza un logger propio para no modificar el logger raíz de Python.
NOMBRE_LOGGER = "tutor_multiagente"

# Nombre fijo del archivo generado durante la ejecución.
NOMBRE_ARCHIVO_LOG = "tutor_multiagente.log"

# Identificadores internos para evitar añadir handlers duplicados.
NOMBRE_HANDLER_CONSOLA = "tutor_multiagente_consola"
NOMBRE_HANDLER_ARCHIVO = "tutor_multiagente_archivo"

# Eventos técnicos que la aplicación puede registrar.
EVENTOS_PERMITIDOS = {
    "coordinador_completado",
    "busqueda_completada",
    "extraccion_completada",
    "borrador_generado",
    "revision_completada",
    "evaluacion_completada",
    "progreso_guardado",
    "error_controlado",
}

# Solo admite metadatos breves que no contienen contenido personal.
CAMPOS_EVENTO_PERMITIDOS = {
    "tecnologia",
    "accion",
    "resultado",
    "cantidad_resultados",
    "cantidad_fuentes",
    "iteracion",
    "puntuacion",
    "progreso_guardado",
    "tipo_error",
}

def configurar_logging(
    nivel: int = logging.INFO,
    directorio: str | Path | None = None,
) -> logging.Logger:
    """
    Configura el logging central del tutor multiagente.

    Registra eventos en consola y en un fichero rotativo. La función es
    idempotente: llamarla varias veces no duplica los handlers.

    Args:
        nivel: Nivel mínimo que se quiere registrar.
        directorio: Ruta alternativa utilizada durante las pruebas.

    Returns:
        Logger configurado del proyecto.

    Raises:
        TypeError: Si nivel o directorio tienen tipos incorrectos.
        RuntimeError: Si no se puede crear el directorio o el fichero.
    """
    # bool es subclase de int, pero no representa un nivel válido.
    if isinstance(nivel, bool) or not isinstance(nivel, int):
        raise TypeError(
            "El nivel de logging debe ser un número entero."
        )

    if directorio is None:
        directorio_logs = RUTA_DIRECTORIO_LOGS
    elif isinstance(directorio, (str, Path)):
        directorio_logs = Path(
            directorio
        )
    else:
        raise TypeError(
            "El directorio de logs debe ser una ruta."
        )

    try:
        directorio_logs.mkdir(
            parents=True,
            exist_ok=True,
        )
    except OSError as error:
        raise RuntimeError(
            "No se pudo crear el directorio de logs."
        ) from error

    logger = logging.getLogger(
        NOMBRE_LOGGER
    )
    logger.setLevel(
        nivel
    )

    # Evita que el mismo evento se repita en el logger raíz.
    logger.propagate = False

    nombres_handlers = {
        handler.get_name()
        for handler in logger.handlers
    }

    # Si ya está completamente configurado, solo actualiza los niveles.
    if {
        NOMBRE_HANDLER_CONSOLA,
        NOMBRE_HANDLER_ARCHIVO,
    }.issubset(nombres_handlers):
        for handler in logger.handlers:
            if handler.get_name() in {
                NOMBRE_HANDLER_CONSOLA,
                NOMBRE_HANDLER_ARCHIVO,
            }:
                handler.setLevel(
                    nivel
                )

        return logger

    # Incluye fecha, nivel, módulo y mensaje del evento.
    formato = logging.Formatter(
        fmt=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler_consola = logging.StreamHandler()
    handler_consola.set_name(
        NOMBRE_HANDLER_CONSOLA
    )
    handler_consola.setLevel(
        nivel
    )
    handler_consola.setFormatter(
        formato
    )

    ruta_log = (
        directorio_logs
        / NOMBRE_ARCHIVO_LOG
    )

    try:
        # Al llegar a 1 MB conserva hasta tres copias anteriores.
        handler_archivo = RotatingFileHandler(
            filename=ruta_log,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError as error:
        raise RuntimeError(
            "No se pudo abrir el archivo de logs."
        ) from error

    handler_archivo.set_name(
        NOMBRE_HANDLER_ARCHIVO
    )
    handler_archivo.setLevel(
        nivel
    )
    handler_archivo.setFormatter(
        formato
    )

    logger.addHandler(
        handler_consola
    )
    logger.addHandler(
        handler_archivo
    )

    return logger

def registrar_evento(
    logger: object,
    evento: object,
    nivel: int = logging.INFO,
    **contexto: object,
) -> None:
    """
    Registra un evento utilizando nombres y campos permitidos.

    No admite mensajes arbitrarios, prompts, respuestas del usuario,
    claves API, fuentes completas ni soluciones privadas.

    Args:
        logger: Logger previamente configurado.
        evento: Nombre técnico incluido en EVENTOS_PERMITIDOS.
        nivel: Nivel estándar utilizado para el evento.
        contexto: Metadatos breves incluidos en la lista permitida.

    Raises:
        TypeError: Si logger, nivel o valores tienen tipos incorrectos.
        ValueError: Si evento, nivel o campos no están permitidos.
    """
    if not isinstance(logger, logging.Logger):
        raise TypeError(
            "El evento requiere un Logger válido."
        )

    if not isinstance(evento, str):
        raise TypeError(
            "El nombre del evento debe ser texto."
        )

    evento_normalizado = evento.strip()

    if evento_normalizado not in EVENTOS_PERMITIDOS:
        raise ValueError(
            "El nombre del evento no está permitido."
        )

    # Solo permite los niveles estándar utilizados por la aplicación.
    niveles_permitidos = {
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    }

    if isinstance(nivel, bool) or not isinstance(nivel, int):
        raise TypeError(
            "El nivel del evento debe ser un entero."
        )

    if nivel not in niveles_permitidos:
        raise ValueError(
            "El nivel del evento no está permitido."
        )

    campos_recibidos = set(
        contexto
    )
    campos_no_permitidos = (
        campos_recibidos - CAMPOS_EVENTO_PERMITIDOS
    )

    if campos_no_permitidos:
        campos = ", ".join(
            sorted(campos_no_permitidos)
        )

        raise ValueError(
            "El evento contiene campos no permitidos: "
            f"{campos}."
        )

    contexto_validado = {}

    for nombre, valor in contexto.items():
        if isinstance(valor, str):
            # Elimina saltos de línea y limita textos técnicos breves.
            valor_normalizado = " ".join(
                valor.split()
            )

            if not valor_normalizado:
                raise ValueError(
                    f"El campo '{nombre}' no puede estar vacío."
                )

            if len(valor_normalizado) > 100:
                raise ValueError(
                    f"El campo '{nombre}' no puede superar "
                    "100 caracteres."
                )

            contexto_validado[nombre] = valor_normalizado

        elif (
            valor is None
            or isinstance(valor, (bool, int))
        ):
            # Admite contadores, puntuaciones, banderas y ausencia de dato.
            contexto_validado[nombre] = valor

        else:
            # Rechaza listas, diccionarios y objetos externos.
            raise TypeError(
                f"El campo '{nombre}' contiene un tipo no permitido."
            )

    datos_evento = {
        "evento": evento_normalizado,
        **contexto_validado,
    }

    # json.dumps evita construir mensajes mediante concatenaciones libres.
    logger.log(
        nivel,
        json.dumps(
            datos_evento,
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
