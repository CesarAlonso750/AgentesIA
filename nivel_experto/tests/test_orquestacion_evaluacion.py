import pytest  # Permite comprobar las excepciones esperadas.
import json  # Inspecciona los eventos estructurados.
import logging  # Construye un logger aislado para las pruebas.

# Permite sustituir temporalmente la llamada real al evaluador.
from nivel_experto.tutor_multiagente.orquestacion import (
    evaluacion as modulo_orquestacion_evaluacion,
)

# Construye un EstadoTutor completo y coherente.
from nivel_experto.tutor_multiagente.estado import (
    crear_estado_inicial,
)

# Importa los modelos utilizados para preparar datos fiables.
from nivel_experto.tutor_multiagente.agentes.esquemas import (
    BorradorTutor,
    EvaluacionEjercicio,
)

# Importa la función determinista que actualiza el estado.
from nivel_experto.tutor_multiagente.orquestacion.evaluacion import (
    crear_actualizacion_evaluacion_ejercicio,
    ejecutar_evaluacion_desde_estado,
)

class HandlerEventosSimulado(logging.Handler):
    """
    Conserva los mensajes del logger sin escribir archivos.
    """

    def __init__(self):
        super().__init__()
        self.mensajes = []

    def emit(self, record):
        """
        Guarda únicamente el mensaje final del evento.
        """
        self.mensajes.append(
            record.getMessage()
        )

def _crear_ejercicio() -> BorradorTutor:
    """
    Construye un ejercicio válido reutilizable en las pruebas.
    """
    return BorradorTutor(
        tipo="ejercicio",
        titulo="Practica con append",
        contenido_markdown=(
            "Crea una lista vacía, añade el número 5 con `append` "
            "y muestra el resultado. [fuente-1]"
        ),
        fuentes_utilizadas=["fuente-1"],

        # Esta solución es privada y no debe aparecer en la respuesta.
        solucion_esperada=(
            "lista = []\n"
            "lista.append(5)\n"
            "print(lista)"
        ),
        criterios_evaluacion=[
            "Crea una lista vacía.",
            "Añade el número 5 utilizando append.",
            "Muestra la lista resultante.",
        ],
    )


def _crear_evaluacion_correcta() -> EvaluacionEjercicio:
    """
    Construye una evaluación que satisface toda la rúbrica.
    """
    return EvaluacionEjercicio(
        respuesta_correcta=True,
        puntuacion=10,
        criterios_cumplidos=[
            "criterio-1",
            "criterio-2",
            "criterio-3",
        ],
        criterios_pendientes=[],
        retroalimentacion_markdown=(
            "La solución cumple correctamente todos los requisitos."
        ),
        recomendacion_siguiente=None,
    )


def test_crear_actualizacion_guarda_evaluacion_correcta():
    """
    Guarda el resultado estructurado y genera la respuesta visible.
    """
    actualizacion = crear_actualizacion_evaluacion_ejercicio(
        evaluacion=_crear_evaluacion_correcta(),
        ejercicio=_crear_ejercicio(),
    )

    assert actualizacion["evaluacion"]["respuesta_correcta"] is True
    assert actualizacion["evaluacion"]["puntuacion"] == 10
    assert actualizacion["errores"] == []
    assert actualizacion["progreso_guardado"] is False

    respuesta_final = actualizacion["respuesta_final"]

    assert "## Evaluación del ejercicio" in respuesta_final
    assert "**Resultado:** Correcta" in respuesta_final
    assert "**Puntuación:** 10/10" in respuesta_final
    assert "cumple correctamente" in respuesta_final


def test_crear_actualizacion_incluye_recomendacion():
    """
    Muestra la recomendación cuando la respuesta necesita mejorar.
    """
    evaluacion = EvaluacionEjercicio(
        respuesta_correcta=False,
        puntuacion=5,
        criterios_cumplidos=["criterio-1"],
        criterios_pendientes=[
            "criterio-2",
            "criterio-3",
        ],
        retroalimentacion_markdown=(
            "Has creado la lista, pero todavía faltan dos requisitos."
        ),
        recomendacion_siguiente=(
            "Revisa cómo utilizar append y print."
        ),
    )

    actualizacion = crear_actualizacion_evaluacion_ejercicio(
        evaluacion=evaluacion,
        ejercicio=_crear_ejercicio(),
    )

    respuesta_final = actualizacion["respuesta_final"]

    assert "**Resultado:** Necesita mejorar" in respuesta_final
    assert "**Puntuación:** 5/10" in respuesta_final
    assert "### Siguiente paso recomendado" in respuesta_final
    assert "Revisa cómo utilizar append y print." in respuesta_final


def test_crear_actualizacion_no_muestra_solucion_privada():
    """
    Impide incluir accidentalmente la solución en la respuesta final.
    """
    ejercicio = _crear_ejercicio()

    actualizacion = crear_actualizacion_evaluacion_ejercicio(
        evaluacion=_crear_evaluacion_correcta(),
        ejercicio=ejercicio,
    )

    # La solución se conserva para futuras evaluaciones.
    assert (
        actualizacion["ejercicio_actual"]["solucion_esperada"]
        == ejercicio.solucion_esperada
    )

    # Sin embargo, nunca debe aparecer en el texto visible.
    assert ejercicio.solucion_esperada not in (
        actualizacion["respuesta_final"]
    )


def test_crear_actualizacion_acepta_ejercicio_persistido():
    """
    Permite recuperar el ejercicio desde EstadoTutor o un JSON.
    """
    ejercicio_persistido = (
        _crear_ejercicio().model_dump()
    )

    actualizacion = crear_actualizacion_evaluacion_ejercicio(
        evaluacion=_crear_evaluacion_correcta(),
        ejercicio=ejercicio_persistido,
    )

    assert (
        actualizacion["ejercicio_actual"]["tipo"]
        == "ejercicio"
    )


def test_crear_actualizacion_rechaza_evaluacion_no_validada():
    """
    Impide guardar directamente un diccionario generado por el modelo.
    """
    with pytest.raises(
        TypeError,
        match="EvaluacionEjercicio validada",
    ):
        crear_actualizacion_evaluacion_ejercicio(
            evaluacion={
                "respuesta_correcta": True,
                "puntuacion": 10,
            },
            ejercicio=_crear_ejercicio(),
        )


def test_crear_actualizacion_rechaza_rubrica_incompleta():
    """
    Impide guardar una evaluación que omite criterios del ejercicio.
    """
    evaluacion_incompleta = EvaluacionEjercicio(
        respuesta_correcta=False,
        puntuacion=5,
        criterios_cumplidos=["criterio-1"],

        # Falta clasificar criterio-3.
        criterios_pendientes=["criterio-2"],
        retroalimentacion_markdown=(
            "La evaluación no contiene toda la rúbrica."
        ),
        recomendacion_siguiente=(
            "Revisa los criterios pendientes."
        ),
    )

    with pytest.raises(
        ValueError,
        match="criterios omitidos: criterio-3",
    ):
        crear_actualizacion_evaluacion_ejercicio(
            evaluacion=evaluacion_incompleta,
            ejercicio=_crear_ejercicio(),
        )

def _crear_estado_para_evaluacion() -> dict[str, object]:
    """
    Construye un estado preparado para evaluar una respuesta.
    """
    estado = crear_estado_inicial(
        "lista = []\nlista.append(5)\nprint(lista)"
    )

    # Simula la decisión previa del coordinador.
    estado["accion"] = "evaluar_respuesta"

    # La tecnología procede de la decisión del coordinador.
    estado["tecnologia"] = "python"

    # Recupera el ejercicio generado en el turno anterior.
    estado["ejercicio_actual"] = (
        _crear_ejercicio().model_dump()
    )

    # Conserva las fuentes oficiales utilizadas para generarlo.
    estado["fuentes_extraidas"] = [
        {
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
    ]

    return estado


def test_ejecutar_evaluacion_desde_estado(
    monkeypatch,
    tmp_path,
):
    """
    Comprueba el encadenado entre EstadoTutor y el evaluador.
    """
    datos_recibidos = {}

    def ejecutar_evaluacion_simulada(
        ejercicio,
        respuesta_estudiante,
        fuentes_extraidas,
        cliente=None,
    ):
        """
        Sustituye Groq y conserva los argumentos recibidos.
        """
        datos_recibidos["ejercicio"] = ejercicio
        datos_recibidos["respuesta_estudiante"] = (
            respuesta_estudiante
        )
        datos_recibidos["fuentes_extraidas"] = (
            fuentes_extraidas
        )
        datos_recibidos["cliente"] = cliente

        return _crear_evaluacion_correcta()

    # Sustituye únicamente la dependencia usada por la orquestación.
    monkeypatch.setattr(
        modulo_orquestacion_evaluacion,
        "ejecutar_evaluacion_ejercicio",
        ejecutar_evaluacion_simulada,
    )

    cliente_simulado = object()
    estado = _crear_estado_para_evaluacion()

    actualizacion = ejecutar_evaluacion_desde_estado(
        estado=estado,
        cliente=cliente_simulado,

        # Evita generar progreso personal dentro del proyecto real.
        directorio_progreso=tmp_path,
    )

    assert datos_recibidos["respuesta_estudiante"] == (
        "lista = []\nlista.append(5)\nprint(lista)"
    )
    assert datos_recibidos["ejercicio"] == (
        estado["ejercicio_actual"]
    )
    assert datos_recibidos["fuentes_extraidas"] == (
        estado["fuentes_extraidas"]
    )
    assert datos_recibidos["cliente"] is cliente_simulado

    assert actualizacion["evaluacion"]["puntuacion"] == 10
    assert "**Resultado:** Correcta" in (
        actualizacion["respuesta_final"]
    )
    # El progreso solo se marca después de guardarse correctamente.
    assert actualizacion["progreso_guardado"] is True

    ruta_progreso = (
        tmp_path
        / "progreso_estudiante.json"
    )
    assert ruta_progreso.is_file()


def test_ejecutar_evaluacion_rechaza_estado_no_diccionario():
    """
    Rechaza estructuras que no pueden representar EstadoTutor.
    """
    with pytest.raises(
        TypeError,
        match="debe ser un diccionario",
    ):
        ejecutar_evaluacion_desde_estado(
            estado=None,
        )


def test_ejecutar_evaluacion_rechaza_accion_incorrecta():
    """
    Impide entrar en esta ruta desde otra decisión del coordinador.
    """
    estado = _crear_estado_para_evaluacion()
    estado["accion"] = "responder_consulta"

    with pytest.raises(
        ValueError,
        match="no corresponde a una evaluación",
    ):
        ejecutar_evaluacion_desde_estado(
            estado=estado,
        )


def test_ejecutar_evaluacion_requiere_ejercicio_activo():
    """
    Impide evaluar si no existe un ejercicio anterior.
    """
    estado = _crear_estado_para_evaluacion()
    estado["ejercicio_actual"] = None

    with pytest.raises(
        ValueError,
        match="No hay ningún ejercicio activo",
    ):
        ejecutar_evaluacion_desde_estado(
            estado=estado,
        )


def test_ejecutar_evaluacion_requiere_fuentes():
    """
    Impide evaluar sin la documentación oficial del ejercicio.
    """
    estado = _crear_estado_para_evaluacion()
    estado["fuentes_extraidas"] = []

    with pytest.raises(
        ValueError,
        match="No hay fuentes oficiales disponibles",
    ):
        ejecutar_evaluacion_desde_estado(
            estado=estado,
        )

def test_ejecutar_evaluacion_conserva_respuesta_si_falla_progreso(
    monkeypatch,
    tmp_path,
):
    """
    Un fallo de disco no debe ocultar la retroalimentación.
    """
    def ejecutar_evaluacion_simulada(
        ejercicio,
        respuesta_estudiante,
        fuentes_extraidas,
        cliente=None,
    ):
        """Evita utilizar Groq durante esta prueba."""
        return _crear_evaluacion_correcta()

    def guardado_fallido(
        registro,
        directorio=None,
    ):
        """Simula un error al persistir el progreso."""
        raise RuntimeError(
            "Fallo de escritura simulado."
        )

    monkeypatch.setattr(
        modulo_orquestacion_evaluacion,
        "ejecutar_evaluacion_ejercicio",
        ejecutar_evaluacion_simulada,
    )
    monkeypatch.setattr(
        modulo_orquestacion_evaluacion,
        "guardar_registro_progreso",
        guardado_fallido,
    )

    actualizacion = ejecutar_evaluacion_desde_estado(
        estado=_crear_estado_para_evaluacion(),
        directorio_progreso=tmp_path,
    )

    # La evaluación permanece visible.
    assert "**Puntuación:** 10/10" in (
        actualizacion["respuesta_final"]
    )
    assert actualizacion["evaluacion"]["puntuacion"] == 10

    # El estado distingue claramente el fallo de persistencia.
    assert actualizacion["progreso_guardado"] is False
    assert len(actualizacion["errores"]) == 1
    assert "no se pudo guardar el progreso" in (
        actualizacion["errores"][0]
    )

def test_ejecutar_evaluacion_registra_eventos_seguros(
    monkeypatch,
    tmp_path,
):
    """
    Registra evaluación y progreso sin contenido privado.
    """
    def ejecutar_evaluacion_simulada(
        ejercicio,
        respuesta_estudiante,
        fuentes_extraidas,
        cliente=None,
    ):
        """Evita llamar a Groq durante la prueba."""
        return _crear_evaluacion_correcta()

    monkeypatch.setattr(
        modulo_orquestacion_evaluacion,
        "ejecutar_evaluacion_ejercicio",
        ejecutar_evaluacion_simulada,
    )

    logger = logging.Logger(
        "evaluacion_segura_prueba",
        level=logging.INFO,
    )
    handler = HandlerEventosSimulado()
    logger.addHandler(
        handler
    )

    estado = _crear_estado_para_evaluacion()

    ejecutar_evaluacion_desde_estado(
        estado=estado,
        directorio_progreso=tmp_path,
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
        "evaluacion_completada",
        "progreso_guardado",
    ]

    assert eventos[0]["tecnologia"] == "python"
    assert eventos[0]["resultado"] == "correcta"
    assert eventos[0]["puntuacion"] == 10
    assert eventos[1]["progreso_guardado"] is True

    contenido_logs = "\n".join(
        handler.mensajes
    )

    # No registra la entrada ni la solución privada.
    assert estado["entrada_usuario"] not in contenido_logs
    assert (
        estado["ejercicio_actual"]["solucion_esperada"]
        not in contenido_logs
    )


def test_ejecutar_evaluacion_registra_fallo_de_progreso(
    monkeypatch,
    tmp_path,
):
    """
    Registra un error técnico sin incluir su mensaje interno.
    """
    def ejecutar_evaluacion_simulada(
        ejercicio,
        respuesta_estudiante,
        fuentes_extraidas,
        cliente=None,
    ):
        """Evita llamar a Groq durante la prueba."""
        return _crear_evaluacion_correcta()

    def guardado_fallido(
        registro,
        directorio=None,
    ):
        """Incluye un texto que no debe terminar en el log."""
        raise RuntimeError(
            "Ruta privada que no debe registrarse."
        )

    monkeypatch.setattr(
        modulo_orquestacion_evaluacion,
        "ejecutar_evaluacion_ejercicio",
        ejecutar_evaluacion_simulada,
    )
    monkeypatch.setattr(
        modulo_orquestacion_evaluacion,
        "guardar_registro_progreso",
        guardado_fallido,
    )

    logger = logging.Logger(
        "error_progreso_prueba",
        level=logging.INFO,
    )
    handler = HandlerEventosSimulado()
    logger.addHandler(
        handler
    )

    ejecutar_evaluacion_desde_estado(
        estado=_crear_estado_para_evaluacion(),
        directorio_progreso=tmp_path,
        logger=logger,
    )

    eventos = [
        json.loads(mensaje)
        for mensaje in handler.mensajes
    ]

    assert eventos[-1] == {
        "evento": "error_controlado",
        "resultado": "progreso_no_guardado",
        "tecnologia": "python",
        "tipo_error": "RuntimeError",
    }

    assert "Ruta privada" not in (
        "\n".join(handler.mensajes)
    )
