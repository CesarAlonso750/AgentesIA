from types import SimpleNamespace  # Simula respuesta y cliente.
import pytest  # Comprueba excepciones esperadas.

from nivel_experto.tutor_multiagente.agentes import (
    cliente_groq as modulo_cliente_groq,
)
from nivel_experto.tutor_multiagente.agentes.cliente_groq import (
    crear_cliente_groq,
    solicitar_completion_groq,
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

class CompletionsConLimiteSimuladas:
    """
    Falla una vez con 429 y después devuelve una respuesta.
    """

    def __init__(
        self,
        error,
        respuesta,
    ):
        self.error = error
        self.respuesta = respuesta
        self.numero_llamadas = 0

    def create(
        self,
        **parametros,
    ):
        """
        Reproduce dos llamadas consecutivas al SDK.
        """
        self.numero_llamadas += 1

        if self.numero_llamadas == 1:
            raise self.error

        return self.respuesta

class CompletionsConVariosLimitesSimuladas:
    """
    Produce varios errores 429 antes de devolver una respuesta.
    """

    def __init__(
        self,
        error,
        respuesta,
        cantidad_limites,
    ):
        self.error = error
        self.respuesta = respuesta
        self.cantidad_limites = cantidad_limites
        self.numero_llamadas = 0

    def create(
        self,
        **parametros,
    ):
        """
        Falla durante la cantidad de llamadas configurada.
        """
        self.numero_llamadas += 1

        if self.numero_llamadas <= self.cantidad_limites:
            raise self.error

        return self.respuesta

def test_completion_reintenta_respetando_retry_after(
    monkeypatch,
):
    """
    Espera el tiempo indicado y realiza una segunda llamada.
    """
    class RateLimitSimulado(Exception):
        """Representa un 429 con cabeceras controladas."""

        def __init__(self):
            self.response = SimpleNamespace(
                headers={
                    "retry-after": "2.2",
                }
            )

    # Sustituye solamente la clase capturada por la utilidad.
    monkeypatch.setattr(
        modulo_cliente_groq,
        "RateLimitError",
        RateLimitSimulado,
    )

    respuesta = object()
    completions = CompletionsConLimiteSimuladas(
        error=RateLimitSimulado(),
        respuesta=respuesta,
    )
    cliente = SimpleNamespace(
        chat=SimpleNamespace(
            completions=completions,
        )
    )

    esperas = []

    resultado = solicitar_completion_groq(
        cliente,
        pausa=esperas.append,
        model="modelo-simulado",
    )

    assert resultado is respuesta
    assert completions.numero_llamadas == 2

    # 2,2 segundos se redondean hacia arriba.
    assert esperas == [3]


def test_completion_no_reintenta_sin_retry_after(
    monkeypatch,
):
    """
    No inventa una espera cuando Groq no envía la cabecera.
    """
    class RateLimitSimulado(Exception):
        """Representa un 429 sin retry-after."""

        def __init__(self):
            self.response = SimpleNamespace(
                headers={}
            )

    monkeypatch.setattr(
        modulo_cliente_groq,
        "RateLimitError",
        RateLimitSimulado,
    )

    completions = CompletionsConLimiteSimuladas(
        error=RateLimitSimulado(),
        respuesta=object(),
    )
    cliente = SimpleNamespace(
        chat=SimpleNamespace(
            completions=completions,
        )
    )

    with pytest.raises(
        RateLimitSimulado,
    ):
        solicitar_completion_groq(
            cliente,
            pausa=lambda segundos: None,
        )

    assert completions.numero_llamadas == 1


def test_completion_no_espera_mas_del_limite(
    monkeypatch,
):
    """
    Devuelve el error si retry-after supera el máximo local.
    """
    class RateLimitSimulado(Exception):
        """Representa una espera excesiva solicitada por Groq."""

        def __init__(self):
            self.response = SimpleNamespace(
                headers={
                    "retry-after": "121",
                }
            )

    # Hace que la utilidad capture nuestra excepción simulada como un 429.
    monkeypatch.setattr(
        modulo_cliente_groq,
        "RateLimitError",
        RateLimitSimulado,
    )

    # Captura el evento sin escribir en consola ni en el archivo de log.
    eventos = []

    monkeypatch.setattr(
        modulo_cliente_groq,
        "registrar_evento",
        lambda logger, evento, **contexto: eventos.append(
            {
                "evento": evento,
                **contexto,
            }
        ),
    )

    completions = CompletionsConLimiteSimuladas(
        error=RateLimitSimulado(),
        respuesta=object(),
    )
    cliente = SimpleNamespace(
        chat=SimpleNamespace(
            completions=completions,
        )
    )

    with pytest.raises(
        RateLimitSimulado,
    ):
        solicitar_completion_groq(
            cliente,
            pausa=lambda segundos: None,
        )

    assert completions.numero_llamadas == 1
    assert len(eventos) == 1
    assert eventos[0]["evento"] == "reintento_descartado"
    assert eventos[0]["resultado"] == "espera_no_admitida"
    assert eventos[0]["iteracion"] == 0

def test_completion_admite_tres_reintentos_consecutivos(
    monkeypatch,
):
    """
    Recupera la respuesta después de tres límites temporales.
    """
    class RateLimitSimulado(Exception):
        """Representa un 429 recuperable en un segundo."""

        def __init__(self):
            self.response = SimpleNamespace(
                headers={
                    "retry-after": "1",
                }
            )

    monkeypatch.setattr(
        modulo_cliente_groq,
        "RateLimitError",
        RateLimitSimulado,
    )

    respuesta = object()
    completions = CompletionsConVariosLimitesSimuladas(
        error=RateLimitSimulado(),
        respuesta=respuesta,
        cantidad_limites=3,
    )
    cliente = SimpleNamespace(
        chat=SimpleNamespace(
            completions=completions,
        )
    )
    esperas = []

    resultado = solicitar_completion_groq(
        cliente,
        pausa=esperas.append,
    )

    assert resultado is respuesta

    # Se realizan la petición inicial y tres reintentos.
    assert completions.numero_llamadas == 4
    assert esperas == [1, 1, 1]


def test_completion_se_detiene_tras_tres_reintentos(
    monkeypatch,
):
    """
    Propaga el cuarto 429 sin crear un bucle infinito.
    """
    class RateLimitSimulado(Exception):
        """Representa un límite que continúa indefinidamente."""

        def __init__(self):
            self.response = SimpleNamespace(
                headers={
                    "retry-after": "1",
                }
            )
    # Hace que la utilidad capture nuestra excepción simulada como un 429.
    monkeypatch.setattr(
        modulo_cliente_groq,
        "RateLimitError",
        RateLimitSimulado,
    )

    # Captura el motivo por el que finaliza el ciclo.
    eventos = []

    monkeypatch.setattr(
        modulo_cliente_groq,
        "registrar_evento",
        lambda logger, evento, **contexto: eventos.append(
            {
                "evento": evento,
                **contexto,
            }
        ),
    )

    completions = CompletionsConVariosLimitesSimuladas(
        error=RateLimitSimulado(),
        respuesta=object(),
        cantidad_limites=4,
    )
    cliente = SimpleNamespace(
        chat=SimpleNamespace(
            completions=completions,
        )
    )
    esperas = []

    with pytest.raises(
        RateLimitSimulado,
    ):
        solicitar_completion_groq(
            cliente,
            pausa=esperas.append,
        )

    # La cuarta llamada falla y ya no genera una cuarta espera.
    assert completions.numero_llamadas == 4
    assert esperas == [1, 1, 1]
    assert len(eventos) == 4

    evento_final = eventos[-1]

    assert evento_final["evento"] == "reintento_descartado"
    assert evento_final["resultado"] == "reintentos_agotados"
    assert evento_final["iteracion"] == 3