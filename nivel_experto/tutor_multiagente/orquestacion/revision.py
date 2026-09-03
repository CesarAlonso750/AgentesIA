from copy import deepcopy  # Evita compartir estructuras mutables.

from nivel_experto.tutor_multiagente.agentes.cliente_groq import (
    ClienteGroq,
)
from nivel_experto.tutor_multiagente.agentes.esquemas import (
    BorradorTutor,
    RevisionBorrador,
)
from nivel_experto.tutor_multiagente.agentes.evaluador import (
    ejecutar_revision_borrador,
)
from nivel_experto.tutor_multiagente.agentes.tutor_investigador import (
    ejecutar_correccion_borrador,
)
from nivel_experto.tutor_multiagente.config import (
    MAX_REVISIONES_BORRADOR,
)


def ejecutar_ciclo_revision_borrador(
    accion: object,
    tecnologia: object,
    peticion_usuario: object,
    consulta_documentacion: object,
    fuentes_extraidas: object,
    borrador_inicial: object,
    cliente_evaluador: ClienteGroq | None = None,
    cliente_correccion: ClienteGroq | None = None,
) -> dict[str, object]:
    """
    Coordina el ciclo limitado entre redactor y evaluador.

    El evaluador revisa primero el borrador inicial. Si lo rechaza,
    el tutor-investigador produce una única versión corregida y el
    evaluador vuelve a revisarla.

    Args:
        accion: Acción original decidida por el coordinador.
        tecnologia: Tecnología registrada.
        peticion_usuario: Petición original del estudiante.
        consulta_documentacion: Consulta utilizada durante la investigación.
        fuentes_extraidas: Fuentes oficiales disponibles.
        borrador_inicial: Primera versión generada por el investigador.
        cliente_evaluador: Cliente alternativo para las revisiones.
        cliente_correccion: Cliente alternativo para la corrección.

    Returns:
        Borrador final, última revisión y contadores del ciclo.

    Raises:
        TypeError: Si el borrador inicial no está validado.
        ValueError: Si alguna entrada local es incoherente.
        RuntimeError: Si una llamada externa no puede completarse.
    """
    # La orquestación no acepta directamente un diccionario del modelo.
    if not isinstance(borrador_inicial, BorradorTutor):
        raise TypeError(
            "El ciclo requiere un BorradorTutor inicial validado."
        )

    # Esta variable cambia únicamente si existe una corrección.
    borrador_actual = borrador_inicial

    # Con dos revisiones se permite una sola corrección intermedia.
    for numero_revision in range(
        1,
        MAX_REVISIONES_BORRADOR + 1,
    ):
        revision = ejecutar_revision_borrador(
            borrador=borrador_actual,
            peticion_usuario=peticion_usuario,
            fuentes_extraidas=fuentes_extraidas,
            cliente=cliente_evaluador,
        )

        # Un borrador aprobado puede continuar hacia la respuesta final.
        if revision.aprobado:
            return {
                "aprobado": True,
                "borrador": borrador_actual,
                "revision": revision,
                "iteraciones_revision": numero_revision,
                "correcciones_realizadas": numero_revision - 1,
            }

        # Si la segunda revisión también lo rechaza, no se vuelve a corregir.
        if numero_revision >= MAX_REVISIONES_BORRADOR:
            return {
                "aprobado": False,
                "borrador": borrador_actual,
                "revision": revision,
                "iteraciones_revision": numero_revision,
                "correcciones_realizadas": numero_revision - 1,
            }

        # El tutor-investigador recibe exclusivamente la revisión validada.
        borrador_actual = ejecutar_correccion_borrador(
            accion=accion,
            tecnologia=tecnologia,
            peticion_usuario=peticion_usuario,
            consulta_documentacion=consulta_documentacion,
            fuentes_extraidas=fuentes_extraidas,
            borrador_anterior=borrador_actual,
            revision=revision,
            cliente=cliente_correccion,
        )

    # El bucle siempre debe devolver en una de las ramas anteriores.
    raise RuntimeError(
        "El ciclo de revisión terminó sin producir un resultado."
    )

def crear_actualizacion_revision(
    resultado_ciclo: object,
) -> dict[str, object]:
    """
    Convierte el resultado del ciclo en campos de EstadoTutor.

    Un borrador aprobado se convierte en respuesta final. Un borrador
    rechazado por segunda vez nunca se muestra al estudiante.

    Args:
        resultado_ciclo: Resultado de ejecutar_ciclo_revision_borrador.

    Returns:
        Actualización segura para el estado compartido.

    Raises:
        TypeError: Si el resultado general no es un diccionario.
        RuntimeError: Si el resultado contiene datos incoherentes.
    """
    if not isinstance(resultado_ciclo, dict):
        raise TypeError(
            "El resultado del ciclo debe ser un diccionario."
        )

    aprobado = resultado_ciclo.get(
        "aprobado"
    )
    borrador = resultado_ciclo.get(
        "borrador"
    )
    revision = resultado_ciclo.get(
        "revision"
    )
    iteraciones = resultado_ciclo.get(
        "iteraciones_revision"
    )
    correcciones = resultado_ciclo.get(
        "correcciones_realizadas"
    )

    # bool debe comprobarse explícitamente porque es subclase de int.
    if not isinstance(aprobado, bool):
        raise RuntimeError(
            "El ciclo no contiene una decisión de aprobación válida."
        )

    if not isinstance(borrador, BorradorTutor):
        raise RuntimeError(
            "El ciclo no contiene un BorradorTutor válido."
        )

    if not isinstance(revision, RevisionBorrador):
        raise RuntimeError(
            "El ciclo no contiene una RevisionBorrador válida."
        )

    if (
        isinstance(iteraciones, bool)
        or not isinstance(iteraciones, int)
        or iteraciones < 1
        or iteraciones > MAX_REVISIONES_BORRADOR
    ):
        raise RuntimeError(
            "El número de revisiones del ciclo no es válido."
        )

    if (
        isinstance(correcciones, bool)
        or not isinstance(correcciones, int)
        or correcciones < 0
        or correcciones != iteraciones - 1
    ):
        raise RuntimeError(
            "El número de correcciones del ciclo no es válido."
        )

    # La decisión resumida debe coincidir con el modelo del evaluador.
    if aprobado != revision.aprobado:
        raise RuntimeError(
            "La aprobación del ciclo contradice la revisión."
        )

    # Un rechazo definitivo solo puede ocurrir al consumir el límite.
    if (
        not aprobado
        and iteraciones < MAX_REVISIONES_BORRADOR
    ):
        raise RuntimeError(
            "El ciclo ha rechazado el borrador antes del límite."
        )

    respuesta_borrador = (
        f"# {borrador.titulo}\n\n"
        f"{borrador.contenido_markdown}"
    )

    if aprobado:
        # Solo una versión aprobada puede mostrarse al estudiante.
        respuesta_final = respuesta_borrador
        errores = []

        # Conserva la solución privada únicamente para ejercicios aprobados.
        ejercicio_actual = (
            deepcopy(borrador.model_dump())
            if borrador.tipo == "ejercicio"
            else None
        )
    else:
        # Nunca muestra un contenido que continúa rechazado.
        respuesta_final = (
            "No he podido generar una respuesta suficientemente "
            "respaldada por las fuentes oficiales."
        )
        errores = [
            "El borrador no superó la revisión del evaluador."
        ]
        ejercicio_actual = None

    return {
        "respuesta_borrador": respuesta_borrador,
        "respuesta_final": respuesta_final,
        "ejercicio_actual": ejercicio_actual,
        "evaluacion": deepcopy(
            revision.model_dump()
        ),
        "iteraciones_revision": iteraciones,
        "errores": errores,
    }
