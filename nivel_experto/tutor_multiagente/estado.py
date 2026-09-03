from typing import Literal, TypedDict
from copy import deepcopy  # Evita compartir estructuras entre turnos.

from nivel_experto.tutor_multiagente.config import (
    MAX_MENSAJES_HISTORIAL,
)

# Define las acciones que puede seleccionar el agente coordinador.
AccionTutor = Literal[
    "responder_consulta",
    "generar_ejercicio",
    "evaluar_respuesta",
    "pedir_aclaracion",
]


class MensajeHistorial(TypedDict):
    """
    Representa un mensaje conservado en el historial de conversación.
    """

    # Identifica quién produjo el mensaje.
    role: Literal["user", "assistant"]

    # Contiene el texto visible del mensaje.
    content: str


class ResultadoBusqueda(TypedDict):
    """
    Representa una página localizada mediante Tavily Search.
    """

    # Identificador interno generado por nuestra herramienta.
    id: str

    # Título de la página oficial.
    titulo: str

    # Dirección validada de la página.
    url: str

    # Fragmento breve devuelto por la búsqueda.
    resumen: str

    # Puntuación de relevancia o None si Tavily no la proporciona.
    puntuacion: float | None


class FuenteExtraida(TypedDict):
    """
    Representa el contenido extraído de una página oficial.
    """

    # Identificador interno de la fuente.
    id: str

    # Dirección oficial de la que procede el contenido.
    url: str

    # Fragmentos en formato Markdown obtenidos por Tavily Extract.
    contenido: str


class EstadoTutor(TypedDict):
    """
    Contiene la información compartida durante un turno del tutor.

    Cada agente leerá solamente los campos que necesite y actualizará
    únicamente los campos que sean responsabilidad suya.
    """

    # Conversación anterior visible para el sistema.
    historial: list[MensajeHistorial]

    # Mensaje que el usuario ha escrito en el turno actual.
    entrada_usuario: str

    # Tecnología identificada por el coordinador.
    tecnologia: str | None

    # Acción decidida por el coordinador.
    accion: AccionTutor | None

    # Consulta concreta que utilizarán las herramientas web.
    consulta_documentacion: str | None

    # Indica si hace falta consultar documentación oficial.
    requiere_documentacion: bool

    # Resultados seguros producidos por Tavily Search.
    resultados_busqueda: list[ResultadoBusqueda]

    # Fragmentos seguros obtenidos mediante Tavily Extract.
    fuentes_extraidas: list[FuenteExtraida]

    # Primera respuesta redactada por el agente tutor.
    respuesta_borrador: str | None

    # Ejercicio que el tutor haya generado durante el turno.
    ejercicio_actual: dict[str, object] | None

    # Resultado producido por el agente evaluador.
    evaluacion: dict[str, object] | None

    # Indica si la última evaluación se guardó en el historial personal.
    progreso_guardado: bool

    # Pregunta utilizada cuando falta información del usuario.
    mensaje_aclaracion: str | None

    # Respuesta que finalmente se mostrará al usuario.
    respuesta_final: str | None

    # Errores controlados encontrados durante el flujo.
    errores: list[str]

    # Número de veces que se ha revisado el borrador.
    iteraciones_revision: int


def crear_estado_inicial(entrada_usuario: object) -> EstadoTutor:
    """
    Construye un estado limpio para un nuevo turno.

    Args:
        entrada_usuario: Mensaje recibido desde la terminal.

    Returns:
        Estado completo con valores iniciales seguros.

    Raises:
        TypeError: Si la entrada no es una cadena.
        ValueError: Si la entrada está vacía.
    """
    # La entrada podría proceder posteriormente de otra interfaz.
    if not isinstance(entrada_usuario, str):
        raise TypeError("La entrada del usuario debe ser una cadena de texto.")

    # Elimina espacios accidentales en los extremos.
    entrada_normalizada = entrada_usuario.strip()

    # Impide iniciar un flujo sin una petición real.
    if not entrada_normalizada:
        raise ValueError("La entrada del usuario no puede estar vacía.")

    # Todos los campos se crean explícitamente para evitar estados incompletos.
    return {
        "historial": [],
        "entrada_usuario": entrada_normalizada,
        "tecnologia": None,
        "accion": None,
        "consulta_documentacion": None,
        "requiere_documentacion": False,
        "resultados_busqueda": [],
        "fuentes_extraidas": [],
        "respuesta_borrador": None,
        "ejercicio_actual": None,
        "evaluacion": None,
        "progreso_guardado": False,
        "mensaje_aclaracion": None,
        "respuesta_final": None,
        "errores": [],
        "iteraciones_revision": 0,
    }

def crear_estado_siguiente_turno(
    entrada_usuario: object,
    estado_anterior: object,
) -> EstadoTutor:
    """
    Construye un turno nuevo conservando contexto seguro del anterior.

    Conserva el historial visible y, si existe, el ejercicio con sus
    fuentes. Reinicia decisiones, borradores, evaluación y errores.

    Args:
        entrada_usuario: Nuevo mensaje escrito por el estudiante.
        estado_anterior: Estado completo del turno ya finalizado.

    Returns:
        EstadoTutor limpio con el contexto necesario.

    Raises:
        TypeError: Si el estado o sus campos tienen tipos incorrectos.
        ValueError: Si el turno anterior todavía no tiene respuesta final.
    """
    if not isinstance(estado_anterior, dict):
        raise TypeError(
            "El estado anterior debe ser un diccionario."
        )

    # Reutiliza la validación de la entrada del primer turno.
    nuevo_estado = crear_estado_inicial(
        entrada_usuario
    )

    historial_anterior = estado_anterior.get(
        "historial"
    )

    if not isinstance(historial_anterior, list):
        raise TypeError(
            "El historial anterior debe ser una lista."
        )

    historial_validado = []

    for mensaje in historial_anterior:
        if not isinstance(mensaje, dict):
            raise TypeError(
                "Cada mensaje del historial debe ser un diccionario."
            )

        if set(mensaje) != {"role", "content"}:
            raise ValueError(
                "Un mensaje del historial contiene "
                "campos ausentes o inesperados."
            )

        role = mensaje["role"]
        content = mensaje["content"]

        if role not in {"user", "assistant"}:
            raise ValueError(
                "El rol del historial no está permitido."
            )

        if not isinstance(content, str):
            raise TypeError(
                "El contenido del historial debe ser texto."
            )

        contenido_normalizado = content.strip()

        if not contenido_normalizado:
            raise ValueError(
                "El contenido del historial no puede estar vacío."
            )

        historial_validado.append(
            {
                "role": role,
                "content": contenido_normalizado,
            }
        )

    entrada_anterior = estado_anterior.get(
        "entrada_usuario"
    )
    respuesta_anterior = estado_anterior.get(
        "respuesta_final"
    )

    if not isinstance(entrada_anterior, str):
        raise TypeError(
            "La entrada del turno anterior debe ser texto."
        )

    entrada_anterior_normalizada = (
        entrada_anterior.strip()
    )

    if not entrada_anterior_normalizada:
        raise ValueError(
            "La entrada del turno anterior no puede estar vacía."
        )

    # Solo un turno terminado puede incorporarse al historial.
    if not isinstance(respuesta_anterior, str):
        raise ValueError(
            "El turno anterior no contiene una respuesta final."
        )

    respuesta_anterior_normalizada = (
        respuesta_anterior.strip()
    )

    if not respuesta_anterior_normalizada:
        raise ValueError(
            "La respuesta final anterior no puede estar vacía."
        )

    historial_actualizado = [
        *historial_validado,
        {
            "role": "user",
            "content": entrada_anterior_normalizada,
        },
        {
            "role": "assistant",
            "content": respuesta_anterior_normalizada,
        },
    ]

    # Conserva solo los mensajes más recientes.
    nuevo_estado["historial"] = deepcopy(
        historial_actualizado[
            -MAX_MENSAJES_HISTORIAL:
        ]
    )

    tecnologia_anterior = estado_anterior.get(
        "tecnologia"
    )

    # Conserva la tecnología como contexto para preguntas de seguimiento.
    if tecnologia_anterior is not None:
        if not isinstance(tecnologia_anterior, str):
            raise TypeError(
                "La tecnología anterior debe ser texto o null."
            )

        nuevo_estado["tecnologia"] = (
            tecnologia_anterior.strip()
        )

    ejercicio_anterior = estado_anterior.get(
        "ejercicio_actual"
    )

    if ejercicio_anterior is not None:
        if not isinstance(ejercicio_anterior, dict):
            raise TypeError(
                "El ejercicio anterior debe ser un diccionario o null."
            )

        fuentes_anteriores = estado_anterior.get(
            "fuentes_extraidas"
        )

        if not isinstance(fuentes_anteriores, list):
            raise TypeError(
                "Las fuentes anteriores deben ser una lista."
            )

        if not fuentes_anteriores:
            raise ValueError(
                "Un ejercicio activo debe conservar sus fuentes."
            )

        # La solución privada se conserva en estado, no en el historial.
        nuevo_estado["ejercicio_actual"] = deepcopy(
            ejercicio_anterior
        )
        nuevo_estado["fuentes_extraidas"] = deepcopy(
            fuentes_anteriores
        )

    return nuevo_estado
