import json  # Crea archivos JSON temporales durante las pruebas.

import pytest  # Comprueba las excepciones esperadas.
from pydantic import ValidationError  # Detecta casos individuales inválidos.

from nivel_experto.evaluacion.casos import (
    CasoEvaluacion,
    cargar_casos_evaluacion,
)


def _crear_caso_valido(
    identificador="CP-001",
):
    """
    Construye un caso correcto reutilizable en las pruebas.
    """
    return {
        "id": identificador,
        "categoria": "consulta_python",
        "entrada": "¿Qué hace append en Python?",
        "contexto_previo": None,
        "accion_esperada": "responder_consulta",
        "tecnologia_esperada": "python",
        "criterios": [
            "Debe utilizar documentación oficial.",
            "Debe citar al menos una fuente.",
        ],
    }


def _guardar_json(
    ruta,
    contenido,
):
    """
    Guarda datos temporales con la misma codificación del proyecto.
    """
    ruta.write_text(
        json.dumps(
            contenido,
            ensure_ascii=False,
            indent=4,
        ),
        encoding="utf-8",
    )


def test_cargar_catalogo_real():
    """
    Comprueba el archivo de evaluación incluido en el proyecto.
    """
    casos = cargar_casos_evaluacion()

    assert len(casos) == 8
    assert casos[0].id == "CP-001"
    assert casos[-1].id == "CP-008"

    # Todos los elementos deben haberse convertido en modelos.
    assert all(
        isinstance(caso, CasoEvaluacion)
        for caso in casos
    )


def test_caso_rechaza_identificador_invalido():
    """
    El identificador debe respetar el patrón CP-NNN.
    """
    datos = _crear_caso_valido(
        identificador="caso-1"
    )

    with pytest.raises(
        ValidationError,
        match="string_pattern_mismatch",
    ):
        CasoEvaluacion.model_validate(
            datos
        )


def test_caso_rechaza_campo_adicional():
    """
    Impide introducir propiedades no contempladas.
    """
    datos = _crear_caso_valido()
    datos["campo_inventado"] = "valor"

    with pytest.raises(
        ValidationError,
        match="extra_forbidden",
    ):
        CasoEvaluacion.model_validate(
            datos
        )


def test_caso_rechaza_criterios_repetidos():
    """
    Detecta criterios duplicados aunque cambien las mayúsculas.
    """
    datos = _crear_caso_valido()
    datos["criterios"] = [
        "Debe citar una fuente.",
        "debe citar una fuente.",
    ]

    with pytest.raises(
        ValidationError,
        match="criterios repetidos",
    ):
        CasoEvaluacion.model_validate(
            datos
        )


def test_cargar_rechaza_json_invalido(
    tmp_path,
):
    """
    Un archivo mal formado produce un error controlado.
    """
    ruta = tmp_path / "casos_invalidos.json"

    # Escribe deliberadamente un JSON incompleto.
    ruta.write_text(
        "[{",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="JSON válido",
    ):
        cargar_casos_evaluacion(
            ruta
        )


def test_cargar_rechaza_objeto_en_lugar_de_lista(
    tmp_path,
):
    """
    El nivel superior del archivo debe ser una lista.
    """
    ruta = tmp_path / "casos_objeto.json"

    _guardar_json(
        ruta,
        _crear_caso_valido(),
    )

    with pytest.raises(
        RuntimeError,
        match="debe contener una lista",
    ):
        cargar_casos_evaluacion(
            ruta
        )


def test_cargar_rechaza_lista_vacia(
    tmp_path,
):
    """
    El conjunto debe contener al menos un caso.
    """
    ruta = tmp_path / "casos_vacios.json"

    _guardar_json(
        ruta,
        [],
    )

    with pytest.raises(
        ValueError,
        match="al menos un caso",
    ):
        cargar_casos_evaluacion(
            ruta
        )


def test_cargar_rechaza_identificadores_repetidos(
    tmp_path,
):
    """
    Cada resultado debe poder asociarse a un único caso.
    """
    ruta = tmp_path / "casos_repetidos.json"

    _guardar_json(
        ruta,
        [
            _crear_caso_valido("CP-001"),
            _crear_caso_valido("CP-001"),
        ],
    )

    with pytest.raises(
        ValueError,
        match="está repetido",
    ):
        cargar_casos_evaluacion(
            ruta
        )