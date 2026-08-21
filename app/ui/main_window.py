"""
Fenêtre principale de l'application VetoPrix.
"""
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QMessageBox, QTabWidget,
    QStatusBar, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor

from app.database.db import init_db
from app.data.csv_importer import import_csv
from app.data.molecule_mapper import sync_molecules_from_anmv
from app.data.online_discovery import scrape_anmv, get_last_scrape_date
from app.ui.search_tab import SearchTab
from app.ui.stats_tab import StatsTab
from app.config import get_local_version
from app.update import check_for_update, start_update_and_quit


class ImportWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            result = import_csv(self.filepath)
            sync_molecules_from_anmv()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class AnmvSyncWorker(QThread):
    progress = pyqtSignal(int, int, str)   # current, total, letter
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            result = scrape_anmv(progress_callback=lambda c, t, l: self.progress.emit(c, t, l))
            sync_molecules_from_anmv()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class UpdateCheckWorker(QThread):
    finished = pyqtSignal(dict)

    def run(self):
        self.finished.emit(check_for_update())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VetoPrix — Comparateur de médicaments vétérinaires")
        self.setMinimumSize(900, 600)
        self._setup_ui()
        self._apply_style()
        self.showMaximized()
        self._auto_sync_anmv()
        # Vérif MAJ au démarrage (non bloquante, non forcée)
        self._check_update(silent=True)

    def _auto_sync_anmv(self):
        """Lance la sync ANMV en arrière-plan si les données ne sont pas à jour."""
        from datetime import date
        last = get_last_scrape_date()
        if last == date.today().isoformat():
            return  # Déjà synchronisé aujourd'hui
        self._sync_anmv(silent=True)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Header ---
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(12)

        title = QLabel("VetoPrix")
        title.setObjectName("app_title")
        header_layout.addWidget(title)

        sep = QLabel("|")
        sep.setObjectName("header_sep")
        header_layout.addWidget(sep)

        subtitle = QLabel("Comparateur de médicaments vétérinaires")
        subtitle.setObjectName("app_subtitle")
        header_layout.addWidget(subtitle)
        header_layout.addStretch()

        # Bouton sync ANMV
        self.btn_anmv = QPushButton("Sync ANMV")
        self.btn_anmv.setObjectName("btn_anmv")
        self.btn_anmv.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_anmv.setToolTip(
            "Télécharge le catalogue officiel des médicaments vétérinaires (ANMV/IRCP)\n"
            "pour obtenir dynamiquement les molécules et détecter les marques absentes de la centrale."
        )
        self.btn_anmv.clicked.connect(self._sync_anmv)
        last_sync = get_last_scrape_date()
        if last_sync:
            self.btn_anmv.setText(f"ANMV ({last_sync})")
        header_layout.addWidget(self.btn_anmv)

        self.btn_update = QPushButton(f"MAJ (v{get_local_version()})")
        self.btn_update.setObjectName("btn_anmv")
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.setToolTip(
            "Vérifie sur GitHub s'il existe une nouvelle version.\n"
            "Si oui, télécharge la mise à jour, ferme l'app, remplace les fichiers\n"
            "puis relance automatiquement (la base data/ est conservée)."
        )
        self.btn_update.clicked.connect(lambda: self._check_update(silent=False))
        header_layout.addWidget(self.btn_update)

        self.btn_import = QPushButton("Importer un tarif CSV")
        self.btn_import.setObjectName("btn_import")
        self.btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_import.clicked.connect(self._import_csv)
        header_layout.addWidget(self.btn_import)

        main_layout.addWidget(header)

        # --- Onglets ---
        self.tabs = QTabWidget()
        self.tabs.setObjectName("main_tabs")
        self.tabs.setDocumentMode(True)

        self.search_tab = SearchTab()
        self.stats_tab = StatsTab()

        self.tabs.addTab(self.search_tab, "Recherche & Comparaison")
        self.tabs.addTab(self.stats_tab, "Statistiques & Historique")

        content = QWidget()
        content.setObjectName("content_area")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 8)
        content_layout.addWidget(self.tabs)
        main_layout.addWidget(content)

        # --- Status bar ---
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Prêt — Importez un fichier CSV Centravet pour commencer.")

    def _check_update(self, silent: bool = False):
        self._update_silent = silent
        self.btn_update.setEnabled(False)
        if not silent:
            self.status.showMessage("Vérification des mises à jour sur GitHub…")
        self._update_worker = UpdateCheckWorker()
        self._update_worker.finished.connect(self._on_update_check_done)
        self._update_worker.start()

    def _on_update_check_done(self, result: dict):
        self.btn_update.setEnabled(True)
        silent = getattr(self, "_update_silent", False)

        if result.get("error"):
            self.status.showMessage("Échec de la vérification de mise à jour.")
            if not silent:
                QMessageBox.warning(
                    self, "Mise à jour",
                    f"Impossible de vérifier les mises à jour :\n{result['error']}"
                )
            return

        local = result["local"]
        remote = result["remote"]

        # À jour
        if not result["available"]:
            msg = f"VetoPrix est à jour (v{local})."
            self.status.showMessage(msg)
            self.btn_update.setText(f"MAJ (v{local})")
            if not silent:
                QMessageBox.information(
                    self, "Mise à jour",
                    f"Le logiciel est à jour.\n\nVersion installée : v{local}"
                    + (f"\nDernière release GitHub : v{remote}" if remote else "")
                )
            return

        # Nouvelle version disponible — proposer, ne jamais forcer
        release = result["release"]
        self.btn_update.setText(f"MAJ dispo (v{remote})")
        self.status.showMessage(f"Nouvelle version disponible : v{remote} (actuelle v{local})")

        notes = (release.body or "").strip()
        if len(notes) > 600:
            notes = notes[:600] + "…"
        msg = (
            f"Une nouvelle version est disponible.\n\n"
            f"Actuelle : v{local}\n"
            f"Nouvelle : v{remote}\n\n"
        )
        if notes:
            msg += f"Notes :\n{notes}\n\n"
        msg += (
            "Souhaitez-vous mettre à jour maintenant ?\n"
            "(L'app se fermera, se mettra à jour, puis se relancera.\n"
            "Vos données dans data/ seront conservées.)\n\n"
            "Vous pouvez aussi refuser et continuer à utiliser cette version."
        )
        reply = QMessageBox.question(
            self, "Mise à jour disponible", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,  # Ne pas forcer : Non par défaut
        )
        if reply != QMessageBox.StandardButton.Yes:
            self.status.showMessage(
                f"Mise à jour reportée — v{remote} disponible (vous êtes en v{local})."
            )
            return

        self.btn_update.setEnabled(False)
        self.status.showMessage(f"Téléchargement de la v{remote}…")
        try:
            start_update_and_quit(release)
        except Exception as e:
            self.btn_update.setEnabled(True)
            self.status.showMessage("Échec du téléchargement.")
            QMessageBox.critical(self, "Mise à jour", f"Échec :\n{e}")

    def _import_csv(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un tarif Centravet",
            str(Path.home()),
            "Fichiers CSV (*.csv);;Tous les fichiers (*)"
        )
        if not filepath:
            return
        self.btn_import.setEnabled(False)
        self.status.showMessage("Import en cours...")
        self._worker = ImportWorker(filepath)
        self._worker.finished.connect(self._on_import_done)
        self._worker.error.connect(self._on_import_error)
        self._worker.start()

    def _sync_anmv(self, silent=False):
        self._anmv_silent = silent
        self.btn_anmv.setEnabled(False)
        self.btn_anmv.setText("Sync ANMV…")
        msg = "Mise à jour du catalogue ANMV en arrière-plan…" if silent else "Téléchargement du catalogue ANMV en cours (A-Z)…"
        self.status.showMessage(msg)
        self._anmv_worker = AnmvSyncWorker()
        self._anmv_worker.progress.connect(self._on_anmv_progress)
        self._anmv_worker.finished.connect(self._on_anmv_done)
        self._anmv_worker.error.connect(self._on_anmv_error)
        self._anmv_worker.start()

    def _on_anmv_progress(self, current, total, letter):
        self.status.showMessage(f"Sync ANMV : lettre {letter} ({current}/{total})…")

    def _on_anmv_done(self, result):
        self.btn_anmv.setEnabled(True)
        self.btn_anmv.setText(f"ANMV ({result['date']})")
        self.status.showMessage(
            f"Catalogue ANMV synchronisé : {result['nb_produits']} médicaments officiels."
        )
        self.search_tab.refresh()
        if not getattr(self, '_anmv_silent', False):
            QMessageBox.information(
                self, "Sync ANMV terminée",
                f"Catalogue ANMV mis à jour.\n"
                f"{result['nb_produits']} médicaments vétérinaires officiels chargés.\n"
                f"Les molécules de la liste de recherche sont maintenant issues de cette base."
            )

    def _on_anmv_error(self, msg):
        self.btn_anmv.setEnabled(True)
        self.btn_anmv.setText("Sync ANMV")
        self.status.showMessage("Erreur lors de la sync ANMV.")
        if not getattr(self, '_anmv_silent', False):
            QMessageBox.critical(self, "Erreur Sync ANMV",
                                 f"Impossible de joindre le catalogue ANMV :\n{msg}")

    def _on_import_done(self, result):
        self.btn_import.setEnabled(True)
        self.status.showMessage(
            f"Import réussi : {result['nb_produits']} médicaments — tarif du {result['date_import']}"
        )
        self.search_tab.refresh()
        self.stats_tab.refresh()
        QMessageBox.information(
            self, "Import terminé",
            f"Tarif du {result['date_import']} importé avec succès.\n"
            f"{result['nb_produits']} médicaments enregistrés."
        )

    def _on_import_error(self, msg):
        self.btn_import.setEnabled(True)
        self.status.showMessage("Erreur lors de l'import.")
        QMessageBox.critical(self, "Erreur d'import", f"Une erreur est survenue :\n{msg}")

    def _apply_style(self):
        # Palette de base claire pour tout l'app
        app = QApplication.instance()
        app.setStyle("Fusion")
        palette = app.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#f4f6fb"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#1a1a2e"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f0f4ff"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#1a1a2e"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#e8ecf5"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1a1a2e"))
        app.setPalette(palette)

        self.setStyleSheet("""
            /* ===== FENÊTRE & FOND ===== */
            QMainWindow, QWidget#content_area {
                background-color: #f4f6fb;
            }

            /* ===== HEADER ===== */
            QFrame#header {
                background-color: #1e3a6e;
                min-height: 56px;
                max-height: 56px;
            }
            QLabel#app_title {
                font-size: 20px;
                font-weight: bold;
                color: #ffffff;
            }
            QLabel#header_sep {
                color: rgba(255,255,255,0.35);
                font-size: 18px;
            }
            QLabel#app_subtitle {
                font-size: 13px;
                color: rgba(255,255,255,0.80);
            }
            QPushButton#btn_import {
                background-color: #ffffff;
                color: #1e3a6e;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 13px;
                min-height: 34px;
            }
            QPushButton#btn_import:hover {
                background-color: #dce8ff;
            }
            QPushButton#btn_import:disabled {
                background-color: #aaa;
                color: #666;
            }
            QPushButton#btn_anmv {
                background-color: rgba(255,255,255,0.15);
                color: #ffffff;
                border: 1px solid rgba(255,255,255,0.4);
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                min-height: 30px;
            }
            QPushButton#btn_anmv:hover {
                background-color: rgba(255,255,255,0.25);
            }
            QPushButton#btn_anmv:disabled {
                color: rgba(255,255,255,0.4);
            }

            /* ===== ONGLETS ===== */
            QTabWidget#main_tabs::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: transparent;
                color: #555;
                font-size: 14px;
                font-weight: 500;
                padding: 10px 28px;
                border: none;
                border-bottom: 3px solid transparent;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                color: #1e3a6e;
                border-bottom: 3px solid #1e3a6e;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                color: #333;
                border-bottom: 3px solid #aac4f5;
            }

            /* ===== GROUPBOX ===== */
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #d0d8e8;
                border-radius: 8px;
                margin-top: 10px;
                padding: 14px 14px 10px 14px;
                font-size: 13px;
                font-weight: bold;
                color: #1e3a6e;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 6px;
                color: #1e3a6e;
            }

            /* ===== LABELS ===== */
            QLabel {
                color: #1a1a2e;
                font-size: 13px;
            }

            /* ===== INPUTS ===== */
            QLineEdit {
                background-color: #ffffff;
                color: #1a1a2e;
                border: 1.5px solid #c0cce0;
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 14px;
                selection-background-color: #aac4f5;
            }
            QLineEdit:focus {
                border-color: #1e3a6e;
            }
            QLineEdit::placeholder {
                color: #9aabbf;
            }
            QComboBox {
                background-color: #ffffff;
                color: #1a1a2e;
                border: 1.5px solid #c0cce0;
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 14px;
                min-height: 34px;
            }
            QComboBox:focus {
                border-color: #1e3a6e;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1a1a2e;
                selection-background-color: #dce8ff;
                border: 1px solid #c0cce0;
                font-size: 14px;
            }

            /* ===== BOUTON PRIMAIRE ===== */
            QPushButton#btn_primary {
                background-color: #1e3a6e;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 28px;
                font-size: 14px;
                font-weight: bold;
                min-height: 38px;
            }
            QPushButton#btn_primary:hover {
                background-color: #2c55a0;
            }
            QPushButton#btn_primary:pressed {
                background-color: #162d57;
            }

            /* ===== TABLEAU ===== */
            QTableWidget {
                background-color: #ffffff;
                color: #1a1a2e;
                gridline-color: #e0e8f5;
                border: 1px solid #d0d8e8;
                border-radius: 8px;
                font-size: 13px;
                selection-background-color: #dce8ff;
                selection-color: #1a1a2e;
                alternate-background-color: #f0f4ff;
            }
            QTableWidget::item {
                padding: 6px 8px;
                color: #1a1a2e;
            }
            QTableWidget::item:selected {
                background-color: #dce8ff;
                color: #1a1a2e;
            }
            QHeaderView::section {
                background-color: #1e3a6e;
                color: #ffffff;
                padding: 8px 10px;
                border: none;
                border-right: 1px solid #2c55a0;
                font-weight: bold;
                font-size: 13px;
            }
            QHeaderView::section:last {
                border-right: none;
            }

            /* ===== STATUS BAR ===== */
            QStatusBar {
                background-color: #e8ecf5;
                color: #444;
                font-size: 12px;
                padding: 3px 8px;
            }

            /* ===== SCROLLBARS ===== */
            QScrollBar:vertical {
                background: #f0f4ff;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #b0bcd8;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #7a94c4;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background: #f0f4ff;
                height: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #b0bcd8;
                border-radius: 5px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #7a94c4;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)


def launch():
    init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    sys.exit(app.exec())
