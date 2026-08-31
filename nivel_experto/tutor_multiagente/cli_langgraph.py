import logging  # Valida e inyecta el logger de la aplicación.
from pathlib import Path  # Permite redirigir el progreso en las pruebas.
from typing import Callable  # Describe las funciones de entrada y salida.

# Reutiliza la interfaz de terminal y su manejo seguro de errores.
from nivel_experto.tutor_multiagente.cli_manual import (
    ejecutar_chat_terminal,
)

# Centraliza el límite de ejecución del grafo.
from nivel_experto.tutor_multiagente.config import (
    MAX_PASOS_LANGGRAPH,
)

# Configura el mismo sistema de logging que la versión manual.
from nivel_experto.tutor_multiagente.logging_config import (
    configurar_logging,
)

# Construye el grafo completo del tutor.
from nivel_experto.tutor_multiagente.orquestacion.langgraph_tutor import (
    crear_grafo_tutor,
)


def ejecutar_chat_langgraph(
    lector: Callable[[str], str] | None = None,
    escritor: Callable[[str], None] | None = None,
    grafo: object | None = None,
    logger: logging.Logger | None = None,
    directorio_progreso: str | Path | None = None,
) -> dict[str, object] | None:
    """
    Ejecuta el tutor desde la terminal utilizando LangGraph.

    Reutiliza la interfaz de la versión manual, pero sustituye la
    función que ejecuta cada turno por una llamada al grafo compilado.

    Args:
        lector: Función compatible con input.
        escritor: Función compatible con print.
        grafo: Grafo alternativo utilizado en las pruebas.
        logger: Logger ya configurado.
        directorio_progreso: Carpeta alternativa para el progreso.

    Returns:
        Último estado completado o None si no terminó ningún turno.
    """
    # Reutiliza un logger recibido o configura el logger real.
    logger_aplicacion = (
        logger
        if logger is not None
        else configurar_logging()
    )

    if not isinstance(logger_aplicacion, logging.Logger):
        raise TypeError(
            "La terminal de LangGraph requiere un Logger válido."
        )

    # En producción construye el grafo real. Durante los tests se
    # puede proporcionar una simulación sin Groq ni Tavily.
    grafo_ejecutable = (
        grafo
        if grafo is not None
        else crear_grafo_tutor(
            directorio_progreso=directorio_progreso,
            logger=logger_aplicacion,
        )
    )

    # No confía en que el objeto inyectado sea realmente un grafo.
    metodo_invoke = getattr(
        grafo_ejecutable,
        "invoke",
        None,
    )

    if not callable(metodo_invoke):
        raise TypeError(
            "El objeto recibido no es un grafo ejecutable."
        )

    def ejecutar_turno_grafo(
        estado,
        directorio_progreso=None,
        logger=None,
    ):
        """
        Adapta graph.invoke al contrato de la terminal manual.

        Los dos últimos parámetros forman parte del contrato común.
        El grafo ya recibió esas dependencias al construirse.
        """
        try:
            resultado = metodo_invoke(
                estado,
                config={
                    # Detiene una ejecución si supera el recorrido
                    # máximo previsto por la arquitectura.
                    "recursion_limit": MAX_PASOS_LANGGRAPH,
                },
            )
        except (TypeError, ValueError, RuntimeError):
            # Los componentes ya han convertido los fallos externos
            # en errores controlados. Conservamos su tipo original
            # para que el logging pueda clasificarlos correctamente.
            raise
        except Exception as error:
            # Convierte únicamente errores inesperados de LangGraph
            # en un error comprendido por la terminal compartida.
            raise RuntimeError(
                "No se pudo completar la ejecución del grafo."
            ) from error

        if not isinstance(resultado, dict):
            raise RuntimeError(
                "El grafo no devolvió un estado válido."
            )

        return resultado

    # La lectura, la memoria entre turnos, la salida y el tratamiento
    # de errores permanecen idénticos a la versión manual.
    return ejecutar_chat_terminal(
        lector=lector,
        escritor=escritor,
        ejecutor=ejecutar_turno_grafo,
        logger=logger_aplicacion,
        directorio_progreso=directorio_progreso,
    )


def main() -> None:
    """
    Punto de entrada para ejecutar la versión LangGraph.
    """
    ejecutar_chat_langgraph()


if __name__ == "__main__":
    main()