import time
import json
import requests
import paho.mqtt.client as mqtt

# Configuración del Broker MQTT
MQTT_HOST = "mosquitto"
MQTT_PORT = 1883
MQTT_TOPIC = "almeria/clima"

# Coordenadas de Almería y endpoint de Open-Meteo
API_URL = "https://api.open-meteo.com/v1/forecast?latitude=36.8381&longitude=-2.4597&current=temperature_2m,relative_humidity_2m,surface_pressure"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Conectado exitosamente al broker MQTT.")
    else:
        print(f"Error de conexión MQTT, código: {rc}")

# Inicializar cliente MQTT
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect

print(f"Conectando a MQTT en {MQTT_HOST}:{MQTT_PORT}...")
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_start()

def fetch_and_publish():
    try:
        # Petición HTTP a la API pública con manejo de errores (robustez mínima requerida)[cite: 2]
        response = requests.get(API_URL, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            current = data.get("current", {})
            
            # Construcción del payload
            payload = {
                "temperature": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "pressure": current.get("surface_pressure"),
                "timestamp": current.get("time")
            }
            
            # Publicación en MQTT
            mqtt_client.publish(MQTT_TOPIC, json.dumps(payload))
            print(f"Datos publicados correctamente: {payload}")
        else:
            print(f"Error en la API: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"Excepción capturada durante la petición o publicación: {e}")

# Bucle principal de ejecución
if __name__ == "__main__":
    print("Iniciando script de captura de clima para Almería...")
    while True:
        fetch_and_publish()
        # Esperar 5 minutos exactos
        time.sleep(300)