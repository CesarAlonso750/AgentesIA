from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from nivel_experto.tutor_multiagente.estado import (
    AccionTutor,
)
from nivel_experto.tutor_multiagente.herramientas.fuentes import (
    obtener_fuente_oficial,
)
from nivel_experto.tutor_multiagente.validadores import (
    validar_consulta,
)


class DecisionCoordinador(BaseModel):
    """
    Representa la decisión estructurada del agente coordinador.

    El modelo no responderá directamente al estudiante. Su responsabilidad
    será clasificar la petición y preparar el siguiente paso del flujo.
    """

    # Rechaza campos inventados y evita conversiones de tipos permisivas.
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )

    accion: AccionTutor = Field(
        description=(
            "Acción que debe ejecutar el sistema para atender al usuario."
        )
    )

    tecnologia: str | None = Field(
        description=(
            "Identificador de la tecnología registrada, por ejemplo "
            "'python', 'java' o 'git'."
        ),
    )

    consulta_documentacion: str | None = Field(
        description=(
            "Consulta concreta que se buscará en la documentación oficial."
        ),
    )

    requiere_documentacion: bool = Field(
        description=(
            "Indica si el turno necesita buscar y extraer documentación."
        )
    )

    mensaje_aclaracion: str | None = Field(
        max_length=500,
        description=(
            "Pregunta breve para el usuario cuando falte información."
        ),
    )

    @field_validator("tecnologia")
    @classmethod
    def validar_tecnologia_registrada(
        cls,
        valor: str | None,
    ) -> str | None:
        """
        Normaliza la tecnología y comprueba que exista en el catálogo.
        """
        # Algunas acciones no necesitan identificar una tecnología.
        if valor is None:
            return None

        # La función también normaliza mayúsculas y espacios.
        fuente = obtener_fuente_oficial(valor)

        # Devuelve siempre el identificador normalizado del catálogo.
        return str(fuente["id"])

    @field_validator("consulta_documentacion")
    @classmethod
    def validar_consulta_documentacion(
        cls,
        valor: str | None,
    ) -> str | None:
        """
        Normaliza la consulta y rechaza URLs u operadores no permitidos.
        """
        # Una aclaración o evaluación puede no necesitar una consulta.
        if valor is None:
            return None

        return validar_consulta(valor)

    @field_validator("mensaje_aclaracion")
    @classmethod
    def validar_mensaje_aclaracion(
        cls,
        valor: str | None,
    ) -> str | None:
        """
        Impide que una aclaración sea una cadena vacía.
        """
        if valor is None:
            return None

        mensaje = valor.strip()

        if not mensaje:
            raise ValueError(
                "El mensaje de aclaración no puede estar vacío."
            )

        return mensaje

    @model_validator(mode="after")
    def validar_coherencia_decision(self) -> Self:
        """
        Comprueba la relación lógica entre todos los campos.
        """
        acciones_con_documentacion = {
            "responder_consulta",
            "generar_ejercicio",
        }

        if self.accion in acciones_con_documentacion:
            # Para investigar necesitamos saber qué tecnología consultar.
            if self.tecnologia is None:
                raise ValueError(
                    "Esta acción requiere indicar una tecnología."
                )

            # También necesitamos una consulta concreta para las herramientas.
            if self.consulta_documentacion is None:
                raise ValueError(
                    "Esta acción requiere una consulta de documentación."
                )

            if not self.requiere_documentacion:
                raise ValueError(
                    "Esta acción debe requerir documentación oficial."
                )

        if self.accion == "pedir_aclaracion":
            # Una aclaración debe contener la pregunta que verá el usuario.
            if self.mensaje_aclaracion is None:
                raise ValueError(
                    "La acción de aclaración requiere un mensaje."
                )

            # No se deben gastar créditos mientras falte información.
            if self.requiere_documentacion:
                raise ValueError(
                    "Una aclaración no debe consultar documentación."
                )

        if self.accion == "evaluar_respuesta":
            # En el MVP se evaluará usando el ejercicio y fuentes ya guardados.
            if self.requiere_documentacion:
                raise ValueError(
                    "La evaluación no debe iniciar una búsqueda nueva."
                )

        if (
            self.accion != "pedir_aclaracion"
            and self.mensaje_aclaracion is not None
        ):
            raise ValueError(
                "Solo una aclaración puede incluir mensaje de aclaración."
            )

        return self