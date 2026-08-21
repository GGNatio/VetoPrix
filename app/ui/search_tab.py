"""
Onglet Recherche : recherche par molécule ou mot-clé libre, tableau comparatif.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QFrame, QSizePolicy, QScrollArea, QCheckBox,
    QDialog, QDialogButtonBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from app.data.search import search_by_keyword, search_by_molecules, get_all_molecules, get_all_imports
from app.data.online_discovery import get_absent_from_catalog, get_last_scrape_date, get_all_anmv_for_dci

_CHIP_STYLE = """
    QPushButton {
        background: #eef3fb;
        color: #1e3a6e;
        border: 1.5px solid #c0d0ea;
        border-radius: 13px;
        padding: 3px 11px;
        font-size: 11px;
        font-weight: 500;
        text-align: center;
    }
    QPushButton:hover:!checked {
        background: #dde9f9;
        border-color: #1e3a6e;
    }
    QPushButton:checked {
        background: #1e3a6e;
        color: #ffffff;
        border-color: #1e3a6e;
        font-weight: 700;
    }
"""

class SearchTab(QWidget):
    def __init__(self):
        super().__init__()
        self._mol_chips = []
        self._last_results = None  # derniers résultats DB bruts
        self._setup_ui()
        self._load_initial_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 4, 0, 0)

        search_card = QFrame()
        search_card.setObjectName("search_card")
        search_card.setStyleSheet("""
            QFrame#search_card {
                background: #ffffff;
                border: 1px solid #d0d8e8;
                border-radius: 10px;
            }
        """)
        card_layout = QVBoxLayout(search_card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(16, 14, 16, 14)

        title_lbl = QLabel("Critères de recherche")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e3a6e;")
        card_layout.addWidget(title_lbl)

        row1 = QHBoxLayout()
        row1.setSpacing(12)

        mol_block = QVBoxLayout()
        mol_block.setSpacing(5)

        mol_header = QHBoxLayout()
        lbl_mol = QLabel("Molécules")
        lbl_mol.setStyleSheet("font-size: 12px; color: #555; font-weight: 600;")
        self.lbl_mol_count = QLabel("")
        self.lbl_mol_count.setStyleSheet("font-size: 11px; color: #1e3a6e; font-weight: 600;")
        mol_header.addWidget(lbl_mol)
        mol_header.addStretch()
        mol_header.addWidget(self.lbl_mol_count)
        btn_reset_mol = QPushButton("↺")
        btn_reset_mol.setFixedSize(22, 22)
        btn_reset_mol.setToolTip("Décocher toutes les molécules")
        btn_reset_mol.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset_mol.setStyleSheet(
            "QPushButton { border: 1px solid #c0d0ea; border-radius: 11px; "
            "font-size: 12px; color: #1e3a6e; background: #eef3fb; }"
            "QPushButton:hover { background: #dde9f9; }"
        )
        btn_reset_mol.clicked.connect(self._reset_molecules)
        mol_header.addWidget(btn_reset_mol)
        mol_block.addLayout(mol_header)

        self.mol_filter = QLineEdit()
        self.mol_filter.setPlaceholderText("Filtrer les molécules…")
        self.mol_filter.setMaximumHeight(26)
        self.mol_filter.setStyleSheet(
            "border: 1px solid #c8d4e8; border-radius: 5px; padding: 2px 7px; font-size: 11px;"
        )
        self.mol_filter.textChanged.connect(self._filter_mol_chips)
        mol_block.addWidget(self.mol_filter)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFixedHeight(118)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1.5px solid #d0d8e8;
                border-radius: 8px;
                background: #f4f7fd;
            }
            QScrollBar:vertical { width: 6px; background: transparent; }
            QScrollBar::handle:vertical { background: #c0d0ea; border-radius: 3px; }
        """)

        self._chip_container = QWidget()
        self._chip_container.setStyleSheet("background: #f4f7fd;")
        self._chip_layout = QVBoxLayout(self._chip_container)
        self._chip_layout.setSpacing(5)
        self._chip_layout.setContentsMargins(6, 6, 6, 6)
        self._chip_layout.addStretch()
        self._scroll_area.setWidget(self._chip_container)

        mol_block.addWidget(self._scroll_area)
        row1.addLayout(mol_block, 3)

        sep_lbl = QLabel("ou")
        sep_lbl.setStyleSheet("color: #aaa; font-size: 13px;")
        sep_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom)
        sep_lbl.setFixedWidth(28)
        sep_lbl.setContentsMargins(0, 0, 0, 6)
        row1.addWidget(sep_lbl)

        kw_block = QVBoxLayout()
        kw_block.setSpacing(4)
        lbl_kw = QLabel("Mot-clé libre")
        lbl_kw.setStyleSheet("font-size: 12px; color: #555; font-weight: 600;")
        self.kw_input = QLineEdit()
        self.kw_input.setPlaceholderText("ex: metacam, amoxicilline…")
        self.kw_input.returnPressed.connect(self._do_search)
        kw_block.addWidget(lbl_kw)
        kw_block.addWidget(self.kw_input)
        row1.addLayout(kw_block, 2)

        imp_block = QVBoxLayout()
        imp_block.setSpacing(4)
        lbl_imp = QLabel("Tarif")
        lbl_imp.setStyleSheet("font-size: 12px; color: #555; font-weight: 600;")
        self.import_combo = QComboBox()
        self.import_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.import_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        imp_block.addWidget(lbl_imp)
        imp_block.addWidget(self.import_combo)
        row1.addLayout(imp_block, 2)

        btn_block = QVBoxLayout()
        btn_block.setSpacing(4)
        btn_block.addWidget(QLabel(""))
        self.btn_search = QPushButton("Rechercher")
        self.btn_search.setObjectName("btn_primary")
        self.btn_search.setMinimumWidth(130)
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.clicked.connect(self._do_search)
        btn_block.addWidget(self.btn_search)
        row1.addLayout(btn_block)

        card_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(24)

        vol_block = QVBoxLayout()
        vol_block.setSpacing(4)
        lbl_vol = QLabel("Volume (ml)")
        lbl_vol.setStyleSheet("font-size: 12px; color: #555; font-weight: 600;")
        self.vol_input = QLineEdit()
        self.vol_input.setPlaceholderText("ex: 25   ou   25-100  (intervalle)")
        self.vol_input.setMaximumWidth(220)
        self.vol_input.returnPressed.connect(self._do_search)
        vol_block.addWidget(lbl_vol)
        vol_block.addWidget(self.vol_input)
        row2.addLayout(vol_block)

        assoc_block = QVBoxLayout()
        assoc_block.setSpacing(4)
        assoc_block.addWidget(QLabel(""))
        self.chk_mono = QCheckBox("Exclure les médicaments à association fixe")
        self.chk_mono.setStyleSheet(
            "QCheckBox { font-size: 12px; color: #555; }"
            "QCheckBox::indicator { width: 15px; height: 15px; }"
        )
        self.chk_mono.setToolTip(
            "Exclut les produits contenant plusieurs molécules actives\n"
            "(ex : Synulox = amoxicilline + acide clavulanique)."
        )
        self.chk_mono.toggled.connect(self._do_search)
        assoc_block.addWidget(self.chk_mono)
        row2.addLayout(assoc_block)

        pur_block = QVBoxLayout()
        pur_block.setSpacing(4)
        pur_block.addWidget(QLabel(""))
        self.chk_pur = QPushButton("Pur uniquement")
        self.chk_pur.setCheckable(True)
        self.chk_pur.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_pur.setToolTip(
            "N'affiche que les médicaments contenant une seule molécule active\n"
            "(masque les associations fixes type amoxicilline + acide clavulanique)."
        )
        self.chk_pur.setStyleSheet("""
            QPushButton {
                background: #eef3fb;
                color: #1e3a6e;
                border: 1.5px solid #c0d0ea;
                border-radius: 6px;
                padding: 4px 14px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover:!checked { background: #dde9f9; }
            QPushButton:checked {
                background: #1e3a6e;
                color: #fff;
                font-weight: 700;
            }
        """)
        self.chk_pur.toggled.connect(self._apply_local_filters)
        pur_block.addWidget(self.chk_pur)
        row2.addLayout(pur_block)

        row2.addStretch(1)

        reset_block = QVBoxLayout()
        reset_block.setSpacing(4)
        reset_block.addStretch()
        self.btn_reset_all = QPushButton("↺ Tout réinitialiser")
        self.btn_reset_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_all.setStyleSheet("""
            QPushButton {
                background: #f5f5f5;
                color: #666;
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 4px 14px;
                font-size: 12px;
            }
            QPushButton:hover { background: #ffe8e8; color: #900; border-color: #f99; }
        """)
        self.btn_reset_all.clicked.connect(self._reset_all)
        reset_block.addWidget(self.btn_reset_all)
        row2.addLayout(reset_block)

        card_layout.addLayout(row2)
        layout.addWidget(search_card)

        # --- Bande absents de la centrale ---
        absent_row = QHBoxLayout()
        absent_row.setSpacing(10)
        self.btn_absent = QPushButton("📊 Médicaments absents de la centrale")
        self.btn_absent.setStyleSheet("""
            QPushButton {
                background: #fff8e1;
                color: #7a5800;
                border: 1.5px solid #f0c040;
                border-radius: 7px;
                padding: 5px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #fff0b3; }
            QPushButton:disabled { color: #bbb; border-color: #ddd; background: #f9f9f9; }
        """)
        self.btn_absent.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_absent.setEnabled(False)
        self.btn_absent.setToolTip(
            "Affiche les médicaments officiellement autorisés (ANMV) pour cette molécule\n"
            "mais introuvables dans le catalogue Centravet importé.\n"
            "Nécessite d'avoir coché une molécule et effectué une Sync ANMV."
        )
        self.btn_absent.clicked.connect(self._show_absent_dialog)
        absent_row.addWidget(self.btn_absent)
        self.lbl_absent_sync = QLabel("")
        self.lbl_absent_sync.setStyleSheet("font-size: 11px; color: #888; font-style: italic;")
        absent_row.addWidget(self.lbl_absent_sync)
        absent_row.addStretch(1)
        layout.addLayout(absent_row)
        self._update_absent_btn_state()

        self.result_label = QLabel("Lancez une recherche pour voir les résultats.")
        self.result_label.setStyleSheet("font-size: 13px; color: #555; padding: 2px 2px;")
        layout.addWidget(self.result_label)

        self.table = QTableWidget()
        self._setup_table()
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        layout.addWidget(self.table)

    def _build_chip_rows(self, chips_to_show):
        while self._chip_layout.count() > 1:
            item = self._chip_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child_item = item.layout().takeAt(0)
                    w = child_item.widget()
                    if w:
                        w.hide()

        cols = 3
        row_hl = None
        for idx, (_, btn) in enumerate(chips_to_show):
            if idx % cols == 0:
                row_hl = QHBoxLayout()
                row_hl.setSpacing(5)
                self._chip_layout.insertLayout(self._chip_layout.count() - 1, row_hl)
            row_hl.addWidget(btn)
            btn.setVisible(True)

        if chips_to_show and row_hl is not None:
            remainder = len(chips_to_show) % cols
            if remainder:
                for _ in range(cols - remainder):
                    row_hl.addStretch(1)

    def _filter_mol_chips(self, text):
        text = text.lower()
        visible = [(mid, btn) for mid, btn in self._mol_chips if text in btn.text().lower()]
        for _, btn in self._mol_chips:
            btn.hide()
        self._build_chip_rows(visible)

    def _on_chip_toggled(self):
        self._update_mol_count_label()
        self._update_absent_btn_state()

    def _update_absent_btn_state(self):
        """Active le bouton 'absents' uniquement si molécule(s) sélectionnée(s) et ANMV syncé."""
        mol_selected = bool(self._get_selected_molecule_ids())
        anmv_ready = bool(get_last_scrape_date())
        self.btn_absent.setEnabled(mol_selected and anmv_ready)
        if not anmv_ready:
            self.lbl_absent_sync.setText("⚠ Sync ANMV nécessaire (bouton dans le header)")
        elif not mol_selected:
            self.lbl_absent_sync.setText("Sélectionnez une molécule")
        else:
            self.lbl_absent_sync.setText(f"Données ANMV du {get_last_scrape_date()}")

    def _update_mol_count_label(self):
        n = len(self._get_selected_molecule_ids())
        self.lbl_mol_count.setText(f"{n} sélectionnée(s)" if n else "")

    def _get_selected_molecule_ids(self):
        return [mid for mid, btn in self._mol_chips if btn.isChecked()]

    def _load_initial_data(self):
        molecules = get_all_molecules()
        for _, btn in self._mol_chips:
            btn.deleteLater()
        self._mol_chips = []

        for mol in molecules:
            btn = QPushButton(mol["nom_dci"].capitalize())
            btn.setCheckable(True)
            btn.setStyleSheet(_CHIP_STYLE)
            btn.toggled.connect(self._on_chip_toggled)
            self._mol_chips.append((mol["id"], btn))

        self._build_chip_rows(self._mol_chips)
        self._update_mol_count_label()

        imports = get_all_imports()
        self.import_combo.clear()
        for imp in imports:
            label = f"{imp['date_import']}  ({imp['nb_produits']} produits)"
            self.import_combo.addItem(label, imp["id"])

    def _setup_table(self, extra_col_label=None):
        headers = [
            "Nom du produit", "Fabricant", "Composition", "Forme",
            "Volume (ml)", "Comprimés",
            "Prix HT (€)", "TVA (%)", "Prix TTC (€)",
            "Prix / ml (€)",
        ]
        if extra_col_label:
            headers.append(extra_col_label)
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(headers)):
            self.table.horizontalHeader().setSectionResizeMode(
                i, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)

    def _get_volume_filter(self):
        txt = self.vol_input.text().strip().replace(",", ".")
        if not txt:
            return None, None, False, None
        if "-" in txt:
            parts = txt.split("-", 1)
            try:
                vmin = float(parts[0].strip())
                vmax = float(parts[1].strip())
                if vmin > 0 and vmax >= vmin:
                    return vmin, vmax, False, None
            except ValueError:
                pass
            return None, None, False, None
        try:
            v = float(txt)
            if v > 0:
                return v - 0.5, v + 0.5, True, v
        except ValueError:
            pass
        return None, None, False, None

    def _do_search(self):
        mol_ids = self._get_selected_molecule_ids()
        keyword = self.kw_input.text().strip()
        import_id = self.import_combo.currentData()
        mono_only = self.chk_mono.isChecked()

        if mol_ids:
            self._last_results = search_by_molecules(mol_ids, import_id, mono_only=mono_only)
        elif keyword:
            self._last_results = search_by_keyword(keyword, import_id)
        else:
            self.result_label.setText("Cochez une molécule ou entrez un mot-clé.")
            return

        self._apply_local_filters()

    def _apply_local_filters(self):
        """Applique les filtres locaux (Pur, volume) sur _last_results sans requête DB."""
        if self._last_results is None:
            return
        results = list(self._last_results)
        if self.chk_pur.isChecked():
            results = [r for r in results if (r.get("nb_molecules") or 1) <= 1]
        vol_min, vol_max, is_exact, exact_vol = self._get_volume_filter()
        self._populate_table(results, vol_min, vol_max, is_exact, exact_vol)

    def _populate_table(self, results, vol_min=None, vol_max=None,
                        is_exact=False, exact_vol=None):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        if not results:
            self.result_label.setText("Aucun résultat trouvé.")
            self._setup_table()
            return

        if vol_min is not None:
            filtered = [r for r in results
                        if r["volume_ml"] is not None
                        and vol_min <= r["volume_ml"] <= vol_max]
        else:
            filtered = results

        has_vol_col = is_exact and exact_vol is not None
        extra_col = f"Prix pour {exact_vol:.0f} ml (€)" if has_vol_col else None
        self._setup_table(extra_col_label=extra_col)

        nb_liq = sum(1 for r in filtered if r["type_forme"] == "liquide")
        resume = f"{len(filtered)} produit(s)"
        if vol_min is not None:
            if is_exact:
                resume += f" à {exact_vol:.0f} ml"
            else:
                resume += f" entre {vol_min:.0f} et {vol_max:.0f} ml"
            if len(results) != len(filtered):
                resume += f" (sur {len(results)} au total)"
        if nb_liq:
            resume += "  —  triés par prix/ml"
        self.result_label.setText(resume)

        if not filtered:
            return

        prix_ml_min = min(
            (r["prix_par_unite"] for r in filtered if r["prix_par_unite"] is not None),
            default=None
        )
        prix_vol_min = None
        if has_vol_col:
            vals = [round(r["prix_par_unite"] * exact_vol, 4)
                    for r in filtered if r["prix_par_unite"] is not None]
            if vals:
                prix_vol_min = min(vals)

        self.table.setRowCount(len(filtered))

        for row_idx, r in enumerate(filtered):

            def cell(val, align=Qt.AlignmentFlag.AlignLeft):
                item = QTableWidgetItem(str(val) if val is not None else "—")
                item.setForeground(QColor("#1a1a2e"))
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return item

            def num_cell(val, decimals=3, suffix=""):
                if val is None:
                    item = QTableWidgetItem("—")
                    item.setForeground(QColor("#aaa"))
                else:
                    item = QTableWidgetItem(f"{val:.{decimals}f}{suffix}")
                    item.setData(Qt.ItemDataRole.UserRole, val)
                    item.setForeground(QColor("#1a1a2e"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                return item

            self.table.setItem(row_idx, 0, cell(r["nom"]))
            self.table.setItem(row_idx, 1, cell(r["fabricant"]))

            nb_mol = r.get("nb_molecules", 1) or 1
            molecules_dci = r.get("molecules_dci") or ""
            if nb_mol > 1:
                comp = QTableWidgetItem(f"Combiné ({nb_mol})")
                comp.setForeground(QColor("#8b4f00"))
                comp.setBackground(QColor("#fff3cd"))
                f0 = QFont(); f0.setBold(True); comp.setFont(f0)
                if molecules_dci:
                    comp.setToolTip(f"Composition :\n{molecules_dci.replace(' + ', chr(10))}")
                comp.setData(Qt.ItemDataRole.UserRole, molecules_dci)
            else:
                comp = QTableWidgetItem("Pur")
                comp.setForeground(QColor("#1e6e3a"))
                if molecules_dci:
                    comp.setToolTip(molecules_dci)
            comp.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 2, comp)

            forme = cell(r["type_forme"])
            if r["type_forme"] == "liquide":
                forme.setForeground(QColor("#1e6e3a"))
            elif r["type_forme"] == "comprimes":
                forme.setForeground(QColor("#6e3a1e"))
            self.table.setItem(row_idx, 3, forme)

            self.table.setItem(row_idx, 4, num_cell(r["volume_ml"], 1))
            self.table.setItem(row_idx, 5, num_cell(r["nb_comprimes"], 0))
            self.table.setItem(row_idx, 6, num_cell(r["prix_ht"], 2, " €"))
            self.table.setItem(row_idx, 7, num_cell(r["tva"], 0, " %"))
            self.table.setItem(row_idx, 8, num_cell(r["prix_ttc"], 2, " €"))

            pu = r["prix_par_unite"]
            col_ml = num_cell(pu, 4, " €")
            if pu is not None and prix_ml_min is not None and abs(pu - prix_ml_min) < 1e-6:
                col_ml.setBackground(QColor("#c8f0d0"))
                col_ml.setForeground(QColor("#0a5c2a"))
                f1 = QFont(); f1.setBold(True); col_ml.setFont(f1)
                col_ml.setText(f"{pu:.4f} €  ★")
            self.table.setItem(row_idx, 9, col_ml)

            if has_vol_col:
                if pu is not None:
                    pv = round(pu * exact_vol, 2)
                    col_v = num_cell(pv, 2, " €")
                    if prix_vol_min is not None and abs(pv - prix_vol_min) < 0.005:
                        col_v.setBackground(QColor("#c8f0d0"))
                        col_v.setForeground(QColor("#0a5c2a"))
                        f2 = QFont(); f2.setBold(True); col_v.setFont(f2)
                        col_v.setText(f"{pv:.2f} €  ★")
                else:
                    col_v = num_cell(None)
                self.table.setItem(row_idx, 10, col_v)

        self.table.setSortingEnabled(True)

    def _on_table_cell_clicked(self, row, col):
        """Affiche la composition exacte quand on clique sur la colonne Composition."""
        if col != 2:
            return
        item = self.table.item(row, col)
        if item is None:
            return
        molecules_dci = item.data(Qt.ItemDataRole.UserRole)
        if not molecules_dci:
            return
        nom_produit = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
        dlg = QDialog(self)
        dlg.setWindowTitle("Composition")
        dlg.setFixedWidth(360)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 16, 20, 14)
        lay.setSpacing(10)
        if nom_produit:
            lbl_nom = QLabel(f"<b>{nom_produit}</b>")
            lbl_nom.setWordWrap(True)
            lay.addWidget(lbl_nom)
        for dci in molecules_dci.split(" + "):
            lbl = QLabel(f"\u2022 {dci.strip()}")
            lbl.setStyleSheet("font-size: 13px; padding: 2px 0;")
            lay.addWidget(lbl)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(dlg.accept)
        lay.addWidget(btns)
        dlg.exec()

    def _show_absent_dialog(self):
        """
        Affiche tous les produits ANMV pour les molécules sélectionnées,
        avec un toggle pour afficher/masquer ceux déjà présents en centrale.
        """
        mol_ids = self._get_selected_molecule_ids()
        if not mol_ids:
            return

        from app.data.search import get_all_molecules
        all_mols = {m['id']: m['nom_dci'] for m in get_all_molecules()}
        selected_dcis = [all_mols[mid] for mid in mol_ids if mid in all_mols]

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        all_products = []
        for dci in selected_dcis:
            prods = get_all_anmv_for_dci(dci)
            for p in prods:
                p['dci_recherchee'] = dci
            all_products.extend(prods)
        QApplication.restoreOverrideCursor()

        nb_absent = sum(1 for p in all_products if not p['en_centrale'])
        nb_present = sum(1 for p in all_products if p['en_centrale'])

        dlg = QDialog(self)
        dlg.setWindowTitle("Médicaments — ANMV vs Centravet")
        dlg.setMinimumSize(900, 520)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(16, 14, 16, 14)
        dlg_layout.setSpacing(10)

        # En-tête
        lbl_header = QLabel()
        lbl_header.setTextFormat(Qt.TextFormat.RichText)
        dlg_layout.addWidget(lbl_header)

        # Checkbox toggle
        chk_show_present = QCheckBox(f"Afficher aussi les {nb_present} médicament(s) déjà référencé(s) en centrale")
        chk_show_present.setChecked(False)
        chk_show_present.setStyleSheet("font-size: 12px; padding: 2px 0;")
        dlg_layout.addWidget(chk_show_present)

        # Tableau
        tbl = QTableWidget()
        tbl.setColumnCount(6)
        tbl.setHorizontalHeaderLabels(["Statut", "Nom commercial", "Laboratoire", "DCI", "Espèces", "Fiche ANMV"])
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in [0, 2, 3, 4, 5]:
            tbl.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        tbl.setAlternatingRowColors(True)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        dlg_layout.addWidget(tbl)

        def _populate(show_present):
            filtered = all_products if show_present else [p for p in all_products if not p['en_centrale']]
            tbl.setSortingEnabled(False)
            tbl.setRowCount(len(filtered))
            for i, p in enumerate(filtered):
                en_centrale = p['en_centrale']
                status = QTableWidgetItem("✅ En centrale" if en_centrale else "❌ Absent")
                status.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                if en_centrale:
                    status.setForeground(QColor('#1e6e3a'))
                    status.setBackground(QColor('#eaf7ee'))
                else:
                    status.setForeground(QColor('#8b0000'))
                    status.setBackground(QColor('#fff0f0'))
                tbl.setItem(i, 0, status)

                def _cell(v, absent=not en_centrale):
                    item = QTableWidgetItem(v or '')
                    item.setForeground(QColor('#1a1a2e') if absent else QColor('#666666'))
                    return item

                tbl.setItem(i, 1, _cell(p['nom']))
                tbl.setItem(i, 2, _cell(p['laboratoire']))
                tbl.setItem(i, 3, _cell(p['dci']))
                tbl.setItem(i, 4, _cell(p['especes']))
                url_item = QTableWidgetItem(p['url_rcp'] or '')
                url_item.setForeground(QColor('#1e3a6e'))
                tbl.setItem(i, 5, url_item)

            tbl.setSortingEnabled(True)
            nb_shown = len(filtered)
            lbl_header.setText(
                f"<b>{nb_absent} absent(s)</b> de la centrale · "
                f"<span style='color:#1e6e3a'>{nb_present} déjà référencé(s)</span> · "
                f"{nb_shown} affiché(s)<br>"
                f"<span style='font-size:11px; color:#888;'>Source : ANMV/IRCP — données du {get_last_scrape_date()}</span>"
            )

        _populate(False)
        chk_show_present.toggled.connect(_populate)

        btn_close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_close.rejected.connect(dlg.reject)
        dlg_layout.addWidget(btn_close)
        dlg.exec()

    def refresh(self):
        self._load_initial_data()
        self._update_absent_btn_state()

    def _reset_molecules(self):
        """Décoche tous les chips molécules et vide le filtre."""
        self.mol_filter.clear()
        for _, btn in self._mol_chips:
            btn.setChecked(False)
        self._build_chip_rows(self._mol_chips)
        self._update_mol_count_label()
        self._update_absent_btn_state()

    def _reset_all(self):
        """Remet tous les filtres à zéro et vide le tableau."""
        self._reset_molecules()
        self.kw_input.clear()
        self.vol_input.clear()
        self.chk_mono.setChecked(False)
        self.chk_pur.setChecked(False)
        self._last_results = None
        self.table.setRowCount(0)
        self._setup_table()
        self.result_label.setText("Lancez une recherche pour voir les résultats.")
