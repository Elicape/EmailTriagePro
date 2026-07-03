#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# EmailTriagePro — Demo script
# ============================================================
# 1. Limpia logs y archivos de ejecuciones anteriores
# 2. Busca un email en la bandeja y lo marca como No Leído
# 3. Ejecuta el clasificador
# 4. Muestra el log de acciones
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo " EmailTriagePro — Demo automatizada"
echo "============================================"

# --- 1. Limpiar estado anterior ---
echo ""
echo "[1/4] Limpiando estado anterior..."
rm -f logs/acciones.log
touch logs/acciones.log
echo "# Log de acciones de EmailTriagePro" > logs/acciones.log
echo "  → logs/acciones.log vaciado"

# --- 2. Marcar último correo como no leído ---
echo ""
echo "[2/4] Marcando último correo como No Leído en IMAP..."
CONFIG="config.ini"

IMAP_HOST=$(grep -A5 '^\[IMAP\]' "$CONFIG" | grep '^host' | head -1 | cut -d'=' -f2 | xargs)
IMAP_PORT=$(grep -A5 '^\[IMAP\]' "$CONFIG" | grep '^port' | head -1 | cut -d'=' -f2 | xargs)
IMAP_USER=$(grep -A5 '^\[IMAP\]' "$CONFIG" | grep '^user' | head -1 | cut -d'=' -f2 | xargs)
IMAP_PASS=$(grep -A5 '^\[IMAP\]' "$CONFIG" | grep '^pass' | head -1 | cut -d'=' -f2 | xargs)

python3.13 -c "
import imaplib
import ssl

ctx = ssl.create_default_context()
M = imaplib.IMAP4_SSL('${IMAP_HOST}', ${IMAP_PORT}, ssl_context=ctx)
M.login('${IMAP_USER}', '${IMAP_PASS}')
M.select('INBOX')

# Buscar todos los correos (leídos y no leídos)
typ, data = M.search(None, 'ALL')
if data[0]:
    ids = data[0].split()
    latest = ids[-1]  # último correo
    M.store(latest, '-FLAGS', '\\Seen')
    print(f'  → Correo ID {latest.decode()} marcado como No Leído')

M.logout()
"
echo "  → OK"

# --- 3. Ejecutar clasificador ---
echo ""
echo "[3/4] Ejecutando clasificador..."
echo ""
python3 daemon.py
echo ""

# --- 4. Mostrar log de acciones ---
echo ""
echo "[4/4] Log de acciones registrado:"
echo "--------------------------------------------"
cat logs/acciones.log
echo "--------------------------------------------"
echo ""
echo "============================================"
echo " Demo completada."
echo " Revisa captura_terminal.png para la salida."
echo "============================================"
