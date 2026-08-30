import json  # Convierte diccionarios en respuestas JSON simuladas.

from copy import deepcopy  # Conserva los parámetros de cada llamada.
from types import SimpleNamespace  # Reproduce objetos del SDK.

import pytest  # Permite comprobar excepciones.

from nivel_experto.tutor_multiagente.agentes.esquemas import (
    BorradorTutor,
    RevisionBorrador,
)
from nivel_experto.tutor_multiagente.orquestacion.revision import (
    crear_actualizacion_revision,
    ejecutar_ciclo_revision_borrador,
)


class CompletionsRevisionSimuladas:
    """
    Simula varias llamadas consecutivas a Groq.
    """

    def __init__(self, respuestas=None):
        self.respuestas = (
            list(respuestas)
            if respuestas is not None
            else []
        )
        self.numero_llamadas = 0
        self.historial_parametros = []

    def create(self, **parametros):
        """Devuelve la siguiente respuesta preparada."""
        self.numero_llamadas += 1
        self.historial_parametros.append(
            deepcopy(parametros)
        )

        indice = self.numero_llamadas - 1

        if indice >= len(self.respuestas):
            raise AssertionError(
                "Se ha realizado una llamada no esperada."
            )

        return self.respuestas[indice]


class ClienteRevisionSimulado:
    """
    Reproduce cliente.chat.completions.create.
    """

    def __init__(self, respuestas=None):
        self.completions = CompletionsRevisionSimuladas(
            respuestas=respuestas,
        )
        self.chat = SimpleNamespace(
            completions=self.completions,
        )


def _crear_respuesta_revision(contenido):
    """
    Construye una respuesta textual simulada de Groq.
    """
    contenido_json = json.dumps(
        contenido,
        ensure_ascii=False,
    )

    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=contenido_json,
                )
            )
        ]
    )


def _crear_fuentes_revision():
    """
    Construye la extracción oficial utilizada durante el ciclo.
    """
    return [
        {
            "id": "fuente-1",
            "url": (
                "https://docs.python.org/3/tutorial/"
                "datastructures.html"
            ),
            "contenido": (
                "list.append(x) añade un elemento al final "
                "de la lista."
            ),
        }
    ]


def _crear_borrador_inicial_revision():
    """
    Construye un borrador válido, aunque semánticamente problemático.
    """
    return BorradorTutor(
        tipo="explicacion",
        titulo="El método append",
        contenido_markdown=(
            "`append` añade una referencia completa. [fuente-1]"
        ),
        fuentes_utilizadas=["fuente-1"],
        solucion_esperada=None,
        criterios_evaluacion=[],
    )

def _crear_resultado_ciclo(
    aprobado=True,
    borrador=None,
    iteraciones=None,
    correcciones=None,
):
    """
    Construye un resultado coherente del ciclo de revisión.
    """
    borrador_validado = (
        borrador
        if borrador is not None
        else _crear_borrador_inicial_revision()
    )

    if aprobado:
        revision = RevisionBorrador(
            aprobado=True,
            fuentes_comprobadas=["fuente-1"],
            problemas_detectados=[],
            instrucciones_revision=None,
            resumen_revision=(
                "El borrador está respaldado por la fuente."
            ),
        )
        iteraciones_finales = (
            1
            if iteraciones is None
            else iteraciones
        )
        correcciones_finales = (
            0
            if correcciones is None
            else correcciones
        )
    else:
        revision = RevisionBorrador(
            aprobado=False,
            fuentes_comprobadas=["fuente-1"],
            problemas_detectados=[
                "La afirmación no está suficientemente respaldada.",
            ],
            instrucciones_revision=(
                "Reformula la afirmación utilizando la fuente."
            ),
            resumen_revision=(
                "El borrador continúa necesitando cambios."
            ),
        )
        iteraciones_finales = (
            2
            if iteraciones is None
            else iteraciones
        )
        correcciones_finales = (
            1
            if correcciones is None
            else correcciones
        )

    return {
        "aprobado": aprobado,
        "borrador": borrador_validado,
        "revision": revision,
        "iteraciones_revision": iteraciones_finales,
        "correcciones_realizadas": correcciones_finales,
    }

def _respuesta_revision_aprobada():
    """
    Prepara una decisión aprobada del evaluador.
    """
    return _crear_respuesta_revision(
        {
            "aprobado": True,
            "fuentes_comprobadas": ["fuente-1"],
            "problemas_detectados": [],
            "instrucciones_revision": None,
            "resumen_revision": (
                "El borrador está respaldado por la fuente."
            ),
        }
    )


def _respuesta_revision_rechazada():
    """
    Prepara una decisión rechazada del evaluador.
    """
    return _crear_respuesta_revision(
        {
            "aprobado": False,
            "fuentes_comprobadas": ["fuente-1"],
            "problemas_detectados": [
                "La afirmación sobre la referencia no está respaldada.",
            ],
            "instrucciones_revision": (
                "Indica únicamente que append añade un elemento "
                "al final de la lista."
            ),
            "resumen_revision": (
                "El borrador necesita una corrección."
            ),
        }
    )


def _respuesta_borrador_corregido():
    """
    Prepara la nueva versión producida por el tutor-investigador.
    """
    return _crear_respuesta_revision(
        {
            "tipo": "explicacion",
            "titulo": "El método append",
            "contenido_markdown": (
                "`append` añade un elemento al final "
                "de la lista. [fuente-1]"
            ),
            "fuentes_utilizadas": ["fuente-1"],
            "solucion_esperada": None,
            "criterios_evaluacion": [],
        }
    )


def test_ciclo_revision_termina_con_aprobacion_inmediata():
    """
    Un borrador aprobado no debe enviarse al corrector.
    """
    cliente_evaluador = ClienteRevisionSimulado(
        respuestas=[
            _respuesta_revision_aprobada(),
        ],
    )
    cliente_correccion = ClienteRevisionSimulado(
        respuestas=[],
    )
    borrador_inicial = _crear_borrador_inicial_revision()

    resultado = ejecutar_ciclo_revision_borrador(
        accion="responder_consulta",
        tecnologia="python",
        peticion_usuario="¿Qué hace append?",
        consulta_documentacion="método append",
        fuentes_extraidas=_crear_fuentes_revision(),
        borrador_inicial=borrador_inicial,
        cliente_evaluador=cliente_evaluador,
        cliente_correccion=cliente_correccion,
    )

    assert resultado["aprobado"] is True
    assert resultado["borrador"] is borrador_inicial
    assert resultado["revision"].aprobado is True
    assert resultado["iteraciones_revision"] == 1
    assert resultado["correcciones_realizadas"] == 0

    assert cliente_evaluador.completions.numero_llamadas == 1
    assert cliente_correccion.completions.numero_llamadas == 0


def test_ciclo_revision_aprueba_despues_de_corregir():
    """
    Comprueba la colaboración evaluador-redactor-evaluador.
    """
    cliente_evaluador = ClienteRevisionSimulado(
        respuestas=[
            _respuesta_revision_rechazada(),
            _respuesta_revision_aprobada(),
        ],
    )
    cliente_correccion = ClienteRevisionSimulado(
        respuestas=[
            _respuesta_borrador_corregido(),
        ],
    )
    borrador_inicial = _crear_borrador_inicial_revision()

    resultado = ejecutar_ciclo_revision_borrador(
        accion="responder_consulta",
        tecnologia="python",
        peticion_usuario="¿Qué hace append?",
        consulta_documentacion="método append",
        fuentes_extraidas=_crear_fuentes_revision(),
        borrador_inicial=borrador_inicial,
        cliente_evaluador=cliente_evaluador,
        cliente_correccion=cliente_correccion,
    )

    assert resultado["aprobado"] is True
    assert resultado["revision"].aprobado is True
    assert resultado["iteraciones_revision"] == 2
    assert resultado["correcciones_realizadas"] == 1

    borrador_final = resultado["borrador"]

    assert isinstance(borrador_final, BorradorTutor)
    assert (
        borrador_final.model_dump()
        != borrador_inicial.model_dump()
    )
    assert "añade un elemento al final" in (
        borrador_final.contenido_markdown
    )

    assert cliente_evaluador.completions.numero_llamadas == 2
    assert cliente_correccion.completions.numero_llamadas == 1


def test_ciclo_revision_termina_tras_segundo_rechazo():
    """
    Un segundo rechazo no puede provocar otra corrección.
    """
    cliente_evaluador = ClienteRevisionSimulado(
        respuestas=[
            _respuesta_revision_rechazada(),
            _respuesta_revision_rechazada(),
        ],
    )
    cliente_correccion = ClienteRevisionSimulado(
        respuestas=[
            _respuesta_borrador_corregido(),
        ],
    )

    resultado = ejecutar_ciclo_revision_borrador(
        accion="responder_consulta",
        tecnologia="python",
        peticion_usuario="¿Qué hace append?",
        consulta_documentacion="método append",
        fuentes_extraidas=_crear_fuentes_revision(),
        borrador_inicial=_crear_borrador_inicial_revision(),
        cliente_evaluador=cliente_evaluador,
        cliente_correccion=cliente_correccion,
    )

    assert resultado["aprobado"] is False
    assert resultado["revision"].aprobado is False
    assert resultado["iteraciones_revision"] == 2
    assert resultado["correcciones_realizadas"] == 1

    assert cliente_evaluador.completions.numero_llamadas == 2
    assert cliente_correccion.completions.numero_llamadas == 1


@pytest.mark.parametrize(
    "borrador_invalido",
    [
        None,
        {},
        "borrador no validado",
    ],
)
def test_ciclo_revision_rechaza_borrador_sin_validar(
    borrador_invalido,
):
    """
    Comprueba la entrada antes de realizar llamadas externas.
    """
    cliente_evaluador = ClienteRevisionSimulado(
        respuestas=[],
    )
    cliente_correccion = ClienteRevisionSimulado(
        respuestas=[],
    )

    with pytest.raises(
        TypeError,
        match="BorradorTutor inicial validado",
    ):
        ejecutar_ciclo_revision_borrador(
            accion="responder_consulta",
            tecnologia="python",
            peticion_usuario="¿Qué hace append?",
            consulta_documentacion="método append",
            fuentes_extraidas=_crear_fuentes_revision(),
            borrador_inicial=borrador_invalido,
            cliente_evaluador=cliente_evaluador,
            cliente_correccion=cliente_correccion,
        )

    assert cliente_evaluador.completions.numero_llamadas == 0
    assert cliente_correccion.completions.numero_llamadas == 0

def test_actualizacion_revision_publica_explicacion_aprobada():
    """
    Una explicación aprobada se convierte en respuesta final.
    """
    resultado = _crear_resultado_ciclo(
        aprobado=True
    )

    actualizacion = crear_actualizacion_revision(
        resultado
    )

    assert actualizacion["respuesta_final"] == (
        actualizacion["respuesta_borrador"]
    )
    assert actualizacion["respuesta_final"].startswith(
        "# El método append\n\n"
    )
    assert "[fuente-1]" in (
        actualizacion["respuesta_final"]
    )

    assert actualizacion["ejercicio_actual"] is None
    assert actualizacion["evaluacion"]["aprobado"] is True
    assert actualizacion["iteraciones_revision"] == 1
    assert actualizacion["errores"] == []


def test_actualizacion_revision_conserva_ejercicio_privado():
    """
    Publica el enunciado pero conserva solución y criterios en el estado.
    """
    borrador = BorradorTutor(
        tipo="ejercicio",
        titulo="Practica con append",
        contenido_markdown=(
            "Añade un elemento a una lista. [fuente-1]"
        ),
        fuentes_utilizadas=["fuente-1"],
        solucion_esperada=(
            "Crear una lista y utilizar lista.append(elemento)."
        ),
        criterios_evaluacion=[
            "Crea una lista.",
            "Utiliza append correctamente.",
        ],
    )

    actualizacion = crear_actualizacion_revision(
        _crear_resultado_ciclo(
            aprobado=True,
            borrador=borrador,
        )
    )

    # La respuesta visible contiene solamente título y enunciado.
    assert actualizacion["respuesta_final"] == (
        "# Practica con append\n\n"
        "Añade un elemento a una lista. [fuente-1]"
    )
    assert "lista.append(elemento)" not in (
        actualizacion["respuesta_final"]
    )

    ejercicio = actualizacion["ejercicio_actual"]

    assert ejercicio["solucion_esperada"] == (
        "Crear una lista y utilizar lista.append(elemento)."
    )
    assert ejercicio["criterios_evaluacion"] == [
        "Crea una lista.",
        "Utiliza append correctamente.",
    ]


def test_actualizacion_revision_oculta_borrador_rechazado():
    """
    Un segundo rechazo produce un mensaje seguro.
    """
    actualizacion = crear_actualizacion_revision(
        _crear_resultado_ciclo(
            aprobado=False
        )
    )

    assert actualizacion["respuesta_final"] == (
        "No he podido generar una respuesta suficientemente "
        "respaldada por las fuentes oficiales."
    )

    # El borrador sigue disponible internamente, pero no se publica.
    assert actualizacion["respuesta_borrador"].startswith(
        "# El método append"
    )
    assert actualizacion["respuesta_final"] != (
        actualizacion["respuesta_borrador"]
    )

    assert actualizacion["ejercicio_actual"] is None
    assert actualizacion["evaluacion"]["aprobado"] is False
    assert actualizacion["iteraciones_revision"] == 2
    assert actualizacion["errores"] == [
        "El borrador no superó la revisión del evaluador."
    ]


def test_actualizacion_revision_devuelve_copias_independientes():
    """
    Modificar el estado no debe alterar los modelos originales.
    """
    resultado = _crear_resultado_ciclo(
        aprobado=True
    )

    actualizacion = crear_actualizacion_revision(
        resultado
    )

    actualizacion["evaluacion"]["resumen_revision"] = (
        "Resumen modificado"
    )

    assert resultado["revision"].resumen_revision == (
        "El borrador está respaldado por la fuente."
    )

@pytest.mark.parametrize(
    "resultado_invalido",
    [
        None,
        [],
        "resultado no estructurado",
    ],
)
def test_actualizacion_revision_rechaza_resultado_no_diccionario(
    resultado_invalido,
):
    """
    Comprueba el tipo general del resultado.
    """
    with pytest.raises(
        TypeError,
        match="debe ser un diccionario",
    ):
        crear_actualizacion_revision(
            resultado_invalido
        )


@pytest.mark.parametrize(
    ("campo", "valor", "mensaje_esperado"),
    [
        (
            "aprobado",
            "sí",
            "decisión de aprobación válida",
        ),
        (
            "borrador",
            {},
            "BorradorTutor válido",
        ),
        (
            "revision",
            {},
            "RevisionBorrador válida",
        ),
        (
            "iteraciones_revision",
            0,
            "número de revisiones",
        ),
        (
            "iteraciones_revision",
            True,
            "número de revisiones",
        ),
        (
            "correcciones_realizadas",
            2,
            "número de correcciones",
        ),
    ],
)
def test_actualizacion_revision_rechaza_campos_invalidos(
    campo,
    valor,
    mensaje_esperado,
):
    """
    Comprueba tipos, límites y contadores del ciclo.
    """
    resultado = _crear_resultado_ciclo(
        aprobado=True
    )
    resultado[campo] = valor

    with pytest.raises(
        RuntimeError,
        match=mensaje_esperado,
    ):
        crear_actualizacion_revision(
            resultado
        )


def test_actualizacion_revision_rechaza_decision_contradictoria():
    """
    La decisión resumida debe coincidir con RevisionBorrador.
    """
    resultado = _crear_resultado_ciclo(
        aprobado=True
    )

    # La revisión sigue aprobada, pero el resumen del ciclo dice lo contrario.
    resultado["aprobado"] = False

    with pytest.raises(
        RuntimeError,
        match="contradice la revisión",
    ):
        crear_actualizacion_revision(
            resultado
        )


def test_actualizacion_revision_rechaza_finalizacion_anticipada():
    """
    Un rechazo definitivo solo puede producirse tras dos revisiones.
    """
    resultado = _crear_resultado_ciclo(
        aprobado=False,
        iteraciones=1,
        correcciones=0,
    )

    with pytest.raises(
        RuntimeError,
        match="antes del límite",
    ):
        crear_actualizacion_revision(
            resultado
        )
