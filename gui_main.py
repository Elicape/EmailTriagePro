#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EmailTriagePro — Interfaz Gráfica para daemon.py
Versión: 1.0
"""

import os
import sys
import imaplib
import configparser

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QScrollArea, QStackedWidget,
    QFormLayout, QLineEdit, QSlider, QSpinBox, QGroupBox,
    QCheckBox, QMessageBox, QStatusBar, QMenuBar, QFrame,
    QSizePolicy
)
from PySide6.QtCore import (
    Qt, QTimer, QThread, QObject, Signal, QProcess,
    QProcessEnvironment
)
from PySide6.QtGui import QAction, QTextCursor


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
            self.result.emit(True, "Conexión IMAP exitosa")
        except imaplib.IMAP4.error as e:
            self.result.emit(False, f"Error de autenticación IMAP: {e}")
        except Exception as e:
            self.result.emit(False, f"Error de conexión IMAP: {e}")


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


# ──────────────────────────────────────────────────────────────
# ConfigView — Pantalla de configuración en QScrollArea
# ──────────────────────────────────────────────────────────────

class ConfigView(QWidget):
    back_requested = Signal()
    saved = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
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

    def _make_form_row(self, label, widget):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(130)
        lbl.setStyleSheet("font-size: 12px; color: #374151;")
        row.addWidget(lbl)
        row.addWidget(widget, 1)
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
        self.btn_back = QPushButton("← Volver al Monitor")
        self.btn_back.setStyleSheet("""
            QPushButton {
                padding: 6px 14px; border-radius: 6px;
                font-weight: 600; font-size: 12px;
                background: transparent; color: #4f46e5;
                border: 1px solid #e5e7eb;
            }
            QPushButton:hover { background: #f3f4f6; }
        """)
        self.btn_back.clicked.connect(self.back_requested.emit)
        cl.addWidget(self.btn_back)

        # ── Título ──
        title = QLabel("Configuración")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #111827;")
        cl.addWidget(title)

        # ════════════════════
        # Cuenta de Correo
        # ════════════════════
        cl.addWidget(self._make_section_title("Cuenta de Correo"))
        cl.addWidget(self._make_separator())

        self.imap_host = QLineEdit()
        self.imap_host.setPlaceholderText("imap.tu-servidor.com")
        self.imap_port = QLineEdit("993")
        self.imap_port.setFixedWidth(80)
        self.imap_user = QLineEdit()
        self.imap_user.setPlaceholderText("tu@email.com")
        self.imap_pass = QLineEdit()
        self.imap_pass.setEchoMode(QLineEdit.Password)
        self.imap_pass.setPlaceholderText("••••••••")

        for w in (self.imap_host, self.imap_port, self.imap_user, self.imap_pass):
            w.setStyleSheet("""
                QLineEdit {
                    padding: 6px 10px; border: 1px solid #d1d5db;
                    border-radius: 6px; font-size: 12px; color: #111827;
                }
                QLineEdit:focus { border-color: #4f46e5; }
            """)

        port_w = QWidget()
        port_row = QHBoxLayout(port_w)
        port_row.setContentsMargins(0, 0, 0, 0)
        port_row.addWidget(self.imap_port)
        port_row.addStretch()

        cl.addLayout(self._make_form_row("Servidor IMAP:", self.imap_host))
        cl.addLayout(self._make_form_row("Puerto:", port_w))
        cl.addLayout(self._make_form_row("Usuario:", self.imap_user))
        cl.addLayout(self._make_form_row("Contraseña:", self.imap_pass))

        self.btn_test_imap = self._make_button("Probar conexión", "#059669", "#047857")
        self.btn_test_imap.clicked.connect(self._test_imap)
        cl.addWidget(self.btn_test_imap, alignment=Qt.AlignRight)

        # ════════════════════
        # Telegram
        # ════════════════════
        cl.addWidget(self._make_section_title("Telegram"))
        cl.addWidget(self._make_separator())

        self.tg_token = QLineEdit()
        self.tg_token.setEchoMode(QLineEdit.Password)
        self.tg_token.setPlaceholderText("123456789:ABCdef...")
        self.tg_chat_id = QLineEdit()
        self.tg_chat_id.setPlaceholderText("123456789")

        for w in (self.tg_token, self.tg_chat_id):
            w.setStyleSheet("""
                QLineEdit {
                    padding: 6px 10px; border: 1px solid #d1d5db;
                    border-radius: 6px; font-size: 12px; color: #111827;
                }
                QLineEdit:focus { border-color: #4f46e5; }
            """)

        cl.addLayout(self._make_form_row("Token del Bot:", self.tg_token))
        cl.addLayout(self._make_form_row("ID del Chat:", self.tg_chat_id))

        self.btn_test_tg = self._make_button("Enviar prueba", "#059669", "#047857")
        self.btn_test_tg.clicked.connect(self._test_telegram)
        cl.addWidget(self.btn_test_tg, alignment=Qt.AlignRight)

        # ════════════════════
        # Motor de IA
        # ════════════════════
        cl.addWidget(self._make_section_title("Motor de IA"))
        cl.addWidget(self._make_separator())

        # Temperatura
        temp_w = QWidget()
        temp_row = QHBoxLayout(temp_w)
        temp_row.setContentsMargins(0, 0, 0, 0)
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(0, 100)
        self.temp_slider.setValue(10)
        self.temp_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px; background: #e5e7eb; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #4f46e5; width: 16px; height: 16px;
                margin: -5px 0; border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #4f46e5; border-radius: 3px;
            }
        """)
        self.temp_label = QLabel("0.10")
        self.temp_label.setStyleSheet("font-size: 12px; color: #374151; font-weight: bold;")
        self.temp_label.setFixedWidth(40)
        temp_row.addWidget(self.temp_slider, 1)
        temp_row.addWidget(self.temp_label)
        self.temp_slider.valueChanged.connect(
            lambda v: self.temp_label.setText(f"{v / 100:.2f}")
        )
        cl.addLayout(self._make_form_row("Temperatura:", temp_w))

        # Tokens máximos
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(32, 4096)
        self.max_tokens.setValue(256)
        self.max_tokens.setStyleSheet("""
            QSpinBox {
                padding: 6px 10px; border: 1px solid #d1d5db;
                border-radius: 6px; font-size: 12px; color: #111827;
            }
            QSpinBox:focus { border-color: #4f46e5; }
        """)
        cl.addLayout(self._make_form_row("Tokens máximos:", self.max_tokens))

        # ════════════════════
        # Ajustes Avanzados (colapsable)
        # ════════════════════
        self.adv_group = QGroupBox("Ajustes Avanzados ▼")
        self.adv_group.setCheckable(True)
        self.adv_group.setChecked(False)
        self.adv_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px; font-weight: bold;
                color: #374151; border: 1px solid #e5e7eb;
                border-radius: 8px; margin-top: 12px;
                padding: 16px 12px 12px 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
            }
        """)
        self.adv_group.toggled.connect(
            lambda c: self.adv_group.setTitle(
                "Ajustes Avanzados ▼" if c else "Ajustes Avanzados ▶"
            )
        )

        adv_layout = QVBoxLayout()
        adv_layout.setSpacing(10)

        warning = QLabel("No modificar si no sabe lo que hace")
        warning.setStyleSheet("color: #d73a49; font-style: italic; font-size: 11px;")
        adv_layout.addWidget(warning)

        # --simple-io (bloqueado)
        sio_row = QHBoxLayout()
        self.simple_io_cb = QCheckBox("--simple-io")
        self.simple_io_cb.setChecked(True)
        self.simple_io_cb.setEnabled(False)
        self.simple_io_cb.setStyleSheet("""
            QCheckBox { font-size: 12px; color: #6b7280; }
            QCheckBox::indicator { width: 16px; height: 16px; }
        """)
        lock = QLabel("🔒")
        lock.setStyleSheet("font-size: 14px;")
        sio_row.addWidget(self.simple_io_cb)
        sio_row.addWidget(lock)
        sio_row.addStretch()
        adv_layout.addLayout(sio_row)

        sio_note = QLabel("Necesario para funcionamiento. No desactivar.")
        sio_note.setStyleSheet("color: #9ca3af; font-size: 10px; padding-left: 24px;")
        adv_layout.addWidget(sio_note)

        # --log-disable
        ld_row = QHBoxLayout()
        ld_row.addWidget(QLabel("--log-disable:"))
        ld_row.setAlignment(Qt.AlignLeft)
        self.log_disable_switch = Switch(True)
        ld_row.addWidget(self.log_disable_switch)
        ld_row.addStretch()
        adv_layout.addLayout(ld_row)

        # --no-show-timings
        nst_row = QHBoxLayout()
        nst_row.addWidget(QLabel("--no-show-timings:"))
        self.no_timings_switch = Switch(True)
        nst_row.addWidget(self.no_timings_switch)
        nst_row.addStretch()
        adv_layout.addLayout(nst_row)

        self.adv_group.setLayout(adv_layout)
        cl.addWidget(self.adv_group)

        # ════════════════════
        # Perfil de Usuario
        # ════════════════════
        cl.addWidget(self._make_section_title("Perfil de Usuario"))
        cl.addWidget(self._make_separator())

        self.user_id = QLineEdit()
        self.user_id.setPlaceholderText("Identificador único (ej: usuario_01)")
        self.user_name = QLineEdit()
        self.user_name.setPlaceholderText("Nombre (ej: Laura)")
        for w in (self.user_id, self.user_name):
            w.setStyleSheet("""
                QLineEdit {
                    padding: 6px 10px; border: 1px solid #d1d5db;
                    border-radius: 6px; font-size: 12px; color: #111827;
                }
                QLineEdit:focus { border-color: #4f46e5; }
            """)

        cl.addLayout(self._make_form_row("ID de usuario:", self.user_id))
        cl.addLayout(self._make_form_row("Nombre:", self.user_name))

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
        self.btn_cancel.clicked.connect(self.back_requested.emit)

        self.btn_save = QPushButton("Guardar y Reiniciar")
        self.btn_save.setStyleSheet("""
            QPushButton {
                padding: 8px 24px; border-radius: 6px;
                font-weight: 600; font-size: 13px;
                background: #4f46e5; color: white; border: none;
            }
            QPushButton:hover { background: #4338ca; }
        """)
        self.btn_save.clicked.connect(self._save_config)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_save)
        cl.addLayout(btn_row)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    # ── API pública ──

    def load_config(self, config):
        cfg = config
        s = lambda sec, key, fallback="": cfg.get(sec, key, fallback=fallback)
        s_bool = lambda sec, key, fallback=True: cfg.getboolean(sec, key, fallback=fallback)

        self.imap_host.setText(s("IMAP", "host"))
        self.imap_port.setText(s("IMAP", "port", "993"))
        self.imap_user.setText(s("IMAP", "user"))
        self.imap_pass.setText(s("IMAP", "pass"))

        self.tg_token.setText(s("TELEGRAM", "token"))
        self.tg_chat_id.setText(s("TELEGRAM", "chat_id"))

        temp = float(s("LLAMA", "temperature", "0.1"))
        self.temp_slider.setValue(int(temp * 100))
        self.max_tokens.setValue(int(s("LLAMA", "max_tokens", "256")))

        self.user_id.setText(s("PERFIL", "user_id"))
        self.user_name.setText(s("PERFIL", "user_name"))

        self.log_disable_switch.set_state(s_bool("GUI", "log_disable", True))
        self.no_timings_switch.set_state(s_bool("GUI", "no_show_timings", True))

    def get_config(self):
        cfg = configparser.ConfigParser()
        cfg["IMAP"] = {
            "host": self.imap_host.text(),
            "port": self.imap_port.text() or "993",
            "user": self.imap_user.text(),
            "pass": self.imap_pass.text(),
            "use_ssl": "true" if self.imap_port.text() in ("993", "143") else "false",
        }
        cfg["TELEGRAM"] = {
            "token": self.tg_token.text(),
            "chat_id": self.tg_chat_id.text(),
        }
        cfg["LLAMA"] = {
            "temperature": f"{self.temp_slider.value() / 100:.2f}",
            "max_tokens": str(self.max_tokens.value()),
        }
        cfg["GUI"] = {
            "poll_interval": "60",
            "temperature": f"{self.temp_slider.value() / 100:.2f}",
            "max_tokens": str(self.max_tokens.value()),
            "log_disable": "true" if self.log_disable_switch.is_on() else "false",
            "no_show_timings": "true" if self.no_timings_switch.is_on() else "false",
        }
        cfg["PERFIL"] = {
            "user_id": self.user_id.text(),
            "user_name": self.user_name.text(),
        }
        return cfg

    def _save_config(self):
        self.saved.emit(dict(self.get_config()))

    def _test_imap(self):
        host = self.imap_host.text().strip()
        port_str = self.imap_port.text().strip()
        user = self.imap_user.text().strip()
        password = self.imap_pass.text()

        if not host or not user or not password:
            QMessageBox.warning(self, "Campos incompletos",
                                "Completa los campos de IMAP primero.")
            return

        try:
            port = int(port_str) if port_str else 993
        except ValueError:
            QMessageBox.warning(self, "Puerto inválido",
                                "El puerto debe ser un número.")
            return

        self.btn_test_imap.setEnabled(False)
        self.btn_test_imap.setText("Probando...")

        thread = ImapTestThread(host, port, user, password, self)
        thread.result.connect(self._on_imap_test_result)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_imap_test_result(self, ok, msg):
        self.btn_test_imap.setEnabled(True)
        self.btn_test_imap.setText("Probar conexión")
        if ok:
            QMessageBox.information(self, "Conexión IMAP", msg)
        else:
            QMessageBox.critical(self, "Error IMAP", msg)

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

        # Estado interno
        self._monitoring = False
        self._daemon_running = False
        self._poll_interval = 60
        self._last_check = "--:--"

        self._build_ui()
        self._setup_daemon()
        self._setup_timers()
        self._update_button_states()

        QTimer.singleShot(800, self._start_monitoring)

    # ── UI ──

    def _build_ui(self):
        # Menú
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

        # Central
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

        # ── Stacked (Monitor / Config) ──
        self._stack = QStackedWidget()
        self._monitor = MonitorView()
        self._config = ConfigView()
        self._config.back_requested.connect(self._show_monitor)
        self._config.saved.connect(self._on_config_saved)
        self._stack.addWidget(self._monitor)
        self._stack.addWidget(self._config)
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
        else:
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)

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

    def _show_monitor(self):
        self._stack.setCurrentIndex(0)
        self._btn_bar.setVisible(True)

    def _on_config_saved(self, cfg_dict):
        cfg = configparser.ConfigParser()
        for section, values in cfg_dict.items():
            cfg[section] = values
        self._save_config_file(cfg)
        self._show_monitor()
        self._monitor.append_output("[GUI] Configuración guardada. Reiniciando...")
        if self._monitoring:
            self._stop_signal.emit()
            QTimer.singleShot(600, self._run_daemon_now)

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
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
