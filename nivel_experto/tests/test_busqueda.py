import pytest  # Permite parametrizar errores y comprobar excepciones.

from tavily import (
    BadRequestError,
    InvalidAPIKeyError,
    MissingAPIKeyError,
    UsageLimitExceededError,
)
from tavily.errors import (
    ForbiddenError,
    TimeoutError as TavilyTimeoutError,
)

from nivel_experto.tutor_multiagente.herramientas.busqueda import (
    buscar_documentacion,
)


class ClienteBusquedaSimulado:
    """
    Simula Tavily sin realizar conexiones ni consumir créditos.
    """

    def __init__(self, respuesta=None, error=None):
        # Guarda la respuesta o excepción configurada para cada prueba.
        self.respuesta = respuesta
        self.error = error

        # Permitirá comprobar qué recibió el cliente.
        self.consulta_recibida = None
        self.parametros_recibidos = None
        self.numero_llamadas = 0

    def search(self, query, **parametros):
        """Imita el método search de TavilyClient."""
        self.numero_llamadas += 1
        self.consulta_recibida = query
        self.parametros_recibidos = parametros

        # Simula errores externos cuando la prueba lo solicita.
        if self.error is not None:
            raise self.error

        return self.respuesta


def test_buscar_documentacion_filtra_y_normaliza_resultados():
    """Comprueba parámetros, dominios, duplicados y URLs inseguras."""
    cliente = ClienteBusquedaSimulado(
        respuesta={
            "results": [
                {
                    "title": "More on Lists",
                    "url": (
                        "https://docs.python.org/3/"
                        "tutorial/datastructures.html"
                    ),
                    "content": "Información sobre append y extend.",
                    "score": 0.95,
                },
                {
                    # Esta página está repetida y debe descartarse.
                    "title": "Resultado repetido",
                    "url": (
                        "https://docs.python.org/3/"
                        "tutorial/datastructures.html"
                    ),
                    "content": "Contenido repetido.",
                    "score": 0.80,
                },
                {
                    # Este dominio no está autorizado.
                    "title": "Página externa",
                    "url": "https://ejemplo.com/python",
                    "content": "Contenido no oficial.",
                    "score": 0.70,
                },
                {
                    # Este resultado no tiene título válido.
                    "title": "",
                    "url": "https://docs.python.org/3/reference/",
                    "content": "Contenido incompleto.",
                    "score": 0.60,
                },
                {
                    "title": "Built-in Types",
                    "url": "https://docs.python.org/3/library/stdtypes.html",
                    "content": "Información sobre secuencias mutables.",
                    # Un booleano no debe aceptarse como puntuación numérica.
                    "score": True,
                },
            ]
        }
    )

    resultado = buscar_documentacion(
        " Python ",
        "  append   y   extend ",
        cliente=cliente,
    )

    assert resultado["ok"] is True
    assert resultado["tecnologia"] == "python"
    assert resultado["consulta"] == "append y extend"

    # Solo deben sobrevivir las dos páginas oficiales y no repetidas.
    assert len(resultado["resultados"]) == 2
    assert resultado["resultados"][0]["id"] == "resultado-1"
    assert resultado["resultados"][1]["id"] == "resultado-2"
    assert resultado["resultados"][0]["puntuacion"] == 0.95
    assert resultado["resultados"][1]["puntuacion"] is None

    # Comprueba la consulta y configuración entregadas al cliente.
    assert cliente.consulta_recibida == "Python append y extend"
    assert cliente.parametros_recibidos["search_depth"] == "advanced"
    assert cliente.parametros_recibidos["chunks_per_source"] == 3
    assert cliente.parametros_recibidos["max_results"] == 5
    assert cliente.parametros_recibidos["include_domains"] == [
        "docs.python.org"
    ]
    assert cliente.parametros_recibidos["include_answer"] is False
    assert cliente.parametros_recibidos["include_raw_content"] is False


def test_buscar_documentacion_controla_lista_vacia():
    """Comprueba una búsqueda válida que no encuentra páginas."""
    cliente = ClienteBusquedaSimulado(
        respuesta={
            "results": []
        }
    )

    resultado = buscar_documentacion(
        "git",
        "ramas remotas",
        cliente=cliente,
    )

    assert resultado["ok"] is False
    assert resultado["resultados"] == []
    assert "No se encontró" in resultado["error"]

def test_buscar_documentacion_usa_respaldo_si_advanced_esta_vacia():
    """
    Repite una búsqueda vacía una sola vez con profundidad basic.
    """
    class ClienteBusquedaSecuencialSimulado:
        """Devuelve una respuesta diferente en cada llamada."""

        def __init__(self):
            self.numero_llamadas = 0
            self.historial_parametros = []

            self.respuestas = [
                {
                    "results": [],
                },
                {
                    "results": [
                        {
                            "title": "Chapter 9. Interfaces",
                            "url": (
                                "https://docs.oracle.com/javase/"
                                "specs/jls/se17/html/jls-9.html"
                            ),
                            "content": (
                                "Official Java specification about "
                                "interfaces."
                            ),
                            "score": 0.90,
                        }
                    ],
                },
            ]

        def search(self, query, **parametros):
            """Imita dos respuestas consecutivas de Tavily."""
            self.numero_llamadas += 1

            self.historial_parametros.append(
                {
                    "query": query,
                    **parametros,
                }
            )

            indice = self.numero_llamadas - 1
            return self.respuestas[indice]

    cliente = ClienteBusquedaSecuencialSimulado()

    consulta = (
        "difference between interface and abstract class "
        "in Java current"
    )

    resultado = buscar_documentacion(
        tecnologia="java",
        consulta=consulta,
        cliente=cliente,
    )

    # El segundo intento debe recuperar una página oficial válida.
    assert resultado["ok"] is True
    assert resultado["tecnologia"] == "java"
    assert len(resultado["resultados"]) == 1
    assert cliente.numero_llamadas == 2

    primer_intento = cliente.historial_parametros[0]
    segundo_intento = cliente.historial_parametros[1]

    # La búsqueda principal conserva la configuración avanzada.
    assert primer_intento["query"] == f"Java {consulta}"
    assert primer_intento["search_depth"] == "advanced"
    assert primer_intento["chunks_per_source"] == 3

    # El respaldo utiliza una consulta directa y profundidad básica.
    assert segundo_intento["query"] == consulta
    assert segundo_intento["search_depth"] == "basic"
    assert segundo_intento["chunks_per_source"] == 1

    # Ambos intentos utilizan exactamente el mismo catálogo oficial.
    assert segundo_intento["include_domains"] == (
        primer_intento["include_domains"]
    )

    # Java admite sus dos dominios oficiales configurados.
    assert set(primer_intento["include_domains"]) == {
        "dev.java",
        "docs.oracle.com",
    }

def test_buscar_documentacion_controla_respuesta_mal_formada():
    """Comprueba que una respuesta externa inválida no cierre el programa."""
    cliente = ClienteBusquedaSimulado(
        respuesta={
            "campo_incorrecto": []
        }
    )

    resultado = buscar_documentacion(
        "java",
        "excepciones",
        cliente=cliente,
    )

    assert resultado["ok"] is False
    assert "lista de resultados" in resultado["error"]


@pytest.mark.parametrize(
    ("error", "mensaje_esperado"),
    [
        (
            MissingAPIKeyError(),
            "autenticar",
        ),
        (
            InvalidAPIKeyError("Clave inválida"),
            "autenticar",
        ),
        (
            ForbiddenError("Acceso prohibido"),
            "autenticar",
        ),
        (
            UsageLimitExceededError("Límite superado"),
            "límite de uso",
        ),
        (
            TavilyTimeoutError(10),
            "demasiado tiempo",
        ),
        (
            BadRequestError("Petición incorrecta"),
            "rechazó los parámetros",
        ),
    ],
)
def test_buscar_documentacion_controla_errores_tavily(
    error,
    mensaje_esperado,
):
    """Comprueba los errores conocidos del SDK de Tavily."""
    cliente = ClienteBusquedaSimulado(error=error)

    resultado = buscar_documentacion(
        "python",
        "listas",
        cliente=cliente,
    )

    assert resultado["ok"] is False
    assert mensaje_esperado in resultado["error"]


def test_buscar_documentacion_controla_error_inesperado():
    """Comprueba que un fallo externo desconocido produce un error genérico."""
    cliente = ClienteBusquedaSimulado(
        error=ConnectionError("Error de red simulado")
    )

    resultado = buscar_documentacion(
        "git",
        "merge",
        cliente=cliente,
    )

    assert resultado["ok"] is False
    assert "error externo" in resultado["error"]


def test_buscar_documentacion_rechaza_tecnologia_desconocida_antes_de_llamar():
    """Comprueba que una tecnología inventada no llegue a Tavily."""
    cliente = ClienteBusquedaSimulado(respuesta={"results": []})

    with pytest.raises(ValueError, match="no está registrada"):
        buscar_documentacion(
            "tecnologia-inventada",
            "tema cualquiera",
            cliente=cliente,
        )

    assert cliente.numero_llamadas == 0


def test_buscar_documentacion_rechaza_consulta_invalida_antes_de_llamar():
    """Comprueba que una consulta con URL no llegue a Tavily."""
    cliente = ClienteBusquedaSimulado(respuesta={"results": []})

    with pytest.raises(ValueError, match="no puede contener una URL"):
        buscar_documentacion(
            "python",
            "consulta https://ejemplo.com",
            cliente=cliente,
        )

    assert cliente.numero_llamadas == 0