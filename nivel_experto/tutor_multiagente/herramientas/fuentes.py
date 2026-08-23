import json  # Permite leer el catálogo guardado en formato JSON.
from copy import deepcopy  # Evita devolver referencias modificables al catálogo.
from pathlib import Path  # Permite trabajar con rutas de forma segura.

from nivel_experto.tutor_multiagente.config import RUTA_CATALOGO_FUENTES
from nivel_experto.tutor_multiagente.validadores import (
    normalizar_dominio,
    normalizar_tecnologia,
    validar_url_oficial,
)


def _validar_texto_configuracion(
    valor: object,
    campo: str,
    tecnologia: str,
) -> None:
    """
    Valida un campo de texto perteneciente al catálogo.

    Esta función es interna porque no será expuesta como herramienta.
    """
    # Cada campo descriptivo debe ser una cadena con contenido.
    if not isinstance(valor, str) or not valor.strip():
        raise RuntimeError(
            f"El campo '{campo}' de la tecnología '{tecnologia}' "
            "debe ser un texto no vacío."
        )


def _validar_lista_textos(
    valor: object,
    campo: str,
    tecnologia: str,
) -> None:
    """
    Valida una lista no vacía formada exclusivamente por textos.
    """
    # El catálogo debe contener al menos un elemento en estas listas.
    if not isinstance(valor, list) or not valor:
        raise RuntimeError(
            f"El campo '{campo}' de la tecnología '{tecnologia}' "
            "debe ser una lista no vacía."
        )

    # Revisa cada elemento para evitar dominios o URLs vacíos.
    for elemento in valor:
        if not isinstance(elemento, str) or not elemento.strip():
            raise RuntimeError(
                f"Todos los elementos de '{campo}' para '{tecnologia}' "
                "deben ser textos no vacíos."
            )


def cargar_catalogo_fuentes(
    ruta_catalogo: str | Path | None = None,
) -> dict[str, dict[str, object]]:
    """
    Carga y valida la estructura completa del catálogo de fuentes.

    Args:
        ruta_catalogo: Ruta alternativa utilizada principalmente por los tests.

    Returns:
        Diccionario cuyas claves son identificadores de tecnologías.

    Raises:
        RuntimeError: Si el archivo no existe, no es JSON válido o su
            estructura no cumple el formato esperado.
    """
    # Utiliza la ruta oficial salvo que el llamador proporcione otra.
    ruta = (
        Path(ruta_catalogo)
        if ruta_catalogo is not None
        else RUTA_CATALOGO_FUENTES
    )

    try:
        # Abre siempre el JSON indicando explícitamente UTF-8.
        with ruta.open("r", encoding="utf-8") as archivo:
            catalogo = json.load(archivo)
    except FileNotFoundError as error:
        # Convierte el error del sistema en un mensaje propio del proyecto.
        raise RuntimeError(
            f"No se encontró el catálogo de fuentes en: {ruta}"
        ) from error
    except json.JSONDecodeError as error:
        # Evita que un JSON dañado continúe hasta los agentes.
        raise RuntimeError(
            f"El catálogo de fuentes no contiene JSON válido: {ruta}"
        ) from error
    except OSError as error:
        # Controla otros problemas de lectura, como permisos insuficientes.
        raise RuntimeError(
            f"No se pudo leer el catálogo de fuentes: {ruta}"
        ) from error

    # La raíz del catálogo debe ser un objeto JSON no vacío.
    if not isinstance(catalogo, dict) or not catalogo:
        raise RuntimeError(
            "El catálogo de fuentes debe ser un objeto JSON no vacío."
        )

    # Valida cada tecnología antes de permitir que sea utilizada.
    for identificador, configuracion in catalogo.items():
        try:
            # Comprueba que el identificador tenga un formato permitido.
            tecnologia_normalizada = normalizar_tecnologia(identificador)
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                f"El catálogo contiene una tecnología inválida: "
                f"{identificador!r}"
            ) from error

        # Obliga a guardar las claves ya normalizadas en el JSON.
        if tecnologia_normalizada != identificador:
            raise RuntimeError(
                f"La tecnología '{identificador}' debe estar normalizada "
                "en minúsculas dentro del catálogo."
            )

        # Cada tecnología debe contener un objeto con su configuración.
        if not isinstance(configuracion, dict):
            raise RuntimeError(
                f"La configuración de '{identificador}' debe ser "
                "un objeto JSON."
            )

        # Valida el nombre visible de la tecnología.
        _validar_texto_configuracion(
            configuracion.get("nombre"),
            "nombre",
            identificador,
        )

        # Valida la descripción que se mostrará al usuario y al agente.
        _validar_texto_configuracion(
            configuracion.get("descripcion"),
            "descripcion",
            identificador,
        )

        # Comprueba que exista al menos un dominio oficial.
        _validar_lista_textos(
            configuracion.get("dominios_permitidos"),
            "dominios_permitidos",
            identificador,
        )

        # Comprueba que exista al menos una página inicial informativa.
        _validar_lista_textos(
            configuracion.get("paginas_iniciales"),
            "paginas_iniciales",
            identificador,
        )

        # Recupera las listas después de comprobar que tienen el tipo correcto.
        dominios = configuracion["dominios_permitidos"]
        paginas_iniciales = configuracion["paginas_iniciales"]

        # Valida individualmente todos los dominios oficiales.
        for dominio in dominios:
            try:
                dominio_normalizado = normalizar_dominio(dominio)
            except (TypeError, ValueError) as error:
                raise RuntimeError(
                    f"El catálogo contiene un dominio inválido para "
                    f"'{identificador}': {dominio!r}"
                ) from error

            # Exige que el JSON ya almacene el dominio normalizado.
            if dominio_normalizado != dominio:
                raise RuntimeError(
                    f"El dominio '{dominio}' de '{identificador}' debe "
                    "estar normalizado en minúsculas y sin punto final."
                )

        # Valida individualmente todas las páginas iniciales.
        for pagina in paginas_iniciales:
            try:
                # Comprueba HTTPS, dominio, credenciales y puerto.
                validar_url_oficial(pagina, dominios)
            except (TypeError, ValueError) as error:
                raise RuntimeError(
                    f"La página inicial '{pagina}' de '{identificador}' "
                    "no es una URL oficial válida."
                ) from error

    # Devuelve el catálogo únicamente después de validar todas sus entradas.
    return catalogo


def listar_fuentes_oficiales() -> list[dict[str, object]]:
    """
    Devuelve una lista segura y ordenada de las fuentes disponibles.
    """
    # Carga el catálogo ya validado.
    catalogo = cargar_catalogo_fuentes()
    fuentes = []

    # Ordena por identificador para producir siempre el mismo resultado.
    for identificador in sorted(catalogo):
        configuracion = catalogo[identificador]

        # Construye una copia con los campos que podrá consultar el agente.
        fuentes.append(
            {
                "id": identificador,
                "nombre": configuracion["nombre"],
                "descripcion": configuracion["descripcion"],
                "dominios_permitidos": deepcopy(
                    configuracion["dominios_permitidos"]
                ),
                "paginas_iniciales": deepcopy(
                    configuracion["paginas_iniciales"]
                ),
            }
        )

    return fuentes


def obtener_fuente_oficial(tecnologia: object) -> dict[str, object]:
    """
    Recupera la configuración de una tecnología concreta.

    Args:
        tecnologia: Identificador recibido del usuario o del modelo.

    Returns:
        Copia de la configuración correspondiente.

    Raises:
        ValueError: Si la tecnología tiene formato válido pero no está
            registrada.
    """
    # Valida primero el formato de la entrada no confiable.
    identificador = normalizar_tecnologia(tecnologia)

    # Carga el catálogo después de comprobar el identificador.
    catalogo = cargar_catalogo_fuentes()

    # Distingue entre formato inválido y tecnología no registrada.
    if identificador not in catalogo:
        disponibles = ", ".join(sorted(catalogo))

        raise ValueError(
            f"La tecnología '{identificador}' no está registrada. "
            f"Opciones disponibles: {disponibles}."
        )

    # Copia el objeto para impedir que otro módulo modifique el catálogo.
    fuente = deepcopy(catalogo[identificador])
    fuente["id"] = identificador

    return fuente