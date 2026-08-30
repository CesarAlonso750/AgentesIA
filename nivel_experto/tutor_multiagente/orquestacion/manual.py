import logging  # Obtiene el logger central sin crear handlers.
import json  # Construye el contexto estructurado del coordinador.
from copy import deepcopy  # Evita modificar directamente el estado recibido.
from pathlib import Path  # Permite redirigir el progreso en las pruebas.

# Ejecuta la tercera ruta posible: evaluar un ejercicio anterior.
from nivel_experto.tutor_multiagente.orquestacion.evaluacion import (
    ejecutar_evaluacion_desde_estado,
)

from nivel_experto.tutor_multiagente.agentes.cliente_groq import (
    ClienteGroq,
)
from nivel_experto.tutor_multiagente.agentes.coordinador import (
    crear_actualizacion_coordinador,
    ejecutar_coordinador,
)
from nivel_experto.tutor_multiagente.logging_config import (
    NOMBRE_LOGGER,
    registrar_evento,
)

# Tipos de clientes utilizados por las herramientas web.
from nivel_experto.tutor_multiagente.herramientas.busqueda import (
    ClienteBusqueda,
)
from nivel_experto.tutor_multiagente.herramientas.extraccion import (
    ClienteExtraccion,
)

# Ejecuta las cuatro fases del tutor-investigador.
from nivel_experto.tutor_multiagente.agentes.tutor_investigador import (
    crear_actualizacion_investigador,
    ejecutar_investigacion_completa,
)

# Coordina la revisión y posible corrección del borrador.
from nivel_experto.tutor_multiagente.orquestacion.revision import (
    crear_actualizacion_revision,
    ejecutar_ciclo_revision_borrador,
)

def construir_entrada_coordinador(
    estado: object,
) -> str:
    """
    Construye el JSON mínimo que recibirá el coordinador.

    No incluye historial completo, fuentes, solución esperada,
    evaluación anterior ni borradores.

    Args:
        estado: EstadoTutor del turno actual.

    Returns:
        JSON textual con entrada y metadatos seguros.

    Raises:
        TypeError: Si el estado o sus campos tienen tipos incorrectos.
        ValueError: Si la entrada está vacía.
    """
    if not isinstance(estado, dict):
        raise TypeError(
            "El estado del tutor debe ser un diccionario."
        )

    entrada_usuario = estado.get(
        "entrada_usuario"
    )

    if not isinstance(entrada_usuario, str):
        raise TypeError(
            "La entrada del estado debe ser texto."
        )

    entrada_normalizada = entrada_usuario.strip()

    if not entrada_normalizada:
        raise ValueError(
            "La entrada del estado no puede estar vacía."
        )

    historial = estado.get(
        "historial",
        [],
    )

    if not isinstance(historial, list):
        raise TypeError(
            "El historial del estado debe ser una lista."
        )

    ejercicio = estado.get(
        "ejercicio_actual"
    )

    if ejercicio is not None and not isinstance(ejercicio, dict):
        raise TypeError(
            "El ejercicio activo debe ser un diccionario o null."
        )

    tecnologia = estado.get(
        "tecnologia"
    )

    if tecnologia is not None:
        if not isinstance(tecnologia, str):
            raise TypeError(
                "La tecnología de contexto debe ser texto o null."
            )

        tecnologia = tecnologia.strip()

        if not tecnologia:
            tecnologia = None

    datos_coordinador = {
        # Único contenido libre escrito por el estudiante.
        "entrada_usuario": entrada_normalizada,

        # Metadatos internos controlados por nuestra aplicación.
        "hay_ejercicio_activo": ejercicio is not None,
        "tecnologia_contexto": tecnologia,
        "cantidad_mensajes_historial": len(historial),
    }

    return json.dumps(
        datos_coordinador,
        ensure_ascii=False,
        indent=2,
    )

def ejecutar_coordinador_desde_estado(
    estado: object,
    cliente: ClienteGroq | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, object]:
    """
    Ejecuta el coordinador utilizando la entrada de EstadoTutor.

    Args:
        estado: Estado compartido del turno actual.
        cliente: Cliente alternativo utilizado en pruebas.
        logger: Logger alternativo utilizado en pruebas.

    Returns:
        Actualización producida por el coordinador.

    Raises:
        TypeError: Si el estado o sus campos tienen tipos incorrectos.
        ValueError: Si la entrada está vacía.
        RuntimeError: Si el coordinador no puede responder.
    """
    if not isinstance(estado, dict):
        raise TypeError(
            "El estado del tutor debe ser un diccionario."
        )

    entrada_usuario = estado.get(
        "entrada_usuario"
    )

    if not isinstance(entrada_usuario, str):
        raise TypeError(
            "La entrada del estado debe ser texto."
        )

    entrada_normalizada = entrada_usuario.strip()

    if not entrada_normalizada:
        raise ValueError(
            "La entrada del estado no puede estar vacía."
        )

    logger_eventos = (
        logger
        if logger is not None
        else logging.getLogger(NOMBRE_LOGGER)
    )

    if not isinstance(logger_eventos, logging.Logger):
        raise TypeError(
            "La orquestación requiere un Logger válido."
        )

    # Construye un contexto mínimo sin fuentes ni solución privada.
    entrada_coordinador = construir_entrada_coordinador(
        estado
    )

    # El coordinador decide la ruta, pero no responde técnicamente.
    decision = ejecutar_coordinador(
        entrada_coordinador,
        cliente=cliente,
    )

    # Convierte el modelo Pydantic en campos de EstadoTutor.
    actualizacion = crear_actualizacion_coordinador(
        decision
    )

    # Solo registra la decisión, nunca la entrada del estudiante.
    registrar_evento(
        logger_eventos,
        "coordinador_completado",
        accion=decision.accion,
        tecnologia=decision.tecnologia,
        resultado="completado",
    )

    return actualizacion

def ejecutar_ruta_documentada_desde_estado(
    estado: object,
    cliente_busqueda: ClienteBusqueda | None = None,
    cliente_seleccion: ClienteGroq | None = None,
    cliente_extraccion: ClienteExtraccion | None = None,
    cliente_redaccion: ClienteGroq | None = None,
    cliente_evaluador: ClienteGroq | None = None,
    cliente_correccion: ClienteGroq | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, object]:
    """
    Ejecuta investigación, redacción y revisión desde EstadoTutor.

    Args:
        estado: Estado actualizado previamente por el coordinador.
        cliente_busqueda: Cliente alternativo para Tavily Search.
        cliente_seleccion: Cliente alternativo para seleccionar fuentes.
        cliente_extraccion: Cliente alternativo para Tavily Extract.
        cliente_redaccion: Cliente alternativo para redactar.
        cliente_evaluador: Cliente alternativo para revisar.
        cliente_correccion: Cliente alternativo para corregir.
        logger: Logger alternativo utilizado en pruebas.

    Returns:
        Actualización con resultados, fuentes y respuesta revisada.

    Raises:
        TypeError: Si el estado contiene tipos incorrectos.
        ValueError: Si la ruta seleccionada no necesita documentación.
        RuntimeError: Si alguna fase externa no puede completarse.
    """
    if not isinstance(estado, dict):
        raise TypeError(
            "El estado del tutor debe ser un diccionario."
        )

    accion = estado.get(
        "accion"
    )

    # Estas son las dos rutas que generan un borrador documentado.
    if accion not in {
        "responder_consulta",
        "generar_ejercicio",
    }:
        raise ValueError(
            "El estado no corresponde a una ruta documentada."
        )

    if estado.get("requiere_documentacion") is not True:
        raise ValueError(
            "La ruta documentada requiere documentación oficial."
        )

    entrada_usuario = estado.get(
        "entrada_usuario"
    )
    tecnologia = estado.get(
        "tecnologia"
    )
    consulta_documentacion = estado.get(
        "consulta_documentacion"
    )

    # Los tres campos deben ser textos no vacíos.
    campos_texto = {
        "entrada_usuario": entrada_usuario,
        "tecnologia": tecnologia,
        "consulta_documentacion": consulta_documentacion,
    }

    for nombre, valor in campos_texto.items():
        if not isinstance(valor, str):
            raise TypeError(
                f"El campo '{nombre}' debe ser texto."
            )

        if not valor.strip():
            raise ValueError(
                f"El campo '{nombre}' no puede estar vacío."
            )

    entrada_normalizada = entrada_usuario.strip()
    tecnologia_normalizada = tecnologia.strip()
    consulta_normalizada = consulta_documentacion.strip()

    logger_eventos = (
        logger
        if logger is not None
        else logging.getLogger(NOMBRE_LOGGER)
    )

    if not isinstance(logger_eventos, logging.Logger):
        raise TypeError(
            "La orquestación requiere un Logger válido."
        )

    # Ejecuta búsqueda, selección, extracción y redacción.
    resultado_investigacion = ejecutar_investigacion_completa(
        accion=accion,
        tecnologia=tecnologia_normalizada,
        peticion_usuario=entrada_normalizada,
        consulta_documentacion=consulta_normalizada,
        cliente_busqueda=cliente_busqueda,
        cliente_seleccion=cliente_seleccion,
        cliente_extraccion=cliente_extraccion,
        cliente_redaccion=cliente_redaccion,
    )

    # Valida los contratos y prepara los campos intermedios del estado.
    actualizacion_investigador = crear_actualizacion_investigador(
        resultado_investigacion
    )

    resultados_busqueda = actualizacion_investigador[
        "resultados_busqueda"
    ]
    fuentes_extraidas = actualizacion_investigador[
        "fuentes_extraidas"
    ]
    borrador = resultado_investigacion.get(
        "borrador"
    )

    # Registra contadores, nunca títulos, URLs ni contenido extraído.
    registrar_evento(
        logger_eventos,
        "busqueda_completada",
        tecnologia=tecnologia_normalizada,
        cantidad_resultados=len(resultados_busqueda),
        resultado="completada",
    )
    registrar_evento(
        logger_eventos,
        "extraccion_completada",
        tecnologia=tecnologia_normalizada,
        cantidad_fuentes=len(fuentes_extraidas),
        resultado="completada",
    )
    registrar_evento(
        logger_eventos,
        "borrador_generado",
        tecnologia=tecnologia_normalizada,
        accion=accion,
        resultado=borrador.tipo,
    )

    # Construye una copia interna con los datos obtenidos.
    estado_investigado = deepcopy(
        estado
    )
    estado_investigado.update(
        actualizacion_investigador
    )

    # El evaluador revisa el borrador y permite una corrección.
    resultado_revision = ejecutar_ciclo_revision_borrador(
        accion=accion,
        tecnologia=tecnologia_normalizada,
        peticion_usuario=entrada_normalizada,
        consulta_documentacion=consulta_normalizada,
        fuentes_extraidas=estado_investigado[
            "fuentes_extraidas"
        ],
        borrador_inicial=borrador,
        cliente_evaluador=cliente_evaluador,
        cliente_correccion=cliente_correccion,
    )

    # Oculta los borradores que no hayan superado la revisión.
    actualizacion_revision = crear_actualizacion_revision(
        resultado_revision
    )

    registrar_evento(
        logger_eventos,
        "revision_completada",
        tecnologia=tecnologia_normalizada,
        accion=accion,
        resultado=(
            "aprobada"
            if resultado_revision["aprobado"]
            else "rechazada"
        ),
        iteracion=resultado_revision[
            "iteraciones_revision"
        ],
    )

    # La revisión sustituye los campos finales del investigador.
    return {
        **actualizacion_investigador,
        **actualizacion_revision,
    }

def ejecutar_turno_manual(
    estado: object,
    cliente_coordinador: ClienteGroq | None = None,
    cliente_busqueda: ClienteBusqueda | None = None,
    cliente_seleccion: ClienteGroq | None = None,
    cliente_extraccion: ClienteExtraccion | None = None,
    cliente_redaccion: ClienteGroq | None = None,
    cliente_evaluador: ClienteGroq | None = None,
    cliente_correccion: ClienteGroq | None = None,
    directorio_progreso: str | Path | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, object]:
    """
    Ejecuta un turno completo mediante orquestación manual.

    El coordinador decide entre aclarar, investigar o evaluar.
    La función trabaja sobre una copia y no modifica el estado recibido.

    Args:
        estado: EstadoTutor preparado para el turno actual.
        cliente_coordinador: Cliente alternativo del coordinador.
        cliente_busqueda: Cliente alternativo de Tavily Search.
        cliente_seleccion: Cliente alternativo del selector.
        cliente_extraccion: Cliente alternativo de Tavily Extract.
        cliente_redaccion: Cliente alternativo del redactor.
        cliente_evaluador: Cliente alternativo del evaluador.
        cliente_correccion: Cliente alternativo del corrector.
        directorio_progreso: Ruta alternativa para el progreso.
        logger: Logger alternativo utilizado en pruebas.

    Returns:
        Copia de EstadoTutor actualizada al finalizar el turno.

    Raises:
        TypeError: Si el estado no es un diccionario.
        RuntimeError: Si aparece una acción no contemplada.
    """
    if not isinstance(estado, dict):
        raise TypeError(
            "El estado del tutor debe ser un diccionario."
        )

    # Conserva intacto el estado proporcionado por quien llama.
    estado_turno = deepcopy(
        estado
    )

    # La tecnología previa pertenece al ejercicio anterior.
    # Debe conservarse si el coordinador devuelve null al evaluar.
    tecnologia_previa = estado_turno.get(
        "tecnologia"
    )

    actualizacion_coordinador = (
        ejecutar_coordinador_desde_estado(
            estado=estado_turno,
            cliente=cliente_coordinador,
            logger=logger,
        )
    )

    estado_turno.update(
        actualizacion_coordinador
    )

    accion = estado_turno.get(
        "accion"
    )

    if accion == "pedir_aclaracion":
        # El coordinador ya ha creado respuesta_final.
        return estado_turno

    if accion in {
        "responder_consulta",
        "generar_ejercicio",
    }:
        actualizacion_documentada = (
            ejecutar_ruta_documentada_desde_estado(
                estado=estado_turno,
                cliente_busqueda=cliente_busqueda,
                cliente_seleccion=cliente_seleccion,
                cliente_extraccion=cliente_extraccion,
                cliente_redaccion=cliente_redaccion,
                cliente_evaluador=cliente_evaluador,
                cliente_correccion=cliente_correccion,
                logger=logger,
            )
        )

        estado_turno.update(
            actualizacion_documentada
        )

        return estado_turno

    if accion == "evaluar_respuesta":
        # El coordinador puede devolver tecnologia=null porque la respuesta
        # aislada no siempre menciona Python, Java o Git.
        if estado_turno.get("tecnologia") is None:
            estado_turno["tecnologia"] = tecnologia_previa

        actualizacion_evaluacion = (
            ejecutar_evaluacion_desde_estado(
                estado=estado_turno,
                cliente=cliente_evaluador,
                directorio_progreso=directorio_progreso,
                logger=logger,
            )
        )

        estado_turno.update(
            actualizacion_evaluacion
        )

        return estado_turno

    # DecisionCoordinador debería impedir esta situación.
    raise RuntimeError(
        "El coordinador produjo una acción no contemplada."
    )
