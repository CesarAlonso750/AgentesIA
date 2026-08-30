from nivel_experto.tutor_multiagente.agentes import (
    cliente_groq as modulo_cliente_groq,
)
from nivel_experto.tutor_multiagente.agentes.cliente_groq import (
    crear_cliente_groq,
)


def test_crear_cliente_groq_desactiva_reintentos_automaticos(
    monkeypatch,
):
    """
    Evita que el SDK espere automáticamente ante un límite 429.
    """
    parametros_recibidos = {}
    cliente_simulado = object()

    def groq_simulado(**parametros):
        """Conserva la configuración enviada al constructor."""
        parametros_recibidos.update(
            parametros
        )
        return cliente_simulado

    # Evita consultar una clave real durante la prueba.
    monkeypatch.setattr(
        modulo_cliente_groq,
        "obtener_variable_entorno",
        lambda nombre: "clave-simulada",
    )

    # Sustituye el constructor real del SDK.
    monkeypatch.setattr(
        modulo_cliente_groq,
        "Groq",
        groq_simulado,
    )

    resultado = crear_cliente_groq()

    assert resultado is cliente_simulado
    assert parametros_recibidos == {
        "api_key": "clave-simulada",
        "max_retries": 0,
    }
