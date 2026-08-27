import pytest  # Permite parametrizar casos inválidos.

from pydantic import ValidationError  # Error generado por modelos inválidos.

from nivel_experto.tutor_multiagente.agentes.esquemas import (
    DecisionCoordinador,
)


def test_decision_coordinador_acepta_consulta_documentada():
    """Comprueba una petición técnica que necesita documentación."""
    decision = DecisionCoordinador(
        accion="responder_consulta",
        tecnologia=" Python ",
        consulta_documentacion="  append   y   extend ",
        requiere_documentacion=True,
        mensaje_aclaracion=None,
    )

    # Los validadores deben normalizar tecnología y consulta.
    assert decision.accion == "responder_consulta"
    assert decision.tecnologia == "python"
    assert decision.consulta_documentacion == "append y extend"
    assert decision.requiere_documentacion is True
    assert decision.mensaje_aclaracion is None


def test_decision_coordinador_acepta_aclaracion():
    """Comprueba una decisión que necesita más información del usuario."""
    decision = DecisionCoordinador(
        accion="pedir_aclaracion",
        tecnologia=None,
        consulta_documentacion=None,
        requiere_documentacion=False,
        mensaje_aclaracion=(
            " ¿Sobre qué tecnología quieres preguntar? "
        ),
    )

    assert decision.accion == "pedir_aclaracion"
    assert decision.tecnologia is None
    assert decision.requiere_documentacion is False
    assert decision.mensaje_aclaracion == (
        "¿Sobre qué tecnología quieres preguntar?"
    )


def test_decision_coordinador_acepta_evaluacion():
    """Comprueba una evaluación que reutilizará el ejercicio guardado."""
    decision = DecisionCoordinador(
        accion="evaluar_respuesta",
        tecnologia="python",
        consulta_documentacion=None,
        requiere_documentacion=False,
        mensaje_aclaracion=None,
    )

    assert decision.accion == "evaluar_respuesta"
    assert decision.tecnologia == "python"
    assert decision.requiere_documentacion is False


def test_decision_coordinador_rechaza_tecnologia_desconocida():
    """Comprueba que el modelo no pueda inventar una tecnología."""
    with pytest.raises(
        ValidationError,
        match="no está registrada",
    ):
        DecisionCoordinador(
            accion="responder_consulta",
            tecnologia="tecnologia-inventada",
            consulta_documentacion="tema cualquiera",
            requiere_documentacion=True,
            mensaje_aclaracion=None,
        )


@pytest.mark.parametrize(
    "datos",
    [
        {
            # Falta la tecnología.
            "accion": "responder_consulta",
            "tecnologia": None,
            "consulta_documentacion": "listas",
            "requiere_documentacion": True,
            "mensaje_aclaracion": None,
        },
        {
            # Falta la consulta.
            "accion": "generar_ejercicio",
            "tecnologia": "python",
            "consulta_documentacion": None,
            "requiere_documentacion": True,
            "mensaje_aclaracion": None,
        },
        {
            # La acción necesita documentación, pero el indicador es falso.
            "accion": "responder_consulta",
            "tecnologia": "git",
            "consulta_documentacion": "ramas remotas",
            "requiere_documentacion": False,
            "mensaje_aclaracion": None,
        },
    ],
)
def test_decision_coordinador_rechaza_acciones_documentadas_incompletas(
    datos,
):
    """Comprueba las condiciones necesarias para consultar fuentes."""
    with pytest.raises(ValidationError):
        DecisionCoordinador(**datos)


@pytest.mark.parametrize(
    "datos",
    [
        {
            # La acción no contiene la pregunta de aclaración.
            "accion": "pedir_aclaracion",
            "tecnologia": None,
            "consulta_documentacion": None,
            "requiere_documentacion": False,
            "mensaje_aclaracion": None,
        },
        {
            # Una aclaración no debe gastar créditos de Tavily.
            "accion": "pedir_aclaracion",
            "tecnologia": None,
            "consulta_documentacion": None,
            "requiere_documentacion": True,
            "mensaje_aclaracion": "¿Qué tecnología quieres estudiar?",
        },
    ],
)
def test_decision_coordinador_rechaza_aclaracion_incoherente(datos):
    """Comprueba que una aclaración tenga un mensaje y no use herramientas."""
    with pytest.raises(ValidationError):
        DecisionCoordinador(**datos)


def test_decision_coordinador_rechaza_evaluacion_con_busqueda():
    """Comprueba que la evaluación reutilice las fuentes ya guardadas."""
    with pytest.raises(
        ValidationError,
        match="no debe iniciar una búsqueda nueva",
    ):
        DecisionCoordinador(
            accion="evaluar_respuesta",
            tecnologia="python",
            consulta_documentacion=None,
            requiere_documentacion=True,
            mensaje_aclaracion=None,
        )


def test_decision_coordinador_rechaza_campos_inventados():
    """Comprueba que el modelo no pueda añadir propiedades desconocidas."""
    with pytest.raises(ValidationError):
        DecisionCoordinador(
            accion="pedir_aclaracion",
            tecnologia=None,
            consulta_documentacion=None,
            requiere_documentacion=False,
            mensaje_aclaracion="¿Qué quieres estudiar?",
            campo_inventado="valor no permitido",
        )


def test_decision_coordinador_rechaza_booleano_como_texto():
    """Comprueba que Pydantic no convierta textos en booleanos."""
    with pytest.raises(ValidationError):
        DecisionCoordinador(
            accion="responder_consulta",
            tecnologia="python",
            consulta_documentacion="listas",
            requiere_documentacion="true",
            mensaje_aclaracion=None,
        )


def test_decision_coordinador_rechaza_accion_inventada():
    """Comprueba que la acción pertenezca al conjunto permitido."""
    with pytest.raises(ValidationError):
        DecisionCoordinador(
            accion="buscar_en_internet",
            tecnologia="python",
            consulta_documentacion="listas",
            requiere_documentacion=True,
            mensaje_aclaracion=None,
        )