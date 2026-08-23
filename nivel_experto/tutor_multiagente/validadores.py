import re  # Permite validar formatos y normalizar espacios.
from ipaddress import ip_address  # Permite detectar direcciones IP.
from urllib.parse import urlsplit  # Separa una URL en componentes seguros.

# Una tecnología puede contener letras, números, guiones y guiones bajos.
PATRON_TECNOLOGIA = re.compile(r"^[a-z0-9][a-z0-9_-]{0,49}$")

# Detecta URLs incluidas dentro de una consulta de búsqueda.
PATRON_URL = re.compile(r"https?://", re.IGNORECASE)

# Detecta el operador site:, que solo debe controlar nuestro programa.
PATRON_OPERADOR_SITE = re.compile(r"\bsite\s*:", re.IGNORECASE)

# Valida dominios DNS sencillos como docs.python.org o git-scm.com.
PATRON_DOMINIO = re.compile(
    r"^(?=.{1,253}$)"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def normalizar_tecnologia(valor: object) -> str:
    """
    Valida y normaliza el identificador de una tecnología.

    Args:
        valor: Valor recibido del usuario o generado por el modelo.

    Returns:
        Identificador convertido a minúsculas y sin espacios exteriores.

    Raises:
        TypeError: Si el valor no es una cadena.
        ValueError: Si está vacío o tiene un formato no permitido.
    """
    # Rechaza números, booleanos, listas y otros tipos inesperados.
    if not isinstance(valor, str):
        raise TypeError("La tecnología debe ser una cadena de texto.")

    # Normaliza mayúsculas y espacios exteriores.
    tecnologia = valor.strip().lower()

    # Evita identificadores vacíos.
    if not tecnologia:
        raise ValueError("La tecnología no puede estar vacía.")

    # Evita nombres excesivamente largos o con caracteres no permitidos.
    if not PATRON_TECNOLOGIA.fullmatch(tecnologia):
        raise ValueError(
            "La tecnología solo puede contener letras minúsculas, números, "
            "guiones y guiones bajos, con un máximo de 50 caracteres."
        )

    return tecnologia


def validar_consulta(valor: object) -> str:
    """
    Valida y normaliza una consulta que se enviará al buscador.

    Args:
        valor: Consulta recibida del usuario o generada por un agente.

    Returns:
        Consulta con los espacios normalizados.

    Raises:
        TypeError: Si el valor no es una cadena.
        ValueError: Si la consulta es demasiado corta, larga o insegura.
    """
    # Rechaza cualquier valor que no sea texto.
    if not isinstance(valor, str):
        raise TypeError("La consulta debe ser una cadena de texto.")

    # Sustituye saltos de línea y grupos de espacios por un único espacio.
    consulta = re.sub(r"\s+", " ", valor).strip()

    # Exige una longitud mínima para evitar búsquedas sin significado.
    if len(consulta) < 3:
        raise ValueError("La consulta debe contener al menos 3 caracteres.")

    # Limita el tamaño enviado a Tavily y a los logs.
    if len(consulta) > 300:
        raise ValueError("La consulta no puede superar los 300 caracteres.")

    # Una consulta debe describir un tema, no proporcionar una URL.
    if PATRON_URL.search(consulta):
        raise ValueError("La consulta no puede contener una URL.")

    # Los dominios de búsqueda se controlan mediante el catálogo local.
    if PATRON_OPERADOR_SITE.search(consulta):
        raise ValueError("La consulta no puede utilizar el operador 'site:'.")

    return consulta

def normalizar_dominio(valor: object) -> str:
    """
    Valida y normaliza un dominio incluido en el catálogo.

    Args:
        valor: Dominio que se quiere utilizar o comprobar.

    Returns:
        Dominio en minúsculas y sin punto final.

    Raises:
        TypeError: Si el dominio no es una cadena.
        ValueError: Si está vacío o tiene un formato inválido.
    """
    # Rechaza listas, números y otros tipos inesperados.
    if not isinstance(valor, str):
        raise TypeError("El dominio debe ser una cadena de texto.")

    # Los nombres DNS no distinguen entre mayúsculas y minúsculas.
    dominio = valor.strip().lower().rstrip(".")

    # Evita dominios vacíos después de normalizar.
    if not dominio:
        raise ValueError("El dominio no puede estar vacío.")

    # Rechaza rutas, protocolos, puertos y formatos DNS incorrectos.
    if not PATRON_DOMINIO.fullmatch(dominio):
        raise ValueError(f"El dominio '{dominio}' no tiene un formato válido.")

    # Un dominio autorizado nunca debe ser directamente una dirección IP.
    try:
        ip_address(dominio)
    except ValueError:
        # ValueError significa que el texto no es una dirección IP.
        pass
    else:
        raise ValueError("No se permiten direcciones IP como dominios.")

    return dominio


def validar_url_oficial(
    valor: object,
    dominios_permitidos: object,
) -> str:
    """
    Comprueba que una URL pertenezca a una fuente oficial autorizada.

    Args:
        valor: URL recibida desde Tavily o desde otro componente externo.
        dominios_permitidos: Colección de dominios obtenida del catálogo local.

    Returns:
        URL validada sin espacios exteriores.

    Raises:
        TypeError: Si los parámetros tienen tipos incorrectos.
        ValueError: Si la URL es insegura o su dominio no está autorizado.
    """
    # La URL siempre debe llegar como texto.
    if not isinstance(valor, str):
        raise TypeError("La URL debe ser una cadena de texto.")

    url = valor.strip()

    # Evita direcciones vacías o excesivamente grandes.
    if not url:
        raise ValueError("La URL no puede estar vacía.")

    if len(url) > 2_048:
        raise ValueError("La URL no puede superar los 2048 caracteres.")

    # Rechaza espacios interiores y barras invertidas ambiguas.
    if any(caracter.isspace() for caracter in url) or "\\" in url:
        raise ValueError("La URL contiene caracteres no permitidos.")

    # La colección de dominios no puede ser una cadena ni estar vacía.
    if (
        isinstance(dominios_permitidos, (str, bytes))
        or not isinstance(dominios_permitidos, (list, tuple, set))
        or not dominios_permitidos
    ):
        raise TypeError(
            "Los dominios permitidos deben formar una colección no vacía."
        )

    # Normaliza también la configuración local antes de compararla.
    dominios_normalizados = {
        normalizar_dominio(dominio)
        for dominio in dominios_permitidos
    }

    # Divide la URL sin realizar ninguna conexión de red.
    partes = urlsplit(url)

    # Obliga a utilizar conexiones HTTPS.
    if partes.scheme.lower() != "https":
        raise ValueError("La URL debe utilizar HTTPS.")

    # Rechaza direcciones que incluyan credenciales.
    if partes.username is not None or partes.password is not None:
        raise ValueError("La URL no puede contener credenciales.")

    # La URL debe contener un nombre de servidor.
    if partes.hostname is None:
        raise ValueError("La URL debe contener un dominio.")

    # Valida y normaliza el dominio real interpretado por Python.
    dominio_url = normalizar_dominio(partes.hostname)

    # Acceder a port también detecta valores de puerto inválidos.
    try:
        puerto = partes.port
    except ValueError as error:
        raise ValueError("La URL contiene un puerto inválido.") from error

    # Solo se permite el puerto HTTPS estándar cuando se indica explícitamente.
    if puerto not in (None, 443):
        raise ValueError("La URL utiliza un puerto no permitido.")

    # Acepta el dominio exacto o uno de sus subdominios.
    dominio_autorizado = any(
        dominio_url == dominio
        or dominio_url.endswith(f".{dominio}")
        for dominio in dominios_normalizados
    )

    if not dominio_autorizado:
        raise ValueError(
            f"El dominio '{dominio_url}' no pertenece a las fuentes autorizadas."
        )

    return url