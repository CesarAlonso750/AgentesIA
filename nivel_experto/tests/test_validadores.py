import pytest  # Proporciona utilidades para escribir y ejecutar pruebas.

from nivel_experto.tutor_multiagente.validadores import (
    normalizar_dominio,
    normalizar_tecnologia,
    validar_consulta,
    validar_url_oficial,
)


def test_normalizar_tecnologia_elimina_espacios_y_mayusculas():
    """Comprueba que un nombre válido se normaliza correctamente."""
    assert normalizar_tecnologia(" Python ") == "python"


@pytest.mark.parametrize(
    "valor",
    [
        None,
        True,
        25,
        ["python"],
    ],
)
def test_normalizar_tecnologia_rechaza_tipos_incorrectos(valor):
    """Comprueba que solamente se aceptan cadenas de texto."""
    with pytest.raises(TypeError):
        normalizar_tecnologia(valor)


@pytest.mark.parametrize(
    "valor",
    [
        "",
        "   ",
        "python!",
        "java script",
        "a" * 51,
    ],
)
def test_normalizar_tecnologia_rechaza_formatos_invalidos(valor):
    """Comprueba que los identificadores inválidos son rechazados."""
    with pytest.raises(ValueError):
        normalizar_tecnologia(valor)


def test_validar_consulta_normaliza_espacios():
    """Comprueba que varios espacios y saltos se convierten en uno."""
    consulta = validar_consulta("  listas\n   de   Python  ")

    assert consulta == "listas de Python"


@pytest.mark.parametrize(
    "valor",
    [
        "",
        "  ",
        "ab",
        "a" * 301,
        "consulta https://ejemplo.com",
        "listas site:ejemplo.com",
    ],
)
def test_validar_consulta_rechaza_textos_invalidos(valor):
    """Comprueba consultas vacías, inseguras o fuera de los límites."""
    with pytest.raises(ValueError):
        validar_consulta(valor)


@pytest.mark.parametrize(
    "valor",
    [
        None,
        True,
        123,
        ["listas", "python"],
    ],
)
def test_validar_consulta_rechaza_tipos_incorrectos(valor):
    """Comprueba que la consulta siempre debe ser una cadena."""
    with pytest.raises(TypeError):
        validar_consulta(valor)
        

def test_normalizar_dominio_elimina_mayusculas_y_punto_final():
    """Comprueba la normalización de un dominio válido."""
    assert normalizar_dominio(" Docs.Python.org. ") == "docs.python.org"


@pytest.mark.parametrize(
    "dominio",
    [
        "",
        "localhost",
        "https://docs.python.org",
        "docs.python.org/ruta",
        "127.0.0.1",
    ],
)
def test_normalizar_dominio_rechaza_formatos_invalidos(dominio):
    """Comprueba que el catálogo no pueda contener dominios inseguros."""
    with pytest.raises(ValueError):
        normalizar_dominio(dominio)


def test_validar_url_oficial_acepta_dominio_exacto():
    """Comprueba una página perteneciente al dominio autorizado."""
    url = "https://docs.python.org/3/tutorial/datastructures.html"

    resultado = validar_url_oficial(url, ["docs.python.org"])

    assert resultado == url


def test_validar_url_oficial_acepta_subdominio_real():
    """Comprueba que se aceptan subdominios separados por un punto."""
    url = "https://subdominio.docs.python.org/documentacion"

    resultado = validar_url_oficial(url, ["docs.python.org"])

    assert resultado == url


@pytest.mark.parametrize(
    "url",
    [
        "http://docs.python.org/3/",
        "https://ejemplo.com/python",
        "https://docs.python.org.ejemplo.com/",
        "https://usuario:clave@docs.python.org/",
        "https://127.0.0.1/",
        "https://localhost/",
        "https://docs.python.org:8443/",
        "https://docs.python.org/ruta con espacios",
    ],
)
def test_validar_url_oficial_rechaza_urls_inseguras(url):
    """Comprueba diferentes intentos de utilizar URLs no autorizadas."""
    with pytest.raises(ValueError):
        validar_url_oficial(url, ["docs.python.org"])


@pytest.mark.parametrize(
    "url",
    [
        None,
        True,
        25,
    ],
)
def test_validar_url_oficial_rechaza_tipos_incorrectos(url):
    """Comprueba que una URL siempre tenga que ser texto."""
    with pytest.raises(TypeError):
        validar_url_oficial(url, ["docs.python.org"])


@pytest.mark.parametrize(
    "dominios",
    [
        None,
        [],
        "docs.python.org",
    ],
)
def test_validar_url_oficial_rechaza_coleccion_invalida(dominios):
    """Comprueba que los dominios formen una colección no vacía."""
    with pytest.raises(TypeError):
        validar_url_oficial(
            "https://docs.python.org/3/",
            dominios,
        )