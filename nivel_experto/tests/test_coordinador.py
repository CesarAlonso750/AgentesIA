import pytest  # Permite comprobar y parametrizar excepciones.

from copy import deepcopy  # Evita que los mensajes guardados cambien después.
from pydantic import ValidationError  # Error de datos estructurados inválidos.
from types import SimpleNamespace  # Crea objetos sencillos con atributos.

from nivel_experto.tutor_multiagente.agentes import (
    coordinador as modulo_coordinador,
)
from nivel_experto.tutor_multiagente.agentes.coordinador import (
    construir_prompt_coordinador,
    crear_actualizacion_coordinador,
    ejecutar_coordinador,
    interpretar_decision_coordinador,
)
from nivel_experto.tutor_multiagente.agentes.cliente_groq import (
    obtener_contenido_respuesta,
)
from nivel_experto.tutor_multiagente.agentes.esquemas import (
    DecisionCoordinador,
)

class CompletionsSimuladas:
    """
    Simula el método cliente.chat.completions.create de Groq.
    """

    def __init__(
        self,
        respuesta=None,
        error=None,
        respuestas=None,
    ):
        # Guarda una respuesta fija para los tests de una sola llamada.
        self.respuesta = respuesta

        # Permite preparar varias respuestas consecutivas.
        self.respuestas = (
            list(respuestas)
            if respuestas is not None
            else None
        )

        # Guarda una posible excepción externa simulada.
        self.error = error

        # Permite inspeccionar las llamadas recibidas.
        self.parametros_recibidos = None
        self.historial_parametros = []
        self.numero_llamadas = 0

    def create(self, **parametros):
        """Imita la creación de una respuesta de chat."""
        self.numero_llamadas += 1

        # Copia los parámetros para que las listas no cambien posteriormente.
        parametros_copiados = deepcopy(parametros)
        self.parametros_recibidos = parametros_copiados
        self.historial_parametros.append(parametros_copiados)

        # Simula errores externos cuando la prueba lo solicita.
        if self.error is not None:
            raise self.error

        # Devuelve respuestas diferentes en llamadas sucesivas.
        if self.respuestas is not None:
            indice_respuesta = self.numero_llamadas - 1

            if indice_respuesta >= len(self.respuestas):
                raise AssertionError(
                    "El cliente simulado no tiene más respuestas."
                )

            return self.respuestas[indice_respuesta]

        # Mantiene compatibilidad con los tests de una sola respuesta.
        return self.respuesta


class ClienteCoordinadorSimulado:
    """
    Reproduce la estructura mínima del cliente oficial de Groq.
    """

    def __init__(
        self,
        respuesta=None,
        error=None,
        respuestas=None,
    ):
        # Crea el componente que recibirá las llamadas simuladas.
        self.completions = CompletionsSimuladas(
            respuesta=respuesta,
            error=error,
            respuestas=respuestas,
        )

        # Reproduce cliente.chat.completions.
        self.chat = SimpleNamespace(
            completions=self.completions,
        )

def test_construir_prompt_coordinador_incluye_catalogo_y_acciones():
    """Comprueba que el prompt incluya fuentes y acciones permitidas."""
    prompt = construir_prompt_coordinador()

    # Las tecnologías deben proceder del catálogo oficial.
    assert "- python: Python" in prompt
    assert "- java: Java" in prompt
    assert "- git: Git" in prompt

    # El coordinador debe conocer las cuatro rutas posibles.
    assert "responder_consulta" in prompt
    assert "generar_ejercicio" in prompt
    assert "evaluar_respuesta" in prompt
    assert "pedir_aclaracion" in prompt

    # Debe quedar explícito que no responde directamente al estudiante.
    assert "No debes responder la pregunta técnica" in prompt

    # Normaliza saltos de línea y espacios repetidos antes de buscar frases.
    prompt_normalizado = " ".join(prompt.split())

    assert "debe describir los conceptos técnicos" in prompt_normalizado
    assert "no debe pedir al buscador" in prompt_normalizado

    # El coordinador recibe contexto mínimo para reconocer soluciones.
    assert "hay_ejercicio_activo" in prompt
    assert "tecnologia_contexto" in prompt

    # La frase ocupa varias líneas dentro del prompt.
    assert "contenido no confiable" in prompt_normalizado

        # Una tecnología externa reconocible debe producir una
    # explicación del alcance, no una aclaración innecesaria.
    assert (
        "tecnología reconocible que no está registrada"
        in prompt_normalizado
    )
    assert (
        "esa tecnología no está disponible"
        in prompt_normalizado
    )
    assert (
        "ofrecer las tecnologías registradas como alternativas"
        in prompt_normalizado
    )
    # Las búsquedas usan el idioma más habitual de la documentación oficial.
    assert "consulta_documentacion en inglés" in prompt_normalizado
    assert "mensajes visibles" in prompt_normalizado
    assert "respondiendo al estudiante en español" in prompt_normalizado

        # Las consultas sin versión deben buscar el comportamiento vigente.
    assert "comportamiento actual" in prompt_normalizado
    assert "current o latest" in prompt_normalizado

    # Una versión solicitada expresamente debe conservarse.
    assert "conserva esa versión" in prompt_normalizado
    assert (
        "no la sustituyas por la versión más reciente"
        in prompt_normalizado
    )

def test_interpretar_decision_coordinador_acepta_json_textual():
    """Comprueba el formato que utilizará la implementación manual."""
    respuesta_json = """
    {
        "accion": "responder_consulta",
        "tecnologia": "python",
        "consulta_documentacion": "listas por comprensión",
        "requiere_documentacion": true,
        "mensaje_aclaracion": null
    }
    """

    decision = interpretar_decision_coordinador(respuesta_json)

    assert isinstance(decision, DecisionCoordinador)
    assert decision.accion == "responder_consulta"
    assert decision.tecnologia == "python"
    assert decision.consulta_documentacion == (
        "listas por comprensión"
    )


def test_interpretar_decision_coordinador_acepta_diccionario():
    """Comprueba el formato utilizado por tests y adaptadores internos."""
    respuesta = {
        "accion": "pedir_aclaracion",
        "tecnologia": None,
        "consulta_documentacion": None,
        "requiere_documentacion": False,
        "mensaje_aclaracion": "¿Qué tecnología quieres estudiar?",
    }

    decision = interpretar_decision_coordinador(respuesta)

    assert isinstance(decision, DecisionCoordinador)
    assert decision.accion == "pedir_aclaracion"
    assert decision.mensaje_aclaracion == (
        "¿Qué tecnología quieres estudiar?"
    )


def test_interpretar_decision_coordinador_acepta_modelo_pydantic():
    """Comprueba el formato que podrá devolver LangChain."""
    respuesta = DecisionCoordinador(
        accion="evaluar_respuesta",
        tecnologia="python",
        consulta_documentacion=None,
        requiere_documentacion=False,
        mensaje_aclaracion=None,
    )

    decision = interpretar_decision_coordinador(respuesta)

    # Si ya está validado, debe reutilizar exactamente el mismo objeto.
    assert decision is respuesta


def test_interpretar_decision_coordinador_rechaza_texto_vacio():
    """Comprueba que una respuesta vacía del modelo produzca un error."""
    with pytest.raises(
        ValueError,
        match="no puede estar vacía",
    ):
        interpretar_decision_coordinador("   ")


def test_interpretar_decision_coordinador_rechaza_json_mal_formado():
    """Comprueba que un texto que no sea JSON no pueda continuar."""
    with pytest.raises(ValidationError):
        interpretar_decision_coordinador(
            "esto no es un objeto JSON"
        )


def test_interpretar_decision_coordinador_rechaza_json_incoherente():
    """Comprueba que el JSON también deba cumplir las reglas del esquema."""
    respuesta_json = """
    {
        "accion": "responder_consulta",
        "tecnologia": "python",
        "consulta_documentacion": null,
        "requiere_documentacion": false,
        "mensaje_aclaracion": null
    }
    """

    with pytest.raises(ValidationError):
        interpretar_decision_coordinador(respuesta_json)


@pytest.mark.parametrize(
    "respuesta",
    [
        None,
        True,
        25,
        ["decision"],
    ],
)
def test_interpretar_decision_coordinador_rechaza_tipos_incorrectos(
    respuesta,
):
    """Comprueba que solo se acepten los tres formatos previstos."""
    with pytest.raises(
        TypeError,
        match="debe ser JSON, un diccionario",
    ):
        interpretar_decision_coordinador(respuesta)

def test_ejecutar_coordinador_envia_parametros_y_valida_respuesta():
    """Comprueba el ciclo completo utilizando un cliente simulado."""
    contenido_json = """
    {
        "accion": "responder_consulta",
        "tecnologia": "python",
        "consulta_documentacion": "diferencia entre append y extend",
        "requiere_documentacion": true,
        "mensaje_aclaracion": null
    }
    """

    # Reproduce respuesta.choices[0].message.content.
    respuesta_simulada = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=contenido_json,
                )
            )
        ]
    )

    cliente = ClienteCoordinadorSimulado(
        respuesta=respuesta_simulada,
    )

    decision = ejecutar_coordinador(
        "  ¿Qué diferencia hay entre append y extend en Python?  ",
        cliente=cliente,
    )

    # Comprueba la decisión final validada mediante Pydantic.
    assert decision.accion == "responder_consulta"
    assert decision.tecnologia == "python"
    assert decision.consulta_documentacion == (
        "diferencia entre append y extend"
    )
    assert decision.requiere_documentacion is True
    assert decision.mensaje_aclaracion is None

    # Debe realizarse exactamente una llamada al cliente simulado.
    assert cliente.completions.numero_llamadas == 1

    parametros = cliente.completions.parametros_recibidos

    # Comprueba la configuración general de Groq.
    assert parametros["model"] == "openai/gpt-oss-20b"
    assert parametros["reasoning_effort"] == "low"
    assert parametros["temperature"] == 0
    assert parametros["max_completion_tokens"] == 1_000
    assert parametros["stream"] is False
    assert parametros["timeout"] == 30

    # Comprueba la separación entre instrucciones y entrada no confiable.
    assert parametros["messages"][0]["role"] == "system"
    assert "agente coordinador" in parametros["messages"][0]["content"]
    assert parametros["messages"][1] == {
        "role": "user",
        "content": (
            "¿Qué diferencia hay entre append y extend en Python?"
        ),
    }

    # Comprueba que Groq reciba el JSON Schema en modo estricto.
    formato = parametros["response_format"]

    assert formato["type"] == "json_schema"
    assert formato["json_schema"]["name"] == "decision_coordinador"
    assert formato["json_schema"]["strict"] is True
    assert formato["json_schema"]["schema"]["additionalProperties"] is False
    assert set(formato["json_schema"]["schema"]["required"]) == {
        "accion",
        "tecnologia",
        "consulta_documentacion",
        "requiere_documentacion",
        "mensaje_aclaracion",
    }

@pytest.mark.parametrize(
    "respuesta",
    [
        None,
        SimpleNamespace(),
        SimpleNamespace(choices=[]),
        SimpleNamespace(choices="formato incorrecto"),
    ],
)
def test_obtener_contenido_rechaza_respuesta_sin_alternativas(
    respuesta,
):
    """Comprueba respuestas que no contienen una lista choices válida."""
    with pytest.raises(
        RuntimeError,
        match="sin alternativas",
    ):
        obtener_contenido_respuesta(respuesta)


def test_obtener_contenido_rechaza_alternativa_sin_mensaje():
    """Comprueba una alternativa que no contiene el atributo message."""
    respuesta = SimpleNamespace(
        choices=[
            SimpleNamespace(),
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="no contiene un mensaje",
    ):
        obtener_contenido_respuesta(respuesta)


@pytest.mark.parametrize(
    "contenido",
    [
        None,
        "",
        "   ",
        25,
    ],
)
def test_obtener_contenido_rechaza_mensaje_sin_decision(
    contenido,
):
    """Comprueba contenidos vacíos o con un tipo incorrecto."""
    respuesta = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=contenido,
                )
            )
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="no contiene contenido válido",
    ):
        obtener_contenido_respuesta(respuesta)


def test_obtener_contenido_normaliza_espacios_exteriores():
    """Comprueba que solo se eliminen los espacios exteriores."""
    respuesta = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="  contenido de prueba  ",
                )
            )
        ]
    )

    resultado = obtener_contenido_respuesta(respuesta)

    assert resultado == "contenido de prueba"

@pytest.mark.parametrize(
    ("entrada", "tipo_error"),
    [
        (
            None,
            TypeError,
        ),
        (
            "   ",
            ValueError,
        ),
    ],
)
def test_ejecutar_coordinador_rechaza_entrada_antes_de_llamar(
    entrada,
    tipo_error,
):
    """Comprueba que una entrada inválida no consuma tokens."""
    cliente = ClienteCoordinadorSimulado(
        respuesta=None,
    )

    with pytest.raises(tipo_error):
        ejecutar_coordinador(
            entrada,
            cliente=cliente,
        )

    # La validación local debe detener el flujo antes de utilizar Groq.
    assert cliente.completions.numero_llamadas == 0


@pytest.mark.parametrize(
    ("nombre_excepcion", "mensaje_esperado"),
    [
        (
            "AuthenticationError",
            "autenticar",
        ),
        (
            "RateLimitError",
            "límite de Groq",
        ),
        (
            "APITimeoutError",
            "demasiado tiempo",
        ),
        (
            "APIConnectionError",
            "establecer conexión",
        ),
        (
            "BadRequestError",
            "rechazó los parámetros",
        ),
        (
            "APIStatusError",
            "devolvió un error",
        ),
    ],
)
def test_ejecutar_coordinador_controla_errores_conocidos(
    monkeypatch,
    nombre_excepcion,
    mensaje_esperado,
):
    """Comprueba la conversión de errores conocidos del SDK."""
    class ErrorGroqSimulado(Exception):
        """Representa una excepción controlada del SDK durante el test."""

    # Sustituye únicamente durante esta prueba la excepción seleccionada.
    monkeypatch.setattr(
        modulo_coordinador,
        nombre_excepcion,
        ErrorGroqSimulado,
    )

    cliente = ClienteCoordinadorSimulado(
        error=ErrorGroqSimulado("Fallo simulado"),
    )

    with pytest.raises(
        RuntimeError,
        match=mensaje_esperado,
    ):
        ejecutar_coordinador(
            "Explícame las listas de Python.",
            cliente=cliente,
        )

    # El error debe producirse durante la única llamada simulada.
    assert cliente.completions.numero_llamadas == 1


def test_ejecutar_coordinador_controla_error_externo_inesperado():
    """Comprueba un error no perteneciente a las categorías conocidas."""
    cliente = ClienteCoordinadorSimulado(
        error=ConnectionError("Error de red simulado"),
    )

    with pytest.raises(
        RuntimeError,
        match="error externo",
    ):
        ejecutar_coordinador(
            "Explícame las listas de Python.",
            cliente=cliente,
        )

    assert cliente.completions.numero_llamadas == 1

def test_ejecutar_coordinador_corrige_decision_incoherente():
    """Comprueba una decisión inválida seguida de otra válida."""
    decision_invalida = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="""
                    {
                        "accion": "generar_ejercicio",
                        "tecnologia": "python",
                        "consulta_documentacion": null,
                        "requiere_documentacion": true,
                        "mensaje_aclaracion": null
                    }
                    """,
                )
            )
        ]
    )

    decision_corregida = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="""
                    {
                        "accion": "generar_ejercicio",
                        "tecnologia": "python",
                        "consulta_documentacion": "listas de Python",
                        "requiere_documentacion": true,
                        "mensaje_aclaracion": null
                    }
                    """,
                )
            )
        ]
    )

    cliente = ClienteCoordinadorSimulado(
        respuestas=[
            decision_invalida,
            decision_corregida,
        ]
    )

    decision = ejecutar_coordinador(
        "Ponme un ejercicio sobre listas de Python.",
        cliente=cliente,
    )

    # La segunda respuesta debe ser la decisión finalmente aceptada.
    assert decision.accion == "generar_ejercicio"
    assert decision.tecnologia == "python"
    assert decision.consulta_documentacion == "listas de Python"
    assert decision.requiere_documentacion is True

    # La corrección debe necesitar exactamente dos llamadas.
    assert cliente.completions.numero_llamadas == 2

    segunda_llamada = cliente.completions.historial_parametros[1]
    mensajes = segunda_llamada["messages"]

    # La segunda llamada contiene los dos mensajes originales,
    # la decisión rechazada y la petición de corrección.
    assert len(mensajes) == 4
    assert mensajes[2]["role"] == "assistant"
    assert '"consulta_documentacion": null' in mensajes[2]["content"]
    assert mensajes[3]["role"] == "user"
    assert "ha sido rechazada" in mensajes[3]["content"]
    assert "consulta de documentación no nula" in mensajes[3]["content"]

def test_ejecutar_coordinador_se_detiene_tras_dos_decisiones_invalidas():
    """Comprueba que el coordinador no entre en un bucle infinito."""
    decision_invalida = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="""
                    {
                        "accion": "generar_ejercicio",
                        "tecnologia": "python",
                        "consulta_documentacion": null,
                        "requiere_documentacion": true,
                        "mensaje_aclaracion": null
                    }
                    """,
                )
            )
        ]
    )

    cliente = ClienteCoordinadorSimulado(
        respuestas=[
            decision_invalida,
            decision_invalida,
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="no pudo generar una decisión válida",
    ):
        ejecutar_coordinador(
            "Ponme un ejercicio sobre listas de Python.",
            cliente=cliente,
        )

    # Nunca debe existir un tercer intento.
    assert cliente.completions.numero_llamadas == 2

def test_crear_actualizacion_coordinador_para_consulta():
    """Comprueba una decisión que todavía necesita ejecutar más pasos."""
    decision = DecisionCoordinador(
        accion="responder_consulta",
        tecnologia="python",
        consulta_documentacion="listas de Python",
        requiere_documentacion=True,
        mensaje_aclaracion=None,
    )

    actualizacion = crear_actualizacion_coordinador(decision)

    assert actualizacion == {
        "accion": "responder_consulta",
        "tecnologia": "python",
        "consulta_documentacion": "listas de Python",
        "requiere_documentacion": True,
        "mensaje_aclaracion": None,
        "respuesta_final": None,
    }


def test_crear_actualizacion_coordinador_para_aclaracion():
    """Comprueba que una aclaración se convierta en respuesta final."""
    decision = DecisionCoordinador(
        accion="pedir_aclaracion",
        tecnologia=None,
        consulta_documentacion=None,
        requiere_documentacion=False,
        mensaje_aclaracion="¿Qué tecnología quieres estudiar?",
    )

    actualizacion = crear_actualizacion_coordinador(decision)

    assert actualizacion == {
        "accion": "pedir_aclaracion",
        "tecnologia": None,
        "consulta_documentacion": None,
        "requiere_documentacion": False,
        "mensaje_aclaracion": "¿Qué tecnología quieres estudiar?",
        "respuesta_final": "¿Qué tecnología quieres estudiar?",
    }


@pytest.mark.parametrize(
    "decision",
    [
        None,
        {
            "accion": "responder_consulta",
        },
        "decisión sin validar",
    ],
)
def test_crear_actualizacion_coordinador_rechaza_decision_no_validada(
    decision,
):
    """Comprueba que no se admitan datos que no hayan pasado Pydantic."""
    with pytest.raises(
        TypeError,
        match="DecisionCoordinador validada",
    ):
        crear_actualizacion_coordinador(decision)
