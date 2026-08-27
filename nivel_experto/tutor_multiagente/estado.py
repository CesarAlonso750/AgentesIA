from typing import Literal, TypedDict


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
        "mensaje_aclaracion": None,
        "respuesta_final": None,
        "errores": [],
        "iteraciones_revision": 0,
    }