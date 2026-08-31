import json  # Lee el conjunto de casos almacenado como JSON.
from pathlib import Path  # Permite recibir rutas independientes del sistema.
from typing import Literal  # Limita acciones y tecnologías admitidas.

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from nivel_experto.tutor_multiagente.config import (
    RUTA_CASOS_EVALUACION,
)


class CasoEvaluacion(BaseModel):
    """
    Representa un caso de evaluación manual del tutor.
    """

    # Rechaza campos inventados y elimina espacios exteriores.
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # Obliga a utilizar identificadores como CP-001.
    id: str = Field(
        pattern=r"^CP-\d{3}$",
    )

    # Agrupa casos similares sin imponer una lista cerrada.
    categoria: str = Field(
        min_length=1,
        max_length=100,
    )

    # Pregunta que se enviará al tutor.
    entrada: str = Field(
        min_length=1,
        max_length=5_000,
    )

    # Describe el contexto que deberá prepararse manualmente.
    contexto_previo: str | None

    # Rutas válidas que puede seleccionar el coordinador.
    accion_esperada: Literal[
        "responder_consulta",
        "generar_ejercicio",
        "evaluar_respuesta",
        "pedir_aclaracion",
    ]

    # El catálogo actual está limitado a estas tecnologías.
    tecnologia_esperada: Literal[
        "python",
        "java",
        "git",
    ] | None

    # Condiciones observables para decidir si el caso es correcto.
    criterios: list[str] = Field(
        min_length=1,
        max_length=10,
    )

    @field_validator("criterios")
    @classmethod
    def validar_criterios(
        cls,
        criterios: list[str],
    ) -> list[str]:
        """
        Impide incluir criterios vacíos o repetidos.
        """
        criterios_normalizados = []
        criterios_detectados = set()

        for criterio in criterios:
            # Pydantic ya garantiza que cada elemento sea texto.
            criterio_normalizado = criterio.strip()

            if not criterio_normalizado:
                raise ValueError(
                    "Los criterios no pueden estar vacíos."
                )

            # Compara en minúsculas para detectar duplicados.
            clave_criterio = criterio_normalizado.lower()

            if clave_criterio in criterios_detectados:
                raise ValueError(
                    "Un caso contiene criterios repetidos."
                )

            criterios_detectados.add(
                clave_criterio
            )
            criterios_normalizados.append(
                criterio_normalizado
            )

        return criterios_normalizados


def cargar_casos_evaluacion(
    ruta: str | Path = RUTA_CASOS_EVALUACION,
) -> list[CasoEvaluacion]:
    """
    Carga y valida el conjunto completo de evaluación.

    Args:
        ruta: Archivo JSON que contiene los casos.

    Returns:
        Lista de casos validados mediante Pydantic.

    Raises:
        TypeError: Si la ruta no es texto ni Path.
        RuntimeError: Si el archivo no puede leerse o su JSON es inválido.
        ValueError: Si no hay casos o existen identificadores duplicados.
    """
    if not isinstance(
        ruta,
        (str, Path),
    ):
        raise TypeError(
            "La ruta de los casos debe ser texto o Path."
        )

    ruta_validada = Path(
        ruta
    )

    try:
        contenido = ruta_validada.read_text(
            encoding="utf-8"
        )
    except OSError as error:
        raise RuntimeError(
            "No se pudo leer el archivo de casos de evaluación."
        ) from error

    try:
        datos = json.loads(
            contenido
        )
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "El archivo de casos no contiene JSON válido."
        ) from error

    if not isinstance(datos, list):
        raise RuntimeError(
            "El archivo de evaluación debe contener una lista."
        )

    if not datos:
        raise ValueError(
            "Debe existir al menos un caso de evaluación."
        )

    casos_validados = []
    identificadores = set()

    for posicion, datos_caso in enumerate(
        datos,
        start=1,
    ):
        try:
            # Convierte cada objeto externo en un modelo validado.
            caso = CasoEvaluacion.model_validate(
                datos_caso
            )
        except ValidationError as error:
            raise RuntimeError(
                "El caso situado en la posición "
                f"{posicion} no es válido."
            ) from error

        # Dos casos con el mismo ID dificultarían registrar resultados.
        if caso.id in identificadores:
            raise ValueError(
                f"El identificador '{caso.id}' está repetido."
            )

        identificadores.add(
            caso.id
        )
        casos_validados.append(
            caso
        )

    return casos_validados