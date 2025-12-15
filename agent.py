import os
import requests
import asyncio
import osmnx as ox
import subprocess
import sys
import unidecode
from agents import set_tracing_export_api_key, Runner, function_tool, Agent
#from IPython.display import Markdown, display
from dotenv import load_dotenv

load_dotenv()

# 1. Leer la API key
api_key = os.getenv("OPENAI_API_KEY")
set_tracing_export_api_key(api_key)


# -----------------------------------------------------------
# 🔧 TOOL: descarga un grafo OSM sin simplificar usando OSMnx
# -----------------------------------------------------------
@function_tool
async def download_osm_map(place_name: str) -> str:
    """
    Descarga el grafo OSM del municipio indicado usando OSMnx sin simplificar.
    El resultado se guarda en un archivo .osm en el directorio actual.
    """
    try:
        # Nombre de archivo seguro
        filename = unidecode.unidecode(place_name.lower().replace(' ', '_')) + ".osm"

        print(f"Descargando el grafo OSM de '{place_name}' usando OSMnx (sin simplificar)...")

        # Descargar el grafo sin simplificar, solo vías transitables en coche
        G = ox.graph_from_place(place_name, network_type='drive', simplify=False)

        # Guardar como archivo .osm
        ox.save_graph_xml(G, filepath=filename)

        return filename

    except Exception as e:
        return f"Error durante la descarga: {str(e)}"


# -----------------------------------------------------------
# 🔧 TOOL 2: convierte un archivo OSM a red SUMO usando osmBuild.py
# -----------------------------------------------------------
@function_tool
async def convert_osm_to_sumo(osm_file: str) -> str:
    """
    Convierte un archivo OSM a red SUMO (.net.xml) usando osmBuild.py
    """
    try:
        if not os.path.exists(osm_file):
            return f"El archivo '{osm_file}' no existe."

        output_file = os.path.splitext(osm_file)[0] + ".net.xml"

        # Ruta a osmBuild.py en Windows dentro del venv
        venv_path = sys.prefix  # apunta a ...\venv
        osm_build_script = os.path.join(venv_path, "Lib", "site-packages", "sumo", "tools", "osmBuild.py")
        if not os.path.exists(osm_build_script):
            return f"No se encontró osmBuild.py en '{osm_build_script}'."

        # Ejecutar osmBuild.py mediante subprocess
        cmd = ["python", osm_build_script, "--osm-file", osm_file]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return f"Error al convertir el OSM: {result.stderr}"

        return f"Archivo SUMO generado correctamente: '{output_file}'"

    except Exception as e:
        return f"Error durante la conversión: {str(e)}"

# -----------------------------------------------------------
# 🔧 TOOL 3: genera demanda SUMO usando randomTrips.py
# -----------------------------------------------------------
@function_tool
async def generate_sumo_demand(net_file: str, duration: int = 3600, period: float = 1.0) -> str:
    """
    Genera una demanda de tráfico para SUMO usando randomTrips.py
    a partir de una red .net.xml existente.
    """
    try:
        if not os.path.exists(net_file):
            return f"El archivo de red '{net_file}' no existe."

        base_name = os.path.splitext(net_file)[0]
        trips_file = base_name + ".trips.xml"
        routes_file = base_name + ".rou.xml"

        # Ruta a randomTrips.py dentro del venv (Windows)
        venv_path = sys.prefix
        random_trips_script = os.path.join(
            venv_path,
            "Lib",
            "site-packages",
            "sumo",
            "tools",
            "randomTrips.py"
        )

        if not os.path.exists(random_trips_script):
            return f"No se encontró randomTrips.py en '{random_trips_script}'."

        print("Generando demanda de tráfico con randomTrips.py...")

        cmd = [
            "python",
            random_trips_script,
            "-n", net_file,
            "-e", str(duration),
            "-p", str(period),
            "--trip-attributes", 'departLane="best" departSpeed="max"',
            "--route-file", routes_file
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return f"Error al generar la demanda: {result.stderr}"

        return (
            "Demanda SUMO generada correctamente:\n"
            f"- Red: {net_file}\n"
            f"- Rutas: {routes_file}\n"
            f"- Duración: {duration}s\n"
            f"- Periodo: {period}s"
        )

    except Exception as e:
        return f"Error durante la generación de demanda: {str(e)}"


# -----------------------------------------------------------
# 🤖 AGENTE: descarga OSM y lo convierte a SUMO automáticamente
# -----------------------------------------------------------
osm_agent = Agent(
    name="Agente OSM a SUMO",
    model="gpt-4.1-mini",
    instructions=(
        "Eres un agente especializado en Movilidad y GIS. "
        "Cuando el usuario indique un lugar o municipio:\n"
        "1. Descarga el archivo OSM\n"
        "2. Lo convierte a red SUMO (.net.xml) usando osmBuild.py \n"
        "3. Genera automáticamente una demanda de tráfico "
        "usando randomTrips.py\n"
        "Devuelve mensajes claros sobre cada paso."
    ),
    tools=[download_osm_map, convert_osm_to_sumo, generate_sumo_demand],
)


# -----------------------------------------------------------
# 🚀 FUNCIÓN PRINCIPAL ASYNC
# -----------------------------------------------------------
async def main():
    # Input en una sola frase
    user_input = "Descarga y convierte a red de SUMO el mapa de Pamplona"

    # Ejecutar el agente
    result = await Runner.run(
        starting_agent=osm_agent,
        input=user_input
    )

    print(result)

# -----------------------------------------------------------
# Ejecutar
# -----------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
