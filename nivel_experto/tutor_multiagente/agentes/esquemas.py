import re  # Permite validar los identificadores de resultados.

from typing import Literal, Self

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

class SeleccionFuentes(BaseModel):
    """
    Representa las páginas elegidas por el tutor-investigador.

    El agente selecciona identificadores internos, nunca URLs escritas
    directamente, para impedir que pueda inventar una fuente.
    """

    # Aplica las mismas restricciones estrictas que al coordinador.
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )

    resultados_seleccionados: list[str] = Field(
        max_length=3,
        description=(
            "Identificadores de los resultados relevantes, con formato "
            "'resultado-N'. Debe estar vacío si no hay resultados útiles."
        ),
    )

    resultados_suficientes: bool = Field(
        description=(
            "Indica si los resultados seleccionados permiten continuar "
            "con la extracción."
        )
    )

    consulta_extraccion: str | None = Field(
        description=(
            "Consulta concreta utilizada para seleccionar fragmentos "
            "durante la extracción, o null si no hay fuentes suficientes."
        )
    )

    motivo: str = Field(
        min_length=3,
        max_length=500,
        description=(
            "Explicación breve de por qué se eligieron o descartaron "
            "los resultados."
        ),
    )

    @field_validator("resultados_seleccionados")
    @classmethod
    def validar_identificadores_resultados(
        cls,
        valores: list[str],
    ) -> list[str]:
        """
        Comprueba formato, duplicados y cantidad de identificadores.
        """
        identificadores_validados = []
        identificadores_incluidos = set()

        for valor in valores:
            # Cada elemento debe conservar el tipo de texto esperado.
            if not isinstance(valor, str):
                raise TypeError(
                    "Cada identificador de resultado debe ser texto."
                )

            identificador = valor.strip()

            # Solo admite identificadores generados por buscar_documentacion.
            if re.fullmatch(r"resultado-[1-9][0-9]*", identificador) is None:
                raise ValueError(
                    "Los identificadores deben seguir el formato "
                    "'resultado-N'."
                )

            # Los duplicados no aportan información y desperdiciarían créditos.
            if identificador in identificadores_incluidos:
                raise ValueError(
                    "No se puede seleccionar dos veces el mismo resultado."
                )

            identificadores_incluidos.add(identificador)
            identificadores_validados.append(identificador)

        return identificadores_validados

    @field_validator("consulta_extraccion")
    @classmethod
    def validar_consulta_para_extraccion(
        cls,
        valor: str | None,
    ) -> str | None:
        """
        Normaliza la consulta que se enviará a Tavily Extract.
        """
        if valor is None:
            return None

        return validar_consulta(valor)

    @model_validator(mode="after")
    def validar_coherencia_seleccion(self) -> Self:
        """
        Comprueba la relación entre suficiencia, resultados y consulta.
        """
        if self.resultados_suficientes:
            # No puede afirmarse que hay fuentes si no se selecciona ninguna.
            if not self.resultados_seleccionados:
                raise ValueError(
                    "Una selección suficiente requiere algún resultado."
                )

            # Tavily necesita una consulta para escoger fragmentos relevantes.
            if self.consulta_extraccion is None:
                raise ValueError(
                    "Una selección suficiente requiere consulta de extracción."
                )

        else:
            # Si no hay resultados adecuados, no se debe ejecutar extracción.
            if self.resultados_seleccionados:
                raise ValueError(
                    "Una selección insuficiente no debe incluir resultados."
                )

            if self.consulta_extraccion is not None:
                raise ValueError(
                    "Una selección insuficiente no necesita consulta."
                )

        return self

class BorradorTutor(BaseModel):
    """
    Representa una explicación o ejercicio basado en fuentes extraídas.

    El evaluador revisará este borrador antes de convertirlo en la
    respuesta final del turno.
    """

    # Rechaza propiedades y conversiones de tipos no previstas.
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )

    tipo: Literal["explicacion", "ejercicio"] = Field(
        description=(
            "Indica si el borrador responde una consulta o propone "
            "un ejercicio."
        )
    )

    titulo: str = Field(
        min_length=3,
        max_length=150,
        description=(
            "Título breve y descriptivo del contenido."
        ),
    )

    contenido_markdown: str = Field(
        min_length=20,
        max_length=8_000,
        description=(
            "Explicación o enunciado en Markdown. Debe citar las fuentes "
            "mediante identificadores como [fuente-1]."
        ),
    )

    fuentes_utilizadas: list[str] = Field(
        min_length=1,
        max_length=3,
        description=(
            "Identificadores de las fuentes utilizadas para redactar "
            "el contenido."
        ),
    )

    solucion_esperada: str | None = Field(
        max_length=4_000,
        description=(
            "Solución privada del ejercicio o null para una explicación."
        ),
    )

    criterios_evaluacion: list[str] = Field(
        max_length=5,
        description=(
            "Criterios utilizados para evaluar el ejercicio. Debe estar "
            "vacío para una explicación."
        ),
    )

    @field_validator("fuentes_utilizadas")
    @classmethod
    def validar_fuentes_utilizadas(
        cls,
        valores: list[str],
    ) -> list[str]:
        """
        Comprueba formato y duplicados de los identificadores de fuente.
        """
        fuentes_validadas = []
        fuentes_incluidas = set()

        for valor in valores:
            if not isinstance(valor, str):
                raise TypeError(
                    "Cada identificador de fuente debe ser texto."
                )

            identificador = valor.strip()

            # Solo admite IDs generados por extraer_documentacion.
            if re.fullmatch(r"fuente-[1-9][0-9]*", identificador) is None:
                raise ValueError(
                    "Las fuentes deben seguir el formato 'fuente-N'."
                )

            if identificador in fuentes_incluidas:
                raise ValueError(
                    "No se puede utilizar dos veces la misma fuente."
                )

            fuentes_incluidas.add(identificador)
            fuentes_validadas.append(identificador)

        return fuentes_validadas

    @field_validator("solucion_esperada")
    @classmethod
    def validar_solucion_esperada(
        cls,
        valor: str | None,
    ) -> str | None:
        """
        Impide aceptar una solución formada únicamente por espacios.
        """
        if valor is None:
            return None

        solucion = valor.strip()

        if not solucion:
            raise ValueError(
                "La solución esperada no puede estar vacía."
            )

        return solucion

    @field_validator("criterios_evaluacion")
    @classmethod
    def validar_criterios_evaluacion(
        cls,
        valores: list[str],
    ) -> list[str]:
        """
        Normaliza los criterios y rechaza valores vacíos o duplicados.
        """
        criterios_validados = []
        criterios_incluidos = set()

        for valor in valores:
            if not isinstance(valor, str):
                raise TypeError(
                    "Cada criterio de evaluación debe ser texto."
                )

            criterio = valor.strip()

            if not criterio:
                raise ValueError(
                    "Los criterios de evaluación no pueden estar vacíos."
                )

            if criterio in criterios_incluidos:
                raise ValueError(
                    "Los criterios de evaluación no pueden repetirse."
                )

            criterios_incluidos.add(criterio)
            criterios_validados.append(criterio)

        return criterios_validados

    @model_validator(mode="after")
    def validar_coherencia_borrador(self) -> Self:
        """
        Comprueba las diferencias entre explicación y ejercicio.
        """
        if self.tipo == "explicacion":
            # Una explicación no necesita guardar una solución privada.
            if self.solucion_esperada is not None:
                raise ValueError(
                    "Una explicación no debe incluir solución esperada."
                )

            if self.criterios_evaluacion:
                raise ValueError(
                    "Una explicación no debe incluir criterios de evaluación."
                )

        if self.tipo == "ejercicio":
            # El evaluador necesitará una solución para revisar al estudiante.
            if self.solucion_esperada is None:
                raise ValueError(
                    "Un ejercicio requiere una solución esperada."
                )

            if not self.criterios_evaluacion:
                raise ValueError(
                    "Un ejercicio requiere criterios de evaluación."
                )

        # Todas las fuentes declaradas deben citarse en el contenido visible.
        for identificador in self.fuentes_utilizadas:
            cita = f"[{identificador}]"

            if cita not in self.contenido_markdown:
                raise ValueError(
                    f"La fuente '{identificador}' no aparece citada "
                    "en el contenido."
                )

        # Recupera todas las citas con formato [fuente-N] escritas en el texto.
        citas_encontradas = set(
            re.findall(
                r"\[(fuente-[1-9][0-9]*)\]",
                self.contenido_markdown,
            )
        )

        fuentes_declaradas = set(
            self.fuentes_utilizadas
        )

        # Detecta citas válidas sintácticamente que no aparecen declaradas.
        citas_no_declaradas = (
            citas_encontradas - fuentes_declaradas
        )

        if citas_no_declaradas:
            # Ordena los identificadores para obtener errores deterministas.
            identificadores = ", ".join(
                sorted(citas_no_declaradas)
            )

            raise ValueError(
                "El contenido cita fuentes que no están declaradas: "
                f"{identificadores}."
            )

        return self