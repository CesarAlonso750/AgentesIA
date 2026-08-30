import pytest  # Permite comprobar y parametrizar excepciones.

from copy import deepcopy  # Comprueba que los estados sean independientes.
from nivel_experto.tutor_multiagente.estado import (
    crear_estado_inicial,
    crear_estado_siguiente_turno,
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
        "progreso_guardado": False,
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

def _crear_estado_anterior_completo():
    """
    Construye un turno terminado con un ejercicio activo.
    """
    estado = crear_estado_inicial(
        "Ponme un ejercicio sobre listas de Python."
    )
    estado["tecnologia"] = "python"
    estado["accion"] = "generar_ejercicio"
    estado["respuesta_final"] = (
        "# Ejercicio\n\nCrea una lista. [fuente-1]"
    )
    estado["ejercicio_actual"] = {
        "tipo": "ejercicio",
        "titulo": "Practica con listas",
        "contenido_markdown": (
            "Crea una lista. [fuente-1]"
        ),
        "fuentes_utilizadas": ["fuente-1"],
        "solucion_esperada": "lista = []",
        "criterios_evaluacion": [
            "Crea una lista vacía.",
        ],
    }
    estado["fuentes_extraidas"] = [
        {
            "id": "fuente-1",
            "url": "https://docs.python.org/3/",
            "contenido": "Documentación sobre listas.",
        }
    ]

    return estado


def test_crear_estado_siguiente_conserva_contexto():
    """
    Conserva historial, tecnología, ejercicio y fuentes.
    """
    anterior = _crear_estado_anterior_completo()

    nuevo = crear_estado_siguiente_turno(
        entrada_usuario="lista = []",
        estado_anterior=anterior,
    )

    assert nuevo["entrada_usuario"] == "lista = []"
    assert nuevo["historial"] == [
        {
            "role": "user",
            "content": (
                "Ponme un ejercicio sobre listas de Python."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "# Ejercicio\n\nCrea una lista. [fuente-1]"
            ),
        },
    ]

    assert nuevo["tecnologia"] == "python"
    assert nuevo["ejercicio_actual"] == (
        anterior["ejercicio_actual"]
    )
    assert nuevo["fuentes_extraidas"] == (
        anterior["fuentes_extraidas"]
    )

    # Los campos temporales empiezan de nuevo.
    assert nuevo["accion"] is None
    assert nuevo["evaluacion"] is None
    assert nuevo["respuesta_final"] is None
    assert nuevo["errores"] == []
    assert nuevo["progreso_guardado"] is False


def test_crear_estado_siguiente_no_comparte_estructuras():
    """
    Impide que modificar el turno nuevo cambie el anterior.
    """
    anterior = _crear_estado_anterior_completo()
    copia_anterior = deepcopy(
        anterior
    )

    nuevo = crear_estado_siguiente_turno(
        entrada_usuario="lista = []",
        estado_anterior=anterior,
    )

    nuevo["historial"][0]["content"] = "modificado"
    nuevo["ejercicio_actual"]["titulo"] = "modificado"
    nuevo["fuentes_extraidas"][0]["contenido"] = "modificado"

    assert anterior == copia_anterior


def test_crear_estado_siguiente_limita_historial():
    """
    Conserva únicamente los veinte mensajes más recientes.
    """
    anterior = _crear_estado_anterior_completo()
    anterior["historial"] = [
        {
            "role": (
                "user"
                if indice % 2 == 0
                else "assistant"
            ),
            "content": f"Mensaje {indice}",
        }
        for indice in range(20)
    ]

    nuevo = crear_estado_siguiente_turno(
        entrada_usuario="Nuevo mensaje",
        estado_anterior=anterior,
    )

    assert len(nuevo["historial"]) == 20

    # Los dos mensajes más antiguos han sido descartados.
    assert nuevo["historial"][0]["content"] == "Mensaje 2"
    assert nuevo["historial"][-1]["role"] == "assistant"
    assert nuevo["historial"][-1]["content"] == (
        anterior["respuesta_final"]
    )


def test_crear_estado_siguiente_requiere_turno_finalizado():
    """
    No incorpora al historial un turno sin respuesta final.
    """
    anterior = _crear_estado_anterior_completo()
    anterior["respuesta_final"] = None

    with pytest.raises(
        ValueError,
        match="no contiene una respuesta final",
    ):
        crear_estado_siguiente_turno(
            entrada_usuario="Nuevo mensaje",
            estado_anterior=anterior,
        )


def test_crear_estado_siguiente_rechaza_historial_invalido():
    """
    Valida también los mensajes procedentes de turnos anteriores.
    """
    anterior = _crear_estado_anterior_completo()
    anterior["historial"] = [
        {
            "role": "system",
            "content": "Mensaje no permitido",
        }
    ]

    with pytest.raises(
        ValueError,
        match="rol del historial no está permitido",
    ):
        crear_estado_siguiente_turno(
            entrada_usuario="Nuevo mensaje",
            estado_anterior=anterior,
        )
