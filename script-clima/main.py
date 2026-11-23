import time
import json
import requests
import paho.mqtt.client as mqtt

# Configuración del Broker MQTT y credenciales
MQTT_HOST = "mosquitto"
MQTT_PORT = 1883
MQTT_TOPIC = "almeria/clima"
MQTT_USER = "admin"
MQTT_PASS = "1308"

API_URL = "https://api.open-meteo.com/v1/forecast?latitude=36.8381&longitude=-2.4597&current=temperature_2m,relative_humidity_2m,surface_pressure"

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("¡Conectado exitosamente al broker MQTT con autenticación!", flush=True)
    else:
        print(f"Error de conexión MQTT, código: {rc}", flush=True)

# Inicializar cliente MQTT
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect

# Configurar usuario y contraseña aquí
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

print(f"Intentando conectar a MQTT en {MQTT_HOST}:{MQTT_PORT}...", flush=True)
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_start()

def enviar_clima():
    try:
        print("Realizando petición a la API de Open-Meteo...", flush=True)
        response = requests.get(API_URL, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            current = data["current"]
            
            payload = {
                "temperature": current["temperature_2m"],
                "humidity": current["relative_humidity_2m"],
                "pressure": current["surface_pressure"],
                "timestamp": current["time"]
            }
            
            mqtt_client.publish(MQTT_TOPIC, json.dumps(payload))
            print(f"API OK. Datos enviados a MQTT: {payload}", flush=True)
        else:
            print(f"Error: No se ha podido conectar con la API (Código HTTP: {response.status_code})", flush=True)
    except Exception as e:
        print(f"Excepción en la petición: {e}", flush=True)

if __name__ == "__main__":
    print("Iniciando script de captura de clima...", flush=True)
    time.sleep(5)
    
    while True:
        enviar_clima()
        time.sleep(300)