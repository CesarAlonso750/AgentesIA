from datetime import datetime, timezone  # Prepara fechas deterministas.

import json  # Prepara archivos JSON simulados.
import pytest  # Comprueba excepciones esperadas.

from pathlib import Path  # Permite simular un fallo de reemplazo.

from nivel_experto.tutor_multiagente.agentes.esquemas import (
    BorradorTutor,
    EvaluacionEjercicio,
)
from nivel_experto.tutor_multiagente.herramientas.progreso import (
    cargar_historial_progreso,
    crear_registro_progreso,
    guardar_registro_progreso,
)


def _crear_ejercicio_progreso() -> BorradorTutor:
    """
    Construye un ejercicio válido para las pruebas.
    """
    return BorradorTutor(
        tipo="ejercicio",
        titulo="Practica con append",
        contenido_markdown=(
            "Crea una lista, añade el número 5 y muéstrala. "
            "[fuente-1]"
        ),
        fuentes_utilizadas=["fuente-1"],
        solucion_esperada=(
            "lista = []\n"
            "lista.append(5)\n"
            "print(lista)"
        ),
        criterios_evaluacion=[
            "Crea una lista vacía.",
            "Añade el número 5.",
            "Muestra la lista.",
        ],
    )


def _crear_evaluacion_progreso() -> EvaluacionEjercicio:
    """
    Construye una evaluación completa para las pruebas.
    """
    return EvaluacionEjercicio(
        respuesta_correcta=True,
        puntuacion=10,
        criterios_cumplidos=[
            "criterio-1",
            "criterio-2",
            "criterio-3",
        ],
        criterios_pendientes=[],
        retroalimentacion_markdown=(
            "La respuesta cumple todos los requisitos."
        ),
        recomendacion_siguiente=None,
    )


def test_crear_registro_progreso():
    """
    Construye un registro JSON con los datos necesarios.
    """
    fecha = datetime(
        2026,
        8,
        30,
        10,
        15,
        20,
        tzinfo=timezone.utc,
    )

    registro = crear_registro_progreso(
        tecnologia="python",
        ejercicio=_crear_ejercicio_progreso(),
        evaluacion=_crear_evaluacion_progreso(),
        fecha=fecha,
    )

    assert registro == {
        "fecha_utc": "2026-08-30T10:15:20+00:00",
        "tecnologia": "python",
        "titulo_ejercicio": "Practica con append",
        "respuesta_correcta": True,
        "puntuacion": 10,
        "criterios_cumplidos": [
            "criterio-1",
            "criterio-2",
            "criterio-3",
        ],
        "criterios_pendientes": [],
    }


def test_crear_registro_normaliza_tecnologia():
    """
    Reutiliza la validación del catálogo oficial.
    """
    registro = crear_registro_progreso(
        tecnologia="  PYTHON  ",
        ejercicio=_crear_ejercicio_progreso(),
        evaluacion=_crear_evaluacion_progreso(),
    )

    assert registro["tecnologia"] == "python"


def test_crear_registro_acepta_ejercicio_persistido():
    """
    Permite utilizar el ejercicio almacenado en EstadoTutor.
    """
    ejercicio_persistido = (
        _crear_ejercicio_progreso().model_dump()
    )

    registro = crear_registro_progreso(
        tecnologia="python",
        ejercicio=ejercicio_persistido,
        evaluacion=_crear_evaluacion_progreso(),
    )

    assert registro["titulo_ejercicio"] == (
        "Practica con append"
    )


def test_crear_registro_no_filtra_solucion_privada():
    """
    Impide almacenar información privada innecesaria.
    """
    ejercicio = _crear_ejercicio_progreso()

    registro = crear_registro_progreso(
        tecnologia="python",
        ejercicio=ejercicio,
        evaluacion=_crear_evaluacion_progreso(),
    )

    assert "solucion_esperada" not in registro
    assert ejercicio.solucion_esperada not in str(
        registro
    )


def test_crear_registro_rechaza_tecnologia_no_registrada():
    """
    Solo admite tecnologías del catálogo oficial.
    """
    with pytest.raises(
        ValueError,
        match="no está registrada",
    ):
        crear_registro_progreso(
            tecnologia="cobol",
            ejercicio=_crear_ejercicio_progreso(),
            evaluacion=_crear_evaluacion_progreso(),
        )


def test_crear_registro_rechaza_fecha_sin_zona_horaria():
    """
    Evita guardar fechas locales ambiguas.
    """
    fecha_sin_zona = datetime(
        2026,
        8,
        30,
        10,
        15,
        20,
    )

    with pytest.raises(
        ValueError,
        match="debe incluir zona horaria",
    ):
        crear_registro_progreso(
            tecnologia="python",
            ejercicio=_crear_ejercicio_progreso(),
            evaluacion=_crear_evaluacion_progreso(),
            fecha=fecha_sin_zona,
        )


def test_crear_registro_requiere_evaluacion_validada():
    """
    Rechaza un diccionario que no haya pasado por Pydantic.
    """
    with pytest.raises(
        TypeError,
        match="EvaluacionEjercicio validada",
    ):
        crear_registro_progreso(
            tecnologia="python",
            ejercicio=_crear_ejercicio_progreso(),
            evaluacion={
                "respuesta_correcta": True,
                "puntuacion": 10,
            },
        )

def test_cargar_historial_inexistente_devuelve_vacio(
    tmp_path,
):
    """
    La primera ejecución comienza con un historial vacío.
    """
    historial = cargar_historial_progreso(
        directorio=tmp_path,
    )

    assert historial == {
        "version": 1,
        "intentos": [],
    }


def test_cargar_historial_valido(
    tmp_path,
):
    """
    Recupera y valida un intento almacenado.
    """
    registro = crear_registro_progreso(
        tecnologia="python",
        ejercicio=_crear_ejercicio_progreso(),
        evaluacion=_crear_evaluacion_progreso(),
        fecha=datetime(
            2026,
            8,
            30,
            10,
            15,
            20,
            tzinfo=timezone.utc,
        ),
    )

    ruta = (
        tmp_path
        / "progreso_estudiante.json"
    )
    ruta.write_text(
        json.dumps(
            {
                "version": 1,
                "intentos": [registro],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    historial = cargar_historial_progreso(
        directorio=tmp_path,
    )

    assert historial["version"] == 1
    assert historial["intentos"] == [
        registro
    ]


def test_cargar_historial_rechaza_json_corrupto(
    tmp_path,
):
    """
    Convierte un JSON ilegible en un error controlado.
    """
    ruta = (
        tmp_path
        / "progreso_estudiante.json"
    )
    ruta.write_text(
        "{esto no es json",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="JSON inválido",
    ):
        cargar_historial_progreso(
            directorio=tmp_path,
        )


def test_cargar_historial_rechaza_version_desconocida(
    tmp_path,
):
    """
    Impide interpretar silenciosamente otro formato de archivo.
    """
    ruta = (
        tmp_path
        / "progreso_estudiante.json"
    )
    ruta.write_text(
        json.dumps(
            {
                "version": 2,
                "intentos": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="versión",
    ):
        cargar_historial_progreso(
            directorio=tmp_path,
        )


def test_cargar_historial_rechaza_intento_manipulado(
    tmp_path,
):
    """
    Detecta campos inesperados dentro de un intento.
    """
    registro = crear_registro_progreso(
        tecnologia="python",
        ejercicio=_crear_ejercicio_progreso(),
        evaluacion=_crear_evaluacion_progreso(),
    )

    # Simula una modificación externa del archivo.
    registro["solucion_esperada"] = "dato no permitido"

    ruta = (
        tmp_path
        / "progreso_estudiante.json"
    )
    ruta.write_text(
        json.dumps(
            {
                "version": 1,
                "intentos": [registro],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="intento inválido",
    ):
        cargar_historial_progreso(
            directorio=tmp_path,
        )

def test_guardar_registro_crea_archivo(
    tmp_path,
):
    """
    Crea el directorio y el archivo durante el primer intento.
    """
    directorio = (
        tmp_path
        / "progreso"
    )

    registro = crear_registro_progreso(
        tecnologia="python",
        ejercicio=_crear_ejercicio_progreso(),
        evaluacion=_crear_evaluacion_progreso(),
        fecha=datetime(
            2026,
            8,
            30,
            10,
            15,
            20,
            tzinfo=timezone.utc,
        ),
    )

    ruta = guardar_registro_progreso(
        registro=registro,
        directorio=directorio,
    )

    assert ruta == (
        directorio
        / "progreso_estudiante.json"
    )
    assert ruta.is_file()

    historial = cargar_historial_progreso(
        directorio=directorio,
    )

    assert historial["version"] == 1
    assert historial["intentos"] == [
        registro
    ]


def test_guardar_registro_conserva_intentos_anteriores(
    tmp_path,
):
    """
    Añade intentos sin sobrescribir los registros anteriores.
    """
    primer_registro = crear_registro_progreso(
        tecnologia="python",
        ejercicio=_crear_ejercicio_progreso(),
        evaluacion=_crear_evaluacion_progreso(),
        fecha=datetime(
            2026,
            8,
            30,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    segundo_registro = crear_registro_progreso(
        tecnologia="python",
        ejercicio=_crear_ejercicio_progreso(),
        evaluacion=_crear_evaluacion_progreso(),
        fecha=datetime(
            2026,
            8,
            30,
            11,
            0,
            tzinfo=timezone.utc,
        ),
    )

    guardar_registro_progreso(
        primer_registro,
        directorio=tmp_path,
    )
    guardar_registro_progreso(
        segundo_registro,
        directorio=tmp_path,
    )

    historial = cargar_historial_progreso(
        directorio=tmp_path,
    )

    assert historial["intentos"] == [
        primer_registro,
        segundo_registro,
    ]


def test_guardar_registro_rechaza_datos_manipulados(
    tmp_path,
):
    """
    Valida el registro antes de crear o modificar archivos.
    """
    registro = crear_registro_progreso(
        tecnologia="python",
        ejercicio=_crear_ejercicio_progreso(),
        evaluacion=_crear_evaluacion_progreso(),
    )

    # Simula un campo que nunca debería persistirse.
    registro["solucion_esperada"] = "dato privado"

    with pytest.raises(
        ValueError,
        match="campos ausentes o inesperados",
    ):
        guardar_registro_progreso(
            registro,
            directorio=tmp_path,
        )

    assert not (
        tmp_path
        / "progreso_estudiante.json"
    ).exists()


def test_guardar_registro_preserva_archivo_si_falla_reemplazo(
    tmp_path,
    monkeypatch,
):
    """
    Conserva el historial anterior si falla el reemplazo atómico.
    """
    registro = crear_registro_progreso(
        tecnologia="python",
        ejercicio=_crear_ejercicio_progreso(),
        evaluacion=_crear_evaluacion_progreso(),
    )

    ruta = guardar_registro_progreso(
        registro,
        directorio=tmp_path,
    )
    contenido_anterior = ruta.read_text(
        encoding="utf-8"
    )

    def reemplazo_fallido(
        self,
        destino,
    ):
        """Simula un error del sistema durante el reemplazo."""
        raise OSError(
            "Fallo de reemplazo simulado"
        )

    monkeypatch.setattr(
        Path,
        "replace",
        reemplazo_fallido,
    )

    with pytest.raises(
        RuntimeError,
        match="No se pudo guardar",
    ):
        guardar_registro_progreso(
            registro,
            directorio=tmp_path,
        )

    # El archivo definitivo anterior permanece intacto.
    assert ruta.read_text(
        encoding="utf-8"
    ) == contenido_anterior
