import os
import sys
import json
import subprocess
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QTextBrowser,
    QDialog, QHeaderView, QStackedWidget, QFrame, QStyle
)
from PySide6.QtCore import Qt, QTimer, QProcess
from PySide6.QtGui import QFont, QColor, QTextCursor

class ActionsCellWidget(QWidget):
    """
    Custom cell widget for the actions column. Contains Approve, Reject, and View buttons.
    """
    def __init__(self, email_id, parent_window):
        super().__init__()
        self.email_id = email_id
        self.parent_window = parent_window
        
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        
        # Approve button
        self.btn_approve = QPushButton("Aprobar")
        self.btn_approve.setStyleSheet("""
            QPushButton {
                background-color: #dcfce7;
                color: #166534;
                border: 1px solid #bbf7d0;
                border-radius: 6px;
                font-weight: 600;
                padding: 5px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #bbf7d0;
            }
            QPushButton:pressed {
                background-color: #86efac;
            }
        """)
        
        # Reject button
        self.btn_reject = QPushButton("Rechazar")
        self.btn_reject.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #991b1b;
                border: 1px solid #fecaca;
                border-radius: 6px;
                font-weight: 600;
                padding: 5px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #fecaca;
            }
            QPushButton:pressed {
                background-color: #fca5a5;
            }
        """)
        
        # View button
        self.btn_view = QPushButton("Ver email")
        self.btn_view.setStyleSheet("""
            QPushButton {
                background-color: #e0f2fe;
                color: #075985;
                border: 1px solid #bae6fd;
                border-radius: 6px;
                font-weight: 600;
                padding: 5px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #bae6fd;
            }
            QPushButton:pressed {
                background-color: #7dd3fc;
            }
        """)
        
        layout.addWidget(self.btn_approve)
        layout.addWidget(self.btn_reject)
        layout.addWidget(self.btn_view)
        self.setLayout(layout)
        
        # Connect clicks
        self.btn_approve.clicked.connect(lambda: self.parent_window.process_action(self.email_id, approved=True))
        self.btn_reject.clicked.connect(lambda: self.parent_window.process_action(self.email_id, approved=False))
        self.btn_view.clicked.connect(lambda: self.parent_window.show_email_details(self.email_id))

class EmailDetailsDialog(QDialog):
    """
    Elegant custom dialog window to display full email contents and AI triage details.
    """
    def __init__(self, email_item, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detalles del Correo — EmailTriagePro")
        self.resize(700, 550)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                font-family: 'Segoe UI', -apple-system, system-ui, sans-serif;
            }
            QLabel {
                font-size: 13px;
                color: #1f2937;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Metadata Card
        meta_card = QFrame()
        meta_card.setStyleSheet("""
            QFrame {
                background-color: #f9fafb;
                border: 1px solid #f3f4f6;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        meta_layout = QVBoxLayout(meta_card)
        meta_layout.setSpacing(6)
        meta_layout.setContentsMargins(10, 10, 10, 10)
        
        lbl_from = QLabel(f"<b>De:</b> {email_item.get('de', 'Desconocido')}")
        lbl_subject = QLabel(f"<b>Asunto:</b> {email_item.get('asunto', '(Sin asunto)')}")
        lbl_date = QLabel(f"<b>Fecha:</b> {email_item.get('hora', '')}")
        
        lbl_from.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl_subject.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl_date.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        meta_layout.addWidget(lbl_from)
        meta_layout.addWidget(lbl_subject)
        meta_layout.addWidget(lbl_date)
        layout.addWidget(meta_card)
        
        # AI Triage Information
        triage_card = QFrame()
        triage_card.setStyleSheet("""
            QFrame {
                background-color: #f5f3ff;
                border: 1px solid #ede9fe;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        triage_layout = QVBoxLayout(triage_card)
        triage_layout.setSpacing(8)
        triage_layout.setContentsMargins(10, 10, 10, 10)
        
        # Category tag styling
        etiqueta = email_item.get('etiqueta', 'Útil-Info')
        urgencia = email_item.get('urgencia', 1)
        
        badge_style = "background-color: #e0e7ff; color: #4338ca; border-radius: 6px; padding: 3px 8px; font-weight: bold; font-size: 11px;"
        if "Urgente" in etiqueta:
            badge_style = "background-color: #fee2e2; color: #991b1b; border-radius: 6px; padding: 3px 8px; font-weight: bold; font-size: 11px;"
        elif etiqueta == "Spam":
            badge_style = "background-color: #f3f4f6; color: #374151; border-radius: 6px; padding: 3px 8px; font-weight: bold; font-size: 11px;"
            
        triage_header_layout = QHBoxLayout()
        lbl_triage_title = QLabel("<b>ANÁLISIS INTELIGENTE (LLM)</b>")
        lbl_triage_title.setStyleSheet("color: #5b21b6; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        triage_header_layout.addWidget(lbl_triage_title)
        triage_header_layout.addStretch()
        
        lbl_badge = QLabel(etiqueta)
        lbl_badge.setStyleSheet(badge_style)
        triage_header_layout.addWidget(lbl_badge)
        
        # Urgency Stars
        urgency_stars = "★" * urgencia + "☆" * (5 - urgencia)
        lbl_urgency = QLabel(f"<b>Nivel de Urgencia:</b> <span style='color: #b45309;'>{urgency_stars}</span> ({urgencia}/5)")
        lbl_urgency.setStyleSheet("font-size: 13px;")
        
        lbl_summary = QLabel(f"<b>Resumen:</b> {email_item.get('resumen', '')}")
        lbl_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        lbl_action = QLabel(f"<b>Acción Sugerida:</b> <i>{email_item.get('accion_sugerida', '')}</i>")
        lbl_action.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        triage_layout.addLayout(triage_header_layout)
        triage_layout.addWidget(lbl_urgency)
        triage_layout.addWidget(lbl_summary)
        triage_layout.addWidget(lbl_action)
        layout.addWidget(triage_card)
        
        # Email Body Text Browser
        layout.addWidget(QLabel("<b>Cuerpo del correo:</b>"))
        body_browser = QTextBrowser()
        body_browser.setPlainText(email_item.get('cuerpo', ''))
        body_browser.setStyleSheet("""
            QTextBrowser {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 12px;
                background-color: #f9fafb;
                color: #1f2937;
                font-size: 13px;
                font-family: inherit;
            }
        """)
        layout.addWidget(body_browser)
        
        # Actions inside popup
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_close = QPushButton("Cerrar")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f3f4f6;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e5e7eb;
            }
        """)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.workspace_dir = os.path.dirname(os.path.abspath(__file__))
        self.current_emails = {}
        
        self.setWindowTitle("EmailTriagePro — Bandeja de Aprobación Humana Obligatoria")
        self.resize(1000, 650)
        
        # Set Modern Stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f3f4f6;
            }
            QTabWidget::pane {
                border: 1px solid #e5e7eb;
                background-color: #ffffff;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #e5e7eb;
                color: #4b5563;
                padding: 10px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #4f46e5;
                border-bottom: 2px solid #4f46e5;
            }
            QTableWidget {
                border: none;
                gridline-color: #f3f4f6;
                background-color: #ffffff;
                alternate-background-color: #fafafa;
                font-size: 13px;
                color: #1f2937;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #f9fafb;
                color: #4b5563;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #e5e7eb;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        
        # Main central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # Header layout
        header_layout = QHBoxLayout()
        
        logo_frame = QFrame()
        logo_frame.setStyleSheet("""
            QFrame {
                background-color: #4f46e5;
                border-radius: 8px;
                min-width: 36px;
                min-height: 36px;
                max-width: 36px;
                max-height: 36px;
            }
        """)
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(0,0,0,0)
        logo_layout.setAlignment(Qt.AlignCenter)
        lbl_logo = QLabel("ET")
        lbl_logo.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 16px;")
        logo_layout.addWidget(lbl_logo)
        header_layout.addWidget(logo_frame)
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        lbl_title = QLabel("EmailTriagePro")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #111827;")
        lbl_subtitle = QLabel("Clasificación de Gmail/Proton con Inteligencia Artificial Local (Qwen3)")
        lbl_subtitle.setStyleSheet("font-size: 12px; color: #6b7280;")
        title_layout.addWidget(lbl_title)
        title_layout.addWidget(lbl_subtitle)
        header_layout.addLayout(title_layout)
        
        header_layout.addStretch()
        
        # Action Buttons
        self.btn_refresh = QPushButton(" ↻ Refrescar ahora")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4338ca;
            }
            QPushButton:pressed {
                background-color: #3730a3;
            }
            QPushButton:disabled {
                background-color: #a5b4fc;
                color: #e0e7ff;
            }
        """)
        self.btn_refresh.clicked.connect(self.trigger_daemon_run)
        header_layout.addWidget(self.btn_refresh)
        
        main_layout.addLayout(header_layout)
        
        # Tabs widget
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # TAB 1: PENDIENTES
        self.tab_pendientes = QWidget()
        tab_p_layout = QVBoxLayout(self.tab_pendientes)
        tab_p_layout.setContentsMargins(12, 12, 12, 12)
        
        # Stacked widget for table vs empty placeholder
        self.stacked_widget = QStackedWidget()
        
        # Page 0: Table
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(6)
        self.table_widget.setHorizontalHeaderLabels(["Hora", "De", "Asunto", "Etiqueta", "Urgencia", "Acciones"])
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setSelectionMode(QTableWidget.SingleSelection)
        
        # Columns resize behavior
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Hora
        header.setSectionResizeMode(1, QHeaderView.Interactive)      # De
        header.setSectionResizeMode(2, QHeaderView.Stretch)          # Asunto
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Etiqueta
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Urgencia
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Acciones
        
        # Page 1: Empty Placeholder
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_layout.setSpacing(12)
        
        lbl_empty_icon = QLabel("📬")
        lbl_empty_icon.setStyleSheet("font-size: 56px; margin-bottom: 8px;")
        lbl_empty_icon.setAlignment(Qt.AlignCenter)
        
        lbl_empty_title = QLabel("Bandeja de pendientes vacía")
        lbl_empty_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #111827;")
        lbl_empty_title.setAlignment(Qt.AlignCenter)
        
        lbl_empty_sub = QLabel("No hay correos esperando aprobación manual en este momento.")
        lbl_empty_sub.setStyleSheet("font-size: 13px; color: #6b7280;")
        lbl_empty_sub.setAlignment(Qt.AlignCenter)
        
        empty_layout.addWidget(lbl_empty_icon)
        empty_layout.addWidget(lbl_empty_title)
        empty_layout.addWidget(lbl_empty_sub)
        
        self.stacked_widget.addWidget(self.table_widget)
        self.stacked_widget.addWidget(self.empty_widget)
        
        tab_p_layout.addWidget(self.stacked_widget)
        
        # TAB 2: LOG
        self.tab_log = QWidget()
        tab_l_layout = QVBoxLayout(self.tab_log)
        tab_l_layout.setContentsMargins(12, 12, 12, 12)
        tab_l_layout.setSpacing(10)
        
        log_header = QHBoxLayout()
        lbl_log_title = QLabel("Registro de Auditoría (acciones.log)")
        lbl_log_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #374151;")
        log_header.addWidget(lbl_log_title)
        log_header.addStretch()
        
        btn_refresh_log = QPushButton("Actualizar Log")
        btn_refresh_log.setStyleSheet("""
            QPushButton {
                background-color: #f3f4f6;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 5px 12px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e5e7eb;
            }
        """)
        btn_refresh_log.clicked.connect(self.load_log_data)
        log_header.addWidget(btn_refresh_log)
        tab_l_layout.addLayout(log_header)
        
        self.log_browser = QTextBrowser()
        self.log_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #111827;
                color: #f3f4f6;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #1f2937;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        tab_l_layout.addWidget(self.log_browser)
        
        # Add tabs
        self.tabs.addTab(self.tab_pendientes, "Pendientes")
        self.tabs.addTab(self.tab_log, "Auditoría (Log)")
        
        main_layout.addWidget(self.tabs)
        
        # Status Bar
        self.statusBar().setStyleSheet("background-color: #ffffff; color: #4b5563; font-size: 11px;")
        self.status_label = QLabel("Listo")
        self.statusBar().addWidget(self.status_label)
        
        # Setup process runner
        self.daemon_process = QProcess(self)
        self.daemon_process.finished.connect(self.on_daemon_finished)
        
        # Polling timer
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.load_pending_data)
        self.poll_timer.start(30000) # every 30s
        
        # Initial load
        self.load_pending_data()
        self.load_log_data()
        
    def load_pending_data(self):
        memoria_path = os.path.join(self.workspace_dir, "memoria", "pendientes.json")
        pending_list = []
        if os.path.exists(memoria_path):
            try:
                with open(memoria_path, "r", encoding="utf-8") as f:
                    pending_list = json.load(f)
                    if not isinstance(pending_list, list):
                        pending_list = []
            except Exception as e:
                print(f"Error cargando pendientes.json: {e}")
                
        if not pending_list:
            self.stacked_widget.setCurrentIndex(1) # Show placeholder
            self.current_emails = {}
            return
            
        self.stacked_widget.setCurrentIndex(0) # Show table
        self.current_emails = {item["id"]: item for item in pending_list}
        
        self.table_widget.setRowCount(0)
        self.table_widget.setRowCount(len(pending_list))
        
        for row, item in enumerate(pending_list):
            # Hora
            it_hora = QTableWidgetItem(item.get("hora", ""))
            it_hora.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table_widget.setItem(row, 0, it_hora)
            
            # De
            it_de = QTableWidgetItem(item.get("de", ""))
            it_de.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table_widget.setItem(row, 1, it_de)
            
            # Asunto
            it_asunto = QTableWidgetItem(item.get("asunto", ""))
            it_asunto.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table_widget.setItem(row, 2, it_asunto)
            
            # Etiqueta
            etiqueta = item.get("etiqueta", "")
            it_etiqueta = QTableWidgetItem(etiqueta)
            it_etiqueta.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            if "Urgente" in etiqueta:
                it_etiqueta.setForeground(QColor("#b91c1c"))
            elif etiqueta == "Spam":
                it_etiqueta.setForeground(QColor("#4b5563"))
            else:
                it_etiqueta.setForeground(QColor("#4f46e5"))
            self.table_widget.setItem(row, 3, it_etiqueta)
            
            # Urgencia
            urgencia = item.get("urgencia", 1)
            stars = "★" * urgencia + "☆" * (5 - urgencia)
            it_urgencia = QTableWidgetItem(stars)
            it_urgencia.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            it_urgencia.setForeground(QColor("#d97706"))
            self.table_widget.setItem(row, 4, it_urgencia)
            
            # Actions cell
            actions_cell = ActionsCellWidget(item.get("id"), self)
            self.table_widget.setCellWidget(row, 5, actions_cell)
            
        # Standard table adjustment
        self.table_widget.resizeRowsToContents()

    def load_log_data(self):
        log_path = os.path.join(self.workspace_dir, "logs", "acciones.log")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.log_browser.setPlainText(content)
                # Auto-scroll to end
                self.log_browser.moveCursor(QTextCursor.End)
            except Exception as e:
                self.log_browser.setPlainText(f"Error al leer archivo de log: {e}")
        else:
            self.log_browser.setPlainText("El archivo de registro de auditoría aún no se ha creado.")

    def process_action(self, email_id, approved):
        memoria_path = os.path.join(self.workspace_dir, "memoria", "pendientes.json")
        log_path = os.path.join(self.workspace_dir, "logs", "acciones.log")
        
        pending_list = []
        if os.path.exists(memoria_path):
            try:
                with open(memoria_path, "r", encoding="utf-8") as f:
                    pending_list = json.load(f)
            except Exception as e:
                print(f"Error cargando pendientes.json al procesar acción: {e}")
                
        email_item = None
        new_pending_list = []
        for item in pending_list:
            if item.get("id") == email_id:
                email_item = item
            else:
                new_pending_list.append(item)
                
        if email_item:
            # Save updated list
            try:
                with open(memoria_path, "w", encoding="utf-8") as f:
                    json.dump(new_pending_list, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Error actualizando pendientes.json: {e}")
                
            # Log action
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            accion_val = email_item.get("accion_sugerida", "procesar")
            aprobado_str = "SI" if approved else "NO"
            
            # format: timestamp | USUARIO: admin | EMAIL_ID: x | ACCION: x | APROBADO: SI
            log_line = f"{timestamp} | USUARIO: admin | EMAIL_ID: {email_id} | ACCION: {accion_val} | APROBADO: {aprobado_str}\n"
            
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(log_line)
            except Exception as e:
                print(f"Error escribiendo en log de auditoría: {e}")
                
            # Update UI
            self.load_pending_data()
            self.load_log_data()
            
            self.status_label.setText(f"Acción procesada para el correo ID: {email_id} ({'Aprobado' if approved else 'Rechazado'}).")
            
    def show_email_details(self, email_id):
        email_item = self.current_emails.get(email_id)
        if email_item:
            dialog = EmailDetailsDialog(email_item, self)
            dialog.exec()
            
    def trigger_daemon_run(self):
        self.btn_refresh.setEnabled(False)
        self.status_label.setText("Sincronizando correos en segundo plano (ejecutando daemon.py)...")
        
        # Read system_global.txt to pass as override argument
        system_global_val = ""
        skills_dir = os.path.join(self.workspace_dir, "skills")
        system_global_path = os.path.join(skills_dir, "system_global.txt")
        if os.path.exists(system_global_path):
            try:
                with open(system_global_path, "r", encoding="utf-8") as f:
                    system_global_val = f.read().strip()
            except Exception as e:
                print(f"Error al leer system_global.txt: {e}")
                
        # Run daemon.py using python interpreter
        python_exe = sys.executable
        daemon_script = os.path.join(self.workspace_dir, "daemon.py")
        
        args = [daemon_script]
        if system_global_val:
            args.extend(["--system-global", system_global_val])
            
        self.daemon_process.start(python_exe, args)
        
    def on_daemon_finished(self, exit_code, exit_status):
        self.btn_refresh.setEnabled(True)
        if exit_code == 0:
            self.status_label.setText("Actualización de la bandeja completada.")
            self.load_pending_data()
            self.load_log_data()
        else:
            self.status_label.setText("Error en la ejecución del daemon. Verifica config.ini o credenciales IMAP.")
            
    def on_tab_changed(self, index):
        if index == 1:
            self.load_log_data()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
