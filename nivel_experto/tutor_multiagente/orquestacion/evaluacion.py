import logging  # Obtiene el logger sin forzar su configuración.

from pathlib import Path  # Permite indicar una ruta alternativa en tests.
from copy import deepcopy  # Evita compartir estructuras mutables.

# Construye y guarda el registro de progreso.
from nivel_experto.tutor_multiagente.herramientas.progreso import (
    crear_registro_progreso,
    guardar_registro_progreso,
)

# Valida la tecnología antes de consumir tokens.
from nivel_experto.tutor_multiagente.herramientas.fuentes import (
    obtener_fuente_oficial,
)

# Importa los modelos utilizados en la actualización del estado.
from nivel_experto.tutor_multiagente.agentes.esquemas import (
    BorradorTutor,
    EvaluacionEjercicio,
)

# Reutiliza la validación del ejercicio persistido.
from nivel_experto.tutor_multiagente.agentes.tutor_investigador import (
    interpretar_borrador_tutor,
)

# Comprueba que la evaluación cubra exactamente toda la rúbrica.
from nivel_experto.tutor_multiagente.agentes.evaluador import (
    ejecutar_evaluacion_ejercicio,
    validar_criterios_evaluacion,
)

# Permite inyectar un cliente simulado durante las pruebas.
from nivel_experto.tutor_multiagente.agentes.cliente_groq import (
    ClienteGroq,
)

# Registra únicamente eventos y metadatos permitidos.
from nivel_experto.tutor_multiagente.logging_config import (
    NOMBRE_LOGGER,
    registrar_evento,
)


def crear_actualizacion_evaluacion_ejercicio(
    evaluacion: object,
    ejercicio: object,
) -> dict[str, object]:
    """
    Convierte una evaluación validada en una actualización de EstadoTutor.

    Args:
        evaluacion: Resultado validado del agente evaluador.
        ejercicio: Ejercicio activo o diccionario recuperado del estado.

    Returns:
        Campos que deben incorporarse al EstadoTutor.

    Raises:
        TypeError: Si la evaluación no es un modelo validado.
        ValueError: Si el ejercicio o su relación con la rúbrica no es válida.
    """
    # No acepta directamente un diccionario generado por el modelo.
    if not isinstance(evaluacion, EvaluacionEjercicio):
        raise TypeError(
            "La actualización requiere una "
            "EvaluacionEjercicio validada."
        )

    # Permite recuperar el ejercicio desde su representación persistida.
    ejercicio_validado = interpretar_borrador_tutor(
        ejercicio
    )

    # Verifica el tipo de borrador y la cobertura completa de su rúbrica.
    validar_criterios_evaluacion(
        evaluacion,
        ejercicio_validado,
    )

    # Traduce la decisión estructurada a un texto visible.
    estado_respuesta = (
        "Correcta"
        if evaluacion.respuesta_correcta
        else "Necesita mejorar"
    )

    partes_respuesta = [
        "## Evaluación del ejercicio",
        "",
        f"**Resultado:** {estado_respuesta}",
        "",
        f"**Puntuación:** {evaluacion.puntuacion}/10",
        "",
        evaluacion.retroalimentacion_markdown,
    ]

    # La recomendación es opcional y solo se muestra cuando existe.
    if evaluacion.recomendacion_siguiente is not None:
        partes_respuesta.extend(
            [
                "",
                "### Siguiente paso recomendado",
                "",
                evaluacion.recomendacion_siguiente,
            ]
        )

    respuesta_final = "\n".join(
        partes_respuesta
    )

    return {
        # Conserva la evaluación estructurada para progreso y logging.
        "evaluacion": deepcopy(
            evaluacion.model_dump()
        ),

        # Mantiene el ejercicio activo sin alterar su solución privada.
        "ejercicio_actual": deepcopy(
            ejercicio_validado.model_dump()
        ),

        # Solo esta versión formateada será visible para el estudiante.
        "respuesta_final": respuesta_final,

        # El guardado se realizará en la función de orquestación exterior.
        "progreso_guardado": False,

        # Una actualización correcta no incorpora errores.
        "errores": [],
    }

def ejecutar_evaluacion_desde_estado(
    estado: object,
    cliente: ClienteGroq | None = None,
    directorio_progreso: str | Path | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, object]:
    """
    Evalúa la respuesta del estado y guarda su progreso.

    Un fallo al guardar el JSON no oculta la evaluación al estudiante:
    se devuelve la respuesta junto con un error controlado.

    Args:
        estado: Estado compartido del turno actual.
        cliente: Cliente alternativo utilizado en las pruebas.
        directorio_progreso: Ruta alternativa para la persistencia.
        logger: Logger alternativo utilizado durante las pruebas.

    Returns:
        Actualización con evaluación, respuesta final y estado del guardado.

    Raises:
        TypeError: Si el estado contiene tipos incorrectos.
        ValueError: Si faltan datos necesarios para evaluar.
        RuntimeError: Si el agente evaluador no puede responder.
    """
    # TypedDict ayuda estáticamente, pero en ejecución sigue siendo dict.
    if not isinstance(estado, dict):
        raise TypeError(
            "El estado del tutor debe ser un diccionario."
        )

    # La aplicación principal configurará este logger al iniciarse.
    # En los tests también podemos proporcionar un logger simulado.
    logger_eventos = (
        logger
        if logger is not None
        else logging.getLogger(NOMBRE_LOGGER)
    )

    # Impide utilizar números, cadenas u otros objetos como logger.
    if not isinstance(logger_eventos, logging.Logger):
        raise TypeError(
            "La orquestación requiere un Logger válido."
        )

    accion = estado.get(
        "accion"
    )

    # Evita ejecutar esta ruta desde otra decisión del coordinador.
    if accion != "evaluar_respuesta":
        raise ValueError(
            "El estado no corresponde a una evaluación de respuesta."
        )

    respuesta_estudiante = estado.get(
        "entrada_usuario"
    )

    # Valida la entrada antes de cualquier llamada externa.
    if not isinstance(respuesta_estudiante, str):
        raise TypeError(
            "La respuesta del estudiante debe ser texto."
        )

    respuesta_normalizada = respuesta_estudiante.strip()

    if not respuesta_normalizada:
        raise ValueError(
            "La respuesta del estudiante no puede estar vacía."
        )

    ejercicio = estado.get(
        "ejercicio_actual"
    )

    if ejercicio is None:
        raise ValueError(
            "No hay ningún ejercicio activo para evaluar."
        )

    fuentes_extraidas = estado.get(
        "fuentes_extraidas"
    )

    if not isinstance(fuentes_extraidas, list):
        raise TypeError(
            "Las fuentes extraídas del estado deben ser una lista."
        )

    if not fuentes_extraidas:
        raise ValueError(
            "No hay fuentes oficiales disponibles para evaluar."
        )

    # Comprueba antes de usar Groq que la tecnología sea oficial.
    fuente_tecnologia = obtener_fuente_oficial(
        estado.get("tecnologia")
    )
    tecnologia = fuente_tecnologia["id"]

    # El agente compara respuesta, solución, rúbrica y fuentes.
    evaluacion = ejecutar_evaluacion_ejercicio(
        ejercicio=ejercicio,
        respuesta_estudiante=respuesta_normalizada,
        fuentes_extraidas=fuentes_extraidas,
        cliente=cliente,
    )

    # Prepara primero la respuesta visible y la evaluación estructurada.
    actualizacion = crear_actualizacion_evaluacion_ejercicio(
        evaluacion=evaluacion,
        ejercicio=ejercicio,
    )

    # Registra únicamente el resultado, sin respuesta ni solución.
    registrar_evento(
        logger_eventos,
        "evaluacion_completada",
        tecnologia=tecnologia,
        resultado=(
            "correcta"
            if evaluacion.respuesta_correcta
            else "incorrecta"
        ),
        puntuacion=evaluacion.puntuacion,
    )

    # El registro omite respuesta del estudiante y solución privada.
    registro = crear_registro_progreso(
        tecnologia=tecnologia,
        ejercicio=ejercicio,
        evaluacion=evaluacion,
    )

    try:
        guardar_registro_progreso(
            registro=registro,
            directorio=directorio_progreso,
        )
    except RuntimeError as error:
        # La evaluación sigue siendo útil aunque falle el almacenamiento.
        actualizacion["errores"] = [
            *actualizacion["errores"],
            (
                "La evaluación se completó, pero no se pudo "
                f"guardar el progreso: {error}"
            ),
        ]

        # Solo registra la clase del error, nunca su contenido.
        registrar_evento(
            logger_eventos,
            "error_controlado",
            nivel=logging.WARNING,
            tecnologia=tecnologia,
            resultado="progreso_no_guardado",
            tipo_error=type(error).__name__,
        )

        return actualizacion

    # Solo se marca como guardado después del reemplazo atómico.
    actualizacion["progreso_guardado"] = True

    registrar_evento(
        logger_eventos,
        "progreso_guardado",
        tecnologia=tecnologia,
        resultado="guardado",
        progreso_guardado=True,
    )

    return actualizacion
