# EmailTriagePro — Clasificador con Qwen local + Alertas Telegram

## v1.0 — Cerrado

**4 cambios clave frente a la versión anterior:**

| Cambio | Por qué |
|--------|---------|
| **Arranque inteligente** | Sin `config.ini` muestra bienvenida humana. Ni un intento fantasma de conexión. |
| **Configuración dinámica** | Elige Gmail / Zoho / Otro IMAP y solo ves los campos que necesitas. |
| **Modo Demo** | 25 emails de ejemplo clasificados con reglas de keywords en 0.02 segundos, sin internet, sin IA. |
| **Documentación para no-técnicos** | `CONEXION_Y_USO.md` explica paso a paso sin palabras raras. |

**5 checks de terminado:** ✅ sin `config.ini` → bienvenida | ✅ Demo clasifica 25 | ✅ Config dinámica 2/4 campos | ✅ README con historia de Laura | ✅ `test_smoke.py` 2/2

---

## El caso de Laura

Laura gestiona papeles para autónomos en un pueblo de Aragón. Recibe 40 emails al día. Entre facturas, Hacienda y ofertas de seguros, se le colaba lo urgente.

Probó esta app: Conectó su Zoho en 2 minutos. Ahora solo mira Telegram cuando vibra. El resto lo revisa los viernes con café.

Laura no sabe qué es IMAP. Ni falta que hace.

---

Sistema autónomo que clasifica correos IMAP mediante un LLM local (Qwen3-VL 2B) y escala alertas Urgente-Firma a Telegram con botones Aprobar/Rechazar. Diseñado para autónomos que necesitan priorizar correos críticos sin depender de APIs externas.

## Arquitectura

```
┌──────────────┐    IMAP SSL    ┌──────────────────────────────────────────────┐
│  Zoho / GMail │ ────────────→ │                daemon.py                     │
│   (IMAP)      │               │                                              │
└──────────────┘               │  ┌──────────┐    ┌──────────────────────┐   │
                               │  │ fetch    │    │  subprocess.run()    │   │
                               │  │ unread   │───→│  llama-cli -m Qwen   │   │
                               │  │ emails   │    │  -p prompt -st       │   │
                               │  └──────────┘    │  --simple-io          │   │
                               │                  └──────────┬───────────┘   │
                               │                             │ JSON          │
                               │  ┌──────────────────────────▼────────────┐  │
                               │  │  parse con rfind('{') + json.load    │  │
                               │  └────────────────┬─────────────────────┘  │
                               │                   │                        │
                               │          ┌────────▼──────────┐             │
                               │          │  Urgente-Firma    │  etiqueta   │
                               │          │  o urgencia>=4    │  otra       │
                               │          └───┬────┬──────────┘             │
                               │              │    │                        │
                               │     Telegram │    │  Guardar en            │
                               │     Bot      │    │  pendientes/*.json     │
                               │     (inline) │    │                        │
                               └──────────────┼────┼────────────────────────┘
                                              │    │
              ┌──────────────────┐            │    │
              │ Telegram Bot     │ ←──────────┘    │
              │ Aprobar / Rechazar│                │
              └──────┬───────────┘                │
                     │ callback                   │
                     ▼                            ▼
              logs/acciones.log          pendientes/*.json (esperan resumen)
              procesados/*.json
```

### Interfaz gráfica (app.py)

```
MainWindow 900x650
├── Button Bar: [▶ Iniciar] [⏸ Pausar] [🔄 Procesar ahora]
├── ● IMAP  ● IA  ● Telegram (luces de estado en vivo)
└── QTabWidget
    ├── Tab Estado → log del daemon + "Última revisión: HH:MM"
    ├── Tab Pendientes → tabla con Aprobar/Rechazar/Ver email
    └── Tab Auditoría → acciones.log en tiempo real
```

## Instalación

```bash
# 1. Clonar repositorio
git clone <repo>
cd EmailTriagePro

# 2. Entorno virtual
python3.13 -m venv venv
source venv/bin/activate

# 3. Dependencias
pip install -r requirements.txt

# 4. Archivos grandes

**OBLIGATORIO: llama.cpp commit `1191758c5`, versión b9780. Otras versiones NO funcionan.**

```bash
# llama-cli (b9780 / commit 1191758c5)
# Descargar desde: https://github.com/ggml-org/llama.cpp/releases/tag/b9780
# O compilar desde el commit exacto:
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
git checkout 1191758c5
cmake -B build
cmake --build build --config Release
cp build/bin/llama-cli ../bin/

# Modelo Qwen (1.3GB). Colocar en models/
# https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF/resolve/main/Qwen3-VL-2B-Instruct-Q4_K_M.gguf
```

También puedes descargar el `.gguf` desde la pestaña "Releases" de HuggingFace
buscando `Qwen3-VL-2B-Instruct-GGUF`.

⚠️ **IMPORTANTE: Modelo único soportado**

Esta app SOLO funciona con:
`Qwen3-VL-2B-Instruct-Q4_K_M.gguf`

¿Por qué no puedo usar Phi-3, Llama-3, Mistral?
Porque v1.0 está calibrada para Qwen3-VL. Otros modelos rompen la clasificación.

Si pones otro modelo la app no arrancará y te avisará.

# 5. Configuración
cp config.ini.example config.ini   # editar con tus datos
```

### config.ini.example

```ini
[IMAP]
host = imap.tu-servidor.com
port = 993
user = tu@email.com
pass = TU_CONTRASEÑA_AQUI
use_ssl = true

[TELEGRAM]
token = 123456789:ABCdefGHIjkl...
chat_id = 123456789

[LLAMA]
llama_path = bin/llama-cli
model_path = models/Qwen3-VL-2B-Instruct-Q4_K_M.gguf

[GUI]
poll_interval = 60
log_disable = true
no_show_timings = true

[PERFIL]
user_id = usuario_01
user_name = Laura
```

**⚠️ `config.ini` contiene tus credenciales reales. No lo compartas ni lo subas al repositorio.**

## Uso

### Interfaz gráfica (recomendado)

```bash
python3 app.py
```

### One-shot (clasificar correos no leídos)

```bash
python3 daemon.py
```

### Bot de Telegram (para manejar callbacks Aprobar/Rechazar)

```bash
python3 daemon.py --bot
```

### Resumen programado

```bash
python3 resumen_batch.py
```

### Modo servicio (systemd)

```ini
[Unit]
Description=EmailTriagePro Daemon
After=network.target

[Service]
Type=simple
ExecStart=/ruta/venv/bin/python3 /ruta/daemon.py
WorkingDirectory=/ruta/
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

## Demo

```bash
# 1. Preparar — limpia estado anterior
./demo.sh
```

El script demo:
1. Limpia logs anteriores
2. Marca el último correo como No Leído en IMAP
3. Ejecuta el clasificador
4. Muestra el log de acciones

## Estructura del proyecto

```
EmailTriagePro/
├── app.py                      # Interfaz gráfica unificada (V2)
├── daemon.py                   # Clasificador principal (one-shot)
├── config.ini.example          # Plantilla de configuración (sin datos reales)
├── config.ini                  # [user] Credenciales reales (no incluido en repo)
├── crypto_utils.py             # Cifrado Fernet para secrets (V2)
├── wizard.py                   # SetupWizard primer arranque (V2)
├── requirements.txt            # Dependencias Python
├── build.spec                  # PyInstaller spec (V2)
├── package.sh                  # Script de empaquetado (V2)
├── skills/
│   ├── system_global.txt       # Prompt identidad del asistente
│   └── system_tarea.txt        # Prompt de clasificación JSON
├── logs/
│   └── acciones.log            # Auditoría de acciones
├── pendientes/                 # JSONs pendientes de aprobación/revisión
├── procesados/                 # JSONs ya procesados (con alerta enviada)
├── bin/llama-cli               # Binario llama-cli (no incluido en repo)
├── models/                     # Modelos GGUF (no incluido en repo)
└── docs/
    └── V2-plan.md              # Plan de desarrollo V2
```

## Tecnologías

- **LLM**: Qwen3-VL-2B-Instruct (GGUF Q4_K_M) vía llama-cli b9780
- **IMAP**: imaplib + SSL (compatible Zoho, Gmail, Outlook)
- **Telegram**: pyTelegramBotAPI con inline keyboards
- **GUI**: PySide6 (Qt for Python)
- **Cifrado**: cryptography (Fernet)
- **Notificaciones**: plyer (desktop notifications)

## Bugs corregidos (V1 → V2)

| # | Bug | Síntoma | Fix |
|---|-----|---------|-----|
| 1 | Guard `test` | Cualquier email con "test" escalaba pese a ser Urgente-Firma | Eliminar condición `'test' in asunto_lower` |
| 2 | Stale JSON | `json.load()` cargaba datos viejos del disco | Sobrescribir siempre con `json.dump()` |
| 3 | stdout contaminado | `stdout.find('{')` agarraba llave del template JSON | Usar `stdout.rfind('{')` para último bloque |
| 4 | Subprocess incompatible | `--no-display-prompt` no silenciaba salida | Reemplazar por `--simple-io` |
| 5 | ID duplicado | Reprocesar email pisaba JSON anterior | Sufijo `_N` con `while os.path.exists()` |
| 6 | Secrets en texto plano | config.ini con credenciales legibles | Cifrado Fernet + SetupWizard (V2) |
| 7 | GUIs duplicadas | gui_main.py y main.py separados | Fusión en app.py (V2) |
| 8 | Sin onboarding | Usuario debía editar .ini a mano | SetupWizard con tests en vivo (V2) |

## Licencia

Uso interno. No redistribuir sin autorización.
