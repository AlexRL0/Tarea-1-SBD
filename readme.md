# Sistema de Monitorización Climática de Almería

Proyecto de captura, procesamiento, almacenamiento y visualización en tiempo real de variables meteorológicas de **Almería** (**temperatura**, **humedad** y **presión atmosférica**) utilizando **Python**, **MQTT (Mosquitto)**, **Node-RED**, **InfluxDB v2** y **Grafana** desplegados con **Docker Compose**.

---

## 1. Cómo levantar el stack

1. **Clonar o situarse en la carpeta del proyecto** donde se encuentran el `docker-compose.yml` y el script de Python.
2. **Levantar los contenedores en segundo plano y el script (si esta implementado como servicio en el Compose):**
   ```bash
   docker compose up -d --build
   ```
3. **Verificar que todos los servicios están activos:**
   ```bash
   docker compose ps
   ```
4. **Detener el stack (cuando sea necesario):**
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

| Variable | Valor por defecto | Descripción |
| :--- | :--- | :--- |
| `MOSQUITTO_PORT` | `1883` | Puerto expuesto para el broker MQTT Eclipse Mosquitto. |
| `NODERED_PORT` | `1880` | Puerto expuesto para el editor/interfaz web de Node-RED. |
| `INFLUXDB_PORT` | `8086` | Puerto expuesto para la interfaz y API HTTP de InfluxDB v2. |
| `GRAFANA_PORT` | `3000` | Puerto expuesto para la interfaz web de Grafana. |
| `DOCKER_INFLUXDB_INIT_MODE` | `setup` | Modo de inicialización automática de InfluxDB en el primer arranque. |
| `DOCKER_INFLUXDB_INIT_USERNAME_FILE` | `/run/secrets/influxdb2-admin-username` | Ruta del secreto con el usuario administrador inicial de InfluxDB. |
| `DOCKER_INFLUXDB_INIT_PASSWORD_FILE` | `/run/secrets/influxdb2-admin-password` | Ruta del secreto con la contraseña administradora inicial de InfluxDB. |
| `DOCKER_INFLUXDB_INIT_ADMIN_TOKEN_FILE` | `/run/secrets/influxdb2-admin-token` | Ruta del secreto con el token de administración de InfluxDB. |
| `DOCKER_INFLUXDB_INIT_ORG` | `docs` | Organización inicial configurada en InfluxDB. |
| `DOCKER_INFLUXDB_INIT_BUCKET` | `home` | Bucket inicial creado durante el arranque de InfluxDB. |
| `GF_SERVER_ROOT_URL` | `http://grafana/` | URL base configurada para el servidor de Grafana. |
| `GF_PLUGINS_PREINSTALL` | `grafana-clock-panel` | Plugin preinstalado al iniciar el contenedor de Grafana. |
| `TIMEZONE` | `Europe/Madrid` | Zona horaria configurada para Node-RED. |

#### Variables y campos de telemetría (InfluxDB / Flux)
- **Bucket de trabajo en consultas:** `Almeria` (además del bucket inicial `home` definido en `.env`)[cite: 9, 11].
- **Measurement (`_measurement`):** `almeria_clima`[cite: 9].
- **Fields (`_field`):** `temperatura`, `humedad` y `presion` (procesados como valores numéricos desde Node-RED / script de publicación)[cite: 9].

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