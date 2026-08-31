import logging  # Permite registrar eventos seguros desde los nodos.
from pathlib import Path  # Permite inyectar la carpeta de progreso.
from typing import Callable, Literal  # Describe rutas y funciones de nodo.

# Construye el grafo, marca su inicio y permite finalizar sus rutas.
from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from nivel_experto.tutor_multiagente.agentes.esquemas import (
    BorradorTutor,
    RevisionBorrador,
)
from nivel_experto.tutor_multiagente.config import (
    MAX_REVISIONES_BORRADOR,
)
from nivel_experto.tutor_multiagente.estado import (
    EstadoTutor,
)

# Contrato común de los clientes de Groq.
from nivel_experto.tutor_multiagente.agentes.cliente_groq import (
    ClienteGroq,
)

# Ejecuta el coordinador reutilizando la versión manual probada.
from nivel_experto.tutor_multiagente.orquestacion.manual import (
    ejecutar_coordinador_desde_estado,
)

# Convierte el resultado interno de la revisión en campos públicos
# y seguros para el estado compartido del tutor.
from nivel_experto.tutor_multiagente.orquestacion.revision import (
    crear_actualizacion_revision,
)

# Evalúa una respuesta y guarda su progreso reutilizando
# la misma implementación probada por la versión manual.
from nivel_experto.tutor_multiagente.orquestacion.evaluacion import (
    ejecutar_evaluacion_desde_estado,
)

# Ejecuta las cuatro fases internas del tutor-investigador.
from nivel_experto.tutor_multiagente.agentes.tutor_investigador import (
    crear_actualizacion_investigador,
    ejecutar_correccion_borrador,
    ejecutar_investigacion_completa,
)

# El tercer agente revisa el borrador actual.
from nivel_experto.tutor_multiagente.agentes.evaluador import (
    ejecutar_revision_borrador,
)

# Contratos de los clientes utilizados por Tavily.
from nivel_experto.tutor_multiagente.herramientas.busqueda import (
    ClienteBusqueda,
)
from nivel_experto.tutor_multiagente.herramientas.extraccion import (
    ClienteExtraccion,
)

# Registra solamente contadores y decisiones permitidas.
from nivel_experto.tutor_multiagente.logging_config import (
    NOMBRE_LOGGER,
    registrar_evento,
)


class EstadoGrafoTutor(EstadoTutor, total=False):
    """
    Amplía EstadoTutor con valores internos del grafo.

    Borrador y revisión se mantienen como modelos Pydantic mientras
    circulan entre nodos. No forman parte de la respuesta visible.
    """

    # Versión validada que está revisando el evaluador.
    borrador_actual: BorradorTutor

    # Última revisión estructurada producida por el evaluador.
    revision_actual: RevisionBorrador

def _seleccionar_logger(
    logger: logging.Logger | None,
) -> logging.Logger:
    """
    Recupera el logger proporcionado o el logger central.

    Args:
        logger: Logger opcional inyectado al construir el grafo.

    Returns:
        Logger válido para registrar eventos.

    Raises:
        TypeError: Si el objeto proporcionado no es un Logger.
    """
    logger_seleccionado = (
        logger
        if logger is not None
        else logging.getLogger(NOMBRE_LOGGER)
    )

    if not isinstance(
        logger_seleccionado,
        logging.Logger,
    ):
        raise TypeError(
            "El grafo requiere un Logger válido."
        )

    return logger_seleccionado

def crear_nodo_coordinador(
    cliente: ClienteGroq | None = None,
    logger: logging.Logger | None = None,
) -> Callable[
    [EstadoGrafoTutor],
    dict[str, object],
]:
    """
    Construye el nodo coordinador con dependencias inyectadas.

    Args:
        cliente: Cliente real o simulado de Groq.
        logger: Logger real o simulado.

    Returns:
        Función compatible con un nodo de LangGraph.
    """
    logger_nodo = _seleccionar_logger(
        logger
    )

    def nodo_coordinador(
        estado: EstadoGrafoTutor,
    ) -> dict[str, object]:
        """
        Clasifica el turno y devuelve solamente su actualización.
        """
        return ejecutar_coordinador_desde_estado(
            estado=estado,
            cliente=cliente,
            logger=logger_nodo,
        )

    return nodo_coordinador

def crear_nodo_investigador(
    cliente_busqueda: ClienteBusqueda | None = None,
    cliente_seleccion: ClienteGroq | None = None,
    cliente_extraccion: ClienteExtraccion | None = None,
    cliente_redaccion: ClienteGroq | None = None,
    logger: logging.Logger | None = None,
) -> Callable[
    [EstadoGrafoTutor],
    dict[str, object],
]:
    """
    Construye el nodo que investiga y redacta el primer borrador.

    El nodo ejecuta búsqueda, selección, extracción y redacción.
    La revisión se mantiene fuera para que el ciclo sea visible
    dentro del grafo.

    Returns:
        Función compatible con un nodo de LangGraph.
    """
    logger_nodo = _seleccionar_logger(
        logger
    )

    def nodo_investigador(
        estado: EstadoGrafoTutor,
    ) -> dict[str, object]:
        """
        Produce un borrador y lo incorpora al estado interno.
        """
        if not isinstance(estado, dict):
            raise TypeError(
                "El estado del grafo debe ser un diccionario."
            )

        accion = estado.get(
            "accion"
        )
        tecnologia = estado.get(
            "tecnologia"
        )
        entrada_usuario = estado.get(
            "entrada_usuario"
        )
        consulta_documentacion = estado.get(
            "consulta_documentacion"
        )

        # Las funciones internas vuelven a validar estos valores.
        resultado = ejecutar_investigacion_completa(
            accion=accion,
            tecnologia=tecnologia,
            peticion_usuario=entrada_usuario,
            consulta_documentacion=consulta_documentacion,
            cliente_busqueda=cliente_busqueda,
            cliente_seleccion=cliente_seleccion,
            cliente_extraccion=cliente_extraccion,
            cliente_redaccion=cliente_redaccion,
        )

        # Comprueba fuentes, citas y contratos de las herramientas.
        actualizacion = crear_actualizacion_investigador(
            resultado
        )

        borrador = resultado.get(
            "borrador"
        )

        if not isinstance(borrador, BorradorTutor):
            raise RuntimeError(
                "La investigación no produjo un borrador validado."
            )

        resultados_busqueda = actualizacion[
            "resultados_busqueda"
        ]
        fuentes_extraidas = actualizacion[
            "fuentes_extraidas"
        ]

        # Registra únicamente cantidades y decisiones técnicas.
        registrar_evento(
            logger_nodo,
            "busqueda_completada",
            tecnologia=tecnologia,
            cantidad_resultados=len(resultados_busqueda),
            resultado="completada",
        )
        registrar_evento(
            logger_nodo,
            "extraccion_completada",
            tecnologia=tecnologia,
            cantidad_fuentes=len(fuentes_extraidas),
            resultado="completada",
        )
        registrar_evento(
            logger_nodo,
            "borrador_generado",
            tecnologia=tecnologia,
            accion=accion,
            resultado=borrador.tipo,
        )

        return {
            **actualizacion,

            # El modelo Pydantic circula entre nodos internos.
            "borrador_actual": borrador,

            # La primera revisión todavía no se ha ejecutado.
            "iteraciones_revision": 0,
        }

    return nodo_investigador

def crear_nodo_revision(
    cliente: ClienteGroq | None = None,
    logger: logging.Logger | None = None,
) -> Callable[
    [EstadoGrafoTutor],
    dict[str, object],
]:
    """
    Construye el nodo que revisa el borrador actual.

    El contador se incrementa aquí porque cada ejecución del nodo
    representa una revisión real del evaluador.
    """
    logger_nodo = _seleccionar_logger(
        logger
    )

    def nodo_revision(
        estado: EstadoGrafoTutor,
    ) -> dict[str, object]:
        """
        Revisa el borrador y actualiza la iteración del grafo.
        """
        if not isinstance(estado, dict):
            raise TypeError(
                "El estado del grafo debe ser un diccionario."
            )

        borrador = estado.get(
            "borrador_actual"
        )

        if not isinstance(borrador, BorradorTutor):
            raise RuntimeError(
                "El nodo de revisión requiere un borrador validado."
            )

        iteraciones_anteriores = estado.get(
            "iteraciones_revision",
            0,
        )

        if (
            isinstance(iteraciones_anteriores, bool)
            or not isinstance(iteraciones_anteriores, int)
            or iteraciones_anteriores < 0
            or iteraciones_anteriores >= MAX_REVISIONES_BORRADOR
        ):
            raise RuntimeError(
                "El contador anterior de revisiones no es válido."
            )

        revision = ejecutar_revision_borrador(
            borrador=borrador,
            peticion_usuario=estado.get(
                "entrada_usuario"
            ),
            fuentes_extraidas=estado.get(
                "fuentes_extraidas"
            ),
            cliente=cliente,
        )

        nueva_iteracion = (
            iteraciones_anteriores + 1
        )

        registrar_evento(
            logger_nodo,
            "revision_completada",
            tecnologia=estado.get("tecnologia"),
            accion=estado.get("accion"),
            resultado=(
                "aprobada"
                if revision.aprobado
                else "rechazada"
            ),
            iteracion=nueva_iteracion,
        )

        return {
            # Modelo validado utilizado por el enrutador condicional.
            "revision_actual": revision,

            # Cada entrada en este nodo equivale a una revisión.
            "iteraciones_revision": nueva_iteracion,
        }

    return nodo_revision

def crear_nodo_correccion(
    cliente: ClienteGroq | None = None,
    logger: logging.Logger | None = None,
) -> Callable[
    [EstadoGrafoTutor],
    dict[str, object],
]:
    """
    Construye el nodo que corrige un borrador rechazado.

    No modifica el contador: la siguiente ejecución del evaluador
    será la que registre la segunda revisión.
    """
    logger_nodo = _seleccionar_logger(
        logger
    )

    def nodo_correccion(
        estado: EstadoGrafoTutor,
    ) -> dict[str, object]:
        """
        Produce una versión corregida y conserva su modelo validado.
        """
        if not isinstance(estado, dict):
            raise TypeError(
                "El estado del grafo debe ser un diccionario."
            )

        borrador_anterior = estado.get(
            "borrador_actual"
        )
        revision = estado.get(
            "revision_actual"
        )

        if not isinstance(
            borrador_anterior,
            BorradorTutor,
        ):
            raise RuntimeError(
                "La corrección requiere un borrador validado."
            )

        if not isinstance(
            revision,
            RevisionBorrador,
        ):
            raise RuntimeError(
                "La corrección requiere una revisión validada."
            )

        # Una aprobación nunca debe entrar en el nodo corrector.
        if revision.aprobado:
            raise RuntimeError(
                "No se puede corregir un borrador aprobado."
            )

        iteraciones = estado.get(
            "iteraciones_revision"
        )

        if (
            isinstance(iteraciones, bool)
            or not isinstance(iteraciones, int)
            or iteraciones < 1
            or iteraciones >= MAX_REVISIONES_BORRADOR
        ):
            raise RuntimeError(
                "La corrección no está permitida en esta iteración."
            )

        borrador_corregido = ejecutar_correccion_borrador(
            accion=estado.get("accion"),
            tecnologia=estado.get("tecnologia"),
            peticion_usuario=estado.get(
                "entrada_usuario"
            ),
            consulta_documentacion=estado.get(
                "consulta_documentacion"
            ),
            fuentes_extraidas=estado.get(
                "fuentes_extraidas"
            ),
            borrador_anterior=borrador_anterior,
            revision=revision,
            cliente=cliente,
        )

        respuesta_borrador = (
            f"# {borrador_corregido.titulo}\n\n"
            f"{borrador_corregido.contenido_markdown}"
        )

        ejercicio_actual = (
            borrador_corregido.model_dump()
            if borrador_corregido.tipo == "ejercicio"
            else None
        )

        registrar_evento(
            logger_nodo,
            "borrador_generado",
            tecnologia=estado.get("tecnologia"),
            accion=estado.get("accion"),
            resultado="corregido",
        )

        return {
            "borrador_actual": borrador_corregido,
            "respuesta_borrador": respuesta_borrador,
            "ejercicio_actual": ejercicio_actual,
        }

    return nodo_correccion

def crear_nodo_finalizacion_revision() -> Callable[
    [EstadoGrafoTutor],
    dict[str, object],
]:
    """
    Construye el nodo que cierra el ciclo de revisión.

    Convierte los modelos internos del grafo en una actualización
    pública y segura para EstadoTutor.
    """

    def nodo_finalizacion_revision(
        estado: EstadoGrafoTutor,
    ) -> dict[str, object]:
        """
        Publica el borrador aprobado u oculta el rechazado.
        """
        # El estado compartido siempre debe ser un diccionario.
        if not isinstance(estado, dict):
            raise TypeError(
                "El estado del grafo debe ser un diccionario."
            )

        # Recupera los objetos internos producidos por los nodos anteriores.
        borrador = estado.get(
            "borrador_actual"
        )
        revision = estado.get(
            "revision_actual"
        )
        iteraciones = estado.get(
            "iteraciones_revision"
        )

        # Impide finalizar utilizando un borrador sin validar.
        if not isinstance(borrador, BorradorTutor):
            raise RuntimeError(
                "La finalización requiere un borrador validado."
            )

        # Impide confiar directamente en un diccionario externo.
        if not isinstance(revision, RevisionBorrador):
            raise RuntimeError(
                "La finalización requiere una revisión validada."
            )

        # Valida el contador antes de calcular las correcciones.
        if (
            isinstance(iteraciones, bool)
            or not isinstance(iteraciones, int)
            or iteraciones < 1
            or iteraciones > MAX_REVISIONES_BORRADOR
        ):
            raise RuntimeError(
                "El contador de revisiones no es válido."
            )

        # La primera revisión no tiene corrección previa.
        # La segunda revisión implica que se realizó una corrección.
        correcciones_realizadas = (
            iteraciones - 1
        )

        # Reconstruye el mismo contrato utilizado por la
        # orquestación manual para reutilizar su validación.
        resultado_ciclo = {
            "aprobado": revision.aprobado,
            "borrador": borrador,
            "revision": revision,
            "iteraciones_revision": iteraciones,
            "correcciones_realizadas": correcciones_realizadas,
        }

        # Genera respuesta_final, evaluación, errores y ejercicio_actual.
        return crear_actualizacion_revision(
            resultado_ciclo
        )

    return nodo_finalizacion_revision

def crear_nodo_evaluacion(
    cliente: ClienteGroq | None = None,
    directorio_progreso: str | Path | None = None,
    logger: logging.Logger | None = None,
) -> Callable[
    [EstadoGrafoTutor],
    dict[str, object],
]:
    """
    Construye el nodo que evalúa la respuesta a un ejercicio.

    Las dependencias se reciben al construir el nodo para facilitar
    las pruebas y evitar crear clientes externos innecesariamente.
    """
    # Selecciona y valida el logger una sola vez.
    logger_nodo = _seleccionar_logger(
        logger
    )

    def nodo_evaluacion(
        estado: EstadoGrafoTutor,
    ) -> dict[str, object]:
        """
        Evalúa la respuesta y devuelve la actualización del estado.
        """
        # Reutiliza toda la orquestación manual ya probada:
        # evaluación, formato de respuesta, progreso y logging.
        return ejecutar_evaluacion_desde_estado(
            estado=estado,
            cliente=cliente,
            directorio_progreso=directorio_progreso,
            logger=logger_nodo,
        )

    return nodo_evaluacion

def enrutar_despues_coordinador(
    estado: object,
) -> Literal[
    "investigar",
    "evaluar",
    "finalizar",
]:
    """
    Selecciona la siguiente fase después del coordinador.

    Args:
        estado: Estado actualizado por el nodo coordinador.

    Returns:
        Nombre lógico de la siguiente ruta.

    Raises:
        TypeError: Si el estado no es un diccionario.
        RuntimeError: Si la acción no está contemplada.
    """
    if not isinstance(estado, dict):
        raise TypeError(
            "El estado del grafo debe ser un diccionario."
        )

    accion = estado.get(
        "accion"
    )

    if accion in {
        "responder_consulta",
        "generar_ejercicio",
    }:
        return "investigar"

    if accion == "evaluar_respuesta":
        return "evaluar"

    if accion == "pedir_aclaracion":
        return "finalizar"

    # DecisionCoordinador debería impedir este caso.
    raise RuntimeError(
        "El coordinador produjo una acción no contemplada."
    )


def enrutar_despues_revision(
    estado: object,
) -> Literal[
    "corregir",
    "finalizar",
]:
    """
    Decide si el borrador vuelve al tutor o termina el grafo.

    Args:
        estado: Estado con revisión e iteración actuales.

    Returns:
        corregir si queda un intento o finalizar en cualquier otro caso.

    Raises:
        TypeError: Si el estado no es un diccionario.
        RuntimeError: Si faltan revisión o contador válidos.
    """
    if not isinstance(estado, dict):
        raise TypeError(
            "El estado del grafo debe ser un diccionario."
        )

    revision = estado.get(
        "revision_actual"
    )

    if not isinstance(revision, RevisionBorrador):
        raise RuntimeError(
            "El estado no contiene una revisión validada."
        )

    iteraciones = estado.get(
        "iteraciones_revision"
    )

    # bool debe rechazarse porque es una subclase de int.
    if (
        isinstance(iteraciones, bool)
        or not isinstance(iteraciones, int)
        or iteraciones < 1
        or iteraciones > MAX_REVISIONES_BORRADOR
    ):
        raise RuntimeError(
            "El contador de revisiones del grafo no es válido."
        )

    # Un borrador aprobado puede mostrarse inmediatamente.
    if revision.aprobado:
        return "finalizar"

    # Un rechazo en la última revisión termina sin otra corrección.
    if iteraciones >= MAX_REVISIONES_BORRADOR:
        return "finalizar"

    # Solo queda esta ruta: primera revisión rechazada.
    return "corregir"

def crear_grafo_tutor(
    cliente_coordinador: ClienteGroq | None = None,
    cliente_busqueda: ClienteBusqueda | None = None,
    cliente_seleccion: ClienteGroq | None = None,
    cliente_extraccion: ClienteExtraccion | None = None,
    cliente_redaccion: ClienteGroq | None = None,
    cliente_revision: ClienteGroq | None = None,
    cliente_correccion: ClienteGroq | None = None,
    cliente_evaluacion: ClienteGroq | None = None,
    directorio_progreso: str | Path | None = None,
    logger: logging.Logger | None = None,
):
    """
    Construye y compila el grafo completo del tutor.

    Cada cliente puede inyectarse por separado para facilitar las
    pruebas. Si se recibe None, los componentes crearán sus clientes
    reales cuando necesiten realizar una llamada externa.
    """
    # Valida una sola vez el logger compartido por todos los nodos.
    logger_grafo = _seleccionar_logger(
        logger
    )

    # Define el tipo de estado que circulará entre los nodos.
    constructor = StateGraph(
        EstadoGrafoTutor
    )

    # El coordinador analiza la intención del estudiante.
    constructor.add_node(
        "coordinador",
        crear_nodo_coordinador(
            cliente=cliente_coordinador,
            logger=logger_grafo,
        ),
    )

    # El investigador busca, selecciona y extrae documentación,
    # y después redacta el primer borrador.
    constructor.add_node(
        "investigador",
        crear_nodo_investigador(
            cliente_busqueda=cliente_busqueda,
            cliente_seleccion=cliente_seleccion,
            cliente_extraccion=cliente_extraccion,
            cliente_redaccion=cliente_redaccion,
            logger=logger_grafo,
        ),
    )

    # El evaluador revisa el borrador utilizando las fuentes.
    constructor.add_node(
        "revision",
        crear_nodo_revision(
            cliente=cliente_revision,
            logger=logger_grafo,
        ),
    )

    # El tutor-investigador corrige un primer rechazo.
    constructor.add_node(
        "correccion",
        crear_nodo_correccion(
            cliente=cliente_correccion,
            logger=logger_grafo,
        ),
    )

    # Convierte la revisión en una respuesta pública segura.
    constructor.add_node(
        "finalizacion_revision",
        crear_nodo_finalizacion_revision(),
    )

    # Evalúa la solución de un ejercicio activo.
    constructor.add_node(
        "evaluacion",
        crear_nodo_evaluacion(
            cliente=cliente_evaluacion,
            directorio_progreso=directorio_progreso,
            logger=logger_grafo,
        ),
    )

    # Todos los turnos comienzan en el coordinador.
    constructor.add_edge(
        START,
        "coordinador",
    )

    # La decisión del coordinador abre tres rutas posibles.
    constructor.add_conditional_edges(
        "coordinador",
        enrutar_despues_coordinador,
        {
            # Consultas y ejercicios necesitan documentación.
            "investigar": "investigador",

            # Una solución utiliza el ejercicio que ya está activo.
            "evaluar": "evaluacion",

            # Una aclaración ya contiene su respuesta final.
            "finalizar": END,
        },
    )

    constructor.add_edge(
        "investigador",
        "revision",
    )

    # La revisión decide si corregir o cerrar el ciclo.
    constructor.add_conditional_edges(
        "revision",
        enrutar_despues_revision,
        {
            "corregir": "correccion",
            "finalizar": "finalizacion_revision",
        },
    )

    # Esta arista crea explícitamente el bucle del grafo.
    # Después de corregir, el evaluador revisa la nueva versión.
    constructor.add_edge(
        "correccion",
        "revision",
    )

    # Una revisión finalizada termina el turno.
    constructor.add_edge(
        "finalizacion_revision",
        END,
    )

    # La evaluación de un ejercicio también termina el turno.
    constructor.add_edge(
        "evaluacion",
        END,
    )

    # Valida la estructura y devuelve el grafo ejecutable.
    return constructor.compile()
