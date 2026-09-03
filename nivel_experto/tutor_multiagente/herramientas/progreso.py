import json  # Lee el historial almacenado en formato JSON.
import re  # Comprueba los identificadores de criterios.
import os  # Fuerza la escritura del archivo temporal en disco.

from tempfile import NamedTemporaryFile  # Crea temporales únicos.
from copy import deepcopy  # Evita devolver referencias compartidas.
from pathlib import Path  # Construye rutas compatibles con cada sistema.
from datetime import datetime, timezone  # Genera fechas UTC comparables.

# Importa los modelos validados utilizados por el progreso.
from nivel_experto.tutor_multiagente.agentes.esquemas import (
    EvaluacionEjercicio,
)

# Recupera y valida ejercicios creados anteriormente.
from nivel_experto.tutor_multiagente.agentes.tutor_investigador import (
    interpretar_borrador_tutor,
)

# Comprueba que la tecnología pertenece al catálogo oficial.
from nivel_experto.tutor_multiagente.herramientas.fuentes import (
    obtener_fuente_oficial,
)

# Comprueba que la evaluación cubra toda la rúbrica.
from nivel_experto.tutor_multiagente.agentes.evaluador import (
    validar_criterios_evaluacion,
)

from nivel_experto.tutor_multiagente.config import (
    RUTA_DIRECTORIO_PROGRESO,
)


def crear_registro_progreso(
    tecnologia: object,
    ejercicio: object,
    evaluacion: object,
    fecha: datetime | None = None,
) -> dict[str, object]:
    """
    Construye un registro seguro de un intento de ejercicio.

    No guarda la respuesta del estudiante, las fuentes completas ni
    la solución privada del ejercicio.

    Args:
        tecnologia: Tecnología oficial estudiada.
        ejercicio: Ejercicio validado o diccionario persistido.
        evaluacion: Resultado validado del agente evaluador.
        fecha: Fecha opcional para pruebas; debe incluir zona horaria.

    Returns:
        Registro serializable como JSON.

    Raises:
        TypeError: Si evaluación o fecha tienen tipos incorrectos.
        ValueError: Si los datos no son coherentes.
    """
    # Valida que la tecnología exista en el catálogo autorizado.
    fuente_tecnologia = obtener_fuente_oficial(
        tecnologia
    )
    tecnologia_validada = fuente_tecnologia["id"]

    # Recupera el ejercicio desde un modelo o un diccionario persistido.
    ejercicio_validado = interpretar_borrador_tutor(
        ejercicio
    )

    # No acepta directamente un diccionario generado por el modelo.
    if not isinstance(evaluacion, EvaluacionEjercicio):
        raise TypeError(
            "El progreso requiere una "
            "EvaluacionEjercicio validada."
        )

    # Evita persistir una evaluación ajena a la rúbrica del ejercicio.
    validar_criterios_evaluacion(
        evaluacion,
        ejercicio_validado,
    )

    if fecha is None:
        # Utiliza UTC para que los registros sean comparables.
        fecha_validada = datetime.now(
            timezone.utc
        )
    else:
        if not isinstance(fecha, datetime):
            raise TypeError(
                "La fecha del progreso debe ser datetime."
            )

        # Una fecha sin zona horaria sería ambigua.
        if fecha.tzinfo is None or fecha.utcoffset() is None:
            raise ValueError(
                "La fecha del progreso debe incluir zona horaria."
            )

        # Normaliza cualquier zona horaria recibida a UTC.
        fecha_validada = fecha.astimezone(
            timezone.utc
        )

    return {
        # ISO 8601 permite ordenar e intercambiar fechas fácilmente.
        "fecha_utc": fecha_validada.isoformat(
            timespec="seconds"
        ),
        "tecnologia": tecnologia_validada,
        "titulo_ejercicio": ejercicio_validado.titulo,
        "respuesta_correcta": evaluacion.respuesta_correcta,
        "puntuacion": evaluacion.puntuacion,

        # Solo guarda IDs de rúbrica, no la solución privada.
        "criterios_cumplidos": list(
            evaluacion.criterios_cumplidos
        ),
        "criterios_pendientes": list(
            evaluacion.criterios_pendientes
        ),
    }

# Nombre fijo para impedir que entradas externas controlen la ruta.
NOMBRE_ARCHIVO_PROGRESO = "progreso_estudiante.json"

# Campos exactos permitidos dentro de cada intento.
CAMPOS_REGISTRO_PROGRESO = {
    "fecha_utc",
    "tecnologia",
    "titulo_ejercicio",
    "respuesta_correcta",
    "puntuacion",
    "criterios_cumplidos",
    "criterios_pendientes",
}


def _obtener_ruta_progreso(
    directorio: str | Path | None = None,
) -> Path:
    """
    Construye la ruta fija del archivo de progreso.

    El parámetro alternativo se utiliza en las pruebas para no escribir
    datos dentro del proyecto real.
    """
    if directorio is None:
        directorio_validado = RUTA_DIRECTORIO_PROGRESO
    elif isinstance(directorio, (str, Path)):
        directorio_validado = Path(directorio)
    else:
        raise TypeError(
            "El directorio de progreso debe ser una ruta."
        )

    return (
        directorio_validado
        / NOMBRE_ARCHIVO_PROGRESO
    )


def _validar_lista_criterios_guardada(
    valor: object,
    nombre_campo: str,
) -> list[str]:
    """
    Valida una lista de identificadores recuperada del JSON.
    """
    if not isinstance(valor, list):
        raise ValueError(
            f"El campo '{nombre_campo}' debe ser una lista."
        )

    if len(valor) > 5:
        raise ValueError(
            f"El campo '{nombre_campo}' no puede superar "
            "cinco criterios."
        )

    criterios_validados = []
    criterios_incluidos = set()

    for criterio in valor:
        if not isinstance(criterio, str):
            raise ValueError(
                f"Los elementos de '{nombre_campo}' deben ser texto."
            )

        identificador = criterio.strip()

        if re.fullmatch(
            r"criterio-[1-5]",
            identificador,
        ) is None:
            raise ValueError(
                f"El campo '{nombre_campo}' contiene "
                "un identificador inválido."
            )

        if identificador in criterios_incluidos:
            raise ValueError(
                f"El campo '{nombre_campo}' contiene duplicados."
            )

        criterios_incluidos.add(identificador)
        criterios_validados.append(identificador)

    return criterios_validados


def _validar_registro_guardado(
    registro: object,
) -> dict[str, object]:
    """
    Valida un intento recuperado desde el archivo de progreso.
    """
    if not isinstance(registro, dict):
        raise ValueError(
            "Cada intento del progreso debe ser un objeto JSON."
        )

    campos_recibidos = set(
        registro
    )

    if campos_recibidos != CAMPOS_REGISTRO_PROGRESO:
        raise ValueError(
            "Un intento del progreso contiene campos "
            "ausentes o inesperados."
        )

    fecha_texto = registro["fecha_utc"]

    if not isinstance(fecha_texto, str):
        raise ValueError(
            "La fecha del intento debe ser texto ISO 8601."
        )

    try:
        fecha = datetime.fromisoformat(
            fecha_texto
        )
    except ValueError as error:
        raise ValueError(
            "La fecha del intento no tiene formato ISO 8601."
        ) from error

    if fecha.tzinfo is None or fecha.utcoffset() is None:
        raise ValueError(
            "La fecha del intento debe incluir zona horaria."
        )

    # Comprueba que la tecnología siga perteneciendo al catálogo.
    fuente_tecnologia = obtener_fuente_oficial(
        registro["tecnologia"]
    )
    tecnologia = fuente_tecnologia["id"]

    titulo = registro["titulo_ejercicio"]

    if not isinstance(titulo, str):
        raise ValueError(
            "El título del ejercicio debe ser texto."
        )

    titulo_normalizado = titulo.strip()

    if not titulo_normalizado or len(titulo_normalizado) > 200:
        raise ValueError(
            "El título del ejercicio debe contener "
            "entre 1 y 200 caracteres."
        )

    respuesta_correcta = registro[
        "respuesta_correcta"
    ]

    if not isinstance(respuesta_correcta, bool):
        raise ValueError(
            "respuesta_correcta debe ser un booleano."
        )

    puntuacion = registro["puntuacion"]

    # bool es subclase de int y debe rechazarse explícitamente.
    if (
        isinstance(puntuacion, bool)
        or not isinstance(puntuacion, int)
        or puntuacion < 0
        or puntuacion > 10
    ):
        raise ValueError(
            "La puntuación debe ser un entero entre 0 y 10."
        )

    cumplidos = _validar_lista_criterios_guardada(
        registro["criterios_cumplidos"],
        "criterios_cumplidos",
    )
    pendientes = _validar_lista_criterios_guardada(
        registro["criterios_pendientes"],
        "criterios_pendientes",
    )

    if not cumplidos and not pendientes:
        raise ValueError(
            "El intento debe contener algún criterio evaluado."
        )

    if set(cumplidos) & set(pendientes):
        raise ValueError(
            "Un criterio no puede estar cumplido y pendiente."
        )

    if respuesta_correcta:
        if pendientes:
            raise ValueError(
                "Una respuesta correcta no puede tener "
                "criterios pendientes."
            )

        if puntuacion < 7:
            raise ValueError(
                "Una respuesta correcta debe obtener "
                "al menos 7 puntos."
            )
    else:
        if not pendientes:
            raise ValueError(
                "Una respuesta incorrecta necesita "
                "criterios pendientes."
            )

        if puntuacion == 10:
            raise ValueError(
                "Una respuesta incorrecta no puede obtener 10 puntos."
            )

    # Devuelve una copia normalizada y segura.
    return {
        "fecha_utc": fecha.astimezone(
            timezone.utc
        ).isoformat(timespec="seconds"),
        "tecnologia": tecnologia,
        "titulo_ejercicio": titulo_normalizado,
        "respuesta_correcta": respuesta_correcta,
        "puntuacion": puntuacion,
        "criterios_cumplidos": cumplidos,
        "criterios_pendientes": pendientes,
    }


def cargar_historial_progreso(
    directorio: str | Path | None = None,
) -> dict[str, object]:
    """
    Carga y valida el historial de progreso.

    Si todavía no existe un archivo, devuelve un historial vacío.
    """
    ruta = _obtener_ruta_progreso(
        directorio
    )

    # La primera ejecución todavía no tendrá datos guardados.
    if not ruta.exists():
        return {
            "version": 1,
            "intentos": [],
        }

    if not ruta.is_file():
        raise RuntimeError(
            "La ruta de progreso no corresponde a un archivo."
        )

    try:
        with ruta.open(
            "r",
            encoding="utf-8",
        ) as archivo:
            contenido = json.load(
                archivo
            )
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "El archivo de progreso contiene JSON inválido."
        ) from error
    except OSError as error:
        raise RuntimeError(
            "No se pudo leer el archivo de progreso."
        ) from error

    if not isinstance(contenido, dict):
        raise RuntimeError(
            "El historial de progreso debe ser un objeto JSON."
        )

    if set(contenido) != {"version", "intentos"}:
        raise RuntimeError(
            "El historial contiene campos ausentes o inesperados."
        )

    # bool debe rechazarse porque también es una subclase de int.
    version = contenido["version"]

    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != 1
    ):
        raise RuntimeError(
            "La versión del historial de progreso no es compatible."
        )

    intentos = contenido["intentos"]

    if not isinstance(intentos, list):
        raise RuntimeError(
            "Los intentos del progreso deben formar una lista."
        )

    try:
        intentos_validados = [
            _validar_registro_guardado(registro)
            for registro in intentos
        ]
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            "El historial contiene un intento inválido."
        ) from error

    return {
        "version": 1,
        "intentos": deepcopy(
            intentos_validados
        ),
    }

def guardar_registro_progreso(
    registro: object,
    directorio: str | Path | None = None,
) -> Path:
    """
    Añade un intento al historial mediante escritura atómica.

    Primero escribe el historial completo en un archivo temporal.
    Solo después reemplaza el archivo definitivo.

    Args:
        registro: Intento generado por crear_registro_progreso.
        directorio: Ruta alternativa utilizada en las pruebas.

    Returns:
        Ruta del archivo de progreso actualizado.

    Raises:
        ValueError: Si el registro no es válido.
        RuntimeError: Si no se puede leer o escribir el historial.
    """
    # Vuelve a validar el registro en el límite de persistencia.
    registro_validado = _validar_registro_guardado(
        registro
    )

    ruta = _obtener_ruta_progreso(
        directorio
    )

    try:
        # Se crea automáticamente en la primera ejecución.
        ruta.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
    except OSError as error:
        raise RuntimeError(
            "No se pudo crear el directorio de progreso."
        ) from error

    # Carga y valida el contenido anterior antes de modificarlo.
    historial = cargar_historial_progreso(
        directorio=ruta.parent,
    )

    historial_actualizado = {
        "version": 1,

        # Construye una lista nueva para no modificar la ya cargada.
        "intentos": [
            *historial["intentos"],
            deepcopy(registro_validado),
        ],
    }

    ruta_temporal = None

    try:
        # El temporal se crea en el mismo directorio para que el reemplazo
        # se realice dentro del mismo sistema de archivos.
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".progreso_",
            suffix=".tmp",
            dir=ruta.parent,
            delete=False,
        ) as archivo_temporal:
            ruta_temporal = Path(
                archivo_temporal.name
            )

            json.dump(
                historial_actualizado,
                archivo_temporal,
                ensure_ascii=False,
                indent=4,
            )
            archivo_temporal.write("\n")

            # Envía el contenido de Python al sistema operativo.
            archivo_temporal.flush()

            # Solicita que el sistema escriba físicamente los datos.
            os.fsync(
                archivo_temporal.fileno()
            )

        # os.replace, utilizado por Path.replace, reemplaza atómicamente
        # el destino cuando ambos archivos están en el mismo volumen.
        ruta_temporal.replace(
            ruta
        )

    except (OSError, TypeError) as error:
        # Elimina únicamente el temporal concreto creado por esta llamada.
        if ruta_temporal is not None:
            try:
                ruta_temporal.unlink(
                    missing_ok=True
                )
            except OSError:
                # Conserva el error original de escritura o reemplazo.
                pass

        raise RuntimeError(
            "No se pudo guardar el archivo de progreso."
        ) from error

    return ruta
