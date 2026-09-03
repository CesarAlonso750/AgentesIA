import logging  # Crea un logger sin handlers reales.

from nivel_experto.tutor_multiagente.cli_manual import (
    ejecutar_chat_terminal,
)


def _crear_lector(
    entradas,
):
    """
    Convierte una lista en una función compatible con input.
    """
    iterador = iter(
        entradas
    )

    def lector(prompt):
        """Devuelve la siguiente entrada preparada."""
        return next(
            iterador
        )

    return lector


def test_chat_manual_ejecuta_varios_turnos():
    """
    Conserva el historial entre dos turnos completados.
    """
    salidas = []
    estados_recibidos = []

    def ejecutor_simulado(
        estado,
        directorio_progreso=None,
        logger=None,
    ):
        """Simula el flujo completo sin APIs externas."""
        estados_recibidos.append(
            estado
        )

        resultado = {
            **estado,
            "respuesta_final": (
                f"Respuesta a: {estado['entrada_usuario']}"
            ),
        }

        return resultado

    logger = logging.Logger(
        "cli_manual_varios_turnos"
    )

    estado_final = ejecutar_chat_terminal(
        lector=_crear_lector(
            [
                "Primera pregunta",
                "Segunda pregunta",
                "salir",
            ]
        ),
        escritor=salidas.append,
        ejecutor=ejecutor_simulado,
        logger=logger,
    )

    assert len(estados_recibidos) == 2
    assert estados_recibidos[0]["historial"] == []

    # El segundo estado contiene el primer intercambio completo.
    assert estados_recibidos[1]["historial"] == [
        {
            "role": "user",
            "content": "Primera pregunta",
        },
        {
            "role": "assistant",
            "content": "Respuesta a: Primera pregunta",
        },
    ]

    assert estado_final["entrada_usuario"] == (
        "Segunda pregunta"
    )
    assert "Saliendo..." in salidas


def test_chat_manual_ignora_entrada_vacia():
    """
    Una entrada vacía no inicia un turno.
    """
    salidas = []
    numero_llamadas = 0

    def ejecutor_simulado(
        estado,
        directorio_progreso=None,
        logger=None,
    ):
        """Cuenta únicamente las entradas válidas."""
        nonlocal numero_llamadas
        numero_llamadas += 1

        return {
            **estado,
            "respuesta_final": "Respuesta correcta.",
        }

    ejecutar_chat_terminal(
        lector=_crear_lector(
            [
                "   ",
                "Pregunta válida",
                "salir",
            ]
        ),
        escritor=salidas.append,
        ejecutor=ejecutor_simulado,
        logger=logging.Logger(
            "cli_manual_entrada_vacia"
        ),
    )

    assert numero_llamadas == 1
    assert "Escribe una consulta o 'salir'." in salidas


def test_chat_manual_conserva_estado_si_un_turno_falla():
    """
    Un fallo posterior no elimina el último estado completado.
    """
    salidas = []
    numero_llamadas = 0

    def ejecutor_simulado(
        estado,
        directorio_progreso=None,
        logger=None,
    ):
        """Completa el primer turno y falla en el segundo."""
        nonlocal numero_llamadas
        numero_llamadas += 1

        if numero_llamadas == 2:
            raise RuntimeError(
                "Fallo simulado"
            )

        return {
            **estado,
            "respuesta_final": "Primera respuesta correcta.",
        }

    estado_final = ejecutar_chat_terminal(
        lector=_crear_lector(
            [
                "Primera pregunta",
                "Pregunta que falla",
                "salir",
            ]
        ),
        escritor=salidas.append,
        ejecutor=ejecutor_simulado,
        logger=logging.Logger(
            "cli_manual_turno_fallido"
        ),
    )

    assert estado_final["entrada_usuario"] == (
        "Primera pregunta"
    )
    assert (
        "No se pudo completar el turno. "
        "Puedes reformular la petición e intentarlo de nuevo."
        in salidas
    )


def test_chat_manual_no_imprime_detalles_del_error():
    """
    Impide mostrar el mensaje interno de una excepción.
    """
    salidas = []

    def ejecutor_fallido(
        estado,
        directorio_progreso=None,
        logger=None,
    ):
        """Simula un error que contiene información privada."""
        raise RuntimeError(
            "GROQ_API_KEY=secreto-no-mostrar"
        )

    ejecutar_chat_terminal(
        lector=_crear_lector(
            [
                "Pregunta",
                "salir",
            ]
        ),
        escritor=salidas.append,
        ejecutor=ejecutor_fallido,
        logger=logging.Logger(
            "cli_manual_error_seguro"
        ),
    )

    texto_visible = "\n".join(
        salidas
    )

    assert "secreto-no-mostrar" not in texto_visible
    assert "Traceback" not in texto_visible


def test_chat_manual_termina_sin_turnos():
    """
    Devuelve None cuando el usuario sale inmediatamente.
    """
    salidas = []

    resultado = ejecutar_chat_terminal(
        lector=_crear_lector(
            [
                "salir",
            ]
        ),
        escritor=salidas.append,
        logger=logging.Logger(
            "cli_manual_salida"
        ),
    )

    assert resultado is None
    assert salidas[-1] == "Saliendo..."

def test_chat_manual_controla_interrupcion_durante_turno():
    """
    Ctrl+C durante una API debe cerrar sin mostrar traceback.
    """
    salidas = []

    def ejecutor_interrumpido(
        estado,
        directorio_progreso=None,
        logger=None,
    ):
        """Simula Ctrl+C mientras una API está esperando."""
        raise KeyboardInterrupt()

    resultado = ejecutar_chat_terminal(
        lector=_crear_lector(
            [
                "Pregunta que inicia una llamada",
            ]
        ),
        escritor=salidas.append,
        ejecutor=ejecutor_interrumpido,
        logger=logging.Logger(
            "cli_manual_interrumpido"
        ),
    )

    assert resultado is None
    assert salidas[-1] == (
        "Operación interrumpida. Saliendo..."
    )

    texto_visible = "\n".join(
        salidas
    )

    assert "Traceback" not in texto_visible
