import logging  # Permite inspeccionar el logger configurado.
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest  # Proporciona fixtures y comprobación de errores.

from nivel_experto.tutor_multiagente.logging_config import (
    EVENTOS_PERMITIDOS,
    NOMBRE_ARCHIVO_LOG,
    NOMBRE_HANDLER_ARCHIVO,
    NOMBRE_HANDLER_CONSOLA,
    NOMBRE_LOGGER,
    configurar_logging,
    registrar_evento,
)


@pytest.fixture
def logger_limpio():
    """
    Elimina únicamente los handlers propios del proyecto.

    Pytest puede añadir LogCaptureHandler internos, que no debemos
    eliminar, cerrar ni contar como handlers de la aplicación.
    """
    logger = logging.getLogger(
        NOMBRE_LOGGER
    )

    nombres_proyecto = {
        NOMBRE_HANDLER_CONSOLA,
        NOMBRE_HANDLER_ARCHIVO,
    }

    # Limpia restos de configuraciones anteriores del proyecto.
    for handler in list(logger.handlers):
        if handler.get_name() in nombres_proyecto:
            logger.removeHandler(
                handler
            )
            handler.close()

    yield logger

    # Cierra únicamente los handlers creados por configurar_logging.
    for handler in list(logger.handlers):
        if handler.get_name() in nombres_proyecto:
            logger.removeHandler(
                handler
            )
            handler.close()


def test_configurar_logging_crea_handlers(
    tmp_path,
    logger_limpio,
):
    """
    Configura exactamente una salida de consola y otra de fichero.
    """
    logger = configurar_logging(
        directorio=tmp_path,
    )

    assert logger is logger_limpio
    assert logger.level == logging.INFO
    assert logger.propagate is False

    # Filtra los handlers internos que pytest puede añadir.
    handlers_proyecto = [
        handler
        for handler in logger.handlers
        if handler.get_name() in {
            NOMBRE_HANDLER_CONSOLA,
            NOMBRE_HANDLER_ARCHIVO,
        }
    ]

    nombres = {
        handler.get_name()
        for handler in handlers_proyecto
    }

    assert len(handlers_proyecto) == 2
    assert nombres == {
        NOMBRE_HANDLER_CONSOLA,
        NOMBRE_HANDLER_ARCHIVO,
    }


def test_configurar_logging_escribe_en_archivo(
    tmp_path,
    logger_limpio,
):
    """
    Comprueba que un evento termine en el fichero configurado.
    """
    logger = configurar_logging(
        directorio=tmp_path,
    )

    logger.info(
        "Evento seguro de prueba"
    )

    # Fuerza la escritura de los handlers antes de leer el fichero.
    for handler in logger.handlers:
        handler.flush()

    ruta = (
        tmp_path
        / NOMBRE_ARCHIVO_LOG
    )

    assert ruta.is_file()

    contenido = ruta.read_text(
        encoding="utf-8"
    )

    assert "INFO" in contenido
    assert "Evento seguro de prueba" in contenido


def test_configurar_logging_utiliza_rotacion(
    tmp_path,
    logger_limpio,
):
    """
    Comprueba límites sin generar un fichero de gran tamaño.
    """
    logger = configurar_logging(
        directorio=tmp_path,
    )

    handler_archivo = next(
        handler
        for handler in logger.handlers
        if isinstance(handler, RotatingFileHandler)
    )

    assert handler_archivo.maxBytes == 1_000_000
    assert handler_archivo.backupCount == 3


def test_configurar_logging_no_duplica_handlers(
    tmp_path,
    logger_limpio,
):
    """
    Permite configurar el logger más de una vez con seguridad.
    """
    primer_logger = configurar_logging(
        directorio=tmp_path,
    )
    segundo_logger = configurar_logging(
        directorio=tmp_path,
    )

    assert segundo_logger is primer_logger

    # Solo cuenta los handlers pertenecientes a la aplicación.
    handlers_proyecto = [
        handler
        for handler in segundo_logger.handlers
        if handler.get_name() in {
            NOMBRE_HANDLER_CONSOLA,
            NOMBRE_HANDLER_ARCHIVO,
        }
    ]

    assert len(handlers_proyecto) == 2


@pytest.mark.parametrize(
    "nivel_invalido",
    [
        None,
        "INFO",
        True,
    ],
)
def test_configurar_logging_rechaza_nivel_invalido(
    nivel_invalido,
    tmp_path,
    logger_limpio,
):
    """
    Impide utilizar tipos incompatibles como niveles.
    """
    with pytest.raises(
        TypeError,
        match="nivel de logging",
    ):
        configurar_logging(
            nivel=nivel_invalido,
            directorio=tmp_path,
        )


@pytest.mark.parametrize(
    "directorio_invalido",
    [
        27,
        [],
        True,
    ],
)
def test_configurar_logging_rechaza_directorio_invalido(
    directorio_invalido,
    logger_limpio,
):
    """
    Rechaza valores que no pueden representar una ruta.
    """
    with pytest.raises(
        TypeError,
        match="directorio de logs",
    ):
        configurar_logging(
            directorio=directorio_invalido,
        )


def test_configurar_logging_controla_error_de_directorio(
    tmp_path,
    logger_limpio,
):
    """
    Controla el caso en que la ruta ya sea un archivo.
    """
    ruta_ocupada = (
        tmp_path
        / "ruta_ocupada"
    )
    ruta_ocupada.write_text(
        "contenido",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="crear el directorio",
    ):
        configurar_logging(
            directorio=ruta_ocupada,
        )

def test_registrar_evento_escribe_json_seguro(
    tmp_path,
    logger_limpio,
):
    """
    Guarda únicamente el nombre y los metadatos permitidos.
    """
    logger = configurar_logging(
        directorio=tmp_path,
    )

    registrar_evento(
        logger,
        "evaluacion_completada",
        tecnologia="python",
        resultado="correcta",
        puntuacion=10,
        progreso_guardado=True,
    )

    for handler in logger.handlers:
        if handler.get_name() == NOMBRE_HANDLER_ARCHIVO:
            handler.flush()

    contenido = (
        tmp_path
        / NOMBRE_ARCHIVO_LOG
    ).read_text(
        encoding="utf-8"
    )

    assert '"evento": "evaluacion_completada"' in contenido
    assert '"tecnologia": "python"' in contenido
    assert '"puntuacion": 10' in contenido
    assert '"progreso_guardado": true' in contenido


def test_registrar_evento_normaliza_texto(
    tmp_path,
    logger_limpio,
):
    """
    Elimina saltos y grupos de espacios de los metadatos.
    """
    logger = configurar_logging(
        directorio=tmp_path,
    )

    registrar_evento(
        logger,
        "error_controlado",
        tipo_error="  Error   de\npersistencia  ",
    )

    for handler in logger.handlers:
        if handler.get_name() == NOMBRE_HANDLER_ARCHIVO:
            handler.flush()

    contenido = (
        tmp_path
        / NOMBRE_ARCHIVO_LOG
    ).read_text(
        encoding="utf-8"
    )

    assert "Error de persistencia" in contenido
    assert "Error   de" not in contenido


def test_registrar_evento_rechaza_nombre_desconocido(
    tmp_path,
    logger_limpio,
):
    """
    Impide registrar eventos arbitrarios.
    """
    logger = configurar_logging(
        directorio=tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="no está permitido",
    ):
        registrar_evento(
            logger,
            "evento_inventado",
        )


@pytest.mark.parametrize(
    "campo_sensible",
    [
        "api_key",
        "prompt",
        "respuesta_usuario",
        "solucion_esperada",
        "contenido_fuente",
    ],
)
def test_registrar_evento_rechaza_campos_sensibles(
    campo_sensible,
    tmp_path,
    logger_limpio,
):
    """
    Evita que los datos sensibles entren en los logs.
    """
    logger = configurar_logging(
        directorio=tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="campos no permitidos",
    ):
        registrar_evento(
            logger,
            "error_controlado",
            **{
                campo_sensible: "dato que no debe guardarse",
            },
        )


def test_registrar_evento_rechaza_objetos_complejos(
    tmp_path,
    logger_limpio,
):
    """
    Impide incluir listas o diccionarios dentro del contexto.
    """
    logger = configurar_logging(
        directorio=tmp_path,
    )

    with pytest.raises(
        TypeError,
        match="tipo no permitido",
    ):
        registrar_evento(
            logger,
            "busqueda_completada",

            # Aunque el campo sea válido, su valor no debe ser una lista.
            cantidad_resultados=[1, 2, 3],
        )


def test_registrar_evento_rechaza_logger_invalido():
    """
    Exige utilizar el logger central configurado.
    """
    with pytest.raises(
        TypeError,
        match="Logger válido",
    ):
        registrar_evento(
            None,
            "error_controlado",
        )


def test_eventos_permitidos_no_incluyen_datos_sensibles():
    """
    Documenta la lista cerrada de eventos admitidos.
    """
    assert "evaluacion_completada" in EVENTOS_PERMITIDOS
    assert "progreso_guardado" in EVENTOS_PERMITIDOS
    assert "reintento_programado" in EVENTOS_PERMITIDOS
    assert "reintento_descartado" in EVENTOS_PERMITIDOS
    assert "prompt" not in EVENTOS_PERMITIDOS
    assert "respuesta_usuario" not in EVENTOS_PERMITIDOS
