import pytest  # Permite parametrizar casos inválidos.

from pydantic import ValidationError  # Error generado por modelos inválidos.

from nivel_experto.tutor_multiagente.agentes.esquemas import (
    BorradorTutor,
    DecisionCoordinador,
    SeleccionFuentes,
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

def test_seleccion_fuentes_acepta_resultados_suficientes():
    """Comprueba una selección válida de páginas relevantes."""
    seleccion = SeleccionFuentes(
        resultados_seleccionados=[
            "resultado-1",
            "resultado-3",
        ],
        resultados_suficientes=True,
        consulta_extraccion=(
            "  métodos   append y extend   de listas "
        ),
        motivo="Las páginas documentan los métodos solicitados.",
    )

    assert seleccion.resultados_seleccionados == [
        "resultado-1",
        "resultado-3",
    ]
    assert seleccion.resultados_suficientes is True
    assert seleccion.consulta_extraccion == (
        "métodos append y extend de listas"
    )


def test_seleccion_fuentes_acepta_resultados_insuficientes():
    """Comprueba que el agente pueda reconocer una búsqueda inútil."""
    seleccion = SeleccionFuentes(
        resultados_seleccionados=[],
        resultados_suficientes=False,
        consulta_extraccion=None,
        motivo="Los resultados no responden a la consulta.",
    )

    assert seleccion.resultados_seleccionados == []
    assert seleccion.resultados_suficientes is False
    assert seleccion.consulta_extraccion is None


def test_seleccion_fuentes_rechaza_mas_de_tres_resultados():
    """Comprueba el límite de páginas que pueden llegar a Extract."""
    with pytest.raises(ValidationError):
        SeleccionFuentes(
            resultados_seleccionados=[
                "resultado-1",
                "resultado-2",
                "resultado-3",
                "resultado-4",
            ],
            resultados_suficientes=True,
            consulta_extraccion="listas de Python",
            motivo="Selección demasiado grande.",
        )


@pytest.mark.parametrize(
    "identificador",
    [
        "https://docs.python.org/3/",
        "resultado-0",
        "resultado-inventado",
    ],
)
def test_seleccion_fuentes_rechaza_identificador_invalido(
    identificador,
):
    """Comprueba que solo se admitan identificadores internos."""
    with pytest.raises(
        ValidationError,
        match="formato 'resultado-N'",
    ):
        SeleccionFuentes(
            resultados_seleccionados=[
                identificador,
            ],
            resultados_suficientes=True,
            consulta_extraccion="listas de Python",
            motivo="Resultado seleccionado.",
        )


def test_seleccion_fuentes_rechaza_identificadores_duplicados():
    """Comprueba que una página no pueda seleccionarse dos veces."""
    with pytest.raises(
        ValidationError,
        match="dos veces el mismo resultado",
    ):
        SeleccionFuentes(
            resultados_seleccionados=[
                "resultado-1",
                "resultado-1",
            ],
            resultados_suficientes=True,
            consulta_extraccion="listas de Python",
            motivo="Resultado repetido.",
        )


@pytest.mark.parametrize(
    "datos",
    [
        {
            # Afirma que hay fuentes, pero no selecciona ninguna.
            "resultados_seleccionados": [],
            "resultados_suficientes": True,
            "consulta_extraccion": "listas de Python",
            "motivo": "Selección incoherente.",
        },
        {
            # Selecciona una fuente, pero no crea consulta de extracción.
            "resultados_seleccionados": ["resultado-1"],
            "resultados_suficientes": True,
            "consulta_extraccion": None,
            "motivo": "Selección incoherente.",
        },
        {
            # Afirma que no hay fuentes, pero incluye un resultado.
            "resultados_seleccionados": ["resultado-1"],
            "resultados_suficientes": False,
            "consulta_extraccion": None,
            "motivo": "Selección incoherente.",
        },
        {
            # Afirma que no hay fuentes, pero prepara una extracción.
            "resultados_seleccionados": [],
            "resultados_suficientes": False,
            "consulta_extraccion": "listas de Python",
            "motivo": "Selección incoherente.",
        },
    ],
)
def test_seleccion_fuentes_rechaza_combinaciones_incoherentes(datos):
    """Comprueba la relación entre suficiencia, IDs y consulta."""
    with pytest.raises(ValidationError):
        SeleccionFuentes(**datos)


def test_seleccion_fuentes_rechaza_campos_inventados():
    """Comprueba que la salida no pueda añadir propiedades desconocidas."""
    with pytest.raises(ValidationError):
        SeleccionFuentes(
            resultados_seleccionados=[],
            resultados_suficientes=False,
            consulta_extraccion=None,
            motivo="No hay resultados útiles.",
            url_inventada="https://ejemplo.com",
        )


def test_seleccion_fuentes_rechaza_url_en_consulta():
    """Comprueba que la consulta de extracción no contenga una URL."""
    with pytest.raises(
        ValidationError,
        match="no puede contener una URL",
    ):
        SeleccionFuentes(
            resultados_seleccionados=["resultado-1"],
            resultados_suficientes=True,
            consulta_extraccion=(
                "consulta https://docs.python.org/3/"
            ),
            motivo="Resultado oficial.",
        )

def test_borrador_tutor_acepta_explicacion():
    """Comprueba una explicación correctamente fundamentada."""
    borrador = BorradorTutor(
        tipo="explicacion",
        titulo="append frente a extend",
        contenido_markdown=(
            "`append()` añade un elemento, mientras que `extend()` "
            "añade los elementos de un iterable [fuente-1]."
        ),
        fuentes_utilizadas=["fuente-1"],
        solucion_esperada=None,
        criterios_evaluacion=[],
    )

    assert borrador.tipo == "explicacion"
    assert borrador.fuentes_utilizadas == ["fuente-1"]
    assert borrador.solucion_esperada is None
    assert borrador.criterios_evaluacion == []


def test_borrador_tutor_acepta_ejercicio():
    """Comprueba un ejercicio con solución y criterios privados."""
    borrador = BorradorTutor(
        tipo="ejercicio",
        titulo="Practicar métodos de listas",
        contenido_markdown=(
            "Escribe un programa que utilice `append()` y `extend()` "
            "para modificar una lista [fuente-1]."
        ),
        fuentes_utilizadas=["fuente-1"],
        solucion_esperada=(
            "  Debe utilizar append una vez y extend otra vez.  "
        ),
        criterios_evaluacion=[
            " Utiliza append correctamente. ",
            "Utiliza extend correctamente.",
        ],
    )

    assert borrador.tipo == "ejercicio"
    assert borrador.solucion_esperada == (
        "Debe utilizar append una vez y extend otra vez."
    )
    assert borrador.criterios_evaluacion == [
        "Utiliza append correctamente.",
        "Utiliza extend correctamente.",
    ]


@pytest.mark.parametrize(
    "identificador",
    [
        "https://docs.python.org/3/",
        "fuente-0",
        "resultado-1",
    ],
)
def test_borrador_tutor_rechaza_identificador_fuente_invalido(
    identificador,
):
    """Comprueba que solo se admitan IDs internos de extracción."""
    with pytest.raises(
        ValidationError,
        match="formato 'fuente-N'",
    ):
        BorradorTutor(
            tipo="explicacion",
            titulo="Explicación técnica",
            contenido_markdown=(
                "Contenido suficientemente largo con una fuente."
            ),
            fuentes_utilizadas=[identificador],
            solucion_esperada=None,
            criterios_evaluacion=[],
        )


def test_borrador_tutor_rechaza_fuentes_duplicadas():
    """Comprueba que una fuente no pueda declararse dos veces."""
    with pytest.raises(
        ValidationError,
        match="dos veces la misma fuente",
    ):
        BorradorTutor(
            tipo="explicacion",
            titulo="Explicación técnica",
            contenido_markdown=(
                "Contenido basado en la documentación [fuente-1]."
            ),
            fuentes_utilizadas=[
                "fuente-1",
                "fuente-1",
            ],
            solucion_esperada=None,
            criterios_evaluacion=[],
        )


def test_borrador_tutor_rechaza_fuente_sin_cita():
    """Comprueba que toda fuente declarada aparezca en el contenido."""
    with pytest.raises(
        ValidationError,
        match="no aparece citada",
    ):
        BorradorTutor(
            tipo="explicacion",
            titulo="Explicación técnica",
            contenido_markdown=(
                "Contenido suficientemente largo pero sin marcador."
            ),
            fuentes_utilizadas=["fuente-1"],
            solucion_esperada=None,
            criterios_evaluacion=[],
        )


@pytest.mark.parametrize(
    "datos_adicionales",
    [
        {
            "solucion_esperada": "Solución que no corresponde.",
            "criterios_evaluacion": [],
        },
        {
            "solucion_esperada": None,
            "criterios_evaluacion": [
                "Criterio que no corresponde.",
            ],
        },
    ],
)
def test_borrador_tutor_rechaza_explicacion_incoherente(
    datos_adicionales,
):
    """Comprueba que una explicación no contenga datos de ejercicio."""
    with pytest.raises(ValidationError):
        BorradorTutor(
            tipo="explicacion",
            titulo="Explicación técnica",
            contenido_markdown=(
                "Contenido basado en documentación [fuente-1]."
            ),
            fuentes_utilizadas=["fuente-1"],
            **datos_adicionales,
        )


@pytest.mark.parametrize(
    "datos_adicionales",
    [
        {
            "solucion_esperada": None,
            "criterios_evaluacion": [
                "Utiliza correctamente el método.",
            ],
        },
        {
            "solucion_esperada": "Una posible solución correcta.",
            "criterios_evaluacion": [],
        },
    ],
)
def test_borrador_tutor_rechaza_ejercicio_incompleto(
    datos_adicionales,
):
    """Comprueba que un ejercicio tenga solución y criterios."""
    with pytest.raises(ValidationError):
        BorradorTutor(
            tipo="ejercicio",
            titulo="Ejercicio técnico",
            contenido_markdown=(
                "Resuelve el siguiente ejercicio técnico [fuente-1]."
            ),
            fuentes_utilizadas=["fuente-1"],
            **datos_adicionales,
        )


@pytest.mark.parametrize(
    "criterios",
    [
        [
            "   ",
        ],
        [
            "Utiliza correctamente el método.",
            "Utiliza correctamente el método.",
        ],
    ],
)
def test_borrador_tutor_rechaza_criterios_invalidos(criterios):
    """Comprueba criterios vacíos o repetidos."""
    with pytest.raises(ValidationError):
        BorradorTutor(
            tipo="ejercicio",
            titulo="Ejercicio técnico",
            contenido_markdown=(
                "Resuelve el siguiente ejercicio técnico [fuente-1]."
            ),
            fuentes_utilizadas=["fuente-1"],
            solucion_esperada="Una posible solución correcta.",
            criterios_evaluacion=criterios,
        )


def test_borrador_tutor_rechaza_campos_inventados():
    """Comprueba que el modelo no añada propiedades desconocidas."""
    with pytest.raises(ValidationError):
        BorradorTutor(
            tipo="explicacion",
            titulo="Explicación técnica",
            contenido_markdown=(
                "Contenido basado en documentación [fuente-1]."
            ),
            fuentes_utilizadas=["fuente-1"],
            solucion_esperada=None,
            criterios_evaluacion=[],
            respuesta_inventada=True,
        )


def test_borrador_tutor_rechaza_mas_de_tres_fuentes():
    """Comprueba el límite máximo de fuentes del borrador."""
    with pytest.raises(ValidationError):
        BorradorTutor(
            tipo="explicacion",
            titulo="Explicación técnica",
            contenido_markdown=(
                "Contenido basado en [fuente-1], [fuente-2], "
                "[fuente-3] y [fuente-4]."
            ),
            fuentes_utilizadas=[
                "fuente-1",
                "fuente-2",
                "fuente-3",
                "fuente-4",
            ],
            solucion_esperada=None,
            criterios_evaluacion=[],
        )

def test_borrador_rechaza_cita_no_declarada():
    """
    Impide que el contenido cite una fuente que no esté declarada.
    """
    with pytest.raises(
        ValidationError,
        match="fuentes que no están declaradas",
    ):
        BorradorTutor(
            tipo="explicacion",
            titulo="Métodos de listas",
            contenido_markdown=(
                "El método append modifica una lista. [fuente-1] "
                "Esta afirmación utiliza otra fuente. [fuente-99]"
            ),

            # El modelo declara solamente fuente-1.
            fuentes_utilizadas=["fuente-1"],
            solucion_esperada=None,
            criterios_evaluacion=[],
        )