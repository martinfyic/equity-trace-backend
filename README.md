# Portfolio Tracker (backend)

API en FastAPI para registrar compras y ventas de acciones y calcular el estado del
portafolio: posiciones, costo promedio, valor de mercado, ganancias realizadas y no
realizadas, y la evolución diaria. El acceso está protegido con login (usuario único) y
token JWT, pensado para usarse online desde un frontend separado.

## Índice
1. [Funcionalidades](#funcionalidades)
2. [Puesta en marcha](#puesta-en-marcha-local)
3. [Configuración](#configuración)
4. [Autenticación](#autenticación)
5. [Referencia de la API](#referencia-de-la-api)
6. [Reglas de negocio y cálculos](#reglas-de-negocio-y-cálculos)
7. [Precios de mercado](#precios-de-mercado)
8. [Errores](#errores)
9. [Modelo de datos y migraciones](#modelo-de-datos-y-migraciones)
10. [Estructura del proyecto](#estructura-del-proyecto)
11. [Tests](#tests)
12. [Producción](#producción)
13. [Limitaciones conocidas](#limitaciones-conocidas)

---

## Funcionalidades

- **Operaciones:** alta, listado con filtros, edición y baja de compras y ventas, con cantidades fraccionarias y comisión por operación.
- **Validación del historial:** no permite ventas por encima de lo que se poseía en esa fecha, ni editar o borrar operaciones que dejarían el historial inválido.
- **Posiciones:** cantidad, costo promedio (con comisiones), costo total, ganancia realizada, y con precio actual: valor de mercado y ganancia no realizada (monto y %).
- **Resumen del portafolio:** totales de costo, valor de mercado, ganancia no realizada y realizada.
- **Evolución diaria:** serie día a día de costo, valor de mercado y ganancias, lista para graficar.
- **Precios actuales e históricos** vía `yfinance`, con caché y respaldo si la fuente falla.
- **Login de usuario único** con contraseña hasheada (bcrypt), token JWT con vencimiento y límite de intentos fallidos.
- **CORS** restringido al dominio del frontend.
- **Base de datos:** SQLite en desarrollo, PostgreSQL en producción, con migraciones (Alembic) y decimales exactos.
- **Endpoint de salud** (`/health`) para chequeos del hosting.

---

## Puesta en marcha (local)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
                                     # Windows Git Bash:   source .venv/Scripts/activate
pip install -r requirements-dev.txt   # incluye las herramientas de test
```

### 1. Configuración
```bash
cp .env.example .env                 # Windows CMD: copy .env.example .env
```
Completá en `.env`:

1. `APP_PASSWORD_HASH`: ejecutá `python -m app.scripts.hash_password`, escribí tu
   contraseña (mínimo 12 caracteres) y pegá el resultado **entre comillas simples**.
2. `JWT_SECRET`: ejecutá `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   y pegá el resultado.
3. `APP_USERNAME` y, si querés, `ACCESS_TOKEN_MINUTES` y `CORS_ORIGINS`.

### 2. Base de datos
```bash
alembic upgrade head
```
Si ya tenías un `portfolio.db` de la versión anterior (con tus operaciones), **no lo borres**:
ejecutá `alembic stamp head` en lugar del comando anterior, y las tablas existentes
quedan registradas como migradas.

### 3. Servidor
```bash
uvicorn app.main:app --reload
```
Documentación interactiva en http://127.0.0.1:8000/docs. Para probar endpoints protegidos:
`POST /auth/login` → copiá `access_token` → botón **Authorize** (candado) → pegalo.

---

## Configuración

Variables de entorno (en desarrollo se leen desde `.env`; las variables ya definidas en el entorno tienen prioridad).

| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `APP_USERNAME` | sí | — | Nombre del usuario único. |
| `APP_PASSWORD_HASH` | sí | — | Hash bcrypt de la contraseña (ver `app.scripts.hash_password`). |
| `JWT_SECRET` | sí | — | Clave para firmar tokens. Mínimo 32 caracteres. |
| `DATABASE_URL` | no | `sqlite:///./portfolio.db` | Base de datos. Acepta `postgresql://…` y `postgres://…` (se convierten solas al driver `psycopg`). |
| `ACCESS_TOKEN_MINUTES` | no | `1440` | Duración de la sesión (24 h). |
| `CORS_ORIGINS` | no | `http://localhost:3000` | Dominios del frontend permitidos, separados por coma. |

Si falta alguna variable obligatoria, la app **no arranca** y el mensaje indica cuál es.

---

## Autenticación

- Hay un único usuario, definido por variables de entorno. No existe registro de usuarios.
- `POST /auth/login` entrega un token JWT (HS256) que vence a los `ACCESS_TOKEN_MINUTES`. No hay renovación: al vencer, hay que volver a iniciar sesión.
- Todas las rutas, salvo `/health` y `/auth/login`, exigen el header `Authorization: Bearer <token>`.
- **Límite de intentos:** tras 5 intentos fallidos desde la misma IP, el login responde `429` durante 15 minutos (incluso con la contraseña correcta). El contador vive en memoria: se reinicia al reiniciar el servidor.
- El login no revela si falló el usuario o la contraseña.
- `/docs` y `/openapi.json` son públicos (muestran la estructura de la API, no datos).

---

## Referencia de la API

Los números decimales viajan como **texto** en el JSON (por ejemplo `"0.036566"`) para no perder precisión. Las fechas usan el formato `AAAA-MM-DD`.

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/health` | no | Estado del servicio. |
| POST | `/auth/login` | no | Iniciar sesión. |
| GET | `/auth/me` | sí | Usuario de la sesión actual. |
| POST | `/transactions` | sí | Crear operación. |
| GET | `/transactions` | sí | Listar y filtrar operaciones. |
| PUT | `/transactions/{id}` | sí | Reemplazar una operación. |
| DELETE | `/transactions/{id}` | sí | Eliminar una operación. |
| GET | `/positions` | sí | Posiciones de todos los activos. |
| GET | `/positions/{ticker}` | sí | Posición de un activo. |
| GET | `/portfolio/summary` | sí | Totales del portafolio. |
| GET | `/portfolio/history` | sí | Evolución diaria. |

### `GET /health`
```json
{ "status": "ok" }
```

### `POST /auth/login`
Cuerpo:
```json
{ "username": "admin", "password": "tu-contraseña" }
```
Respuesta `200`:
```json
{ "access_token": "eyJhbGciOi...", "token_type": "bearer", "expires_in": 86400 }
```
`expires_in` está en segundos. Errores: `401` credenciales incorrectas, `429` demasiados intentos.

### `GET /auth/me`
```json
{ "username": "admin" }
```
Útil para que el frontend compruebe si la sesión sigue vigente.

### `POST /transactions`
Cuerpo:
```json
{
  "ticker": "msft",
  "type": "BUY",
  "date": "2025-09-26",
  "quantity": "0.036566",
  "price": "508.94",
  "fee": "1.39",
  "notes": "primera compra"
}
```

| Campo | Tipo | Reglas |
|---|---|---|
| `ticker` | texto | 1 a 20 caracteres. Se guarda en mayúsculas. Si el activo no existe, se crea solo. |
| `type` | `BUY` o `SELL` | Obligatorio. |
| `date` | fecha | No puede ser futura. |
| `quantity` | decimal | Mayor que 0. Admite fracciones. |
| `price` | decimal | Mayor que 0. Precio por unidad. |
| `fee` | decimal | Mayor o igual a 0. Opcional (por defecto 0). |
| `notes` | texto | Opcional, hasta 255 caracteres. |

Respuesta `201`:
```json
{
  "type": "BUY", "date": "2025-09-26", "quantity": "0.036566",
  "price": "508.94", "fee": "1.39", "notes": "primera compra",
  "id": 1, "ticker": "MSFT"
}
```
Errores: `422` si un campo no cumple las reglas, o si es una venta mayor a lo que se poseía en esa fecha.

### `GET /transactions`
Parámetros opcionales (se pueden combinar):

| Parámetro | Ejemplo | Efecto |
|---|---|---|
| `ticker` | `?ticker=msft` | Solo ese activo (no distingue mayúsculas). |
| `date_from` | `?date_from=2025-10-01` | Desde esa fecha, inclusive. |
| `date_to` | `?date_to=2025-12-31` | Hasta esa fecha, inclusive. |

Devuelve una lista de operaciones ordenada por fecha y luego por id. Una fecha con formato inválido responde `422`.

### `PUT /transactions/{id}`
Reemplaza la operación completa. El cuerpo es el mismo que el de creación, **sin `ticker`** (el activo no se puede cambiar; si te equivocaste de activo, borrá la operación y creala de nuevo).
```json
{ "type": "BUY", "date": "2025-10-09", "quantity": "0.094106", "price": "719.72", "fee": "2.50" }
```
Respuesta `200` con la operación actualizada. Errores: `404` si no existe, `422` si el nuevo historial quedaría inválido (por ejemplo, reducir una compra que respalda una venta posterior).

### `DELETE /transactions/{id}`
Respuesta `204` sin cuerpo. Errores: `404` si no existe, `422` si al borrarla alguna venta posterior quedaría sin respaldo.

### `GET /positions`
Una entrada por activo con cantidad mayor a 0.

| Parámetro | Efecto |
|---|---|
| `include_closed=true` | Incluye también los activos que ya vendiste por completo (cantidad 0), útiles para ver su ganancia realizada. |

```json
[
  {
    "ticker": "MSFT",
    "quantity": "0.130672",
    "avg_cost": "689.3586",
    "total_cost": "90.08",
    "realized_pnl": "0.00",
    "current_price": "535.79",
    "market_value": "70.01",
    "unrealized_pnl": "-20.07",
    "unrealized_pnl_pct": "-22.28"
  }
]
```

| Campo | Significado |
|---|---|
| `ticker` | Activo. |
| `quantity` | Cantidad que se posee hoy (compras menos ventas). |
| `avg_cost` | Costo promedio por unidad, **incluyendo comisiones**. |
| `total_cost` | Dinero invertido en lo que todavía se posee (incluye comisiones). |
| `realized_pnl` | Ganancia o pérdida ya concretada por ventas. |
| `current_price` | Precio actual por unidad. |
| `market_value` | `quantity × current_price`. |
| `unrealized_pnl` | `market_value − total_cost`. Ganancia "en papel". |
| `unrealized_pnl_pct` | `unrealized_pnl / total_cost × 100`. |

Si no se pudo obtener el precio actual, los cinco campos que dependen de él (`current_price`, `market_value`, `unrealized_pnl`, `unrealized_pnl_pct`) vienen en `null`; el resto se calcula igual. En posiciones cerradas tampoco se consulta el precio.

### `GET /positions/{ticker}`
Misma estructura que un elemento de `/positions`, para un solo activo (sin distinguir mayúsculas). Devuelve también activos cerrados. Error `404` si el activo no existe.

### `GET /portfolio/summary`
```json
{
  "total_cost": "90.08",
  "market_value": "70.01",
  "unrealized_pnl": "-20.07",
  "realized_pnl": "0.00",
  "tickers_without_price": []
}
```

| Campo | Significado |
|---|---|
| `total_cost` | Suma del costo de todas las posiciones abiertas. |
| `market_value` | Suma del valor de mercado de las posiciones abiertas con precio disponible. |
| `unrealized_pnl` | Suma de las ganancias no realizadas de esas mismas posiciones. |
| `realized_pnl` | Ganancia realizada acumulada de **todos** los activos, incluidos los cerrados. |
| `tickers_without_price` | Activos abiertos cuyo precio no se pudo obtener. Quedan fuera de `market_value` y `unrealized_pnl`, pero sí cuentan en `total_cost`. |

### `GET /portfolio/history`
Evolución día a día del portafolio.

| Parámetro | Por defecto | Efecto |
|---|---|---|
| `date_from` | fecha de la primera operación | Inicio de la serie. |
| `date_to` | hoy | Fin de la serie. |

```json
[
  { "date": "2025-09-26", "total_cost": "20.00", "market_value": "18.65",
    "unrealized_pnl": "-1.35", "realized_pnl": "0.00" },
  "...",
  { "date": "2025-10-10", "total_cost": "90.08", "market_value": "91.47",
    "unrealized_pnl": "1.39", "realized_pnl": "0.00" }
]
```
(Ejemplo con precios de cierre de prueba.)

- Devuelve **un punto por día**, incluidos fines de semana y feriados.
- `total_cost`, `market_value` y `unrealized_pnl` reflejan lo que se poseía ese día; `realized_pnl` es acumulado hasta ese día.
- Si no hay operaciones, devuelve `[]`. Si `date_from` es posterior a `date_to`, responde `422`.
- **Precio de cada día:** el último cierre disponible hasta esa fecha (así sábados y feriados arrastran el último cierre). Si todavía no hay cierres, o la fuente de precios falló, se usa el precio de la última operación registrada.

---

## Reglas de negocio y cálculos

El método es **costo promedio ponderado**. Todo el cálculo usa `Decimal` y el redondeo se aplica solo al devolver la respuesta (2 decimales para dinero, 4 para `avg_cost`; `quantity` se muestra tal cual).

**Compra**
- Costo de la operación = `cantidad × precio + comisión`.
- La cantidad y el costo se suman a la posición.

**Venta**
- Ingreso neto = `cantidad × precio − comisión`.
- Ganancia realizada = ingreso neto − (`cantidad vendida × costo promedio al momento de la venta`).
- El costo promedio de lo que queda **no cambia**; bajan la cantidad y el costo total proporcionalmente.
- Si se vende todo, la posición queda en cero y su costo vuelve a 0.

**Orden de las operaciones**
- Se procesan cronológicamente. Si hay varias el mismo día, las compras van antes que las ventas.

**Validaciones del historial**
- En cada alta, edición o baja se simula el historial completo resultante. Si en algún punto se vendería más de lo que se tenía, la operación se rechaza con `422` y un mensaje como `Venta de 5 el 2025-09-26 excede la cantidad disponible (0.036566).`

**Ejemplo (las dos compras de MSFT)**

| Operación | Cálculo | Costo con comisión |
|---|---|---|
| Compra 26/09/2025 | 0,036566 × 508,94 + 1,39 | ≈ 20,00 |
| Compra 09/10/2025 | 0,094106 × 719,72 + 2,35 | ≈ 70,08 |
| **Total** | cantidad 0,130672 | **≈ 90,08** |

Costo promedio con comisiones: ≈ 689,36 por acción.

---

## Precios de mercado

- **Fuente:** `yfinance` (Yahoo Finance, no oficial: puede fallar o cambiar sin aviso).
- **Precio actual:** caché en memoria de 10 minutos.
- **Precios históricos:** cierres diarios sin ajustar por dividendos, con caché de 1 hora.
- **Si la fuente falla:** se devuelve el último valor conocido aunque esté vencido; si no hay ninguno, el precio queda en `null` (posiciones y resumen) o se usa el último precio operado (historial).
- Las cachés viven en memoria: se vacían al reiniciar el servidor.
- Los precios están en la moneda de cotización del activo (para acciones de EE. UU., dólares).

---

## Errores

| Código | Cuándo |
|---|---|
| `401` | Falta el token, es inválido, está vencido, o las credenciales del login son incorrectas. |
| `404` | La operación o el activo no existen. |
| `422` | Datos inválidos, o una regla de negocio no se cumple (venta excesiva, historial inválido, rango de fechas invertido). |
| `429` | Demasiados intentos de login fallidos. |

Hay dos formatos de `422`:

- **Regla de negocio:** `{ "detail": "Venta de 5 el 2025-09-26 excede la cantidad disponible (0.036566)." }`
- **Campo inválido:** `detail` es una lista con la ubicación del problema, por ejemplo `"loc": ["body", "quantity"]` y `"msg": "Input should be greater than 0"`.

---

## Modelo de datos y migraciones

**`assets`**: `id`, `ticker` (único), `name`, `currency` (por defecto `USD`). Se crea automáticamente al registrar la primera operación de un ticker; por ahora `name` repite el ticker y la moneda no se expone en la API.

**`transactions`**: `id`, `asset_id`, `type` (`BUY`/`SELL`), `date`, `quantity`, `price`, `fee`, `notes`.

**Decimales:** en PostgreSQL se guardan como `NUMERIC(24,10)` (hasta 10 decimales); en SQLite como texto, para no perder precisión.

**Migraciones (Alembic)**
```bash
alembic upgrade head                      # aplicar migraciones
alembic stamp head                        # registrar como migrada una base ya existente
alembic revision --autogenerate -m "..."  # crear una migración tras cambiar models.py
alembic check                             # verificar que modelos y migraciones coinciden
```
Alembic toma la base desde `DATABASE_URL` y no necesita las variables de login.

---

## Estructura del proyecto

```
portfolio-tracker/
├── app/
│   ├── main.py             # app, CORS, /health y registro de routers protegidos
│   ├── config.py           # variables de entorno
│   ├── auth.py             # login, JWT, límite de intentos
│   ├── db.py               # conexión a la base
│   ├── models.py           # tablas (SQLAlchemy)
│   ├── schemas.py          # validación de entrada y salida (Pydantic)
│   ├── routers/
│   │   ├── transactions.py # CRUD de operaciones
│   │   ├── positions.py    # posiciones y resumen
│   │   └── history.py      # evolución diaria
│   ├── services/
│   │   ├── portfolio.py    # cálculos (puros, sin base de datos)
│   │   ├── history.py      # serie diaria (pura)
│   │   ├── ledger.py       # valida el historial de operaciones
│   │   └── prices.py       # precios actuales e históricos con caché
│   └── scripts/
│       └── hash_password.py
├── alembic/                # migraciones
├── tests/
├── .env.example
├── alembic.ini
└── requirements.txt
```

La lógica de cálculo vive en `services/` y no depende de FastAPI ni de la base de datos, por lo que se prueba directamente y se puede cambiar el método (por ejemplo, a FIFO) tocando solo `portfolio.py`.

---

## Tests

```bash
pytest
```
Cubren los cálculos (compras, ventas parciales y totales, validación cronológica, orden en el mismo día), la evolución diaria, el login (token válido, inválido, vencido y falsificado, límite de intentos), CORS y los endpoints de operaciones, posiciones, resumen e historial. Los tests no consultan precios reales: usan valores simulados.

---

## Producción
- Guía paso a paso del despliegue (Neon + Render + Vercel): ver `GUIA-DESPLIEGUE.md`.
- Comando de arranque: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- La versión de Python está fijada en `.python-version` (3.12), que es con la que se probó.

- Usá PostgreSQL: `DATABASE_URL=postgresql://usuario:clave@host/db` (también acepta `postgres://`).
- Ejecutá `alembic upgrade head` en cada despliegue, antes de levantar la app.
- `CORS_ORIGINS` debe contener el dominio exacto del frontend (por ejemplo `https://mi-app.vercel.app`).
- Serví siempre por HTTPS y guardá las variables como secretos del hosting, nunca en git.
- Detrás de un proxy, el límite de intentos de login ve la IP del proxy; en una app de un solo usuario alcanza, y se puede ajustar con las opciones de cabeceras de proxy de uvicorn.

---

## Limitaciones conocidas

- **Un solo usuario** y una sola moneda (USD); no hay multi-moneda.
- **Splits y dividendos:** las cantidades no se ajustan por splits de acciones (los cierres históricos de Yahoo sí vienen ajustados por splits, lo que distorsionaría el historial de un activo con split), y los dividendos no se registran.
- **Método de costo:** solo costo promedio; no hay FIFO ni cálculo de impuestos.
- **Precios:** dependen de `yfinance`, que no es una fuente oficial. Con varios usuarios o mucho tráfico convendría un proveedor con API key.
- **Caché y límite de login en memoria:** válidos para una sola instancia del servidor.
- **Sesión:** el token no se puede revocar antes de que venza (no hay logout del lado del servidor).
