import pytest  # Comprueba rutas y errores esperados.
import logging  # Construye loggers aislados para probar los nodos.

from nivel_experto.tutor_multiagente.agentes.esquemas import (
    BorradorTutor,
    RevisionBorrador,
)
from nivel_experto.tutor_multiagente.config import (
    MAX_REVISIONES_BORRADOR,
)
from nivel_experto.tutor_multiagente.estado import (
    crear_estado_inicial,
)
from nivel_experto.tutor_multiagente.orquestacion.langgraph_tutor import (
    enrutar_despues_coordinador,
    enrutar_despues_revision,
    crear_nodo_coordinador,
    crear_nodo_investigador,
    crear_nodo_correccion,
    crear_nodo_revision,
    crear_nodo_finalizacion_revision,
    crear_nodo_evaluacion,
    crear_grafo_tutor,
)
from nivel_experto.tutor_multiagente.orquestacion import (
    langgraph_tutor as modulo_langgraph_tutor,
)


@pytest.mark.parametrize(
    ("accion", "ruta_esperada"),
    [
        (
            "responder_consulta",
            "investigar",
        ),
        (
            "generar_ejercicio",
            "investigar",
        ),
        (
            "evaluar_respuesta",
            "evaluar",
        ),
        (
            "pedir_aclaracion",
            "finalizar",
        ),
    ],
)
def test_enrutar_despues_coordinador(
    accion,
    ruta_esperada,
):
    """
    Relaciona cada decisión del coordinador con su ruta.
    """
    estado = crear_estado_inicial(
        "Petición de prueba"
    )
    estado["accion"] = accion

    assert enrutar_despues_coordinador(
        estado
    ) == ruta_esperada


def test_enrutar_coordinador_rechaza_accion_desconocida():
    """
    Mantiene una defensa adicional ante un estado manipulado.
    """
    estado = crear_estado_inicial(
        "Petición de prueba"
    )
    estado["accion"] = "accion_inventada"

    with pytest.raises(
        RuntimeError,
        match="acción no contemplada",
    ):
        enrutar_despues_coordinador(
            estado
        )


def _crear_revision_grafo(
    aprobado,
) -> RevisionBorrador:
    """
    Construye una revisión aprobada o rechazada.
    """
    if aprobado:
        return RevisionBorrador(
            aprobado=True,
            fuentes_comprobadas=["fuente-1"],
            problemas_detectados=[],
            instrucciones_revision=None,
            resumen_revision=(
                "El borrador está respaldado por la fuente."
            ),
        )

    return RevisionBorrador(
        aprobado=False,
        fuentes_comprobadas=["fuente-1"],
        problemas_detectados=[
            "Existe un problema material.",
        ],
        instrucciones_revision=(
            "Corrige el problema utilizando la fuente."
        ),
        resumen_revision=(
            "El borrador necesita una corrección."
        ),
    )


def test_enrutar_revision_aprobada_finaliza():
    """
    Un borrador aprobado nunca vuelve al redactor.
    """
    estado = crear_estado_inicial(
        "Petición de prueba"
    )
    estado["revision_actual"] = (
        _crear_revision_grafo(True)
    )
    estado["iteraciones_revision"] = 1

    assert enrutar_despues_revision(
        estado
    ) == "finalizar"


def test_enrutar_primera_revision_rechazada_corrige():
    """
    La primera revisión rechazada permite una corrección.
    """
    estado = crear_estado_inicial(
        "Petición de prueba"
    )
    estado["revision_actual"] = (
        _crear_revision_grafo(False)
    )
    estado["iteraciones_revision"] = 1

    assert enrutar_despues_revision(
        estado
    ) == "corregir"


def test_enrutar_ultima_revision_rechazada_finaliza():
    """
    El límite impide una segunda corrección.
    """
    estado = crear_estado_inicial(
        "Petición de prueba"
    )
    estado["revision_actual"] = (
        _crear_revision_grafo(False)
    )
    estado["iteraciones_revision"] = (
        MAX_REVISIONES_BORRADOR
    )

    assert enrutar_despues_revision(
        estado
    ) == "finalizar"


def test_enrutar_revision_requiere_modelo_validado():
    """
    No confía directamente en un diccionario externo.
    """
    estado = crear_estado_inicial(
        "Petición de prueba"
    )
    estado["revision_actual"] = {
        "aprobado": True,
    }
    estado["iteraciones_revision"] = 1

    with pytest.raises(
        RuntimeError,
        match="revisión validada",
    ):
        enrutar_despues_revision(
            estado
        )


@pytest.mark.parametrize(
    "contador_invalido",
    [
        None,
        True,
        0,
        MAX_REVISIONES_BORRADOR + 1,
    ],
)
def test_enrutar_revision_rechaza_contador_invalido(
    contador_invalido,
):
    """
    Impide utilizar contadores ausentes o fuera del límite.
    """
    estado = crear_estado_inicial(
        "Petición de prueba"
    )
    estado["revision_actual"] = (
        _crear_revision_grafo(False)
    )
    estado["iteraciones_revision"] = contador_invalido

    with pytest.raises(
        RuntimeError,
        match="contador de revisiones",
    ):
        enrutar_despues_revision(
            estado
        )

def _crear_borrador_langgraph() -> BorradorTutor:
    """
    Construye un borrador documentado para los nodos.
    """
    return BorradorTutor(
        tipo="explicacion",
        titulo="Método append",
        contenido_markdown=(
            "`append` añade un elemento a una lista. [fuente-1]"
        ),
        fuentes_utilizadas=["fuente-1"],
        solucion_esperada=None,
        criterios_evaluacion=[],
    )

def _crear_estado_revision_langgraph():
    """
    Construye un estado preparado para revisar un borrador.
    """
    estado = crear_estado_inicial(
        "¿Qué hace append?"
    )
    estado.update(
        {
            "accion": "responder_consulta",
            "tecnologia": "python",
            "consulta_documentacion": "método append",
            "requiere_documentacion": True,
            "fuentes_extraidas": [
                {
                    "id": "fuente-1",
                    "url": "https://docs.python.org/3/",
                    "contenido": "Documentación oficial de append.",
                }
            ],
            "borrador_actual": _crear_borrador_langgraph(),
            "iteraciones_revision": 0,
        }
    )

    return estado

def test_nodo_coordinador_reutiliza_orquestacion_manual(
    monkeypatch,
):
    """
    Comprueba la delegación y la inyección de dependencias.
    """
    datos_recibidos = {}

    def coordinador_simulado(
        estado,
        cliente=None,
        logger=None,
    ):
        """Conserva las dependencias entregadas al nodo."""
        datos_recibidos["estado"] = estado
        datos_recibidos["cliente"] = cliente
        datos_recibidos["logger"] = logger

        return {
            "accion": "pedir_aclaracion",
            "respuesta_final": "¿Qué tecnología quieres estudiar?",
        }

    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_coordinador_desde_estado",
        coordinador_simulado,
    )

    cliente = object()
    logger = logging.Logger(
        "nodo_coordinador_prueba"
    )

    nodo = crear_nodo_coordinador(
        cliente=cliente,
        logger=logger,
    )
    estado = crear_estado_inicial(
        "Explícame cómo funciona."
    )

    actualizacion = nodo(
        estado
    )

    assert datos_recibidos["estado"] is estado
    assert datos_recibidos["cliente"] is cliente
    assert datos_recibidos["logger"] is logger
    assert actualizacion["accion"] == "pedir_aclaracion"


def test_nodo_investigador_guarda_borrador_validado(
    monkeypatch,
):
    """
    Conserva resultados, fuentes y modelo interno del borrador.
    """
    borrador = _crear_borrador_langgraph()

    resultado = {
        "resultados_busqueda": [
            {
                "id": "resultado-1",
                "titulo": "Estructuras de datos",
                "url": "https://docs.python.org/3/",
                "resumen": "Métodos de listas.",
                "puntuacion": 0.9,
            }
        ],
        "fuentes_extraidas": [
            {
                "id": "fuente-1",
                "url": "https://docs.python.org/3/",
                "contenido": "Documentación de append.",
            }
        ],
        "borrador": borrador,
    }

    datos_recibidos = {}

    def investigacion_simulada(**parametros):
        """Sustituye Groq y Tavily."""
        datos_recibidos.update(
            parametros
        )
        return resultado

    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_investigacion_completa",
        investigacion_simulada,
    )

    estado = crear_estado_inicial(
        "¿Qué hace append?"
    )
    estado.update(
        {
            "accion": "responder_consulta",
            "tecnologia": "python",
            "consulta_documentacion": "método append",
            "requiere_documentacion": True,
        }
    )

    nodo = crear_nodo_investigador(
        cliente_busqueda=object(),
        cliente_seleccion=object(),
        cliente_extraccion=object(),
        cliente_redaccion=object(),
        logger=logging.Logger(
            "nodo_investigador_prueba"
        ),
    )

    actualizacion = nodo(
        estado
    )

    assert actualizacion["borrador_actual"] is borrador
    assert actualizacion["iteraciones_revision"] == 0
    assert len(actualizacion["resultados_busqueda"]) == 1
    assert len(actualizacion["fuentes_extraidas"]) == 1

    assert datos_recibidos["accion"] == "responder_consulta"
    assert datos_recibidos["tecnologia"] == "python"
    assert datos_recibidos["peticion_usuario"] == (
        "¿Qué hace append?"
    )


def test_nodo_investigador_rechaza_borrador_no_validado(
    monkeypatch,
):
    """
    Impide que un diccionario externo circule como modelo interno.
    """
    resultado = {
        "resultados_busqueda": [],
        "fuentes_extraidas": [],
        "borrador": {
            "tipo": "explicacion",
        },
    }

    # En esta prueba se aísla la comprobación final del nodo.
    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_investigacion_completa",
        lambda **parametros: resultado,
    )
    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "crear_actualizacion_investigador",
        lambda resultado: {
            "resultados_busqueda": [],
            "fuentes_extraidas": [],
            "respuesta_borrador": "Borrador simulado.",
            "ejercicio_actual": None,
        },
    )

    estado = crear_estado_inicial(
        "¿Qué hace append?"
    )
    estado.update(
        {
            "accion": "responder_consulta",
            "tecnologia": "python",
            "consulta_documentacion": "método append",
            "requiere_documentacion": True,
        }
    )

    nodo = crear_nodo_investigador()

    with pytest.raises(
        RuntimeError,
        match="borrador validado",
    ):
        nodo(
            estado
        )

def test_nodo_revision_incrementa_contador(
    monkeypatch,
):
    """
    La primera ejecución registra exactamente una revisión.
    """
    revision = _crear_revision_grafo(
        True
    )
    datos_recibidos = {}

    def revision_simulada(**parametros):
        """Sustituye al evaluador real."""
        datos_recibidos.update(
            parametros
        )
        return revision

    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_revision_borrador",
        revision_simulada,
    )

    cliente = object()
    estado = _crear_estado_revision_langgraph()

    nodo = crear_nodo_revision(
        cliente=cliente,
        logger=logging.Logger(
            "nodo_revision_prueba"
        ),
    )
    actualizacion = nodo(
        estado
    )

    assert actualizacion["revision_actual"] is revision
    assert actualizacion["iteraciones_revision"] == 1
    assert datos_recibidos["borrador"] is (
        estado["borrador_actual"]
    )
    assert datos_recibidos["cliente"] is cliente


def test_nodo_revision_rechaza_contador_agotado():
    """
    Impide ejecutar una tercera revisión.
    """
    estado = _crear_estado_revision_langgraph()
    estado["iteraciones_revision"] = (
        MAX_REVISIONES_BORRADOR
    )

    nodo = crear_nodo_revision()

    with pytest.raises(
        RuntimeError,
        match="contador anterior",
    ):
        nodo(
            estado
        )


def test_nodo_correccion_produce_nuevo_borrador(
    monkeypatch,
):
    """
    Utiliza borrador y revisión rechazados para producir otra versión.
    """
    estado = _crear_estado_revision_langgraph()
    revision = _crear_revision_grafo(
        False
    )
    estado["revision_actual"] = revision
    estado["iteraciones_revision"] = 1

    borrador_corregido = BorradorTutor(
        tipo="explicacion",
        titulo="Método append corregido",
        contenido_markdown=(
            "`append` añade un único elemento. [fuente-1]"
        ),
        fuentes_utilizadas=["fuente-1"],
        solucion_esperada=None,
        criterios_evaluacion=[],
    )

    datos_recibidos = {}

    def correccion_simulada(**parametros):
        """Sustituye al redactor real."""
        datos_recibidos.update(
            parametros
        )
        return borrador_corregido

    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_correccion_borrador",
        correccion_simulada,
    )

    cliente = object()
    nodo = crear_nodo_correccion(
        cliente=cliente,
        logger=logging.Logger(
            "nodo_correccion_prueba"
        ),
    )

    actualizacion = nodo(
        estado
    )

    assert actualizacion["borrador_actual"] is borrador_corregido
    assert actualizacion["ejercicio_actual"] is None
    assert actualizacion["respuesta_borrador"].startswith(
        "# Método append corregido"
    )

    assert datos_recibidos["borrador_anterior"] is (
        estado["borrador_actual"]
    )
    assert datos_recibidos["revision"] is revision
    assert datos_recibidos["cliente"] is cliente


def test_nodo_correccion_rechaza_revision_aprobada():
    """
    Una revisión aprobada nunca debe entrar en el ciclo.
    """
    estado = _crear_estado_revision_langgraph()
    estado["revision_actual"] = (
        _crear_revision_grafo(True)
    )
    estado["iteraciones_revision"] = 1

    nodo = crear_nodo_correccion()

    with pytest.raises(
        RuntimeError,
        match="borrador aprobado",
    ):
        nodo(
            estado
        )


def test_nodo_correccion_rechaza_ultima_iteracion():
    """
    El límite impide corregir después de la segunda revisión.
    """
    estado = _crear_estado_revision_langgraph()
    estado["revision_actual"] = (
        _crear_revision_grafo(False)
    )
    estado["iteraciones_revision"] = (
        MAX_REVISIONES_BORRADOR
    )

    nodo = crear_nodo_correccion()

    with pytest.raises(
        RuntimeError,
        match="no está permitida",
    ):
        nodo(
            estado
        )

def test_nodo_finalizacion_publica_borrador_aprobado():
    """
    Un borrador aprobado se convierte en respuesta final.
    """
    estado = _crear_estado_revision_langgraph()
    estado["revision_actual"] = (
        _crear_revision_grafo(True)
    )
    estado["iteraciones_revision"] = 1

    nodo = crear_nodo_finalizacion_revision()
    actualizacion = nodo(
        estado
    )

    # El estudiante puede ver el contenido aprobado.
    assert actualizacion["respuesta_final"].startswith(
        "# Método append"
    )

    # No debe registrarse ningún error.
    assert actualizacion["errores"] == []

    # La primera aprobación no necesitó correcciones.
    assert actualizacion["iteraciones_revision"] == 1


def test_nodo_finalizacion_oculta_borrador_rechazado():
    """
    Un rechazo definitivo nunca muestra el borrador al estudiante.
    """
    estado = _crear_estado_revision_langgraph()
    estado["revision_actual"] = (
        _crear_revision_grafo(False)
    )
    estado["iteraciones_revision"] = (
        MAX_REVISIONES_BORRADOR
    )

    nodo = crear_nodo_finalizacion_revision()
    actualizacion = nodo(
        estado
    )

    # Se devuelve un mensaje seguro en lugar del borrador rechazado.
    assert actualizacion["respuesta_final"] == (
        "No he podido generar una respuesta suficientemente "
        "respaldada por las fuentes oficiales."
    )

    # El motivo del fallo queda registrado en el estado.
    assert actualizacion["errores"] == [
        "El borrador no superó la revisión del evaluador."
    ]


def test_nodo_finalizacion_impide_rechazo_anticipado():
    """
    Un primer rechazo debe pasar por corrección, no finalizar.
    """
    estado = _crear_estado_revision_langgraph()
    estado["revision_actual"] = (
        _crear_revision_grafo(False)
    )
    estado["iteraciones_revision"] = 1

    nodo = crear_nodo_finalizacion_revision()

    # La utilidad compartida detecta que aún queda una corrección.
    with pytest.raises(
        RuntimeError,
        match="antes del límite",
    ):
        nodo(
            estado
        )

def test_nodo_evaluacion_reutiliza_orquestacion_manual(
    monkeypatch,
    tmp_path,
):
    """
    Comprueba la delegación y la inyección de dependencias.
    """
    datos_recibidos = {}

    def evaluacion_simulada(
        estado,
        cliente=None,
        directorio_progreso=None,
        logger=None,
    ):
        """
        Sustituye la evaluación real sin utilizar Groq ni el disco.
        """
        datos_recibidos["estado"] = estado
        datos_recibidos["cliente"] = cliente
        datos_recibidos["directorio_progreso"] = (
            directorio_progreso
        )
        datos_recibidos["logger"] = logger

        return {
            "respuesta_final": "Evaluación simulada.",
            "evaluacion": {
                "puntuacion": 8,
            },
            "progreso_guardado": True,
            "errores": [],
        }

    # Sustituye únicamente la dependencia usada por este módulo.
    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_evaluacion_desde_estado",
        evaluacion_simulada,
    )

    cliente = object()
    logger = logging.Logger(
        "nodo_evaluacion_prueba"
    )

    estado = crear_estado_inicial(
        "Mi respuesta al ejercicio"
    )
    estado["accion"] = "evaluar_respuesta"

    nodo = crear_nodo_evaluacion(
        cliente=cliente,
        directorio_progreso=tmp_path,
        logger=logger,
    )
    actualizacion = nodo(
        estado
    )

    # Comprueba el resultado devuelto por la orquestación.
    assert actualizacion["respuesta_final"] == (
        "Evaluación simulada."
    )
    assert actualizacion["progreso_guardado"] is True

    # Comprueba que todas las dependencias lleguen correctamente.
    assert datos_recibidos["estado"] is estado
    assert datos_recibidos["cliente"] is cliente
    assert datos_recibidos["directorio_progreso"] == tmp_path
    assert datos_recibidos["logger"] is logger


def test_nodo_evaluacion_rechaza_accion_incorrecta():
    """
    Impide ejecutar la evaluación desde otra ruta del grafo.
    """
    estado = crear_estado_inicial(
        "¿Qué hace append?"
    )
    estado["accion"] = "responder_consulta"

    nodo = crear_nodo_evaluacion(
        logger=logging.Logger(
            "nodo_evaluacion_accion_incorrecta"
        )
    )

    # La validación procede de la orquestación manual reutilizada.
    with pytest.raises(
        ValueError,
        match="no corresponde a una evaluación",
    ):
        nodo(
            estado
        )

def test_crear_grafo_registra_todos_los_nodos():
    """
    Comprueba que el grafo compilado contenga todas las fases.
    """
    grafo = crear_grafo_tutor(
        logger=logging.Logger(
            "estructura_grafo_prueba"
        )
    )

    estructura = grafo.get_graph()

    # LangGraph añade automáticamente sus nodos de inicio y final.
    assert set(estructura.nodes) == {
        "__start__",
        "coordinador",
        "investigador",
        "revision",
        "correccion",
        "finalizacion_revision",
        "evaluacion",
        "__end__",
    }


def test_crear_grafo_contiene_bucle_de_revision():
    """
    Comprueba las conexiones esenciales y el bucle de corrección.
    """
    grafo = crear_grafo_tutor(
        logger=logging.Logger(
            "conexiones_grafo_prueba"
        )
    )

    estructura = grafo.get_graph()

    # Convierte las aristas en parejas fáciles de comparar.
    conexiones = {
        (
            arista.source,
            arista.target,
        )
        for arista in estructura.edges
    }

    # Todo turno empieza por el coordinador.
    assert (
        "__start__",
        "coordinador",
    ) in conexiones

    # La investigación siempre conduce a una revisión.
    assert (
        "investigador",
        "revision",
    ) in conexiones

    # Una corrección vuelve al evaluador: esta es la arista
    # que convierte el flujo en un bucle.
    assert (
        "correccion",
        "revision",
    ) in conexiones

    # Las dos salidas públicas terminan el turno.
    assert (
        "finalizacion_revision",
        "__end__",
    ) in conexiones
    assert (
        "evaluacion",
        "__end__",
    ) in conexiones

def test_grafo_ejecuta_correccion_y_segunda_revision(
    monkeypatch,
):
    """
    Recorre el bucle completo con dependencias simuladas.

    La primera revisión rechaza el borrador, el corrector genera
    una segunda versión y la siguiente revisión la aprueba.
    """
    # Primer borrador producido por el investigador.
    borrador_inicial = BorradorTutor(
        tipo="explicacion",
        titulo="Método append",
        contenido_markdown=(
            "Explicación inicial sobre `append`. [fuente-1]"
        ),
        fuentes_utilizadas=["fuente-1"],
        solucion_esperada=None,
        criterios_evaluacion=[],
    )

    # Segunda versión producida después del rechazo.
    borrador_corregido = BorradorTutor(
        tipo="explicacion",
        titulo="Método append corregido",
        contenido_markdown=(
            "`append` añade un elemento al final "
            "de una lista. [fuente-1]"
        ),
        fuentes_utilizadas=["fuente-1"],
        solucion_esperada=None,
        criterios_evaluacion=[],
    )

    # Fuente mínima con el mismo contrato que utiliza el proyecto.
    fuente_extraida = {
        "id": "fuente-1",
        "url": (
            "https://docs.python.org/3/"
            "tutorial/datastructures.html"
        ),
        "contenido": (
            "list.append(x) añade un elemento "
            "al final de la lista."
        ),
    }

    # Permite comprobar cuántas veces entra el grafo
    # en los nodos de revisión y corrección.
    llamadas = {
        "revision": 0,
        "correccion": 0,
    }

    def coordinador_simulado(
        estado,
        cliente=None,
        logger=None,
    ):
        """
        Envía la petición por la ruta de investigación.
        """
        return {
            "accion": "responder_consulta",
            "tecnologia": "python",
            "consulta_documentacion": "método append",
            "requiere_documentacion": True,
            "respuesta_final": None,
        }

    def investigacion_simulada(**parametros):
        """
        Devuelve una investigación validable sin usar Tavily.
        """
        return {
            "resultados_busqueda": [],
            "fuentes_extraidas": [
                fuente_extraida,
            ],
            "borrador": borrador_inicial,
        }

    def revision_simulada(**parametros):
        """
        Rechaza la primera versión y aprueba la segunda.
        """
        llamadas["revision"] += 1

        if llamadas["revision"] == 1:
            return _crear_revision_grafo(
                False
            )

        return _crear_revision_grafo(
            True
        )

    def correccion_simulada(**parametros):
        """
        Devuelve el borrador corregido sin llamar a Groq.
        """
        llamadas["correccion"] += 1
        return borrador_corregido

    # Sustituye las cuatro operaciones externas antes de construir
    # el grafo, de modo que sus nodos utilicen las simulaciones.
    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_coordinador_desde_estado",
        coordinador_simulado,
    )
    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_investigacion_completa",
        investigacion_simulada,
    )
    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_revision_borrador",
        revision_simulada,
    )
    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_correccion_borrador",
        correccion_simulada,
    )

    # Construye el grafo después de instalar las simulaciones.
    grafo = crear_grafo_tutor(
        logger=logging.Logger(
            "bucle_langgraph_prueba"
        )
    )

    estado_inicial = crear_estado_inicial(
        "¿Qué hace append en Python?"
    )

    # Ejecuta el grafo hasta alcanzar END.
    estado_final = grafo.invoke(
        estado_inicial,

        # Este límite es superior a los seis nodos esperados,
        # pero detectaría un posible bucle infinito.
        config={
            "recursion_limit": 10,
        },
    )

    # El evaluador debe haberse ejecutado dos veces.
    assert llamadas["revision"] == 2

    # Entre ambas revisiones debe existir una sola corrección.
    assert llamadas["correccion"] == 1

    # El estado conserva el número real de revisiones.
    assert estado_final["iteraciones_revision"] == 2

    # La respuesta pública debe proceder de la versión corregida.
    assert estado_final["respuesta_final"].startswith(
        "# Método append corregido"
    )

    # La versión finalmente aprobada no produce errores.
    assert estado_final["errores"] == []

    # La última revisión almacenada debe ser la aprobada.
    assert estado_final["evaluacion"]["aprobado"] is True

def test_grafo_finaliza_directamente_con_aclaracion(
    monkeypatch,
):
    """
    Una petición ambigua termina después del coordinador.
    """
    llamadas = {
        "investigacion": 0,
        "evaluacion": 0,
    }

    def coordinador_simulado(
        estado,
        cliente=None,
        logger=None,
    ):
        """
        Simula una decisión que solicita más información.
        """
        return {
            "accion": "pedir_aclaracion",
            "tecnologia": None,
            "consulta_documentacion": None,
            "requiere_documentacion": False,
            "respuesta_final": (
                "¿Quieres estudiar Python, Java o Git?"
            ),
        }

    def investigacion_prohibida(**parametros):
        """
        Detecta si el grafo entra por una ruta incorrecta.
        """
        llamadas["investigacion"] += 1

        pytest.fail(
            "La aclaración no debe ejecutar la investigación."
        )

    def evaluacion_prohibida(**parametros):
        """
        Detecta una entrada accidental en la evaluación.
        """
        llamadas["evaluacion"] += 1

        pytest.fail(
            "La aclaración no debe evaluar un ejercicio."
        )

    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_coordinador_desde_estado",
        coordinador_simulado,
    )
    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_investigacion_completa",
        investigacion_prohibida,
    )
    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_evaluacion_desde_estado",
        evaluacion_prohibida,
    )

    grafo = crear_grafo_tutor(
        logger=logging.Logger(
            "aclaracion_langgraph_prueba"
        )
    )

    estado_final = grafo.invoke(
        crear_estado_inicial(
            "Explícame cómo funciona."
        ),
        config={
            "recursion_limit": 10,
        },
    )

    # Conserva directamente la aclaración del coordinador.
    assert estado_final["respuesta_final"] == (
        "¿Quieres estudiar Python, Java o Git?"
    )

    # No debe entrar en ninguna de las otras ramas.
    assert llamadas["investigacion"] == 0
    assert llamadas["evaluacion"] == 0

def test_grafo_ejecuta_ruta_de_evaluacion(
    monkeypatch,
    tmp_path,
):
    """
    Una respuesta a un ejercicio pasa directamente al evaluador.
    """
    llamadas = {
        "investigacion": 0,
        "evaluacion": 0,
    }

    def coordinador_simulado(
        estado,
        cliente=None,
        logger=None,
    ):
        """
        Clasifica la entrada como solución de un ejercicio.
        """
        return {
            "accion": "evaluar_respuesta",
            "tecnologia": "python",
            "consulta_documentacion": None,
            "requiere_documentacion": False,
            "respuesta_final": None,
        }

    def investigacion_prohibida(**parametros):
        """
        Impide buscar nuevamente documentación en esta ruta.
        """
        llamadas["investigacion"] += 1

        pytest.fail(
            "La evaluación no debe repetir la investigación."
        )

    def evaluacion_simulada(
        estado,
        cliente=None,
        directorio_progreso=None,
        logger=None,
    ):
        """
        Simula la evaluación y el guardado del progreso.
        """
        llamadas["evaluacion"] += 1

        return {
            "respuesta_final": (
                "## Evaluación del ejercicio\n\n"
                "**Resultado:** Correcta\n\n"
                "**Puntuación:** 9/10"
            ),
            "evaluacion": {
                "respuesta_correcta": True,
                "puntuacion": 9,
            },
            "ejercicio_actual": estado["ejercicio_actual"],
            "progreso_guardado": True,
            "errores": [],
        }

    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_coordinador_desde_estado",
        coordinador_simulado,
    )
    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_investigacion_completa",
        investigacion_prohibida,
    )
    monkeypatch.setattr(
        modulo_langgraph_tutor,
        "ejecutar_evaluacion_desde_estado",
        evaluacion_simulada,
    )

    grafo = crear_grafo_tutor(
        directorio_progreso=tmp_path,
        logger=logging.Logger(
            "evaluacion_langgraph_prueba"
        ),
    )

    estado = crear_estado_inicial(
        "lista = []\nlista.append(5)\nprint(lista)"
    )

    # Simula el contexto conservado de un turno anterior.
    estado["tecnologia"] = "python"
    estado["ejercicio_actual"] = {
        "tipo": "ejercicio",
        "titulo": "Añadir un elemento",
        "contenido_markdown": "Añade el número 5 a una lista.",
        "fuentes_utilizadas": ["fuente-1"],
        "solucion_esperada": (
            "Crear una lista y utilizar append(5)."
        ),
        "criterios_evaluacion": [
            "Crea una lista.",
            "Utiliza append con el número 5.",
        ],
    }
    estado["fuentes_extraidas"] = [
        {
            "id": "fuente-1",
            "url": "https://docs.python.org/3/",
            "contenido": (
                "list.append(x) añade un elemento "
                "al final de la lista."
            ),
        }
    ]

    estado_final = grafo.invoke(
        estado,
        config={
            "recursion_limit": 10,
        },
    )

    # La rama de evaluación se ejecuta exactamente una vez.
    assert llamadas["evaluacion"] == 1

    # No vuelve a consumir una búsqueda de documentación.
    assert llamadas["investigacion"] == 0

    # Conserva la respuesta y el resultado del guardado.
    assert estado_final["respuesta_final"].startswith(
        "## Evaluación del ejercicio"
    )
    assert estado_final["progreso_guardado"] is True
    assert estado_final["evaluacion"]["puntuacion"] == 9