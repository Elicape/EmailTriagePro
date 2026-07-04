"""
daemon.py - Core de EmailTriagePro
Entry points:
1. python daemon.py → run_classification() → loop IMAP cada 15min
2. python daemon.py --bot → start_bot() → escucha Telegram
3. import daemon; daemon.send_summary() → llamado por resumen_batch.py

Dependencias externas: llama-cli, config.ini
No importar desde GUI. La GUI lo ejecuta por QProcess.
"""
import os
import sys
import warnings
import socket
import imaplib
import email
import subprocess
import json
import requests
import configparser
import platform
import argparse
import shutil
import glob
import hashlib
import telebot
from pathlib import Path
from datetime import datetime
from email.header import decode_header

socket.setdefaulttimeout(10.0)

def decode_mime_header(header_value):
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        result_parts = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    result_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
                except Exception:
                    result_parts.append(part.decode('latin1', errors='ignore'))
            else:
                result_parts.append(part)
        return "".join(result_parts)
    except Exception:
        return str(header_value)

def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='ignore')
        # Fallback to HTML if text/plain not found
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='ignore')
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or 'utf-8'
            return payload.decode(charset, errors='ignore')
    return body

def get_llama_cli_path(config_path=None):
    if config_path and os.path.exists(config_path):
        return config_path
    
    is_windows = platform.system() == "Windows"
    filename = "llama-cli.exe" if is_windows else "llama-cli"
    
    # 1. Check relative bin/ directory in workspace
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    bin_path = os.path.join(workspace_dir, "bin", filename)
    if os.path.exists(bin_path):
        return bin_path
        
    # 2. Check user home llama.cpp paths
    home = os.path.expanduser("~")
    search_paths = [
        os.path.join(home, "llama.cpp", "build", "bin", filename),
        os.path.join(home, "llama.cpp", "buil", "bin", "llama-ci" if not is_windows else "llama-ci.exe"),
        os.path.join(home, "llama.cpp", "build", "bin", "llama-cli"),
        os.path.join(home, "llama.cpp", "buil", "bin", "llama-cli"),
    ]
    for p in search_paths:
        if os.path.exists(p):
            return p
            
    # 3. Fallback to system PATH
    return filename

def get_model_path(config_model_path=None):
    if config_model_path and os.path.exists(config_model_path):
        return config_model_path
        
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    search_paths = [
        os.path.join(workspace_dir, "Qwen3-VL-2B-Instruct-Q4_K_M.gguf"),
        os.path.join(workspace_dir, "models", "Qwen3-VL-2B-Instruct-Q4_K_M.gguf"),
        os.path.join(workspace_dir, "models", "qwen3-vl-2b-q4_k_m.gguf"),
    ]
    for p in search_paths:
        if os.path.exists(p):
            return p
    return "Qwen3-VL-2B-Instruct-Q4_K_M.gguf"


BASE_DIR = Path(__file__).parent
if platform.system() == "Windows":
    LLAMA_CLI = BASE_DIR / "bin_win" / "llama-cli"
else:
    LLAMA_CLI = BASE_DIR / "bin" / "llama-cli"
MODELO_ESPERADO = "Qwen3-VL-2B-Instruct-Q4_K_M.gguf"


def verificar_entorno():
    if not os.path.exists(LLAMA_CLI):
        raise FileNotFoundError(
            "No encuentro bin/llama-cli. Lee CONEXION_Y_USO.md"
        )

    modelo_path = Path("./models") / MODELO_ESPERADO
    if not modelo_path.exists():
        raise FileNotFoundError(
            f"No encuentro el modelo obligatorio.\n\n"
            f"Falta: models/{MODELO_ESPERADO}\n"
            f"Descárgalo de HuggingFace. Lee CONEXION_Y_USO.md sección 4.\n\n"
            f"IMPORTANTE: Otros modelos .gguf NO funcionan en v1.0."
        )

    env = os.environ.copy()
    bin_dir = os.path.dirname(LLAMA_CLI)
    env["LD_LIBRARY_PATH"] = f"{bin_dir}{os.pathsep}{env.get('LD_LIBRARY_PATH', '')}"

    result = subprocess.run(
        [LLAMA_CLI, "--version"],
        capture_output=True, text=True, env=env
    )
    if "1191758c5" not in result.stdout + result.stderr:
        raise RuntimeError(
            f"Versión incorrecta de llama-cli.\n"
            f"Necesitas: 9780 (1191758c5)\n"
            f"Baja la correcta desde README.md"
        )


def send_desktop_notification(title, message):
    try:
        from plyer import notification
        warnings.filterwarnings("ignore", message=".*dbus.*", category=UserWarning)
        notification.notify(
            title=title,
            message=message,
            app_name="EmailTriagePro",
            timeout=8
        )
    except Exception as e:
        print(f"[ERROR] No se pudo enviar notificación de escritorio: {e}", file=sys.stderr)

def log_accion(email_id, user_type, accion, aprobado, log_path):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp} | USUARIO: {user_type} | EMAIL_ID: {email_id} | ACCION: {accion} | APROBADO: {aprobado}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_line)

def load_prompt_file(filepath, default_content):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            print(f"[!] Advertencia al leer archivo de prompt {filepath}: {e}", file=sys.stderr)
    return default_content

def run_classification(system_global_override=None):
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(workspace_dir, "config.ini")
    
    # Read config
    config = configparser.ConfigParser()
    if os.path.exists(config_file):
        config.read(config_file, encoding='utf-8')
    else:
        print(f"[ERROR] No se encuentra el archivo de configuración {config_file}", file=sys.stderr)
        return
        
    proton_host = config.get("IMAP", "host", fallback="127.0.0.1")
    proton_port = config.getint("IMAP", "port", fallback=1143)
    proton_user = config.get("IMAP", "user", fallback="")
    proton_pass = config.get("IMAP", "pass", fallback="")
    
    tg_token = config.get("TELEGRAM", "token", fallback="")
    tg_chat_id = config.get("TELEGRAM", "chat_id", fallback="")
    
    llama_cfg_path = config.get("LLAMA", "llama_path", fallback="")
    model_cfg_path = config.get("LLAMA", "model_path", fallback="")
    
    llama_bin = get_llama_cli_path(llama_cfg_path)
    model_path = get_model_path(model_cfg_path)
    
    print(f"[*] Buscando ejecutable de llama-cli en: {llama_bin}")
    print(f"[*] Buscando modelo en: {model_path}")
    
    # Load separate system prompts from skills/
    skills_dir = os.path.join(workspace_dir, "skills")
    system_global_path = os.path.join(skills_dir, "system_global.txt")
    system_tarea_path = os.path.join(skills_dir, "system_tarea.txt")
    
    _DEFAULT_GLOBAL = (
        'Eres un asistente de inteligencia artificial confiable, profesional y '
        'enfocado en la administración de correos electrónicos. Tu identidad es '
        '"EmailTriagePro Assistant". Límites: Nunca inventes información. '
        'Limítate estrictamente a analizar los datos provistos y bajo ninguna '
        'circunstancia intentes ejecutar o comprometer acciones autónomas sin '
        'el consentimiento expreso del usuario humano.'
    )
    _DEFAULT_TAREA = (
        'Analiza el correo electrónico del usuario y clasifícalo devolviendo '
        'ÚNICAMENTE un objeto JSON válido con los siguientes campos:\n'
        '{"etiqueta": "Urgente-Firma" | "Urgente-Pago" | "Urgente-Decisión" '
        '| "Útil-Oportunidad" | "Útil-Info" | "Spam",\n'
        '"urgencia": 1-5,\n'
        '"resumen": "resumen en máximo 15 palabras",\n'
        '"accion_sugerida": "acción concreta propuesta",\n'
        '"requiere_aprobacion": true/false}\n\n'
        'Reglas críticas de clasificación:\n'
        '1. Si la etiqueta calculada es "Spam" y urgencia <= 2, '
        '"requiere_aprobacion" = false.\n'
        '2. Para cualquier otra combinación, este campo debe ser true.\n'
        '3. Responde exclusivamente con el JSON. Sin explicaciones, '
        'introducciones o bloques de código markdown.'
    )

    if system_global_override:
        print("[*] Usando system global proporcionado por argumento.")
        system_global = system_global_override.strip()
    else:
        system_global = load_prompt_file(system_global_path, _DEFAULT_GLOBAL)

    system_tarea = load_prompt_file(system_tarea_path, _DEFAULT_TAREA)
    
    # Connect IMAP with SSL -> Plain fallback
    mail = None
    use_ssl = config.getboolean("IMAP", "use_ssl", fallback=True)
    if use_ssl:
        try:
            print(f"[*] Conectando vía SSL en {proton_host}:{proton_port}...")
            mail = imaplib.IMAP4_SSL(proton_host, proton_port)
        except Exception as ssl_err:
            print(f"[!] Conexión SSL fallida ({ssl_err}). Reintentando conexión en plano...")
            try:
                mail = imaplib.IMAP4(proton_host, proton_port)
            except Exception as plain_err:
                print(f"[ERROR] No se pudo conectar al servidor IMAP: {plain_err}", file=sys.stderr)
                return
    else:
        try:
            print(f"[*] Conectando en plano en {proton_host}:{proton_port}...")
            mail = imaplib.IMAP4(proton_host, proton_port)
        except Exception as plain_err:
            print(f"[ERROR] No se pudo conectar al servidor IMAP: {plain_err}", file=sys.stderr)
            return

    try:
        print(f"[*] Autenticando usuario {proton_user}...")
        mail.login(proton_user, proton_pass)
        mail.select("inbox")
    except Exception as login_err:
        print(f"[ERROR] Error al iniciar sesión en IMAP: {login_err}", file=sys.stderr)
        try:
            mail.logout()
        except:
            pass
        return

    # Search for unseen emails
    try:
        _, data = mail.search(None, 'UNSEEN')
        email_ids = data[0].split()
        total_unseen = len(email_ids)
        print(f"[*] Encontrados {total_unseen} correos no leídos.")
    except Exception as search_err:
        print(f"[ERROR] Error al buscar correos: {search_err}", file=sys.stderr)
        mail.logout()
        return

    if total_unseen == 0:
        print("[*] No hay correos pendientes de clasificar.")
        mail.logout()
        return

    nuevos_archivos = []
    
    # Process each unseen email
    for idx, num in enumerate(email_ids):
        try:
            print(f"[*] Procesando correo {idx+1}/{total_unseen}...")
            _, msg_data = mail.fetch(num, '(RFC822)')
            if not msg_data or not msg_data[0]:
                continue
                
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            de_header = decode_mime_header(msg.get("From", "Desconocido"))
            asunto_header = decode_mime_header(msg.get("Subject", "(Sin asunto)"))
            cuerpo = get_email_body(msg)
            
            # Formulate Message-ID or unique identifier
            message_id = msg.get("Message-ID", "")
            if not message_id:
                message_id = f"gen_{int(datetime.now().timestamp())}_{idx}"
            else:
                # Clean up brackets
                message_id = message_id.strip("<>")
            
            date_str = msg.get("Date", "")
            # Format date parsed
            try:
                date_tuple = email.utils.parsedate_tz(date_str)
                if date_tuple:
                    local_time = email.utils.mktime_tz(date_tuple)
                    hora_email = datetime.fromtimestamp(local_time).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    hora_email = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                hora_email = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Call llama-cli with separated ChatML formatting for Qwen
            print(f"[*] Ejecutando LLM local para clasificar correo de: {de_header}...")
            
            chatml_prompt = (
                "<|im_start|>system\n"
                f"{system_global}\n\n"
                f"{system_tarea}"
                "<|im_end|>\n"
                "<|im_start|>user\n"
                f"ASUNTO: {asunto_header}\n"
                f"CUERPO:\n"
                f"{cuerpo[:2000]}"
                "<|im_end|>\n"
                "<|im_start|>assistant\n"
            )

            # Build subprocess command
            cmd = [
                llama_bin, 
                "-m", model_path, 
                "-p", chatml_prompt, 
                "-n", "256", 
                "--temp", "0.1",
                "-st",
                "--simple-io",
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
            
            # Find and parse JSON in llama output
            stdout = result.stdout or ""
            json_start = stdout.rfind('{')
            json_end = stdout.rfind('}')
            
            classification = None
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_str = stdout[json_start:json_end+1]
                try:
                    classification = json.loads(json_str)
                except Exception as e:
                    print(f"[!] Error al parsear JSON devuelto por modelo: {e}. Usando fallback.")
            
            # Fallback if parsing failed
            if not classification:
                stdout_lower = stdout.lower()
                is_spam = "spam" in stdout_lower or "spam" in asunto_header.lower()
                classification = {
                    "etiqueta": "Spam" if is_spam else "Útil-Info",
                    "urgencia": 1 if is_spam else 2,
                    "resumen": asunto_header[:50],
                    "accion_sugerida": "Revisar manualmente" if not is_spam else "Auto-archivar",
                    "requiere_aprobacion": not is_spam
                }
            
            # Enforce local business rule: Spam with urgency <= 2 -> requiere_aprobacion = False
            urgencia_val = int(classification.get("urgencia", 1))
            etiqueta_val = classification.get("etiqueta", "Spam")
            
            if etiqueta_val == "Spam" and urgencia_val <= 2:
                classification["requiere_aprobacion"] = False
            
            requiere_aprobacion = classification.get("requiere_aprobacion", True)
            resumen_val = classification.get("resumen", "(Sin resumen)")
            accion_val = classification.get("accion_sugerida", "Revisar manualmente")
            
            # Prepare email item for memory
            email_item = {
                "id": message_id,
                "hora": hora_email,
                "de": de_header,
                "asunto": asunto_header,
                "cuerpo": cuerpo,
                "etiqueta": etiqueta_val,
                "urgencia": urgencia_val,
                "resumen": resumen_val,
                "accion_sugerida": accion_val,
                "requiere_aprobacion": requiere_aprobacion
            }
            email_item.update(classification)
            email_item['urgencia'] = int(email_item['urgencia'])
            
            log_filepath = os.path.join(workspace_dir, "logs", "acciones.log")
            
            # Save or Auto-archive
            if requiere_aprobacion:
                pendientes_dir = os.path.join(workspace_dir, "pendientes")
                procesados_dir = os.path.join(workspace_dir, "procesados")
                os.makedirs(pendientes_dir, exist_ok=True)
                os.makedirs(procesados_dir, exist_ok=True)
                # 1. Ruta única — si el archivo ya existe, añadir sufijo _2, _3, ...
                base_id = message_id
                json_path = os.path.join(pendientes_dir, f"{message_id}.json")
                counter = 1
                while os.path.exists(json_path):
                    counter += 1
                    message_id = f"{base_id}_{counter}"
                    json_path = os.path.join(pendientes_dir, f"{message_id}.json")
                email_item["id"] = message_id
                with open(json_path, "w", encoding="utf-8") as fp:
                    json.dump(email_item, fp, ensure_ascii=False, indent=2)
                nuevos_archivos.append(json_path)
                
                escalada = (email_item.get('etiqueta','').strip() == 'Urgente-Firma' or int(email_item.get('urgencia', 0)) >= 4)
                
                if escalada:
                    print("[*] ALERTA: Urgente-Firma o urgencia>=4 detectado. Notificando...")
                    send_telegram_alert(tg_token, tg_chat_id, [email_item])
                    log_accion(message_id, "telegram", f"alerta ({etiqueta_val}, urgencia={urgencia_val})", "SI", log_filepath)
                    shutil.move(json_path, os.path.join(procesados_dir, os.path.basename(json_path)))
                    print("[*] ALERTA enviada. Archivo movido a procesados/")
                else:
                    print(f"[*] Guardado en pendientes/{os.path.basename(json_path)}. Esperando resumen programado.")
            else:
                # Auto-archive rule triggered
                print(f"[*] Correo {message_id} auto-archivado (requiere_aprobacion = False).")
                log_accion(message_id, "sistema", f"auto-archivo ({etiqueta_val})", "SI", log_filepath)

            # Desktop notification if urgency >= 4
            if urgencia_val >= 4:
                noti_title = f"🚨 {etiqueta_val} - Urgencia: {urgencia_val}"
                noti_body = f"De: {de_header}\nAsunto: {asunto_header}\nResumen: {resumen_val}"
                send_desktop_notification(noti_title, noti_body)

            # Mark email as SEEN only after successful classification
            mail.store(num, '+FLAGS', '\\Seen')
            print(f"[*] Correo {message_id} marcado como LEÍDO en servidor IMAP.")

        except Exception as msg_err:
            print(f"[ERROR] Error procesando correo index {idx}: {msg_err}", file=sys.stderr)

    # Logout from server
    try:
        mail.close()
        mail.logout()
        print("[*] Conexión IMAP cerrada correctamente.")
    except:
        pass
    
    if not nuevos_archivos:
        print("[*] No se guardaron nuevos correos en pendientes.")

def send_telegram_alert(token, chat_id, jsons):
    urgente_firma = [j for j in jsons if j['etiqueta'] == 'Urgente-Firma']
    no_urgentes = [j for j in jsons if j not in urgente_firma]
    
    mensaje = "*🔥 ALERTA EmailTriagePro*\n\n"
    mensaje += "*Requiere acción <24h:*\n"
    
    keyboard = []
    for email in urgente_firma:
        hash_id = hashlib.md5(email['id'].encode()).hexdigest()[:16]
        mensaje += f"- {email['resumen']}\n  Acción: {email['accion_sugerida']}\n"
        keyboard.append([
            {'text': 'Aprobar ✅', 'callback_data': f'app_{hash_id}'},
            {'text': 'Posponer ⏰', 'callback_data': f'rej_{hash_id}'}
        ])
    
    if no_urgentes:
        mensaje += f"\nResto: {len(no_urgentes)} emails procesados sin urgencia."
    
    data = {
        'chat_id': chat_id,
        'text': mensaje,
        'parse_mode': 'Markdown',
    }
    if keyboard:
        data['reply_markup'] = json.dumps({'inline_keyboard': keyboard})
    
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=15)
        if r.status_code == 200:
            print(f"[*] Alerta Telegram enviada correctamente.")
        else:
            print(f"[ERROR] Alerta Telegram respondió {r.status_code}: {r.text}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Error al enviar alerta Telegram: {e}", file=sys.stderr)

def send_summary():
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(workspace_dir, "config.ini")
    
    config = configparser.ConfigParser()
    if not os.path.exists(config_file):
        print(f"[ERROR] No se encuentra {config_file}", file=sys.stderr)
        return
    
    config.read(config_file, encoding='utf-8')
    tg_token = config.get("TELEGRAM", "token", fallback="")
    tg_chat_id = config.get("TELEGRAM", "chat_id", fallback="")
    
    if not tg_token or not tg_chat_id:
        print("[ERROR] TELEGRAM token/chat_id no configurados", file=sys.stderr)
        return
    
    pendientes_dir = os.path.join(workspace_dir, "pendientes")
    procesados_dir = os.path.join(workspace_dir, "procesados")
    
    os.makedirs(pendientes_dir, exist_ok=True)
    os.makedirs(procesados_dir, exist_ok=True)
    
    jsons = []
    for f in glob.glob(os.path.join(pendientes_dir, '*.json')):
        with open(f) as fp:
            data = json.load(fp)
            data['id'] = os.path.basename(f).replace('.json', '')
            jsons.append(data)
    
    if not jsons:
        print("[*] No hay pendientes.")
        return
    
    urgente_firma = [j for j in jsons if j['etiqueta'] == 'Urgente-Firma']
    oportunidades = [j for j in jsons if j['etiqueta'] == 'Útil-Oportunidad']
    infos = [j for j in jsons if j['etiqueta'] == 'Útil-Info']
    spam = [j for j in jsons if j['etiqueta'] == 'Spam']
    
    hora = datetime.now().strftime("%H:%M")
    mensaje = f"*EmailTriagePro - {hora}*\n\n"
    mensaje += f"Tienes *{len(jsons)} mensajes* hoy:\n"
    
    if urgente_firma:
        mensaje += f"- *{len(urgente_firma)} urgente* para firma\n"
    if oportunidades:
        mensaje += f"- *{len(oportunidades)} ofertas* que te pueden beneficiar\n"
    if infos:
        mensaje += f"- *{len(infos)} info*: {infos[0]['resumen']}" + (" y otros" if len(infos)>1 else "") + "\n"
    if spam:
        mensaje += f"- *{len(spam)} spam* detectado\n"
    
    keyboard = []
    if urgente_firma:
        mensaje += "\n*Requiere aprobación:*\n"
        for email in urgente_firma:
            hash_id = hashlib.md5(email['id'].encode()).hexdigest()[:16]
            mensaje += f"- {email['resumen']}\n Acción: {email['accion_sugerida']}\n"
            keyboard.append([
                {'text': f"Aprobar: {email['resumen'][:20]}...", 'callback_data': f'app_{hash_id}'},
                {'text': 'Rechazar', 'callback_data': f'rej_{hash_id}'}
            ])
    
    data = {
        'chat_id': tg_chat_id,
        'text': mensaje,
        'parse_mode': 'Markdown',
    }
    if keyboard:
        data['reply_markup'] = json.dumps({'inline_keyboard': keyboard})
    
    try:
        r = requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage", data=data, timeout=15)
        if r.status_code == 200:
            for f in glob.glob(os.path.join(pendientes_dir, '*.json')):
                shutil.move(f, os.path.join(procesados_dir, os.path.basename(f)))
            print(f"[*] Resumen enviado. {len(jsons)} archivos movidos a procesados/")
        else:
            print(f"[ERROR] Telegram respondió {r.status_code}: {r.text}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Error al enviar resumen a Telegram: {e}", file=sys.stderr)

def start_bot():
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(workspace_dir, "config.ini")
    
    config = configparser.ConfigParser()
    if not os.path.exists(config_file):
        print(f"[ERROR] No se encuentra {config_file}", file=sys.stderr)
        return
    
    config.read(config_file, encoding='utf-8')
    tg_token = config.get("TELEGRAM", "token", fallback="")
    if not tg_token:
        print("[ERROR] TELEGRAM token no configurado", file=sys.stderr)
        return
    
    bot = telebot.TeleBot(tg_token)
    pendientes_dir = os.path.join(workspace_dir, "pendientes")
    
    @bot.callback_query_handler(func=lambda call: True)
    def handle_callback(call):
        try:
            action, msg_hash = call.data.split('_', 1)
        except ValueError:
            bot.answer_callback_query(call.id, "Error: callback inválido")
            return
        
        # Find the pendiente file by hash
        target = None
        if os.path.isdir(pendientes_dir):
            for fname in os.listdir(pendientes_dir):
                if not fname.endswith('.json'):
                    continue
                fpath = os.path.join(pendientes_dir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    email_id = data.get('id', '')
                    computed = hashlib.md5(email_id.encode()).hexdigest()[:16]
                    if computed == msg_hash:
                        target = (fpath, data)
                        break
                except Exception:
                    continue
        
        if action == 'app':
            bot.answer_callback_query(call.id, "Aprobado ✅")
            print(f"[*] Callback: aprobado -> hash {msg_hash}", flush=True)
            if target:
                fpath, data = target
                print(f"[*] Pendiente aprobado: {data.get('resumen', '?')}", flush=True)
        else:
            bot.answer_callback_query(call.id, "Rechazado ❌")
            print(f"[*] Callback: rechazado -> hash {msg_hash}", flush=True)
            if target:
                fpath, data = target
                print(f"[*] Pendiente rechazado: {data.get('resumen', '?')}", flush=True)
    
    print("[*] Bot de Telegram iniciado. Esperando callbacks...")
    bot.infinity_polling()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daemon de clasificación de EmailTriagePro")
    parser.add_argument("--system-global", type=str, help="Prompt del sistema global para sobrescribir skills/system_global.txt")
    parser.add_argument("--bot", action="store_true", help="Iniciar bot de Telegram para manejar callbacks")
    args = parser.parse_args()
    
    if args.bot:
        start_bot()
    else:
        run_classification(system_global_override=args.system_global)
