import pytest  # Permite comprobar y parametrizar excepciones.

from nivel_experto.tutor_multiagente.estado import (
    crear_estado_inicial,
)


def test_crear_estado_inicial_devuelve_estructura_completa():
    """Comprueba todos los valores de un turno recién creado."""
    resultado = crear_estado_inicial(
        "  Explícame las listas de Python.  "
    )

    assert resultado == {
        "historial": [],
        "entrada_usuario": "Explícame las listas de Python.",
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


@pytest.mark.parametrize(
    "entrada",
    [
        None,
        True,
        25,
        ["Python"],
    ],
)
def test_crear_estado_inicial_rechaza_tipos_incorrectos(entrada):
    """Comprueba que la entrada del usuario tenga que ser texto."""
    with pytest.raises(
        TypeError,
        match="debe ser una cadena de texto",
    ):
        crear_estado_inicial(entrada)


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_crear_estado_inicial_rechaza_texto_vacio(entrada):
    """Comprueba que no pueda iniciarse un turno sin contenido."""
    with pytest.raises(
        ValueError,
        match="no puede estar vacía",
    ):
        crear_estado_inicial(entrada)


def test_crear_estado_inicial_no_comparte_listas_entre_turnos():
    """Comprueba que cada turno posea sus propias listas mutables."""
    primer_estado = crear_estado_inicial("Primera pregunta")
    segundo_estado = crear_estado_inicial("Segunda pregunta")

    # Modifica únicamente las listas del primer estado.
    primer_estado["errores"].append("Error simulado")
    primer_estado["resultados_busqueda"].append(
        {
            "id": "resultado-1",
            "titulo": "Documentación",
            "url": "https://docs.python.org/3/",
            "resumen": "Contenido",
            "puntuacion": 0.9,
        }
    )

    # El segundo estado debe permanecer completamente independiente.
    assert segundo_estado["errores"] == []
    assert segundo_estado["resultados_busqueda"] == []