import json  # Permite crear catálogos temporales durante las pruebas.

import pytest  # Proporciona fixtures y comprobación de excepciones.

from nivel_experto.tutor_multiagente.herramientas.fuentes import (
    cargar_catalogo_fuentes,
    listar_fuentes_oficiales,
    obtener_fuente_oficial,
)


def test_cargar_catalogo_principal_contiene_tecnologias_esperadas():
    """Comprueba que el catálogo real contiene las tecnologías iniciales."""
    catalogo = cargar_catalogo_fuentes()

    assert set(catalogo) == {"python", "java", "git"}


def test_listar_fuentes_devuelve_resultado_ordenado():
    """Comprueba que las fuentes se devuelven en un orden determinista."""
    fuentes = listar_fuentes_oficiales()
    identificadores = [fuente["id"] for fuente in fuentes]

    assert identificadores == ["git", "java", "python"]


def test_obtener_fuente_normaliza_el_identificador():
    """Comprueba que se admiten mayúsculas y espacios exteriores."""
    fuente = obtener_fuente_oficial(" Python ")

    assert fuente["id"] == "python"
    assert fuente["nombre"] == "Python"
    assert fuente["dominios_permitidos"] == ["docs.python.org"]


def test_obtener_fuente_rechaza_tecnologia_no_registrada():
    """Comprueba que un nombre válido pero desconocido produce ValueError."""
    with pytest.raises(ValueError, match="no está registrada"):
        obtener_fuente_oficial("cobol")


def test_obtener_fuente_rechaza_tipo_incorrecto():
    """Comprueba que los valores que no son texto no llegan al catálogo."""
    with pytest.raises(TypeError):
        obtener_fuente_oficial(True)


def test_obtener_fuente_devuelve_una_copia_independiente():
    """Comprueba que modificar el resultado no altera el catálogo original."""
    primera_consulta = obtener_fuente_oficial("python")

    # Modifica únicamente la lista devuelta por esta llamada.
    primera_consulta["dominios_permitidos"].append("dominio-inventado.com")

    # Vuelve a cargar la fuente para comprobar que el catálogo sigue intacto.
    segunda_consulta = obtener_fuente_oficial("python")

    assert segunda_consulta["dominios_permitidos"] == ["docs.python.org"]


def test_cargar_catalogo_rechaza_archivo_inexistente(tmp_path):
    """Comprueba el tratamiento controlado de una ruta que no existe."""
    ruta_inexistente = tmp_path / "no_existe.json"

    with pytest.raises(RuntimeError, match="No se encontró"):
        cargar_catalogo_fuentes(ruta_inexistente)


def test_cargar_catalogo_rechaza_json_invalido(tmp_path):
    """Comprueba que un archivo JSON dañado no sea aceptado."""
    ruta_catalogo = tmp_path / "catalogo_invalido.json"

    # Escribe deliberadamente un contenido que no es JSON válido.
    ruta_catalogo.write_text("{contenido incorrecto", encoding="utf-8")

    with pytest.raises(RuntimeError, match="no contiene JSON válido"):
        cargar_catalogo_fuentes(ruta_catalogo)


@pytest.mark.parametrize(
    "contenido",
    [
        {},
        [],
        "texto",
    ],
)
def test_cargar_catalogo_rechaza_raiz_invalida(tmp_path, contenido):
    """Comprueba que la raíz debe ser un objeto JSON no vacío."""
    ruta_catalogo = tmp_path / "catalogo.json"

    # Convierte cada valor de prueba a JSON válido antes de guardarlo.
    ruta_catalogo.write_text(
        json.dumps(contenido),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="objeto JSON no vacío"):
        cargar_catalogo_fuentes(ruta_catalogo)


def test_cargar_catalogo_rechaza_campos_obligatorios_ausentes(tmp_path):
    """Comprueba que cada tecnología incluya todos sus campos."""
    ruta_catalogo = tmp_path / "catalogo_incompleto.json"

    # Omite deliberadamente descripción, dominios y páginas iniciales.
    contenido = {
        "python": {
            "nombre": "Python"
        }
    }

    ruta_catalogo.write_text(
        json.dumps(contenido),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="descripcion"):
        cargar_catalogo_fuentes(ruta_catalogo)
        

def test_cargar_catalogo_rechaza_dominio_invalido(tmp_path):
    """Comprueba que un dominio no pueda contener protocolo ni ruta."""
    ruta_catalogo = tmp_path / "catalogo_dominio_invalido.json"

    contenido = {
        "python": {
            "nombre": "Python",
            "descripcion": "Documentación oficial de Python.",
            "dominios_permitidos": [
                "https://docs.python.org"
            ],
            "paginas_iniciales": [
                "https://docs.python.org/3/"
            ],
        }
    }

    # Guarda un catálogo válido como JSON, pero con un dominio incorrecto.
    ruta_catalogo.write_text(
        json.dumps(contenido),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="dominio inválido"):
        cargar_catalogo_fuentes(ruta_catalogo)


def test_cargar_catalogo_rechaza_pagina_de_otro_dominio(tmp_path):
    """Comprueba que las páginas pertenezcan a los dominios autorizados."""
    ruta_catalogo = tmp_path / "catalogo_pagina_invalida.json"

    contenido = {
        "python": {
            "nombre": "Python",
            "descripcion": "Documentación oficial de Python.",
            "dominios_permitidos": [
                "docs.python.org"
            ],
            "paginas_iniciales": [
                "https://ejemplo.com/python"
            ],
        }
    }

    # La página utiliza HTTPS, pero no pertenece al dominio oficial.
    ruta_catalogo.write_text(
        json.dumps(contenido),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="no es una URL oficial válida"):
        cargar_catalogo_fuentes(ruta_catalogo)