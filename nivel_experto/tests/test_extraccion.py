import pytest  # Permite comprobar excepciones y parametrizar pruebas.

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

from nivel_experto.tutor_multiagente.config import (
    MAX_CARACTERES_EXTRAIDOS,
)
from nivel_experto.tutor_multiagente.herramientas.extraccion import (
    _procesar_extracciones,
    _validar_urls_extraccion,
    extraer_documentacion,
)

class ClienteExtraccionSimulado:
    """
    Simula Tavily Extract sin realizar conexiones ni consumir créditos.
    """

    def __init__(self, respuesta=None, error=None):
        # Guarda la respuesta o excepción que utilizará cada prueba.
        self.respuesta = respuesta
        self.error = error

        # Estos atributos permiten inspeccionar la llamada recibida.
        self.urls_recibidas = None
        self.parametros_recibidos = None
        self.numero_llamadas = 0

    def extract(self, urls, **parametros):
        """Imita el método extract de TavilyClient."""
        self.numero_llamadas += 1
        self.urls_recibidas = urls
        self.parametros_recibidos = parametros

        # Permite simular errores externos en pruebas posteriores.
        if self.error is not None:
            raise self.error

        return self.respuesta

def test_validar_urls_extraccion_acepta_urls_oficiales():
    """Comprueba que se acepten páginas pertenecientes al dominio oficial."""
    urls = [
        "https://docs.python.org/3/tutorial/datastructures.html",
        "https://docs.python.org/3/library/stdtypes.html",
    ]

    resultado = _validar_urls_extraccion(
        urls,
        ["docs.python.org"],
    )

    assert resultado == urls


def test_validar_urls_extraccion_elimina_duplicados():
    """Comprueba que una misma página no se extraiga dos veces."""
    url = "https://docs.python.org/3/tutorial/datastructures.html"

    resultado = _validar_urls_extraccion(
        [url, url],
        ["docs.python.org"],
    )

    assert resultado == [url]


@pytest.mark.parametrize(
    "urls",
    [
        None,
        "https://docs.python.org/3/",
        (
            "https://docs.python.org/3/",
        ),
    ],
)
def test_validar_urls_extraccion_rechaza_tipos_incorrectos(urls):
    """Comprueba que las URL deban recibirse dentro de una lista."""
    with pytest.raises(
        TypeError,
        match="deben proporcionarse dentro de una lista",
    ):
        _validar_urls_extraccion(
            urls,
            ["docs.python.org"],
        )


def test_validar_urls_extraccion_rechaza_lista_vacia():
    """Comprueba que no se pueda solicitar una extracción sin páginas."""
    with pytest.raises(
        ValueError,
        match="al menos una URL",
    ):
        _validar_urls_extraccion(
            [],
            ["docs.python.org"],
        )


def test_validar_urls_extraccion_rechaza_demasiadas_urls():
    """Comprueba el límite de tres extracciones por turno."""
    urls = [
        "https://docs.python.org/3/tutorial/",
        "https://docs.python.org/3/library/",
        "https://docs.python.org/3/reference/",
        "https://docs.python.org/3/faq/",
    ]

    with pytest.raises(
        ValueError,
        match="más de 3 URL",
    ):
        _validar_urls_extraccion(
            urls,
            ["docs.python.org"],
        )


def test_validar_urls_extraccion_rechaza_dominio_no_oficial():
    """Comprueba que una página externa no llegue hasta Tavily."""
    urls = [
        "https://pagina-no-oficial.com/python",
    ]

    with pytest.raises(
        ValueError,
        match="no pertenece a las fuentes autorizadas",
    ):
        _validar_urls_extraccion(
            urls,
            ["docs.python.org"],
        )

def test_procesar_extracciones_filtra_resultados_invalidos():
    """
    Comprueba duplicados, dominios externos y páginas no solicitadas.
    """
    url_primera = (
        "https://docs.python.org/3/tutorial/datastructures.html"
    )
    url_segunda = (
        "https://docs.python.org/3/library/stdtypes.html"
    )

    respuesta = {
        "results": [
            {
                "url": url_primera,
                "raw_content": "Contenido oficial de la primera página.",
            },
            {
                # Esta página está duplicada y debe descartarse.
                "url": url_primera,
                "raw_content": "Contenido duplicado.",
            },
            {
                # Esta página pertenece a un dominio no autorizado.
                "url": "https://pagina-no-oficial.com/python",
                "raw_content": "Contenido externo.",
            },
            {
                # El dominio es oficial, pero esta URL no fue solicitada.
                "url": "https://docs.python.org/3/faq/",
                "raw_content": "Contenido oficial no solicitado.",
            },
            {
                # Un contenido vacío no debe entregarse al agente.
                "url": url_segunda,
                "raw_content": "   ",
            },
            {
                "url": url_segunda,
                "raw_content": "Contenido oficial de la segunda página.",
            },
            # Un elemento que no sea un diccionario debe ignorarse.
            "resultado incorrecto",
        ]
    }

    resultado = _procesar_extracciones(
        respuesta,
        ["docs.python.org"],
        [url_primera, url_segunda],
    )

    assert resultado == [
        {
            "id": "fuente-1",
            "url": url_primera,
            "contenido": "Contenido oficial de la primera página.",
        },
        {
            "id": "fuente-2",
            "url": url_segunda,
            "contenido": "Contenido oficial de la segunda página.",
        },
    ]


def test_procesar_extracciones_limita_caracteres_totales():
    """Comprueba que el límite se aplique entre todas las fuentes."""
    url_primera = "https://docs.python.org/3/tutorial/"
    url_segunda = "https://docs.python.org/3/library/"

    respuesta = {
        "results": [
            {
                "url": url_primera,
                "raw_content": "a" * 8_000,
            },
            {
                "url": url_segunda,
                "raw_content": "b" * 8_000,
            },
        ]
    }

    resultado = _procesar_extracciones(
        respuesta,
        ["docs.python.org"],
        [url_primera, url_segunda],
    )

    # La primera fuente conserva sus 8000 caracteres.
    assert len(resultado[0]["contenido"]) == 8_000

    # De la segunda fuente solo caben otros 4000 caracteres.
    assert len(resultado[1]["contenido"]) == 4_000

    # Ninguna combinación puede superar el límite global configurado.
    total_caracteres = sum(
        len(fuente["contenido"])
        for fuente in resultado
    )
    assert total_caracteres == MAX_CARACTERES_EXTRAIDOS


@pytest.mark.parametrize(
    "respuesta",
    [
        None,
        [],
        "respuesta incorrecta",
    ],
)
def test_procesar_extracciones_rechaza_respuesta_principal_invalida(
    respuesta,
):
    """Comprueba que la respuesta principal tenga formato de objeto."""
    with pytest.raises(
        RuntimeError,
        match="formato inválido",
    ):
        _procesar_extracciones(
            respuesta,
            ["docs.python.org"],
            ["https://docs.python.org/3/"],
        )


@pytest.mark.parametrize(
    "respuesta",
    [
        {},
        {"results": None},
        {"results": "contenido incorrecto"},
    ],
)
def test_procesar_extracciones_rechaza_lista_resultados_invalida(
    respuesta,
):
    """Comprueba que results exista y sea una lista."""
    with pytest.raises(
        RuntimeError,
        match="lista de extracciones",
    ):
        _procesar_extracciones(
            respuesta,
            ["docs.python.org"],
            ["https://docs.python.org/3/"],
        )


def test_procesar_extracciones_acepta_lista_vacia():
    """Comprueba una extracción válida que no produce contenido."""
    resultado = _procesar_extracciones(
        {"results": []},
        ["docs.python.org"],
        ["https://docs.python.org/3/"],
    )

    assert resultado == []

def test_extraer_documentacion_procesa_respuesta_correcta():
    """Comprueba una extracción completa utilizando un cliente simulado."""
    url = "https://docs.python.org/3/tutorial/datastructures.html"

    cliente = ClienteExtraccionSimulado(
        respuesta={
            "results": [
                {
                    "url": url,
                    "raw_content": (
                        "list.append añade un elemento. "
                        "list.extend añade los elementos de un iterable."
                    ),
                }
            ]
        }
    )

    resultado = extraer_documentacion(
        " Python ",
        "  diferencia   entre   append y extend ",
        [url],
        cliente=cliente,
    )

    # Comprueba el resultado que recibirá posteriormente el agente.
    assert resultado == {
        "ok": True,
        "tecnologia": "python",
        "consulta": "diferencia entre append y extend",
        "fuentes": [
            {
                "id": "fuente-1",
                "url": url,
                "contenido": (
                    "list.append añade un elemento. "
                    "list.extend añade los elementos de un iterable."
                ),
            }
        ],
    }

    # La función debe realizar exactamente una llamada externa.
    assert cliente.numero_llamadas == 1

    # Comprueba las URL entregadas a Tavily.
    assert cliente.urls_recibidas == [url]

    # Comprueba la consulta utilizada para seleccionar fragmentos.
    assert cliente.parametros_recibidos["query"] == (
        "Python diferencia entre append y extend"
    )

    # Comprueba los límites y opciones de bajo consumo.
    assert cliente.parametros_recibidos["chunks_per_source"] == 3
    assert cliente.parametros_recibidos["extract_depth"] == "basic"
    assert cliente.parametros_recibidos["format"] == "markdown"
    assert cliente.parametros_recibidos["include_images"] is False
    assert cliente.parametros_recibidos["include_favicon"] is False
    assert cliente.parametros_recibidos["include_usage"] is True
    assert cliente.parametros_recibidos["timeout"] == 10

def test_extraer_documentacion_controla_resultados_vacios():
    """Comprueba una petición correcta que no consigue extraer contenido."""
    url = "https://docs.python.org/3/tutorial/"

    cliente = ClienteExtraccionSimulado(
        respuesta={
            "results": [],
        }
    )

    resultado = extraer_documentacion(
        "python",
        "listas",
        [url],
        cliente=cliente,
    )

    assert resultado["ok"] is False
    assert resultado["fuentes"] == []
    assert "No se pudo extraer contenido" in resultado["error"]


def test_extraer_documentacion_controla_respuesta_mal_formada():
    """Comprueba que una respuesta externa inválida no cierre el programa."""
    url = "https://docs.python.org/3/tutorial/"

    cliente = ClienteExtraccionSimulado(
        respuesta={
            "campo_incorrecto": [],
        }
    )

    resultado = extraer_documentacion(
        "python",
        "listas",
        [url],
        cliente=cliente,
    )

    assert resultado["ok"] is False
    assert resultado["fuentes"] == []
    assert "lista de extracciones" in resultado["error"]


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
def test_extraer_documentacion_controla_errores_tavily(
    error,
    mensaje_esperado,
):
    """Comprueba los errores conocidos del SDK de Tavily."""
    url = "https://docs.python.org/3/tutorial/"

    cliente = ClienteExtraccionSimulado(
        error=error,
    )

    resultado = extraer_documentacion(
        "python",
        "listas",
        [url],
        cliente=cliente,
    )

    assert resultado["ok"] is False
    assert resultado["fuentes"] == []
    assert mensaje_esperado in resultado["error"]

    # Confirma que el error ocurrió durante la única llamada simulada.
    assert cliente.numero_llamadas == 1


def test_extraer_documentacion_controla_error_inesperado():
    """Comprueba que un fallo desconocido produzca un error controlado."""
    url = "https://docs.python.org/3/tutorial/"

    cliente = ClienteExtraccionSimulado(
        error=ConnectionError("Error de red simulado"),
    )

    resultado = extraer_documentacion(
        "python",
        "listas",
        [url],
        cliente=cliente,
    )

    assert resultado["ok"] is False
    assert resultado["fuentes"] == []
    assert "error externo" in resultado["error"]
    assert cliente.numero_llamadas == 1

def test_extraer_documentacion_rechaza_tecnologia_desconocida_antes_de_llamar():
    """Comprueba que una tecnología inventada no llegue a Tavily."""
    cliente = ClienteExtraccionSimulado(
        respuesta={
            "results": [],
        }
    )

    with pytest.raises(
        ValueError,
        match="no está registrada",
    ):
        extraer_documentacion(
            "tecnologia-inventada",
            "tema cualquiera",
            ["https://docs.python.org/3/"],
            cliente=cliente,
        )

    # La validación debe detener el flujo antes de la llamada externa.
    assert cliente.numero_llamadas == 0


def test_extraer_documentacion_rechaza_consulta_invalida_antes_de_llamar():
    """Comprueba que una consulta con URL no llegue a Tavily."""
    cliente = ClienteExtraccionSimulado(
        respuesta={
            "results": [],
        }
    )

    with pytest.raises(
        ValueError,
        match="no puede contener una URL",
    ):
        extraer_documentacion(
            "python",
            "consulta https://ejemplo.com",
            ["https://docs.python.org/3/"],
            cliente=cliente,
        )

    assert cliente.numero_llamadas == 0


def test_extraer_documentacion_rechaza_dominio_externo_antes_de_llamar():
    """Comprueba que una URL no oficial no llegue a Tavily."""
    cliente = ClienteExtraccionSimulado(
        respuesta={
            "results": [],
        }
    )

    with pytest.raises(
        ValueError,
        match="no pertenece a las fuentes autorizadas",
    ):
        extraer_documentacion(
            "python",
            "listas",
            ["https://pagina-no-oficial.com/python"],
            cliente=cliente,
        )

    assert cliente.numero_llamadas == 0


def test_extraer_documentacion_rechaza_demasiadas_urls_antes_de_llamar():
    """Comprueba que el límite de tres páginas se aplique localmente."""
    cliente = ClienteExtraccionSimulado(
        respuesta={
            "results": [],
        }
    )

    urls = [
        "https://docs.python.org/3/tutorial/",
        "https://docs.python.org/3/library/",
        "https://docs.python.org/3/reference/",
        "https://docs.python.org/3/faq/",
    ]

    with pytest.raises(
        ValueError,
        match="más de 3 URL",
    ):
        extraer_documentacion(
            "python",
            "listas",
            urls,
            cliente=cliente,
        )

    assert cliente.numero_llamadas == 0