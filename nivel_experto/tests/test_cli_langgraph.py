import logging  # Crea loggers aislados para las pruebas.

import pytest  # Comprueba las excepciones esperadas.

from nivel_experto.tutor_multiagente.cli_langgraph import (
    ejecutar_chat_langgraph,
)
from nivel_experto.tutor_multiagente.config import (
    MAX_PASOS_LANGGRAPH,
)


def _crear_lector(
    entradas,
):
    """
    Convierte una lista en una función compatible con input.
    """
    iterador = iter(
        entradas
    )

    def lector(prompt):
        """
        Devuelve la siguiente entrada preparada.
        """
        return next(
            iterador
        )

    return lector


class GrafoSimulado:
    """
    Reproduce la parte de LangGraph utilizada por la terminal.
    """

    def __init__(self):
        """
        Conserva todos los estados y configuraciones recibidos.
        """
        self.llamadas = []

    def invoke(
        self,
        estado,
        config=None,
    ):
        """
        Simula la ejecución completa de un turno.
        """
        self.llamadas.append(
            {
                "estado": estado,
                "config": config,
            }
        )

        return {
            **estado,
            "respuesta_final": (
                f"Respuesta a: {estado['entrada_usuario']}"
            ),
        }


def test_chat_langgraph_ejecuta_varios_turnos():
    """
    Ejecuta invoke y conserva el historial entre turnos.
    """
    grafo = GrafoSimulado()
    salidas = []

    estado_final = ejecutar_chat_langgraph(
        lector=_crear_lector(
            [
                "Primera pregunta",
                "Segunda pregunta",
                "salir",
            ]
        ),
        escritor=salidas.append,
        grafo=grafo,
        logger=logging.Logger(
            "cli_langgraph_varios_turnos"
        ),
    )

    # El grafo debe ejecutarse una vez por cada entrada válida.
    assert len(grafo.llamadas) == 2

    primera_llamada = grafo.llamadas[0]
    segunda_llamada = grafo.llamadas[1]

    # Todos los turnos utilizan el límite centralizado.
    assert primera_llamada["config"] == {
        "recursion_limit": MAX_PASOS_LANGGRAPH,
    }
    assert segunda_llamada["config"] == {
        "recursion_limit": MAX_PASOS_LANGGRAPH,
    }

    # El primer turno todavía no tiene historial.
    assert primera_llamada["estado"]["historial"] == []

    # El segundo turno recibe el intercambio anterior completo.
    assert segunda_llamada["estado"]["historial"] == [
        {
            "role": "user",
            "content": "Primera pregunta",
        },
        {
            "role": "assistant",
            "content": "Respuesta a: Primera pregunta",
        },
    ]

    assert estado_final["entrada_usuario"] == (
        "Segunda pregunta"
    )
    assert "Saliendo..." in salidas


def test_chat_langgraph_rechaza_objeto_sin_invoke():
    """
    Impide utilizar un objeto que no sea un grafo ejecutable.
    """
    with pytest.raises(
        TypeError,
        match="no es un grafo ejecutable",
    ):
        ejecutar_chat_langgraph(
            lector=_crear_lector(
                [
                    "salir",
                ]
            ),
            escritor=lambda texto: None,
            grafo=object(),
            logger=logging.Logger(
                "cli_langgraph_grafo_invalido"
            ),
        )


def test_chat_langgraph_controla_resultado_invalido():
    """
    Un resultado que no sea un estado produce un error visible seguro.
    """
    salidas = []

    class GrafoInvalido:
        """
        Simula un grafo que incumple su contrato de salida.
        """

        def invoke(
            self,
            estado,
            config=None,
        ):
            """
            Devuelve deliberadamente una cadena incorrecta.
            """
            return "estado incorrecto"

    resultado = ejecutar_chat_langgraph(
        lector=_crear_lector(
            [
                "Pregunta",
                "salir",
            ]
        ),
        escritor=salidas.append,
        grafo=GrafoInvalido(),
        logger=logging.Logger(
            "cli_langgraph_resultado_invalido"
        ),
    )

    # El turno fallido no debe convertirse en estado válido.
    assert resultado is None

    assert (
        "No se pudo completar el turno. "
        "Puedes reformular la petición e intentarlo de nuevo."
        in salidas
    )


def test_chat_langgraph_no_muestra_error_interno():
    """
    Impide mostrar trazas o información privada del grafo.
    """
    salidas = []

    class GrafoConError:
        """
        Simula un fallo interno durante la ejecución.
        """

        def invoke(
            self,
            estado,
            config=None,
        ):
            """
            Lanza un error con un supuesto secreto.
            """
            raise RuntimeError(
                "TAVILY_API_KEY=secreto-no-mostrar"
            )

    ejecutar_chat_langgraph(
        lector=_crear_lector(
            [
                "Pregunta",
                "salir",
            ]
        ),
        escritor=salidas.append,
        grafo=GrafoConError(),
        logger=logging.Logger(
            "cli_langgraph_error_seguro"
        ),
    )

    texto_visible = "\n".join(
        salidas
    )

    # El usuario solo recibe el mensaje genérico de la terminal.
    assert "secreto-no-mostrar" not in texto_visible
    assert "Traceback" not in texto_visible
    assert "No se pudo completar el turno." in texto_visible