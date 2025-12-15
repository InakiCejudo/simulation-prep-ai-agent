# SUMO simulation preparation AI Agent
Sistema multiagente IA para descargar el mapa OSM de una localidad, convertirlo a network de SUMO y generar una demanda de tráfico aleatoria.

## Instrucciones 

1. Crea un entorno virtual de Python y actívalo
   ```
   uv venv
   (Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)
   .\.venv\Scripts\activate
   ```
2. Instala dependencias:
   ```
   uv pip install -r requirements.txt
   ```
3. Crea un fichero .env con tu API KEY de OPENAI.

4. Inicia el agente
   ```
   python sumo-agent.py
   ```

* Prompt ejemplo: "Descarga y convierte a SUMO el mapa de Pamplona y genera demanda" o "Descarga y convierte a SUMO el mapa de Donostia".

## Arquitectura sistema multi agente

![Arquitectura](architecture.png)