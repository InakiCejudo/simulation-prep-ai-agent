# -*- coding: utf-8 -*-

import os
import asyncio
import subprocess
import sys
import unidecode
import osmnx as ox

from dotenv import load_dotenv
from agents import (
    set_tracing_export_api_key,
    Runner,
    function_tool,
    Agent,
)

# =========================================================
# ENV
# =========================================================
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
set_tracing_export_api_key(api_key)

# =========================================================
# 🔧 TOOL 1: Descargar OSM
# =========================================================
@function_tool
async def download_osm_map(place_name: str) -> str:
    """
    Descarga un grafo OSM sin simplificar y lo guarda como .osm.
    Devuelve SOLO el nombre del archivo generado.
    """
    filename = unidecode.unidecode(place_name.lower().replace(" ", "_")) + ".osm"
    print(f"📥 Descargando mapa OSM para: {place_name} ...")

    G = ox.graph_from_place(
        place_name,
        network_type="drive",
        simplify=False
    )

    ox.save_graph_xml(G, filepath=filename)
    print(f"✅ Archivo OSM generado: {filename}")
    return filename


# =========================================================
# 🔧 TOOL 2: Convertir OSM → SUMO (.net.xml)
# =========================================================
@function_tool
async def convert_osm_to_sumo(osm_file: str) -> str:
    """
    Convierte un archivo .osm a red SUMO (.net.xml).
    Devuelve el nombre REAL del archivo .net.xml generado.
    """
    if not os.path.exists(osm_file):
        raise FileNotFoundError(osm_file)

    base_name = os.path.splitext(osm_file)[0]
    output_net = base_name + ".net.xml"

    venv_path = sys.prefix
    osm_build_script = os.path.join(
        venv_path, "Lib", "site-packages", "sumo", "tools", "osmBuild.py"
    )
    print(f"⚙️  Convirtiendo {osm_file} a red SUMO (.net.xml) ...")
    subprocess.run(
        [
            "python",
            osm_build_script,
            "--osm-file", osm_file,
            "--prefix", base_name
        ],
        check=True,
        capture_output=True,
        text=True
    )

    if not os.path.exists(output_net):
        raise RuntimeError(f"No se generó el archivo esperado: {output_net}")

    print(f"✅ Archivo SUMO generado: {output_net}")
    return output_net



# =========================================================
# 🔧 TOOL 3: Generar demanda SUMO
# =========================================================
@function_tool
async def generate_sumo_demand(
    net_file: str,
    duration: int = 1800,
    period: float = 1.0
) -> str:
    """
    Genera demanda SUMO con randomTrips.py.
    Devuelve un mensaje resumen.
    """
    if not os.path.exists(net_file):
        raise FileNotFoundError(net_file)

    base = os.path.splitext(net_file)[0]
    routes_file = base + ".rou.xml"

    venv_path = sys.prefix
    random_trips_script = os.path.join(
        venv_path, "Lib", "site-packages", "sumo", "tools", "randomTrips.py"
    )

    print(f"🚦 Generando demanda SUMO para {net_file} ...")
    subprocess.run(
        [
            "python",
            random_trips_script,
            "-n", net_file,
            "-e", str(duration),
            "-p", str(period),
            "--trip-attributes", 'departLane="best" departSpeed="max"',
            "--route-file", routes_file,
        ],
        check=True,
        capture_output=True,
        text=True
    )

    print(f"✅ Demanda generada: {routes_file}")
    return (
        "Demanda generada correctamente:\n"
        f"- Red: {net_file}\n"
        f"- Rutas: {routes_file}\n"
        f"- Duración: {duration}s\n"
        f"- Periodo: {period}s"
    )


# =========================================================
# 🤖 SUBAGENTE 1: Descarga OSM
# =========================================================
osm_download_agent = Agent(
    name="Agente Descargador OSM",
    model="gpt-4.1-mini",
    instructions=(
        "Descarga mapas OSM usando OSMnx. "
        "Recibes un nombre de lugar y devuelves "
        "EXCLUSIVAMENTE el nombre del archivo .osm generado."
    ),
    tools=[download_osm_map],
)

# =========================================================
# 🤖 SUBAGENTE 2: Conversión a red SUMO
# =========================================================
sumo_net_agent = Agent(
    name="Agente Conversor SUMO",
    model="gpt-4.1-mini",
    instructions=(
        "Conviertes archivos .osm en redes SUMO (.net.xml) "
        "usando osmBuild.py. "
        "Recibes un archivo .osm y devuelves "
        "EXCLUSIVAMENTE el nombre del archivo .net.xml."
    ),
    tools=[convert_osm_to_sumo],
)

# =========================================================
# 🤖 SUBAGENTE 3: Generación de demanda
# =========================================================
demand_agent = Agent(
    name="Agente Generador de Demanda",
    model="gpt-4.1-mini",
    instructions=(
        "Generas demanda de tráfico para SUMO usando randomTrips.py. "
        "Recibes un archivo .net.xml y produces un archivo .rou.xml."
    ),
    tools=[generate_sumo_demand],
)

# =========================================================
# 🧠 ORQUESTADOR
# =========================================================
ORCHESTRATOR_PROMPT = (
    "Eres el orquestador de un sistema multi-agente para simulaciones "
    "de tráfico con SUMO.\n\n"
    "Debes ejecutar SIEMPRE este flujo:\n"
    "1. Llamar al agente de descarga OSM\n"
    "2. Pasar el archivo OSM al agente de conversión SUMO\n"
    "3. Pasar la red SUMO al agente de generación de demanda\n\n"
    "No preguntes al usuario si desea continuar.\n"
    "Al final, devuelve un resumen completo del proceso."
)

orchestrator = Agent(
    name="Orquestador SUMO",
    model="gpt-4.1",
    instructions=ORCHESTRATOR_PROMPT,
    tools=[
        osm_download_agent.as_tool(
            tool_name="download_osm",
            tool_description="Descargar mapa OSM de un municipio"
        ),
        sumo_net_agent.as_tool(
            tool_name="convert_to_sumo",
            tool_description="Convertir OSM a red SUMO (.net.xml)"
        ),
        demand_agent.as_tool(
            tool_name="generate_demand",
            tool_description="Generar demanda SUMO con randomTrips.py"
        ),
    ],
)

# =========================================================
# 🚀 REPL INTERACTIVO
# =========================================================
async def repl():
    print("🤖 REPL Orquestador SUMO. Escribe 'exit' para salir.\n")
    while True:
        user_input = input("➡️  Tú: ").strip()
        if user_input.lower() in ("exit", "quit"):
            print("👋 Saliendo del REPL...")
            break
        if not user_input:
            continue

        try:
            result = await Runner.run(
                starting_agent=orchestrator,
                input=user_input
            )
            print("\n===== RESULTADO =====\n")
            print(result.final_output)
            print("\n====================\n")
        except Exception as e:
            print("🚨 Error durante la ejecución:")
            print(e)
            print("\n====================\n")

if __name__ == "__main__":
    asyncio.run(repl())
