"""
test_smoke.py — Smoke tests for EmailTriagePro

Tests:
  1. daemon.py: simulate 1 fake email through run_classification,
     verify llama-cli and Telegram are called, no real connections leak.
  2. gui_main.py: import MainWindow, instantiate without crash.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)


class TestDaemonSmoke(unittest.TestCase):
    """Simulate 1 fake email through the full classification pipeline."""

    FAKE_EMAIL_RFC822 = (
        b"From: sender@test.com\r\n"
        b"To: recipient@test.com\r\n"
        b"Subject: Firma urgente hoy\r\n"
        b"Message-ID: <test123@mail.test.com>\r\n"
        b"Date: Wed, 01 Jan 2025 12:00:00 +0000\r\n"
        b"\r\n"
        b"Necesito que firmes el contrato hoy antes de las 18hs."
    )

    FAKE_CLASSIFICATION = {
        "etiqueta": "Urgente-Firma",
        "urgencia": 5,
        "resumen": "Firmar contrato urgente",
        "accion_sugerida": "Firmar antes de las 18hs",
        "requiere_aprobacion": True,
    }

    @patch("daemon.imaplib.IMAP4_SSL")
    @patch("daemon.subprocess.run")
    @patch("daemon.requests.post")
    def test_pipeline_one_email(self, mock_requests, mock_subprocess, mock_imap):
        """1 email fake, verifica que llama-cli y Telegram se invocan."""

        # --- IMAP mock: 1 unseen email ---
        mock_mail = MagicMock()
        mock_imap.return_value = mock_mail
        mock_mail.search.return_value = ("OK", [b"1"])
        mock_mail.fetch.return_value = (
            "OK",
            [(b"1", self.FAKE_EMAIL_RFC822)],
        )

        # --- llama-cli mock: return fake JSON ---
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(self.FAKE_CLASSIFICATION)
        mock_subprocess.return_value = mock_result

        # --- Telegram mock: return OK ---
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.return_value = mock_resp

        # --- Execute (lee config.ini real pero no conecta a nada) ---
        import daemon

        daemon.run_classification(
            system_global_override="Eres un asistente de test"
        )

        # --- Asserts ---
        # 1. IMAP conectó y autenticó
        mock_imap.assert_called_once()
        mock_mail.login.assert_called_once()

        # 2. Buscó no-leídos
        mock_mail.search.assert_called_once_with(None, "UNSEEN")

        # 3. Fetch el email
        mock_mail.fetch.assert_called_once_with(b"1", "(RFC822)")

        # 4. LLM se ejecutó (llama-cli)
        mock_subprocess.assert_called_once()

        # 5. Telegram fue llamado (Urgente-Firma con urgencia 5)
        mock_requests.assert_called_once()

        # 6. Email marcado como leído
        mock_mail.store.assert_called_once_with(
            b"1", "+FLAGS", "\\Seen"
        )

        # 7. Telegram recibió un payload con chat_id
        call_args, call_kwargs = mock_requests.call_args
        self.assertIn("bot", call_args[0])


class TestGuiSmoke(unittest.TestCase):
    """Import gui_main.py and verify MainWindow instantiates."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    def test_mainwindow_instantiate(self):
        """MainWindow se crea sin crash en modo offscreen."""
        from PySide6.QtWidgets import QApplication

        _app = QApplication.instance() or QApplication(sys.argv)

        # Parcheamos _setup_daemon para evitar QThread persistente
        with patch(
            "gui_main.MainWindow._setup_daemon", return_value=None
        ), patch(
            "gui_main.MainWindow._cleanup", return_value=None
        ):
            import gui_main

            window = gui_main.MainWindow()
            self.assertIsNotNone(window)
            self.assertEqual(
                window.windowTitle(),
                "Aplicación de Correo - Clasificador Inteligente",
            )
            # Cancelar timer si llegó a crearse
            if hasattr(window, "_poll_timer") and window._poll_timer.isActive():
                window._poll_timer.stop()


if __name__ == "__main__":
    unittest.main()
