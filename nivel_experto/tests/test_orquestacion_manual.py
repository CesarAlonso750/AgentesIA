import json  # Permite inspeccionar eventos estructurados.
import logging  # Crea un logger aislado para las pruebas.
import pytest  # Comprueba las excepciones esperadas.
from copy import deepcopy  # Copia estados sin compartir estructuras mutables.

from nivel_experto.tutor_multiagente.agentes.esquemas import (
    BorradorTutor,
    DecisionCoordinador,
    RevisionBorrador,
)
from nivel_experto.tutor_multiagente.estado import (
    crear_estado_inicial,
)
from nivel_experto.tutor_multiagente.orquestacion import (
    manual as modulo_orquestacion_manual,
)
from nivel_experto.tutor_multiagente.orquestacion.manual import (
    ejecutar_coordinador_desde_estado,
    ejecutar_ruta_documentada_desde_estado,
    ejecutar_turno_manual,
    construir_entrada_coordinador,
)


class HandlerManualSimulado(logging.Handler):
    """
    Conserva eventos sin escribirlos en consola ni fichero.
    """

    def __init__(self):
        super().__init__()
        self.mensajes = []

    def emit(self, record):
        """Conserva el mensaje estructurado."""
        self.mensajes.append(
            record.getMessage()
        )

def _crear_borrador_manual() -> BorradorTutor:
    """
    Construye una explicación documentada.
    """
    return BorradorTutor(
        tipo="explicacion",
        titulo="Método append",
        contenido_markdown=(
            "`append` añade un elemento al final de una lista. "
            "[fuente-1]"
        ),
        fuentes_utilizadas=["fuente-1"],
        solucion_esperada=None,
        criterios_evaluacion=[],
    )


def _crear_revision_manual(
    aprobado=True,
) -> RevisionBorrador:
    """
    Construye una revisión coherente para el flujo manual.
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
            "La explicación contiene un error material.",
        ],
        instrucciones_revision=(
            "Corrige el error utilizando la fuente oficial."
        ),
        resumen_revision=(
            "El borrador necesita una corrección."
        ),
    )


def _crear_estado_documentado() -> dict[str, object]:
    """
    Construye un estado ya clasificado por el coordinador.
    """
    estado = crear_estado_inicial(
        "¿Qué hace append en Python?"
    )
    estado.update(
        {
            "accion": "responder_consulta",
            "tecnologia": "python",
            "consulta_documentacion": "método append de listas",
            "requiere_documentacion": True,
        }
    )

    return estado

def test_ejecutar_coordinador_devuelve_aclaracion(
    monkeypatch,
):
    """
    Una petición ambigua termina directamente con una aclaración.
    """
    decision = DecisionCoordinador(
        accion="pedir_aclaracion",
        tecnologia=None,
        consulta_documentacion=None,
        requiere_documentacion=False,
        mensaje_aclaracion=(
            "¿Sobre qué tecnología necesitas ayuda?"
        ),
    )

    datos_recibidos = {}

    def coordinador_simulado(
        peticion_usuario,
        cliente=None,
    ):
        """Sustituye la llamada real a Groq."""
        datos_recibidos["peticion_usuario"] = (
            peticion_usuario
        )
        datos_recibidos["cliente"] = cliente
        return decision

    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_coordinador",
        coordinador_simulado,
    )

    cliente_simulado = object()
    estado = crear_estado_inicial(
        "  Explícame cómo funciona.  "
    )

    actualizacion = ejecutar_coordinador_desde_estado(
        estado=estado,
        cliente=cliente_simulado,
    )

    datos_coordinador = json.loads(
        datos_recibidos["peticion_usuario"]
    )

    assert datos_coordinador == {
        "entrada_usuario": "Explícame cómo funciona.",
        "hay_ejercicio_activo": False,
        "tecnologia_contexto": None,
        "cantidad_mensajes_historial": 0,
    }
    assert datos_recibidos["cliente"] is cliente_simulado

    assert actualizacion["accion"] == "pedir_aclaracion"
    assert actualizacion["tecnologia"] is None
    assert actualizacion["requiere_documentacion"] is False
    assert actualizacion["respuesta_final"] == (
        "¿Sobre qué tecnología necesitas ayuda?"
    )


def test_ejecutar_coordinador_prepara_consulta_documentada(
    monkeypatch,
):
    """
    Una consulta técnica queda preparada para el investigador.
    """
    decision = DecisionCoordinador(
        accion="responder_consulta",
        tecnologia="python",
        consulta_documentacion=(
            "diferencia entre append y extend"
        ),
        requiere_documentacion=True,
        mensaje_aclaracion=None,
    )

    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_coordinador",
        lambda peticion_usuario, cliente=None: decision,
    )

    estado = crear_estado_inicial(
        "¿Qué diferencia hay entre append y extend?"
    )

    actualizacion = ejecutar_coordinador_desde_estado(
        estado=estado,
    )

    assert actualizacion["accion"] == "responder_consulta"
    assert actualizacion["tecnologia"] == "python"
    assert actualizacion["consulta_documentacion"] == (
        "diferencia entre append y extend"
    )
    assert actualizacion["requiere_documentacion"] is True

    # Todavía no hay respuesta: debe continuar al investigador.
    assert actualizacion["respuesta_final"] is None


def test_ejecutar_coordinador_registra_decision_segura(
    monkeypatch,
):
    """
    Registra la ruta sin guardar la petición original.
    """
    decision = DecisionCoordinador(
        accion="generar_ejercicio",
        tecnologia="python",
        consulta_documentacion="ejercicio sobre listas",
        requiere_documentacion=True,
        mensaje_aclaracion=None,
    )

    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_coordinador",
        lambda peticion_usuario, cliente=None: decision,
    )

    logger = logging.Logger(
        "coordinador_manual_prueba",
        level=logging.INFO,
    )
    handler = HandlerManualSimulado()
    logger.addHandler(
        handler
    )

    estado = crear_estado_inicial(
        "Ponme un ejercicio privado sobre listas."
    )

    ejecutar_coordinador_desde_estado(
        estado=estado,
        logger=logger,
    )

    assert len(handler.mensajes) == 1

    evento = json.loads(
        handler.mensajes[0]
    )

    assert evento == {
        "accion": "generar_ejercicio",
        "evento": "coordinador_completado",
        "resultado": "completado",
        "tecnologia": "python",
    }

    assert estado["entrada_usuario"] not in (
        handler.mensajes[0]
    )


@pytest.mark.parametrize(
    "estado_invalido",
    [
        None,
        [],
        "estado",
    ],
)
def test_ejecutar_coordinador_rechaza_estado_invalido(
    estado_invalido,
):
    """
    Impide invocar al coordinador con estructuras incorrectas.
    """
    with pytest.raises(
        TypeError,
        match="debe ser un diccionario",
    ):
        ejecutar_coordinador_desde_estado(
            estado=estado_invalido,
        )


def test_ejecutar_coordinador_rechaza_entrada_vacia():
    """
    Valida la entrada antes de consumir tokens.
    """
    estado = {
        "entrada_usuario": "   ",
    }

    with pytest.raises(
        ValueError,
        match="no puede estar vacía",
    ):
        ejecutar_coordinador_desde_estado(
            estado=estado,
        )

def test_ejecutar_ruta_documentada_aprobada(
    monkeypatch,
):
    """
    Encadena investigación y revisión sin servicios externos.
    """
    borrador = _crear_borrador_manual()

    resultado_investigacion = {
        "resultados_busqueda": [
            {
                "id": "resultado-1",
                "titulo": "Estructuras de datos",
                "url": (
                    "https://docs.python.org/3/"
                    "tutorial/datastructures.html"
                ),
                "resumen": "Métodos de listas.",
                "puntuacion": 0.9,
            }
        ],
        "seleccion_fuentes": object(),
        "urls_seleccionadas": [
            (
                "https://docs.python.org/3/"
                "tutorial/datastructures.html"
            )
        ],
        "fuentes_extraidas": [
            {
                "id": "fuente-1",
                "url": (
                    "https://docs.python.org/3/"
                    "tutorial/datastructures.html"
                ),
                "contenido": (
                    "list.append(x) añade un elemento al final."
                ),
            }
        ],
        "borrador": borrador,
    }

    datos_revision = {}

    def investigacion_simulada(**parametros):
        """Sustituye las cuatro fases externas."""
        return resultado_investigacion

    def revision_simulada(**parametros):
        """Sustituye el ciclo entre redactor y evaluador."""
        datos_revision.update(
            parametros
        )

        return {
            "aprobado": True,
            "borrador": borrador,
            "revision": _crear_revision_manual(),
            "iteraciones_revision": 1,
            "correcciones_realizadas": 0,
        }

    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_investigacion_completa",
        investigacion_simulada,
    )
    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_ciclo_revision_borrador",
        revision_simulada,
    )

    actualizacion = ejecutar_ruta_documentada_desde_estado(
        estado=_crear_estado_documentado(),
    )

    assert len(actualizacion["resultados_busqueda"]) == 1
    assert len(actualizacion["fuentes_extraidas"]) == 1
    assert actualizacion["ejercicio_actual"] is None
    assert actualizacion["iteraciones_revision"] == 1
    assert actualizacion["errores"] == []

    assert actualizacion["respuesta_final"] == (
        "# Método append\n\n"
        "`append` añade un elemento al final de una lista. "
        "[fuente-1]"
    )

    # La revisión recibe el borrador y las fuentes investigadas.
    assert datos_revision["borrador_inicial"] is borrador
    assert datos_revision["fuentes_extraidas"] == (
        resultado_investigacion["fuentes_extraidas"]
    )


def test_ejecutar_ruta_documentada_registra_fases(
    monkeypatch,
):
    """
    Registra fases y contadores sin guardar contenido documental.
    """
    borrador = _crear_borrador_manual()

    resultado_investigacion = {
        "resultados_busqueda": [
            {
                "id": "resultado-1",
                "titulo": "Título que no debe registrarse",
                "url": "https://docs.python.org/3/",
                "resumen": "Resumen que no debe registrarse",
                "puntuacion": 0.9,
            }
        ],
        "fuentes_extraidas": [
            {
                "id": "fuente-1",
                "url": "https://docs.python.org/3/",
                "contenido": "Contenido que no debe registrarse",
            }
        ],
        "borrador": borrador,
    }

    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_investigacion_completa",
        lambda **parametros: resultado_investigacion,
    )
    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_ciclo_revision_borrador",
        lambda **parametros: {
            "aprobado": True,
            "borrador": borrador,
            "revision": _crear_revision_manual(),
            "iteraciones_revision": 1,
            "correcciones_realizadas": 0,
        },
    )

    logger = logging.Logger(
        "ruta_documentada_prueba",
        level=logging.INFO,
    )
    handler = HandlerManualSimulado()
    logger.addHandler(
        handler
    )

    ejecutar_ruta_documentada_desde_estado(
        estado=_crear_estado_documentado(),
        logger=logger,
    )

    eventos = [
        json.loads(mensaje)
        for mensaje in handler.mensajes
    ]

    assert [
        evento["evento"]
        for evento in eventos
    ] == [
        "busqueda_completada",
        "extraccion_completada",
        "borrador_generado",
        "revision_completada",
    ]

    assert eventos[0]["cantidad_resultados"] == 1
    assert eventos[1]["cantidad_fuentes"] == 1
    assert eventos[3]["resultado"] == "aprobada"

    contenido_logs = "\n".join(
        handler.mensajes
    )

    assert "Título que no debe registrarse" not in contenido_logs
    assert "Contenido que no debe registrarse" not in contenido_logs


def test_ejecutar_ruta_documentada_rechaza_accion_incorrecta():
    """
    Impide entrar en esta ruta desde una evaluación o aclaración.
    """
    estado = _crear_estado_documentado()
    estado["accion"] = "evaluar_respuesta"

    with pytest.raises(
        ValueError,
        match="no corresponde a una ruta documentada",
    ):
        ejecutar_ruta_documentada_desde_estado(
            estado=estado,
        )

def test_ejecutar_turno_manual_termina_con_aclaracion(
    monkeypatch,
):
    """
    La aclaración no debe ejecutar investigación ni evaluación.
    """
    def coordinador_simulado(
        estado,
        cliente=None,
        logger=None,
    ):
        """Devuelve directamente la ruta de aclaración."""
        return {
            "accion": "pedir_aclaracion",
            "tecnologia": None,
            "consulta_documentacion": None,
            "requiere_documentacion": False,
            "mensaje_aclaracion": (
                "¿Sobre qué tecnología necesitas ayuda?"
            ),
            "respuesta_final": (
                "¿Sobre qué tecnología necesitas ayuda?"
            ),
        }

    def ruta_no_permitida(*args, **kwargs):
        """Falla si el enrutador continúa indebidamente."""
        raise AssertionError(
            "No debía ejecutarse esta ruta."
        )

    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_coordinador_desde_estado",
        coordinador_simulado,
    )
    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_ruta_documentada_desde_estado",
        ruta_no_permitida,
    )
    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_evaluacion_desde_estado",
        ruta_no_permitida,
    )

    estado_original = crear_estado_inicial(
        "Explícame cómo funciona."
    )

    resultado = ejecutar_turno_manual(
        estado_original
    )

    assert resultado["accion"] == "pedir_aclaracion"
    assert resultado["respuesta_final"] == (
        "¿Sobre qué tecnología necesitas ayuda?"
    )

    # El estado original permanece sin modificar.
    assert estado_original["accion"] is None
    assert estado_original["respuesta_final"] is None


def test_ejecutar_turno_manual_envia_consulta_a_documentacion(
    monkeypatch,
):
    """
    Enruta responder_consulta hacia investigación y revisión.
    """
    datos_ruta = {}

    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_coordinador_desde_estado",
        lambda estado, cliente=None, logger=None: {
            "accion": "responder_consulta",
            "tecnologia": "python",
            "consulta_documentacion": "método append",
            "requiere_documentacion": True,
            "mensaje_aclaracion": None,
            "respuesta_final": None,
        },
    )

    def ruta_documentada_simulada(
        estado,
        **parametros,
    ):
        """Conserva el estado recibido y simula la respuesta."""
        datos_ruta["estado"] = deepcopy(
            estado
        )
        datos_ruta["parametros"] = parametros

        return {
            "respuesta_final": (
                "# Método append\n\nExplicación aprobada."
            ),
            "errores": [],
        }

    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_ruta_documentada_desde_estado",
        ruta_documentada_simulada,
    )

    estado_original = crear_estado_inicial(
        "¿Qué hace append?"
    )

    resultado = ejecutar_turno_manual(
        estado=estado_original,
    )

    assert datos_ruta["estado"]["accion"] == (
        "responder_consulta"
    )
    assert datos_ruta["estado"]["tecnologia"] == "python"
    assert resultado["respuesta_final"] == (
        "# Método append\n\nExplicación aprobada."
    )

    # Sigue sin modificar el objeto original.
    assert estado_original["respuesta_final"] is None


def test_ejecutar_turno_manual_evalua_ejercicio_anterior(
    monkeypatch,
    tmp_path,
):
    """
    Conserva tecnología, ejercicio y fuentes entre la decisión y evaluación.
    """
    estado = crear_estado_inicial(
        "lista = []\nlista.append(5)\nprint(lista)"
    )

    # Simula el contexto conservado desde el turno anterior.
    estado["tecnologia"] = "python"
    estado["ejercicio_actual"] = {
        "tipo": "ejercicio",
        "titulo": "Practica con append",
        "contenido_markdown": (
            "Crea una lista y añade el número 5. [fuente-1]"
        ),
        "fuentes_utilizadas": ["fuente-1"],
        "solucion_esperada": (
            "lista = []\nlista.append(5)\nprint(lista)"
        ),
        "criterios_evaluacion": [
            "Crea una lista.",
            "Utiliza append.",
            "Muestra la lista.",
        ],
    }
    estado["fuentes_extraidas"] = [
        {
            "id": "fuente-1",
            "url": "https://docs.python.org/3/",
            "contenido": "Documentación de append.",
        }
    ]

    # La respuesta aislada no menciona explícitamente Python.
    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_coordinador_desde_estado",
        lambda estado, cliente=None, logger=None: {
            "accion": "evaluar_respuesta",
            "tecnologia": None,
            "consulta_documentacion": None,
            "requiere_documentacion": False,
            "mensaje_aclaracion": None,
            "respuesta_final": None,
        },
    )

    datos_evaluacion = {}

    def evaluacion_simulada(
        estado,
        cliente=None,
        directorio_progreso=None,
        logger=None,
    ):
        """Comprueba el contexto recibido por la ruta."""
        datos_evaluacion["estado"] = deepcopy(
            estado
        )
        datos_evaluacion["directorio"] = (
            directorio_progreso
        )

        return {
            "evaluacion": {
                "respuesta_correcta": True,
                "puntuacion": 10,
            },
            "respuesta_final": "Evaluación completada.",
            "progreso_guardado": True,
            "errores": [],
        }

    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_evaluacion_desde_estado",
        evaluacion_simulada,
    )

    resultado = ejecutar_turno_manual(
        estado=estado,
        directorio_progreso=tmp_path,
    )

    # Recupera la tecnología previa en lugar de conservar null.
    assert datos_evaluacion["estado"]["tecnologia"] == "python"
    assert datos_evaluacion["estado"]["ejercicio_actual"] is not None
    assert len(
        datos_evaluacion["estado"]["fuentes_extraidas"]
    ) == 1
    assert datos_evaluacion["directorio"] == tmp_path

    assert resultado["respuesta_final"] == (
        "Evaluación completada."
    )
    assert resultado["progreso_guardado"] is True


def test_ejecutar_turno_manual_rechaza_accion_desconocida(
    monkeypatch,
):
    """
    Mantiene una defensa adicional aunque Pydantic limite las acciones.
    """
    monkeypatch.setattr(
        modulo_orquestacion_manual,
        "ejecutar_coordinador_desde_estado",
        lambda estado, cliente=None, logger=None: {
            "accion": "accion_inventada",
            "tecnologia": None,
            "consulta_documentacion": None,
            "requiere_documentacion": False,
            "mensaje_aclaracion": None,
            "respuesta_final": None,
        },
    )

    with pytest.raises(
        RuntimeError,
        match="acción no contemplada",
    ):
        ejecutar_turno_manual(
            crear_estado_inicial(
                "Petición de prueba"
            )
        )

def test_construir_entrada_coordinador_indica_ejercicio_activo():
    """
    Proporciona contexto suficiente para reconocer una solución.
    """
    estado = crear_estado_inicial(
        "lista = []\nlista.append(5)"
    )
    estado["tecnologia"] = "python"
    estado["historial"] = [
        {
            "role": "user",
            "content": "Ponme un ejercicio.",
        },
        {
            "role": "assistant",
            "content": "Crea una lista.",
        },
    ]
    estado["ejercicio_actual"] = {
        "tipo": "ejercicio",

        # Estos datos privados no deben enviarse al coordinador.
        "solucion_esperada": "lista = []",
    }

    entrada_json = construir_entrada_coordinador(
        estado
    )
    datos = json.loads(
        entrada_json
    )

    assert datos == {
        "entrada_usuario": "lista = []\nlista.append(5)",
        "hay_ejercicio_activo": True,
        "tecnologia_contexto": "python",
        "cantidad_mensajes_historial": 2,
    }


def test_construir_entrada_coordinador_no_filtra_datos_privados():
    """
    Impide enviar solución, fuentes o historial completo.
    """
    estado = crear_estado_inicial(
        "Mi respuesta es lista = []"
    )
    estado["tecnologia"] = "python"
    estado["historial"] = [
        {
            "role": "assistant",
            "content": "Contenido anterior privado",
        }
    ]
    estado["ejercicio_actual"] = {
        "tipo": "ejercicio",
        "solucion_esperada": "SOLUCION_PRIVADA",
    }
    estado["fuentes_extraidas"] = [
        {
            "id": "fuente-1",
            "contenido": "CONTENIDO_FUENTE_PRIVADO",
        }
    ]

    entrada_json = construir_entrada_coordinador(
        estado
    )

    assert "SOLUCION_PRIVADA" not in entrada_json
    assert "CONTENIDO_FUENTE_PRIVADO" not in entrada_json
    assert "Contenido anterior privado" not in entrada_json

    assert set(
        json.loads(entrada_json)
    ) == {
        "entrada_usuario",
        "hay_ejercicio_activo",
        "tecnologia_contexto",
        "cantidad_mensajes_historial",
    }
