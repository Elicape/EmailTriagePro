# EmailTriagePro — Inventario de dependencias V1

## Archivos .py del proyecto (excluyendo venv/)

```
daemon.py              628 líneas
gui_main.py           1014 líneas
main.py                669 líneas
resumen_batch.py         8 líneas
test_telegram_alert.py 151 líneas
```

---

## 1. daemon.py

### Funciones

| Línea | Función | Qué hace | Entrada / Huérfana |
|-------|---------|----------|-------------------|
| 40 | `decode_mime_header(header_value)` | Decodifica cabeceras MIME (Base64/QP) a string legible | [ENTRADA: daemon.run_classification] |
| 58 | `get_email_body(msg)` | Extrae cuerpo texto/html de un email.message | [ENTRADA: daemon.run_classification] |
| 84 | `get_llama_cli_path(config_path=None)` | Busca binario llama-cli en bin/, ~/llama.cpp/ o PATH | [ENTRADA: daemon.run_classification] |
| 112 | `get_model_path(config_model_path=None)` | Busca archivo .gguf en models/ o raíz del workspace | [ENTRADA: daemon.run_classification] |
| 127 | `send_telegram_msg(token, chat_id, text)` | Envía mensaje simple a Telegram via requests.post | **[HUÉRFANA]** — definida pero nunca llamada |
| 136 | `send_desktop_notification(title, message)` | Notificación nativa con plyer | [ENTRADA: daemon.run_classification] |
| 149 | `log_accion(email_id, user_type, accion, aprobado, log_path)` | Escribe línea de auditoría en logs/acciones.log | [ENTRADA: daemon.run_classification] |
| 156 | `load_prompt_file(filepath, default_content)` | Lee archivo de prompt o devuelve default | [ENTRADA: daemon.run_classification] |
| 167 | `run_classification(system_global_override=None)` | Clasificador principal: conecta IMAP, ejecuta LLM, decide escalada | [ENTRADA: CLI (__main__), gui_main (QProcess), main (QProcess)] |
| 441 | `send_telegram_alert(token, chat_id, jsons)` | Envía alerta con inline keyboard Aprobar/Rechazar | [ENTRADA: daemon.run_classification] |
| 477 | `send_summary()` | Envía resumen de pendientes por Telegram | [ENTRADA: resumen_batch (import directo)] |
| 559 | `start_bot()` | Inicia bot Telegram para callbacks con polling infinito | [ENTRADA: CLI (daemon.py --bot)] |

### Clases

Ninguna.

---

## 2. gui_main.py

### Clases

| Línea | Clase | Métodos | Qué hace | Entrada / Huérfana |
|-------|-------|---------|----------|-------------------|
| 31 | **Switch(QPushButton)** | `__init__`, `_on_click`, `_update_style`, `set_state`, `is_on` | Botón ON/OFF deslizante personalizado | [ENTRADA: ConfigView lo instancia] |
| 81 | **ImapTestThread(QThread)** | `__init__`, `run` | Prueba conexión IMAP en hilo separado | [ENTRADA: ConfigView._test_imap] |
| 103 | **TelegramTestThread(QThread)** | `__init__`, `run` | Envía mensaje de prueba a Telegram en hilo | [ENTRADA: ConfigView._test_telegram] |
| 131 | **DaemonWorker(QObject)** | `__init__`, `start`, `stop`, `is_running`, `_on_stdout`, `_on_finished` | Ejecuta daemon.py via QProcess, captura stdout, parsea resultado | [ENTRADA: MainWindow._setup_daemon] |
| 212 | **MonitorView(QWidget)** | `__init__`, `append_output`, `clear_output` | QTextEdit con estilo terminal oscuro, solo lectura | [ENTRADA: MainWindow._build_ui] |
| 251 | **ConfigView(QWidget)** | `__init__`, `_make_section_title`, `_make_separator`, `_make_form_row`, `_make_button`, `_build_ui`, `load_config`, `get_config`, `_save_config`, `_test_imap`, `_on_imap_test_result`, `_test_telegram`, `_on_tg_test_result` | Formulario de configuración en QScrollArea con tests en vivo | [ENTRADA: MainWindow._build_ui] |
| 707 | **MainWindow(QMainWindow)** | `__init__`, `_build_ui`, `_update_button_states`, `_update_status_lights`, `_show_about`, `_setup_daemon`, `_setup_timers`, `_start_monitoring`, `_pause_monitoring`, `_on_timer_tick`, `_run_daemon_now`, `_on_run_started`, `_on_run_finished`, `_now_str`, `_show_config`, `_show_monitor`, `_on_config_saved`, `_load_config_file`, `_save_config_file`, `closeEvent`, `_cleanup` | Ventana principal con barra de botones, luces de estado, stack monitor/config | [ENTRADA: CLI (__main__)] |

### Funciones sueltas

Ninguna — todo está encapsulado en clases.

---

## 3. main.py

### Clases

| Línea | Clase | Métodos | Qué hace | Entrada / Huérfana |
|-------|-------|---------|----------|-------------------|
| 14 | **ActionsCellWidget(QWidget)** | `__init__` | Widget con 3 botones (Aprobar/Rechazar/Ver email) por fila de tabla | [ENTRADA: MainWindow.load_pending_data] |
| 97 | **EmailDetailsDialog(QDialog)** | `__init__` | Dialog modal con metadatos, triage IA y cuerpo del email | [ENTRADA: MainWindow.show_email_details] |
| 240 | **MainWindow(QMainWindow)** | `__init__`, `load_pending_data`, `load_log_data`, `process_action`, `show_email_details`, `trigger_daemon_run`, `on_daemon_finished`, `on_tab_changed` | Ventana con tabs Pendientes/Log, tabla de correos, ejecuta daemon.py via QProcess | [ENTRADA: CLI (__main__)] |

### Funciones sueltas

Ninguna.

---

## 4. resumen_batch.py

### Funciones

Ninguna definida. Solo `__main__` que importa y llama a `daemon.send_summary()`.

---

## 5. test_telegram_alert.py

### Funciones

| Línea | Función | Qué hace | Entrada / Huérfana |
|-------|---------|----------|-------------------|
| 8 | `parse_qwen_output(stdout)` | Replica el parseo con rfind de daemon.py | **[HUÉRFANA]** — solo usada en tests |
| 19 | `escalada(email_item)` | Replica la lógica de escalada Urgente-Firma/urgencia>=4 | **[HUÉRFANA]** — solo usada en tests |
| 22 | `build_email_item(message_id, de, asunto, cuerpo, classification)` | Replica la construcción de email_item con update fix | **[HUÉRFANA]** — solo usada en tests |

### Clases

Ninguna.

---

## 6. Resumen de [HUÉRFANAS]

| Archivo | Función | Línea | Notas |
|---------|---------|-------|-------|
| `daemon.py` | `send_telegram_msg` | 127 | Definida pero nunca invocada en ningún .py del proyecto. Sobrante de un refactor (se pasó a `send_telegram_alert` que usa inline keyboards). |
| `test_telegram_alert.py` | `parse_qwen_output` | 8 | Solo llamada dentro del `__main__` del test |
| `test_telegram_alert.py` | `escalada` | 19 | Solo llamada dentro del `__main__` del test |
| `test_telegram_alert.py` | `build_email_item` | 22 | Solo llamada dentro del `__main__` del test |

---

## 7. Grafo de dependencias

```
                  ┌──────────────────────────────────────────┐
                  │              CLI (usuario)                │
                  │  python3 daemon.py [--bot]               │
                  │  python3 gui_main.py / main.py           │
                  │  python3 resumen_batch.py                │
                  └──────┬─────────────────────┬─────────────┘
                         │                     │
              ┌──────────▼────────┐   ┌───────▼───────────┐
              │   gui_main.py     │   │     main.py        │
              │   (QMainWindow)   │   │  (QMainWindow)     │
              │                   │   │                    │
              │  ┌─ Switch        │   │  ┌─ ActionsCell    │
              │  ├─ ImapTestThrd  │   │  ├─ EmailDetails   │
              │  ├─ TelegramTest  │   │  └─ DaemonRunner   │
              │  ├─ DaemonWorker──┼───┼───► QProcess       │
              │  ├─ MonitorView   │   │     daemon.py      │
              │  ├─ ConfigView    │   └───────┬────────────┘
              │  └─ MainWindow    │           │
              └────────┬──────────┘           │
                       │                      │
                       │  QProcess            │  QProcess
                       │  (subprocess)        │  (subprocess)
                       ▼                      ▼
              ┌──────────────────────────────────────────────┐
              │               daemon.py                       │
              │                                               │
              │  run_classification() ←── entrada principal   │
              │       │                                       │
              │       ├── decode_mime_header()                │
              │       ├── get_email_body()                    │
              │       ├── get_llama_cli_path()                │
              │       ├── get_model_path()                    │
              │       ├── send_desktop_notification()         │
              │       ├── log_accion()                        │
              │       ├── load_prompt_file()                  │
              │       └── send_telegram_alert()               │
              │                                               │
              │  send_summary() ←── importado por             │
              │     resumen_batch.py                          │
              │                                               │
              │  start_bot() ←── CLI --bot flag               │
              │       └── handle_callback() (inner)           │
              │                                               │
              │  send_telegram_msg() [HUÉRFANA]               │
              └──────────────────────────────────────────────┘

Importación directa (Python import):
    resumen_batch.py  ──import──►  daemon.send_summary()

Ejecución por subproceso (QProcess / subprocess):
    gui_main.DaemonWorker  ──QProcess──►  daemon.py
    main.MainWindow        ──QProcess──►  daemon.py

Sin relación entre sí (no se importan):
    gui_main.py  ──X──  main.py     (no hay import mutuo)
    test_telegram_alert.py  ──X──  daemon.py  (código duplicado, no import)
```

---

## 8. Observaciones

1. **Dos GUIs separadas que hacen lo mismo**: `gui_main.py` y `main.py` son dos entry points que no se comunican entre sí. Ambas ejecutan `daemon.py` via QProcess. Código duplicado que el plan V2 fusiona en `app.py`.

2. **`send_telegram_msg` muerta**: La función en `daemon.py:127` es un wrapper para mensajes simples a Telegram, pero nunca se llama. El código actual usa `requests.post()` directamente dentro de `send_telegram_alert` y `send_summary`.

3. **Tests con código duplicado**: `test_telegram_alert.py` replica la lógica de parseo y escalada de `daemon.py` en vez de importarla. Cualquier cambio en `daemon.py` requiere actualizar el test manualmente.

4. **`resumen_batch.py` es el único import directo entre archivos**: Es el único caso donde un .py importa una función de otro mediante `from daemon import send_summary`.

5. **Sin dependencias circulares**: El grafo es estrictamente jerárquico (daemon.py en la base, GUIs por encima).
