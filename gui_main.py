#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EmailTriagePro v1.0 — Interfaz Gráfica
Cerrado: Clasificador con configuración dinámica, modo demo, bienvenida humana.
"""

import os
import sys
import time
import imaplib
import configparser

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QScrollArea, QStackedWidget,
    QLineEdit, QComboBox, QMessageBox, QStatusBar, QFrame,
    QSizePolicy
)
from PySide6.QtCore import (
    Qt, QTimer, QThread, QObject, Signal, QProcess,
    QProcessEnvironment
)
from PySide6.QtGui import QAction, QTextCursor

from demo_emails import EMAILS_DEMO


# ──────────────────────────────────────────────────────────────
# Switch (botón ON/OFF deslizante)
# ──────────────────────────────────────────────────────────────

class Switch(QPushButton):
    toggled = Signal(bool)

    def __init__(self, initial=False, parent=None):
        super().__init__(parent)
        self._state = initial
        self.setFixedSize(70, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._on_click)
        self._update_style()

    def _on_click(self):
        self._state = not self._state
        self._update_style()
        self.toggled.emit(self._state)

    def _update_style(self):
        if self._state:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2ea043; color: white;
                    border: none; border-radius: 15px;
                    font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: #2c9740; }
            """)
            self.setText("  ON  ")
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #d73a49; color: white;
                    border: none; border-radius: 15px;
                    font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: #cb2431; }
            """)
            self.setText(" OFF ")

    def set_state(self, state):
        self._state = state
        self._update_style()

    def is_on(self):
        return self._state


# ──────────────────────────────────────────────────────────────
# Hilos para pruebas de conexión (IMAP / Telegram)
# ──────────────────────────────────────────────────────────────

class ImapTestThread(QThread):
    result = Signal(bool, str)

    def __init__(self, host, port, user, password, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.user = user
        self.password = password

    def run(self):
        try:
            mail = imaplib.IMAP4_SSL(self.host, self.port)
            mail.login(self.user, self.password)
            mail.logout()
            self.result.emit(True, "Conexión exitosa")
        except imaplib.IMAP4.error as e:
            self.result.emit(False, f"Error de autenticación: {e}")
        except Exception as e:
            self.result.emit(False, f"Error de conexión: {e}")


class TelegramTestThread(QThread):
    result = Signal(bool, str)

    def __init__(self, token, chat_id, parent=None):
        super().__init__(parent)
        self.token = token
        self.chat_id = chat_id

    def run(self):
        import requests
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            r = requests.post(url, json={
                "chat_id": self.chat_id,
                "text": "Prueba desde EmailTriagePro GUI"
            }, timeout=10)
            if r.status_code == 200:
                self.result.emit(True, "Mensaje de prueba enviado a Telegram")
            else:
                self.result.emit(False, f"Error {r.status_code}: {r.text}")
        except Exception as e:
            self.result.emit(False, f"Error al enviar: {e}")


# ──────────────────────────────────────────────────────────────
# DaemonWorker — ejecuta daemon.py en QThread vía QProcess
# ──────────────────────────────────────────────────────────────

class DaemonWorker(QObject):
    output_line = Signal(str)
    run_finished = Signal(int, bool, bool, bool)
    run_started = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._buffer = ""

    def start(self, daemon_path, system_global=""):
        self._buffer = ""
        args = [daemon_path]
        if system_global:
            args.extend(["--system-global", system_global])

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")

        self._proc = QProcess()
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.setProcessEnvironment(env)
        self._proc.readyReadStandardOutput.connect(self._on_stdout)
        self._proc.finished.connect(self._on_finished)
        self._proc.start(sys.executable, args)
        self.run_started.emit()

    def stop(self):
        if self._proc and self._proc.state() == QProcess.Running:
            self._proc.kill()
            self._proc.waitForFinished(2000)
        self._proc = None

    def is_running(self):
        return self._proc is not None and self._proc.state() == QProcess.Running

    def _on_stdout(self):
        data = self._proc.readAllStandardOutput().data().decode("utf-8", errors="ignore")
        self._buffer += data
        for line in data.split("\n"):
            line = line.strip("\r")
            if line:
                self.output_line.emit(line)

    def _on_finished(self, exit_code):
        if self._proc is None:
            return
        imap_ok = None
        ai_ok = None
        tg_ok = None

        if ("[*] Autenticando usuario" in self._buffer
                or "[*] Conexión IMAP cerrada" in self._buffer):
            imap_ok = True
        if ("[ERROR] No se pudo conectar" in self._buffer
                or "[ERROR] Error al iniciar sesión" in self._buffer):
            imap_ok = False

        if "[!] Error al parsear JSON" in self._buffer:
            ai_ok = False
        elif ("etiqueta" in self._buffer.lower()
              or "[*] Ejecutando LLM local" in self._buffer):
            ai_ok = True

        if ("[*] Alerta Telegram enviada" in self._buffer
                or "[*] Resumen enviado" in self._buffer):
            tg_ok = True
        if ("[ERROR] Telegram" in self._buffer
                or "[ERROR] No se pudo enviar" in self._buffer):
            tg_ok = False

        self.run_finished.emit(exit_code,
                               imap_ok if imap_ok is not None else False,
                               ai_ok if ai_ok is not None else False,
                               tg_ok if tg_ok is not None else False)


# ──────────────────────────────────────────────────────────────
# MonitorView — QTextEdit con fondo oscuro
# ──────────────────────────────────────────────────────────────

class MonitorView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: none;
                padding: 8px;
                selection-background-color: #264f78;
            }
            QTextEdit:focus { border: none; }
        """)
        layout.addWidget(self.text_edit)

        welcome = ("EmailTriagePro — Clasificador Inteligente\n"
                   "Cargando aplicación...\n")
        self.text_edit.setPlainText(welcome)

    def append_output(self, text):
        self.text_edit.append(text)
        sb = self.text_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_output(self):
        self.text_edit.clear()

    def set_output(self, text):
        self.text_edit.setPlainText(text)


# ──────────────────────────────────────────────────────────────
# WelcomeScreen — Pantalla de inicio cuando no hay config
# ──────────────────────────────────────────────────────────────

class WelcomeScreen(QWidget):
    connect_requested = Signal()
    demo_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(60, 40, 60, 40)

        title = QLabel("EmailTriagePro v1.0")
        title.setStyleSheet("""
            font-size: 28px; font-weight: bold; color: #111827;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Clasificador Inteligente de Correo")
        subtitle.setStyleSheet("""
            font-size: 14px; color: #6b7280;
        """)
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        intro = QLabel("Esta herramienta lee tu correo y te avisa solo de lo urgente. No borra nada.")
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 14px; color: #374151;")
        intro.setAlignment(Qt.AlignCenter)
        layout.addWidget(intro)

        steps = QLabel(
            "1. Conectas tu correo\n"
            "2. La app mira si hay algo urgente\n"
            "3. Te avisa por Telegram si hay fuego\n"
            "4. Tú decides qué hacer"
        )
        steps.setWordWrap(True)
        steps.setStyleSheet("""
            font-size: 13px; color: #4b5563;
            background: #f3f4f6; border-radius: 8px;
            padding: 16px; max-width: 400px;
        """)
        steps.setAlignment(Qt.AlignLeft)
        w = QWidget()
        wl = QHBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addStretch()
        wl.addWidget(steps)
        wl.addStretch()
        layout.addWidget(w)

        layout.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        btn_row.addStretch()

        self.btn_connect = QPushButton("Conectar mi correo")
        self.btn_connect.setStyleSheet("""
            QPushButton {
                padding: 12px 28px; border-radius: 8px;
                font-weight: 700; font-size: 14px;
                background: #4f46e5; color: white; border: none;
            }
            QPushButton:hover { background: #4338ca; }
        """)
        self.btn_connect.clicked.connect(self.connect_requested.emit)

        self.btn_demo = QPushButton("Ver cómo funciona")
        self.btn_demo.setStyleSheet("""
            QPushButton {
                padding: 12px 28px; border-radius: 8px;
                font-weight: 700; font-size: 14px;
                background: #ffffff; color: #4f46e5;
                border: 2px solid #4f46e5;
            }
            QPushButton:hover { background: #f5f3ff; }
        """)
        self.btn_demo.clicked.connect(self.demo_requested.emit)

        btn_row.addWidget(self.btn_connect)
        btn_row.addWidget(self.btn_demo)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()


# ──────────────────────────────────────────────────────────────
# ConfigView — Pantalla de configuración con proveedor dinámico
# ──────────────────────────────────────────────────────────────

class ConfigView(QWidget):
    back_requested = Signal()
    saved = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connection_ok = False
        self._build_ui()

    def _make_section_title(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("""
            font-size: 14px; font-weight: bold;
            color: #4f46e5; margin-top: 8px;
        """)
        return lbl

    def _make_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #e5e7eb; max-height: 1px;")
        return sep

    def _make_form_row(self, label, widget, help_text=""):
        row = QVBoxLayout()
        row.setSpacing(2)
        h = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(140)
        lbl.setStyleSheet("font-size: 12px; color: #374151;")
        h.addWidget(lbl)
        h.addWidget(widget, 1)
        row.addLayout(h)
        if help_text:
            hl = QLabel(help_text)
            hl.setStyleSheet("color: #9ca3af; font-size: 9px; padding-left: 144px;")
            row.addWidget(hl)
        return row

    def _make_button(self, text, color_bg="#4f46e5", color_hover="#4338ca"):
        btn = QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px; border-radius: 6px;
                font-weight: 600; font-size: 12px;
                background: {color_bg}; color: white; border: none;
            }}
            QPushButton:hover {{ background: {color_hover}; }}
            QPushButton:disabled {{
                background: #a5b4fc; color: #e0e7ff;
            }}
        """)
        return btn

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #f3f4f6; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #d1d5db; border-radius: 4px; min-height: 30px;
            }
        """)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(16)
        cl.setContentsMargins(24, 16, 24, 16)

        # ── Botón volver ──
        self.btn_back = QPushButton("← Volver")
        self.btn_back.setStyleSheet("""
            QPushButton {
                padding: 6px 14px; border-radius: 6px;
                font-weight: 600; font-size: 12px;
                background: transparent; color: #4f46e5;
                border: 1px solid #e5e7eb;
            }
            QPushButton:hover { background: #f3f4f6; }
        """)
        self.btn_back.clicked.connect(self._on_back)
        cl.addWidget(self.btn_back)

        title = QLabel("Conectar tu correo")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #111827;")
        cl.addWidget(title)

        # ════════════════════
        # Proveedor
        # ════════════════════
        cl.addWidget(self._make_section_title("Proveedor"))
        cl.addWidget(self._make_separator())

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Gmail", "Zoho", "Otro IMAP"])
        self.provider_combo.setStyleSheet("""
            QComboBox {
                padding: 6px 10px; border: 1px solid #d1d5db;
                border-radius: 6px; font-size: 12px; color: #111827;
                background: white;
            }
            QComboBox:focus { border-color: #4f46e5; }
            QComboBox::drop-down { border: none; width: 24px; }
        """)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.provider_combo.setToolTip(
            "Elige tu proveedor de correo.\n"
            "Gmail: usa tu cuenta de Gmail normal.\n"
            "Zoho: crea cuenta gratis en zoho.com.\n"
            "Otro: si usas un servidor de correo propio."
        )
        cl.addWidget(self.provider_combo)

        # ════════════════════
        # Campos de conexión
        # ════════════════════
        cl.addWidget(self._make_section_title("Cuenta de Correo"))
        cl.addWidget(self._make_separator())

        # Email
        self.input_email = QLineEdit()
        self.input_email.setPlaceholderText("tu@email.com")
        self.input_email.setToolTip("Escribe tu correo completo. Ej: laura@zoho.eu")
        self._style_input(self.input_email)
        self.input_email.textChanged.connect(self._on_field_changed)
        cl.addLayout(self._make_form_row("Email:", self.input_email,
                                         "Tu dirección de correo electrónico"))

        # Contraseña de aplicación
        self.input_password = QLineEdit()
        self.input_password.setEchoMode(QLineEdit.Password)
        self.input_password.setPlaceholderText("••••••••")
        self.input_password.setToolTip(
            "No uses tu contraseña normal. Crea una 'contraseña de aplicación' especial.\n"
            "Gmail: ve a myaccount.google.com/apppasswords\n"
            "Zoho: en Zoho Mail → Ajustes → Contraseñas de aplicación"
        )
        self._style_input(self.input_password)
        self.input_password.textChanged.connect(self._on_field_changed)
        cl.addLayout(self._make_form_row("Contraseña de app:", self.input_password,
                                         "Es una clave especial, no la de tu correo normal"))

        # Servidor IMAP (solo Otro)
        self.imap_host_label = QLabel("Servidor IMAP:")
        self.imap_host_label.setStyleSheet("font-size: 12px; color: #374151;")
        self.imap_host_label.setFixedWidth(140)

        self.imap_host = QLineEdit()
        self.imap_host.setPlaceholderText("imap.tu-servidor.com")
        self.imap_host.setToolTip("Pregunta a tu proveedor de correo cuál es su servidor IMAP")
        self._style_input(self.imap_host)
        self.imap_host.textChanged.connect(self._on_field_changed)

        imap_row = QHBoxLayout()
        imap_row.addWidget(self.imap_host_label)
        imap_row.addWidget(self.imap_host, 1)

        self.imap_help = QLabel("Ej: imap.tu-servidor.com")
        self.imap_help.setStyleSheet("color: #9ca3af; font-size: 9px; padding-left: 144px;")

        self.imap_host_container = QVBoxLayout()
        self.imap_host_container.addLayout(imap_row)
        self.imap_host_container.addWidget(self.imap_help)

        # Puerto (solo Otro)
        self.imap_port_label = QLabel("Puerto:")
        self.imap_port_label.setStyleSheet("font-size: 12px; color: #374151;")
        self.imap_port_label.setFixedWidth(140)

        self.imap_port = QLineEdit("993")
        self.imap_port.setFixedWidth(80)
        self.imap_port.setToolTip("Normalmente 993 para conexión segura. 143 para sin cifrar.")
        self._style_input(self.imap_port)
        self.imap_port.textChanged.connect(self._on_field_changed)

        port_row = QHBoxLayout()
        port_row.addWidget(self.imap_port_label)
        port_row.addWidget(self.imap_port)
        port_row.addStretch()

        self.imap_port_container = QVBoxLayout()
        self.imap_port_container.addLayout(port_row)

        cl.addLayout(self.imap_host_container)
        cl.addLayout(self.imap_port_container)

        # Botón probar conexión
        btn_test_row = QHBoxLayout()
        btn_test_row.addStretch()

        self.btn_test = self._make_button("Probar conexión", "#059669", "#047857")
        self.btn_test.setToolTip("Comprueba si el correo y la contraseña son correctos")
        self.btn_test.clicked.connect(self._test_connection)
        btn_test_row.addWidget(self.btn_test)

        self.test_status_label = QLabel("")
        self.test_status_label.setStyleSheet("font-size: 11px; color: #6b7280; padding-left: 8px;")
        btn_test_row.addWidget(self.test_status_label)

        cl.addLayout(btn_test_row)

        # ════════════════════
        # Telegram
        # ════════════════════
        cl.addWidget(self._make_section_title("Telegram (opcional)"))
        cl.addWidget(self._make_separator())

        tg_note = QLabel("Sin Telegram la app sigue funcionando, solo no recibirás avisos en el móvil.")
        tg_note.setStyleSheet("color: #9ca3af; font-size: 10px; font-style: italic;")
        cl.addWidget(tg_note)

        self.tg_token = QLineEdit()
        self.tg_token.setEchoMode(QLineEdit.Password)
        self.tg_token.setPlaceholderText("123456789:ABCdef...")
        self.tg_token.setToolTip(
            "Token de tu bot de Telegram.\n"
            "Crea un bot en @BotFather y copia el token aquí."
        )
        self._style_input(self.tg_token)

        self.tg_chat_id = QLineEdit()
        self.tg_chat_id.setPlaceholderText("123456789")
        self.tg_chat_id.setToolTip(
            "Tu ID de usuario de Telegram.\n"
            "Escribe a @userinfobot en Telegram para saberlo."
        )
        self._style_input(self.tg_chat_id)

        cl.addLayout(self._make_form_row("Token del Bot:", self.tg_token))
        cl.addLayout(self._make_form_row("ID del Chat:", self.tg_chat_id))

        self.btn_test_tg = self._make_button("Enviar prueba", "#059669", "#047857")
        self.btn_test_tg.clicked.connect(self._test_telegram)
        cl.addWidget(self.btn_test_tg, alignment=Qt.AlignRight)

        # ════════════════════
        # Botones Guardar / Cancelar
        # ════════════════════
        cl.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                padding: 8px 24px; border-radius: 6px;
                font-weight: 600; font-size: 13px;
                background: #f3f4f6; color: #374151;
                border: 1px solid #d1d5db;
            }
            QPushButton:hover { background: #e5e7eb; }
        """)
        self.btn_cancel.clicked.connect(self._on_back)

        self.btn_save = QPushButton("Guardar y usar")
        self.btn_save.setStyleSheet("""
            QPushButton {
                padding: 8px 24px; border-radius: 6px;
                font-weight: 600; font-size: 13px;
                background: #4f46e5; color: white; border: none;
            }
            QPushButton:hover { background: #4338ca; }
            QPushButton:disabled {
                background: #a5b4fc; color: #e0e7ff;
            }
        """)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_config)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_save)
        cl.addLayout(btn_row)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Estado inicial: Gmail (ocultar server/port)
        self._on_provider_changed(0)

    def _style_input(self, w):
        w.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px; border: 1px solid #d1d5db;
                border-radius: 6px; font-size: 12px; color: #111827;
            }
            QLineEdit:focus { border-color: #4f46e5; }
        """)

    def _on_provider_changed(self, index):
        provider = self.provider_combo.currentText()
        if provider == "Otro IMAP":
            self.imap_host_label.setVisible(True)
            self.imap_host.setVisible(True)
            self.imap_help.setVisible(True)
            self.imap_port_label.setVisible(True)
            self.imap_port.setVisible(True)
            self.imap_host_container.setEnabled(True)
            self.imap_port_container.setEnabled(True)
        else:
            self.imap_host_label.setVisible(False)
            self.imap_host.setVisible(False)
            self.imap_help.setVisible(False)
            self.imap_port_label.setVisible(False)
            self.imap_port.setVisible(False)
            self.imap_host_container.setEnabled(False)
            self.imap_port_container.setEnabled(False)
            if provider == "Gmail":
                self.imap_host.setText("imap.gmail.com")
                self.imap_port.setText("993")
            elif provider == "Zoho":
                self.imap_host.setText("imap.zoho.eu")
                self.imap_port.setText("993")
        self._on_field_changed()

    def _on_field_changed(self):
        self.connection_ok = False
        self.btn_save.setEnabled(False)
        self.test_status_label.setText("")

    def _test_connection(self):
        email = self.input_email.text().strip()
        password = self.input_password.text()
        host = self.imap_host.text().strip()
        port_str = self.imap_port.text().strip()

        if not email or not password:
            QMessageBox.warning(self, "Campos incompletos",
                                "Rellena el email y la contraseña primero.")
            return

        try:
            port = int(port_str) if port_str else 993
        except ValueError:
            QMessageBox.warning(self, "Puerto inválido",
                                "El puerto debe ser un número.")
            return

        self.btn_test.setEnabled(False)
        self.btn_test.setText("Probando...")
        self.test_status_label.setText("Conectando...")

        thread = ImapTestThread(host, port, email, password, self)
        thread.result.connect(self._on_test_result)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_test_result(self, ok, msg):
        self.btn_test.setEnabled(True)
        self.btn_test.setText("Probar conexión")
        if ok:
            self.connection_ok = True
            self.btn_save.setEnabled(True)
            self.test_status_label.setText("Conexión correcta")
            self.test_status_label.setStyleSheet("font-size: 11px; color: #2ea043; padding-left: 8px;")
            QMessageBox.information(self, "Conexión correcta",
                                    "Todo funciona. Ya puedes guardar la configuración.")
        else:
            self.connection_ok = False
            self.test_status_label.setText("Error")
            self.test_status_label.setStyleSheet("font-size: 11px; color: #d73a49; padding-left: 8px;")
            QMessageBox.critical(self, "Error de conexión",
                                 f"{msg}\n\n"
                                 "¿Usaste una contraseña de aplicación especial?\n"
                                 "No es tu contraseña normal de correo.")

    def _test_telegram(self):
        token = self.tg_token.text().strip()
        chat_id = self.tg_chat_id.text().strip()
        if not token or not chat_id:
            QMessageBox.warning(self, "Campos incompletos",
                                "Completa los campos de Telegram primero.")
            return
        self.btn_test_tg.setEnabled(False)
        self.btn_test_tg.setText("Enviando...")
        thread = TelegramTestThread(token, chat_id, self)
        thread.result.connect(self._on_tg_test_result)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_tg_test_result(self, ok, msg):
        self.btn_test_tg.setEnabled(True)
        self.btn_test_tg.setText("Enviar prueba")
        if ok:
            QMessageBox.information(self, "Telegram", msg)
        else:
            QMessageBox.critical(self, "Error Telegram", msg)

    def _on_back(self):
        self.back_requested.emit()

    # ── API pública ──

    def load_config(self, config):
        cfg = config
        s = lambda sec, key, fallback="": cfg.get(sec, key, fallback=fallback)
        self.input_email.setText(s("IMAP", "user"))
        self.input_password.setText(s("IMAP", "pass"))
        host = s("IMAP", "host", "")
        port = s("IMAP", "port", "")
        if "gmail" in host:
            self.provider_combo.setCurrentIndex(0)
        elif "zoho" in host:
            self.provider_combo.setCurrentIndex(1)
        else:
            self.provider_combo.setCurrentIndex(2)
            self.imap_host.setText(host)
            self.imap_port.setText(port or "993")
        self.tg_token.setText(s("TELEGRAM", "token"))
        self.tg_chat_id.setText(s("TELEGRAM", "chat_id"))

    def get_config(self):
        cfg = configparser.ConfigParser()
        provider = self.provider_combo.currentText()
        host = self.imap_host.text().strip()
        port = self.imap_port.text().strip() or "993"
        cfg["IMAP"] = {
            "host": host,
            "port": port,
            "user": self.input_email.text().strip(),
            "pass": self.input_password.text(),
            "use_ssl": "true" if port in ("993", "143") else "false",
        }
        cfg["TELEGRAM"] = {
            "token": self.tg_token.text().strip(),
            "chat_id": self.tg_chat_id.text().strip(),
        }
        cfg["LLAMA"] = {
            "llama_path": "bin/llama-cli",
            "model_path": "models/Qwen3-VL-2B-Instruct-Q4_K_M.gguf",
            "temperature": "0.1",
            "max_tokens": "256",
        }
        cfg["GUI"] = {
            "poll_interval": "60",
            "log_disable": "true",
            "no_show_timings": "true",
        }
        cfg["PERFIL"] = {
            "user_id": "usuario_01",
            "user_name": "",
        }
        return cfg

    def _save_config(self):
        self.saved.emit(dict(self.get_config()))


# ──────────────────────────────────────────────────────────────
# DemoClassifier — Clasifica 25 emails con keywords (sin IA)
# ──────────────────────────────────────────────────────────────

def demo_classify(log_func):
    KEYWORDS_URGENTE = [
        "urgente", "error", "crítico", "hacienda", "caduca",
        "requerimiento", "bloqueo", "caída"
    ]
    KEYWORDS_RESPUESTA = [
        "respuesta necesaria", "confirmar", "disponibilidad",
        "consulta", "¿puedes", "¿podrías"
    ]
    KEYWORDS_TRAMITE = [
        "factura", "documentación", "iva", "informe",
        "presupuesto", "solicitud", "vencida",
        "rectificativa"
    ]
    KEYWORDS_PROMOCION = [
        "descuento", "oferta", "newsletter", "webinar",
        "liquidación", "colaboración"
    ]

    def word_in_text(word, txt):
        return f" {word} " in f" {txt} "

    start = time.time()

    log_func("═══════════════════════════════════════════")
    log_func("           MODO DEMO - 25 emails")
    log_func("═══════════════════════════════════════════")
    log_func("")

    counts = {"Urgente": 0, "Urgente-Firma": 0, "Útil-Info": 0,
              "Útil-Oportunidad": 0, "Spam": 0}

    for mail in EMAILS_DEMO:
        text = (mail["asunto"] + " " + mail["cuerpo"]).lower()

        urgente_match = any(kw in text for kw in KEYWORDS_URGENTE)
        firma_match = word_in_text("firma", text) or word_in_text("firmar", text)
        contrato_match = word_in_text("contrato", text)
        respuesta_match = any(kw in text for kw in KEYWORDS_RESPUESTA)
        tramite_match = any(kw in text for kw in KEYWORDS_TRAMITE)
        promocion_match = any(kw in text for kw in KEYWORDS_PROMOCION)

        if firma_match and contrato_match:
            etiqueta = "Urgente-Firma"
            urgencia = 5
            accion = "Firmar contrato urgente"
        elif urgente_match:
            etiqueta = "Urgente"
            urgencia = 4
            accion = "Revisar con urgencia"
        elif promocion_match:
            etiqueta = "Útil-Oportunidad"
            urgencia = 1
            accion = "Oferta promocional"
        elif respuesta_match:
            etiqueta = "Útil-Info"
            urgencia = 3
            accion = "Responder cuando sea posible"
        elif tramite_match:
            etiqueta = "Útil-Info"
            urgencia = 2
            accion = "Revisar y archivar"
        else:
            etiqueta = "Útil-Info"
            urgencia = 1
            accion = "Sin acción necesaria"

        counts[etiqueta] = counts.get(etiqueta, 0) + 1

        stars = "★" * urgencia + "☆" * (5 - urgencia)
        log_func(f" [{mail['id']:2d}] {mail['asunto']}")
        log_func(f"       → {etiqueta} · {stars} ({urgencia}/5) · {accion}")
        log_func("")

    elapsed = time.time() - start

    log_func("═══════════════════════════════════════════")
    log_func("              RESUMEN")
    log_func("═══════════════════════════════════════════")
    for cat in ["Urgente", "Urgente-Firma", "Útil-Info", "Útil-Oportunidad", "Spam"]:
        n = counts.get(cat, 0)
        bar = "█" * n + "░" * (max(0, 20 - n))
        log_func(f" {cat:20s} {n:2d}  {bar}")
    log_func("")
    log_func(f" Demo completada en {elapsed:.2f} segundos")
    log_func(f" {len(EMAILS_DEMO)} emails clasificados sin usar internet")
    log_func("═══════════════════════════════════════════")
    log_func("")
    log_func("Vuelve a 'Ver cómo funciona' si quieres repetir la demo.")


# ──────────────────────────────────────────────────────────────
# MainWindow — Ventana principal 900x650
# ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    _run_signal = Signal(str, str)
    _stop_signal = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aplicación de Correo - Clasificador Inteligente")
        self.resize(900, 650)
        self.setMinimumSize(700, 500)

        self.workspace_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.workspace_dir, "config.ini")

        self._monitoring = False
        self._daemon_running = False
        self._poll_interval = 60
        self._last_check = "--:--"

        self._build_ui()
        self._setup_daemon()
        self._setup_timers()

        if os.path.exists(self.config_path):
            self._stack.setCurrentIndex(0)
            self._btn_bar.setVisible(True)
            self._update_button_states()
            self._start_monitoring()
        else:
            self._stack.setCurrentIndex(2)
            self._btn_bar.setVisible(False)
            self._update_button_states()

    # ── UI ──

    def _build_ui(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar { background: #f9fafb; border-bottom: 1px solid #e5e7eb; }
            QMenuBar::item { padding: 6px 12px; }
            QMenuBar::item:selected { background: #e5e7eb; }
            QMenu { background: white; border: 1px solid #e5e7eb; }
            QMenu::item:selected { background: #f3f4f6; }
        """)

        archivo = menubar.addMenu("Archivo")
        salir = QAction("Salir", self)
        salir.triggered.connect(self.close)
        archivo.addAction(salir)

        ayuda = menubar.addMenu("Ayuda")
        acerca = QAction("Acerca de", self)
        acerca.triggered.connect(self._show_about)
        ayuda.addAction(acerca)

        central = QWidget()
        self.setCentralWidget(central)
        ml = QVBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        # ── Button Bar ──
        self._btn_bar = QWidget()
        self._btn_bar.setFixedHeight(50)
        self._btn_bar.setObjectName("buttonBar")
        self._btn_bar.setStyleSheet("""
            QWidget#buttonBar {
                background-color: #f9fafb;
                border-bottom: 1px solid #e5e7eb;
            }
        """)
        bl = QHBoxLayout(self._btn_bar)
        bl.setContentsMargins(12, 6, 12, 6)
        bl.setSpacing(8)

        self.btn_start = QPushButton("▶ Iniciar")
        self.btn_pause = QPushButton("⏸ Pausar")
        self.btn_process = QPushButton("🔄 Procesar ahora")

        btn_style = """
            QPushButton {
                padding: 6px 14px; border-radius: 6px;
                font-weight: 600; font-size: 12px;
                border: 1px solid #d1d5db;
                background: #ffffff; color: #374151;
            }
            QPushButton:hover { background: #f3f4f6; }
            QPushButton:disabled { color: #9ca3af; }
        """
        for b in (self.btn_start, self.btn_pause, self.btn_process):
            b.setStyleSheet(btn_style)

        self.btn_start.clicked.connect(self._start_monitoring)
        self.btn_pause.clicked.connect(self._pause_monitoring)
        self.btn_process.clicked.connect(self._run_daemon_now)

        bl.addWidget(self.btn_start)
        bl.addWidget(self.btn_pause)
        bl.addWidget(self.btn_process)

        sep = QLabel(" | ")
        sep.setStyleSheet("color: #d1d5db; font-size: 16px; padding: 0 4px;")
        bl.addWidget(sep)

        self.light_imap = QLabel("● IMAP")
        self.light_ai = QLabel("● IA")
        self.light_tg = QLabel("● Telegram")
        for l in (self.light_imap, self.light_ai, self.light_tg):
            l.setStyleSheet("color: #6b7280; font-size: 11px; font-weight: 600; padding: 0 4px;")
        bl.addWidget(self.light_imap)
        bl.addWidget(self.light_ai)
        bl.addWidget(self.light_tg)

        bl.addStretch()

        self.btn_settings = QPushButton("⚙️ Configuración")
        self.btn_settings.setStyleSheet(btn_style)
        self.btn_settings.clicked.connect(self._show_config)
        bl.addWidget(self.btn_settings)

        ml.addWidget(self._btn_bar)

        # ── Stacked (Monitor / Config / Welcome) ──
        self._stack = QStackedWidget()

        self._monitor = MonitorView()
        self._config = ConfigView()
        self._welcome = WelcomeScreen()

        self._config.back_requested.connect(self._on_config_back)
        self._config.saved.connect(self._on_config_saved)

        self._welcome.connect_requested.connect(self._show_config)
        self._welcome.demo_requested.connect(self._run_demo)

        self._stack.addWidget(self._monitor)   # index 0
        self._stack.addWidget(self._config)    # index 1
        self._stack.addWidget(self._welcome)   # index 2
        self._stack.setCurrentIndex(0)

        ml.addWidget(self._stack, 1)

        # ── Status Bar ──
        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.setStyleSheet("""
            QStatusBar {
                background: #f9fafb;
                border-top: 1px solid #e5e7eb;
                font-size: 11px; padding: 2px 8px;
                max-height: 25px; color: #4b5563;
            }
        """)
        self._status_label = QLabel("Estado: Esperando... | Última revisión: --:--")
        sb.addWidget(self._status_label)

    def _update_button_states(self):
        if self._monitoring:
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_process.setEnabled(False)
        else:
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_process.setEnabled(True)

    def _update_status_lights(self, imap_ok, ai_ok, tg_ok):
        def _style(ok, name):
            if ok:
                return f"color: #2ea043; font-size: 11px; font-weight: 600;"
            else:
                return f"color: #d73a49; font-size: 11px; font-weight: 600;"
        self.light_imap.setStyleSheet(_style(imap_ok, "IMAP"))
        self.light_ai.setStyleSheet(_style(ai_ok, "IA"))
        self.light_tg.setStyleSheet(_style(tg_ok, "Telegram"))

    def _show_about(self):
        QMessageBox.about(self, "Acerca de",
                          "EmailTriagePro v1.0\n\n"
                          "Clasificador Inteligente de Correo\n"
                          "con Inteligencia Artificial Local\n\n"
                          "© 2026 — Todos los derechos reservados")

    def _on_config_back(self):
        if os.path.exists(self.config_path):
            self._stack.setCurrentIndex(0)
            self._btn_bar.setVisible(True)
        else:
            self._stack.setCurrentIndex(2)
            self._btn_bar.setVisible(False)

    # ── Demo ──

    def _run_demo(self):
        self._stack.setCurrentIndex(0)
        self._btn_bar.setVisible(True)
        self.btn_start.setEnabled(False)
        self.btn_process.setEnabled(False)
        self.btn_settings.setEnabled(False)
        self._monitor.clear_output()
        self._monitor.set_output("")
        demo_classify(lambda txt: self._monitor.append_output(txt))
        self.btn_settings.setEnabled(True)
        self._status_label.setText("Estado: Demo completada | Sin conexión a internet")

    # ── Daemon ──

    def _setup_daemon(self):
        self._thread = QThread(self)
        self._worker = DaemonWorker()
        self._worker.moveToThread(self._thread)

        self._run_signal.connect(self._worker.start)
        self._stop_signal.connect(self._worker.stop)

        self._worker.run_started.connect(self._on_run_started)
        self._worker.output_line.connect(self._monitor.append_output)
        self._worker.run_finished.connect(self._on_run_finished)

        self._thread.start()

    def _setup_timers(self):
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._on_timer_tick)

    def _start_monitoring(self):
        if self._monitoring:
            return
        self._monitoring = True
        self._update_button_states()
        self._poll_timer.start(self._poll_interval * 1000)
        self._run_daemon_now()

    def _pause_monitoring(self):
        self._monitoring = False
        self._poll_timer.stop()
        self._stop_signal.emit()
        self._daemon_running = False
        self._update_button_states()
        self._status_label.setText("Estado: Pausado | Última revisión: --:--")

    def _on_timer_tick(self):
        if not self._daemon_running:
            self._run_daemon_now()

    def _run_daemon_now(self):
        if self._daemon_running:
            return
        self._daemon_running = True
        self._status_label.setText("Estado: Ejecutando...")

        system_global = ""
        sg_path = os.path.join(self.workspace_dir, "skills", "system_global.txt")
        if os.path.exists(sg_path):
            with open(sg_path, "r", encoding="utf-8") as f:
                system_global = f.read().strip()

        daemon_path = os.path.join(self.workspace_dir, "daemon.py")
        self._run_signal.emit(daemon_path, system_global)

    def _on_run_started(self):
        self._monitor.append_output("[GUI] Ejecutando daemon.py...")
        self._status_label.setText("Estado: Ejecutando...")

    def _on_run_finished(self, exit_code, imap_ok, ai_ok, tg_ok):
        self._daemon_running = False
        self._last_check = self._now_str()
        self._update_status_lights(imap_ok, ai_ok, tg_ok)

        if exit_code == 0:
            self._status_label.setText(
                f"Estado: OK | Última revisión: {self._last_check}")
        else:
            self._status_label.setText(
                f"Estado: Error (código {exit_code}) | Última revisión: {self._last_check}")

    def _now_str(self):
        from datetime import datetime
        return datetime.now().strftime("%H:%M")

    # ── Config ──

    def _show_config(self):
        self._btn_bar.setVisible(False)
        cfg = self._load_config_file()
        self._config.load_config(cfg)
        self._stack.setCurrentIndex(1)

    def _on_config_saved(self, cfg_dict):
        cfg = configparser.ConfigParser()
        for section, values in cfg_dict.items():
            cfg[section] = values
        self._save_config_file(cfg)
        self._stack.setCurrentIndex(0)
        self._btn_bar.setVisible(True)
        self._monitor.append_output("[GUI] Configuración guardada")
        if self._monitoring:
            self._stop_signal.emit()
            QTimer.singleShot(600, self._run_daemon_now)
        else:
            self._start_monitoring()

    def _load_config_file(self):
        cfg = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            cfg.read(self.config_path, encoding="utf-8")
        return cfg

    def _save_config_file(self, cfg):
        with open(self.config_path, "w", encoding="utf-8") as f:
            cfg.write(f)

    # ── Cierre ──

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, "Confirmar salida",
            "¿Salir? El servicio se detendrá.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._cleanup()
            event.accept()
        else:
            event.ignore()

    def _cleanup(self):
        self._monitoring = False
        self._poll_timer.stop()
        self._stop_signal.emit()
        self._thread.quit()
        self._thread.wait(3000)


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    try:
        from daemon import verificar_entorno
        verificar_entorno()
    except ImportError as e:
        QMessageBox.critical(
            None, "Error de importación",
            f"Falta una dependencia: {e}\n\n"
            "Ejecuta: pip install -r requirements.txt"
        )
        sys.exit(1)
    except RuntimeError as e:
        QMessageBox.critical(
            None, "Entorno incompleto",
            str(e)
        )
        sys.exit(1)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
