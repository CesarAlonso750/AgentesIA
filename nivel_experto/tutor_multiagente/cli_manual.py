import logging  # Permite inyectar un logger durante las pruebas.
from pathlib import Path  # Permite redirigir el progreso.
from typing import Callable  # Describe entrada, salida y ejecutor.

from nivel_experto.tutor_multiagente.estado import (
    crear_estado_inicial,
    crear_estado_siguiente_turno,
)
from nivel_experto.tutor_multiagente.logging_config import (
    configurar_logging,
    registrar_evento,
)
from nivel_experto.tutor_multiagente.orquestacion.manual import (
    ejecutar_turno_manual,
)


def ejecutar_chat_terminal(
    lector: Callable[[str], str] | None = None,
    escritor: Callable[[str], None] | None = None,
    ejecutor: Callable[..., dict[str, object]] | None = None,
    logger: logging.Logger | None = None,
    directorio_progreso: str | Path | None = None,
) -> dict[str, object] | None:
    """
    Ejecuta el tutor multiagente manual desde la terminal.

    Los parámetros alternativos permiten probar la conversación sin
    utilizar stdin, stdout, Groq, Tavily ni el directorio real.

    Args:
        lector: Función compatible con input.
        escritor: Función compatible con print.
        ejecutor: Función que ejecuta un turno manual.
        logger: Logger ya configurado.
        directorio_progreso: Ruta alternativa para guardar el progreso.

    Returns:
        Último estado completado o None si no terminó ningún turno.
    """
    leer = (
        lector
        if lector is not None
        else input
    )
    escribir = (
        escritor
        if escritor is not None
        else print
    )
    ejecutar = (
        ejecutor
        if ejecutor is not None
        else ejecutar_turno_manual
    )
    logger_aplicacion = (
        logger
        if logger is not None
        else configurar_logging()
    )

    if not isinstance(logger_aplicacion, logging.Logger):
        raise TypeError(
            "La terminal requiere un Logger válido."
        )

    estado_anterior = None

    escribir(
        "Tutor técnico multiagente iniciado."
    )
    escribir(
        "Tecnologías disponibles: Python, Java y Git."
    )
    escribir(
        "Escribe 'salir' para terminar."
    )
    escribir(
        "-" * 60
    )

    while True:
        try:
            entrada = leer(
                "Tú: "
            )
        except (EOFError, KeyboardInterrupt):
            # Permite cerrar limpiamente con Ctrl+Z/Ctrl+D o Ctrl+C.
            escribir("")
            escribir(
                "Saliendo..."
            )
            return estado_anterior

        if not isinstance(entrada, str):
            escribir(
                "La entrada debe ser texto."
            )
            escribir(
                "-" * 60
            )
            continue

        entrada_normalizada = entrada.strip()

        if entrada_normalizada.lower() == "salir":
            escribir(
                "Saliendo..."
            )
            return estado_anterior

        if not entrada_normalizada:
            escribir(
                "Escribe una consulta o 'salir'."
            )
            escribir(
                "-" * 60
            )
            continue

        try:
            if estado_anterior is None:
                # El primer turno no tiene contexto previo.
                estado_turno = crear_estado_inicial(
                    entrada_normalizada
                )
            else:
                # Los siguientes turnos conservan historial y ejercicio.
                estado_turno = crear_estado_siguiente_turno(
                    entrada_usuario=entrada_normalizada,
                    estado_anterior=estado_anterior,
                )

            resultado = ejecutar(
                estado=estado_turno,
                directorio_progreso=directorio_progreso,
                logger=logger_aplicacion,
            )

            if not isinstance(resultado, dict):
                raise RuntimeError(
                    "El turno no devolvió un estado válido."
                )

            respuesta_final = resultado.get(
                "respuesta_final"
            )

            if not isinstance(respuesta_final, str):
                raise RuntimeError(
                    "El turno no produjo una respuesta final."
                )

            respuesta_normalizada = respuesta_final.strip()

            if not respuesta_normalizada:
                raise RuntimeError(
                    "La respuesta final está vacía."
                )

        except KeyboardInterrupt:
            # También permite interrumpir limpiamente una llamada externa.
            escribir("")
            escribir(
                "Operación interrumpida. Saliendo..."
            )
            return estado_anterior

        except (TypeError, ValueError, RuntimeError) as error:
            # Nunca imprime claves, prompts ni trazas al estudiante.
            escribir(
                "No se pudo completar el turno. "
                "Puedes reformular la petición e intentarlo de nuevo."
            )

            registrar_evento(
                logger_aplicacion,
                "error_controlado",
                nivel=logging.ERROR,
                resultado="turno_no_completado",
                tipo_error=type(error).__name__,
            )

            # No sustituye el último estado correcto por uno incompleto.
            escribir(
                "-" * 60
            )
            continue

        # Solo conserva estados que hayan llegado a una respuesta final.
        estado_anterior = resultado

        escribir(
            "Tutor:"
        )
        escribir(
            respuesta_normalizada
        )
        escribir(
            "-" * 60
        )


def main() -> None:
    """
    Punto de entrada utilizado al ejecutar el módulo.
    """
    ejecutar_chat_terminal()


if __name__ == "__main__":
    main()
