# Sistema de Monitorización Climática de Almería (IoT & Observabilidad)

Proyecto de captura, procesamiento, almacenamiento y visualización en tiempo real de variables meteorológicas de **Almería** (**temperatura**, **humedad** y **presión atmosférica**) utilizando **Python**, **MQTT (Mosquitto)**, **Node-RED**, **InfluxDB v2** y **Grafana** desplegados con **Docker Compose**.

---

## 1. Cómo levantar el stack

1. **Clonar o situarse en la carpeta del proyecto** donde se encuentran el `docker-compose.yml` y el script de Python.
2. **Levantar los contenedores en segundo plano:**
   ```bash
   docker compose up -d
   ```
3. **Verificar que todos los servicios están activos:**
   ```bash
   docker compose ps
   ```
4. **Ejecutar el productor de datos en Python** (si no está ya como servicio en el Compose):
   ```bash
   python3 productor_clima.py
   ```
5. **Detener el stack (cuando sea necesario):**
   ```bash
   docker compose down
   ```

---

## 2. Endpoints y Credenciales por Defecto

| Servicio | Endpoint Local | Endpoint Red Interna Docker | Usuario por defecto | Contraseña por defecto | Notas |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Grafana** | `http://localhost:3000` | `http://grafana:3000` | `admin` | `admin` | Solicita cambio de clave en el primer inicio |
| **InfluxDB v2** | `http://localhost:8086` | `http://influxdb:8086` | *(Configurado en `.env` / Compose)* | *(Configurado en `.env` / Compose)* | Bucket: `Almeria` |
| **Node-RED** | `http://localhost:1880` | `http://nodered:1880` | *Sin autenticación* (o según `settings.js`) | *N/A* | Flujo MQTT $\rightarrow$ InfluxDB |
| **Mosquitto (MQTT)** | `mqtt://localhost:1883` | `mqtt://mosquitto:1883` | *Acceso anónimo* (por defecto) | *N/A* | Puerto TCP `1883` |

---

## 3. Variables Utilizadas

### a) Variables de entorno / configuración del stack (`.env` / `docker-compose.yml`)
* `DOCKER_INFLUXDB_INIT_MODE`: `setup`
* `DOCKER_INFLUXDB_INIT_USERNAME`: usuario administrador de InfluxDB
* `DOCKER_INFLUXDB_INIT_PASSWORD`: contraseña de InfluxDB
* `DOCKER_INFLUXDB_INIT_ORG`: organización en InfluxDB
* `DOCKER_INFLUXDB_INIT_BUCKET`: `Almeria`
* `DOCKER_INFLUXDB_INIT_ADMIN_TOKEN`: token de acceso utilizado por Node-RED y Grafana
* `MQTT_BROKER` / `MQTT_PORT` / `MQTT_TOPIC`: host (`mosquitto` o `localhost`), puerto (`1883`) y tópico donde publica el script de Python

### b) Variables meteorológicas almacenadas en InfluxDB
* **Bucket:** `Almeria`
* **Measurement (`_measurement`):** `almeria_clima`
* **Fields (`_field`) — tipo numérico (`float`):**
  * `temperatura`: temperatura ambiente ($^\circ\text{C}$)
  * `humedad`: humedad relativa ($\%$)
  * `presion`: presión atmosférica ($\text{hPa}$)

---

## 4. Procesamiento y Consultas del Dashboard

### Transformación en Node-RED (`function`)
Convierte el JSON entrante desde MQTT a *Line Protocol* numérico para InfluxDB:

```javascript
const d = msg.payload || {};

const temperatura = Number(d.temperature);
const humedad = Number(d.humidity);
const presion = Number(d.pressure);

msg.payload = `almeria_clima temperatura=${temperatura},humedad=${humedad},presion=${presion}`;

return msg;
```

### Consultas Flux en Grafana (`Clima-Almeria`)

* **a) Valores actuales (`Stat`):**
  ```flux
  from(bucket: "Almeria")
    |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
    |> filter(fn: (r) => r["_measurement"] == "almeria_clima")
    |> filter(fn: (r) => r["_field"] == "temperatura" or r["_field"] == "humedad" or r["_field"] == "presion")
    |> last()
  ```

* **b) Gráfica última hora (`Time series`, intervalo fijo `-1h` y *auto-refresh*):**
  ```flux
  from(bucket: "Almeria")
    |> range(start: -1h, stop: now())
    |> filter(fn: (r) => r["_measurement"] == "almeria_clima")
    |> filter(fn: (r) => r["_field"] == "temperatura" or r["_field"] == "humedad" or r["_field"] == "presion")
    |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
    |> yield(name: "mean")
  ```

* **c) Tendencia 24 h (`Stat` con indicador $\uparrow$/$\downarrow$, porcentaje a 2 decimales y umbral rojo $< 0$):**
  ```flux
  import "math"

  from(bucket: "Almeria")
    |> range(start: -24h, stop: now())
    |> filter(fn: (r) => r["_measurement"] == "almeria_clima" and (r["_field"] == "temperatura" or r["_field"] == "humedad" or r["_field"] == "presion"))
    |> keep(columns: ["_time", "_field", "_value"])
    |> group(columns: ["_field"])
    |> sort(columns: ["_time"])
    |> reduce(
        fn: (r, accumulator) => ({
          primero: if accumulator.count == 0 then r._value else accumulator.primero,
          ultimo: r._value,
          count: accumulator.count + 1
        }),
        identity: {primero: 0.0, ultimo: 0.0, count: 0}
      )
    |> map(fn: (r) => {
        raw_pct = if r.primero != 0.0 then (r.ultimo - r.primero) / r.primero * 100.0 else 0.0
        pct = math.round(x: raw_pct * 100.0) / 100.0
        flecha = if pct >= 0.0 then "↑" else "↓"
        return {
          _time: now(),
          _value: pct,
          tendencia: r._field + ": " + flecha + " " + string(v: pct) + "%"
        }
      })
  ```

---

## 5. Capturas del Dashboard

*(Sustituye las rutas por las imágenes guardadas en tu carpeta `docs/` o `img/` del repositorio)*

### Vista general del Dashboard (`Clima-Almeria`)
![Vista general del Dashboard](./img/dashboard_general.png)

### Paneles individuales (Valores actuales, Gráfica 1h y Tendencia 24h)
![Panel Tendencia 24h](./img/panel_tendencia_24h.png)