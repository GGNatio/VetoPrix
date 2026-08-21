"""
Onglet Statistiques : courbes d'évolution des prix dans le temps.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
import matplotlib.dates as mdates
from datetime import datetime

from app.data.search import (
    get_all_molecules, get_price_history,
    get_global_price_trend, get_all_imports
)
from app.database.db import get_connection


def _fmt_euro(val, decimals=2):
    if val is None:
        return "—"
    return f"{val:.{decimals}f} €"


def _fmt_date(dt):
    return dt.strftime("%d/%m/%Y")


def _to_xnum(x):
    if hasattr(x, "toordinal"):
        return mdates.date2num(x)
    return float(x)


class _HoverTooltip:
    """
    Tooltip au survol via QToolTip (pas de redraw matplotlib → pas de flicker).
    Les positions pixels des points sont mises en cache après chaque draw.
    """

    _MAX_DIST_PX = 28

    def __init__(self, canvas, figure, on_tip=None):
        self.canvas = canvas
        self.figure = figure
        self._on_tip = on_tip  # callback(str|None)
        self._targets = []       # (line, ax, tip_builder)
        self._points = []        # (px, py, tip_text) en coords display
        self._cid_move = None
        self._cid_draw = None
        self._last_tip = None

    def clear(self):
        from PyQt6.QtWidgets import QToolTip
        QToolTip.hideText()
        if self._cid_move is not None:
            self.canvas.mpl_disconnect(self._cid_move)
            self._cid_move = None
        if self._cid_draw is not None:
            self.canvas.mpl_disconnect(self._cid_draw)
            self._cid_draw = None
        self._targets = []
        self._points = []
        self._last_tip = None
        if self._on_tip:
            self._on_tip(None)

    def register(self, line, ax, tip_builder):
        """tip_builder(idx, x, y) -> str"""
        self._targets.append((line, ax, tip_builder))

    def enable(self):
        if not self._targets:
            return
        self._cid_draw = self.canvas.mpl_connect("draw_event", self._on_draw)
        self._cid_move = self.canvas.mpl_connect("motion_notify_event", self._on_move)
        self._rebuild_cache()

    def _on_draw(self, _event):
        self._rebuild_cache()

    def _rebuild_cache(self):
        points = []
        for line, ax, tip_builder in self._targets:
            if ax.figure is None:
                continue
            xdata, ydata = line.get_data()
            for idx in range(len(xdata)):
                yd = ydata[idx]
                if yd is None:
                    continue
                try:
                    xd = _to_xnum(xdata[idx])
                    yd_f = float(yd)
                except (TypeError, ValueError):
                    continue
                disp = ax.transData.transform((xd, yd_f))
                tip = tip_builder(idx, xdata[idx], yd_f)
                points.append((float(disp[0]), float(disp[1]), tip))
        self._points = points

    def _on_move(self, event):
        from PyQt6.QtWidgets import QToolTip
        from PyQt6.QtGui import QCursor

        if event.inaxes is None or event.x is None or event.y is None or not self._points:
            if self._last_tip is not None:
                QToolTip.hideText()
                self._last_tip = None
                if self._on_tip:
                    self._on_tip(None)
            return

        ex, ey = float(event.x), float(event.y)
        best_tip = None
        best_d2 = self._MAX_DIST_PX ** 2
        for px, py, tip in self._points:
            d2 = (px - ex) ** 2 + (py - ey) ** 2
            if d2 <= best_d2:
                best_d2 = d2
                best_tip = tip

        if best_tip is None:
            if self._last_tip is not None:
                QToolTip.hideText()
                self._last_tip = None
                if self._on_tip:
                    self._on_tip(None)
            return

        if best_tip == self._last_tip:
            return

        self._last_tip = best_tip
        QToolTip.showText(QCursor.pos(), best_tip, self.canvas)
        if self._on_tip:
            self._on_tip(best_tip)


class StatsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._hover = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 4, 0, 0)

        # --- Card de contrôles ---
        ctrl_card = QFrame()
        ctrl_card.setObjectName("stats_card")
        ctrl_card.setStyleSheet("""
            QFrame#stats_card {
                background: #ffffff;
                border: 1px solid #d0d8e8;
                border-radius: 10px;
            }
        """)
        ctrl_outer = QVBoxLayout(ctrl_card)
        ctrl_outer.setContentsMargins(16, 14, 16, 14)
        ctrl_outer.setSpacing(10)

        title_lbl = QLabel("Paramètres du graphique")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e3a6e;")
        ctrl_outer.addWidget(title_lbl)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(12)

        # Vue
        vue_block = QVBoxLayout()
        vue_block.setSpacing(4)
        lbl_vue = QLabel("Vue")
        lbl_vue.setStyleSheet("font-size: 12px; color: #555; font-weight: 600;")
        self.view_combo = QComboBox()
        self.view_combo.addItem("Évolution globale des prix", "global")
        self.view_combo.addItem("Par molécule", "molecule")
        self.view_combo.addItem("Par produit spécifique", "product")
        self.view_combo.currentIndexChanged.connect(self._on_view_changed)
        self.view_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        vue_block.addWidget(lbl_vue)
        vue_block.addWidget(self.view_combo)
        ctrl_layout.addLayout(vue_block, 2)

        # Molécule
        mol_block = QVBoxLayout()
        mol_block.setSpacing(4)
        lbl_mol = QLabel("Molécule")
        lbl_mol.setStyleSheet("font-size: 12px; color: #555; font-weight: 600;")
        self.mol_combo = QComboBox()
        self.mol_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.mol_combo.currentIndexChanged.connect(self._on_mol_changed)
        self.mol_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        mol_block.addWidget(lbl_mol)
        mol_block.addWidget(self.mol_combo)
        ctrl_layout.addLayout(mol_block, 2)

        # Produit
        prod_block = QVBoxLayout()
        prod_block.setSpacing(4)
        lbl_prod = QLabel("Produit spécifique")
        lbl_prod.setStyleSheet("font-size: 12px; color: #555; font-weight: 600;")
        self.prod_combo = QComboBox()
        self.prod_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.prod_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        prod_block.addWidget(lbl_prod)
        prod_block.addWidget(self.prod_combo)
        ctrl_layout.addLayout(prod_block, 3)

        # Bouton
        btn_block = QVBoxLayout()
        btn_block.setSpacing(4)
        btn_block.addWidget(QLabel(""))  # alignement vertical
        btn_plot = QPushButton("Afficher le graphique")
        btn_plot.setObjectName("btn_primary")
        btn_plot.setMinimumWidth(160)
        btn_plot.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_plot.clicked.connect(self._do_plot)
        btn_block.addWidget(btn_plot)
        ctrl_layout.addLayout(btn_block)

        ctrl_outer.addLayout(ctrl_layout)
        layout.addWidget(ctrl_card)

        self.hint_label = QLabel("Survolez un point pour afficher la date et le prix.")
        self.hint_label.setStyleSheet("font-size: 12px; color: #6a7a94; font-style: italic; padding: 0 4px;")
        self._hint_default = "Survolez un point pour afficher la date et le prix."
        layout.addWidget(self.hint_label)

        # --- Canvas matplotlib ---
        canvas_frame = QFrame()
        canvas_frame.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #d0d8e8;
                border-radius: 10px;
            }
        """)
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(8, 8, 8, 8)
        self.figure = Figure(tight_layout={"pad": 1.6})
        self.figure.patch.set_facecolor("#ffffff")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setStyleSheet("""
            QToolTip {
                background-color: #1e3a6e;
                color: #ffffff;
                border: 1px solid #152a52;
                padding: 6px 8px;
                font-size: 12px;
            }
        """)
        canvas_layout.addWidget(self.canvas)
        layout.addWidget(canvas_frame)

        self._hover = _HoverTooltip(self.canvas, self.figure, on_tip=self._on_hover_tip)
        self._load_molecules()
        self._on_view_changed()

    def _on_hover_tip(self, tip):
        if tip:
            self.hint_label.setText(tip.replace("\n", "  ·  "))
            self.hint_label.setStyleSheet(
                "font-size: 12px; color: #1e3a6e; font-weight: 600; padding: 0 4px;"
            )
        else:
            self.hint_label.setText(self._hint_default)
            self.hint_label.setStyleSheet(
                "font-size: 12px; color: #6a7a94; font-style: italic; padding: 0 4px;"
            )

    def _set_hint_default(self, text):
        self._hint_default = text
        self.hint_label.setText(text)
        self.hint_label.setStyleSheet(
            "font-size: 12px; color: #6a7a94; font-style: italic; padding: 0 4px;"
        )

    def _load_molecules(self):
        self.mol_combo.clear()
        for m in get_all_molecules():
            self.mol_combo.addItem(m["nom_dci"].capitalize(), m["id"])

    def _on_view_changed(self):
        view = self.view_combo.currentData()
        self.mol_combo.setEnabled(view in ("molecule", "product"))
        self.prod_combo.setEnabled(view == "product")
        if view == "product":
            self._on_mol_changed()

    def _on_mol_changed(self):
        if self.view_combo.currentData() != "product":
            return
        mol_id = self.mol_combo.currentData()
        if mol_id is None:
            return
        conn = get_connection()
        rows = conn.execute("""
            SELECT p.code, p.nom FROM produits p
            JOIN molecule_produits mp ON mp.produit_id = p.id
            WHERE mp.molecule_id = ?
            ORDER BY p.nom
        """, (mol_id,)).fetchall()
        conn.close()
        self.prod_combo.clear()
        for r in rows:
            self.prod_combo.addItem(r["nom"], r["code"])

    def _style_ax(self, ax, title, ylabel):
        ax.set_facecolor("#f4f7fd")
        ax.set_title(title, fontsize=14, fontweight="bold", color="#1e3a6e", pad=14)
        ax.set_ylabel(ylabel, fontsize=12, color="#334155", fontweight="600")
        ax.set_xlabel("Date du tarif", fontsize=11, color="#64748b")
        ax.tick_params(colors="#475569", labelsize=10)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cbd5e1")
        ax.spines["bottom"].set_color("#cbd5e1")
        ax.grid(True, color="#dbe4f3", linewidth=0.9, linestyle="--", alpha=0.9)
        ax.set_axisbelow(True)

    def _format_date_axis(self, ax, dates):
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        if len(dates) <= 4:
            ax.set_xticks(dates)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y"))
        else:
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=8))
        for label in ax.get_xticklabels():
            label.set_rotation(25)
            label.set_ha("right")

    def _autofit_y(self, ax, values, min_pad_ratio=0.15):
        """Élargit l'échelle Y pour rendre visibles les petites variations."""
        vals = [v for v in values if v is not None]
        if not vals:
            return
        ymin, ymax = min(vals), max(vals)
        span = ymax - ymin
        if span < 1e-12:
            pad = max(abs(ymax) * 0.05, 0.01)
        else:
            pad = max(span * min_pad_ratio, abs(ymax) * 0.01, 0.005)
        ax.set_ylim(ymin - pad, ymax + pad)

    def _msg_no_data(self, ax, msg="Importez au moins 2 fichiers CSV\npour voir les tendances."):
        ax.set_facecolor("#f4f7fd")
        ax.text(
            0.5, 0.5, msg, ha="center", va="center",
            transform=ax.transAxes, fontsize=14, color="#888", style="italic",
        )
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])

    def _short_label(self, nom, max_len=42):
        nom = nom.strip()
        return nom if len(nom) <= max_len else nom[: max_len - 1] + "…"

    def _do_plot(self):
        view = self.view_combo.currentData()
        self._hover.clear()
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if view == "global":
            self._plot_global(ax)
        elif view == "molecule":
            self._plot_molecule(ax)
        elif view == "product":
            self._plot_product(ax)

        self._hover.enable()
        self.canvas.draw()

    def _plot_global(self, ax):
        data = get_global_price_trend()
        if len(data) < 2:
            self._msg_no_data(ax)
            return

        dates = [datetime.strptime(d["date_import"], "%Y-%m-%d") for d in data]
        prix = [d["prix_moyen_par_ml"] for d in data]
        counts = [d["nb_produits"] for d in data]

        line, = ax.plot(
            dates, prix,
            marker="o", color="#1e3a6e", linewidth=2.8, markersize=10,
            markerfacecolor="#ffffff", markeredgewidth=2.5, markeredgecolor="#1e3a6e",
            zorder=5,
        )
        ax.fill_between(dates, prix, alpha=0.12, color="#1e3a6e")

        # Étiquettes permanentes quand peu de points
        for i, (dt, val) in enumerate(zip(dates, prix)):
            ax.annotate(
                _fmt_euro(val, 4),
                (mdates.date2num(dt), val),
                textcoords="offset points",
                xytext=(0, 12),
                ha="center",
                fontsize=9,
                color="#1e3a6e",
                fontweight="bold",
            )

        self._style_ax(ax, "Évolution globale — Prix moyen / ml (liquides)", "Prix moyen (€ / ml)")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.3f}"))
        self._format_date_axis(ax, dates)
        self._autofit_y(ax, prix, min_pad_ratio=0.35)

        # Delta global
        if len(prix) >= 2 and prix[0]:
            delta = prix[-1] - prix[0]
            pct = delta / prix[0] * 100
            ax.text(
                0.98, 0.02,
                f"Δ {delta:+.4f} €/ml ({pct:+.2f}%)",
                transform=ax.transAxes, ha="right", va="bottom",
                fontsize=10, color="#0f766e" if delta <= 0 else "#b45309",
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.35", fc="#ffffff", ec="#d0d8e8"),
            )

        self._set_hint_default(
            "Survolez un point pour la date, le prix moyen / ml et le nombre de produits."
        )

        def tip(idx, x, y):
            return (
                f"{_fmt_date(dates[idx])}\n"
                f"Moyenne : {_fmt_euro(y, 4)} / ml\n"
                f"{counts[idx]} produits liquides"
            )

        self._hover.register(line, ax, tip)

    def _plot_molecule(self, ax):
        mol_id = self.mol_combo.currentData()
        mol_name = self.mol_combo.currentText()
        if mol_id is None:
            return

        imports = get_all_imports()
        if len(imports) < 2:
            self._msg_no_data(ax)
            return

        conn = get_connection()
        produits = conn.execute("""
            SELECT p.code, p.nom, p.type_forme FROM produits p
            JOIN molecule_produits mp ON mp.produit_id = p.id
            WHERE mp.molecule_id = ? AND p.type_forme = 'liquide'
            ORDER BY p.nom
        """, (mol_id,)).fetchall()
        conn.close()

        # Collecter historiques et prioriser ceux qui changent vraiment
        series = []
        for prod in produits:
            hist = get_price_history(prod["code"])
            vals = [h["prix_par_unite"] for h in hist if h["prix_par_unite"] is not None]
            if len(vals) < 1:
                continue
            spread = (max(vals) - min(vals)) if vals else 0
            series.append((spread, prod, hist))

        series.sort(key=lambda t: t[0], reverse=True)
        # Limiter pour lisibilité : d'abord ceux qui bougent, sinon les premiers
        changed = [s for s in series if s[0] > 1e-9]
        stable = [s for s in series if s[0] <= 1e-9]
        selected = (changed + stable)[:12]

        if not selected:
            self._msg_no_data(ax, "Aucun produit liquide pour cette molécule.")
            return

        colors = [
            "#e74c3c", "#2563eb", "#059669", "#d97706", "#7c3aed",
            "#0891b2", "#ea580c", "#334155", "#db2777", "#0d9488",
            "#4f46e5", "#65a30d",
        ]

        for idx, (_, prod, hist) in enumerate(selected):
            dates = [datetime.strptime(h["date_import"], "%Y-%m-%d") for h in hist]
            prix = [h["prix_par_unite"] for h in hist]
            # Filtrer None
            pairs = [(d, p) for d, p in zip(dates, prix) if p is not None]
            if not pairs:
                continue
            dates, prix = zip(*pairs)
            dates, prix = list(dates), list(prix)
            color = colors[idx % len(colors)]
            label = self._short_label(prod["nom"])
            line, = ax.plot(
                dates, prix,
                marker="o", label=label, color=color,
                linewidth=2.2, markersize=8,
                markerfacecolor="#ffffff", markeredgewidth=2, markeredgecolor=color,
                zorder=5,
            )

            # Snapshot pour closure
            _dates = dates
            _prix = prix
            _name = prod["nom"]
            _ht = [h["prix_ht"] for h in hist if h["prix_par_unite"] is not None]

            def make_tip(name, dts, ht_list):
                def tip(i, x, y):
                    ht = ht_list[i] if i < len(ht_list) else None
                    lines = [
                        self._short_label(name, 48),
                        _fmt_date(dts[i]),
                        f"Prix / ml : {_fmt_euro(y, 4)}",
                    ]
                    if ht is not None:
                        lines.append(f"Prix HT : {_fmt_euro(ht)}")
                    return "\n".join(lines)
                return tip

            self._hover.register(line, ax, make_tip(_name, _dates, _ht))

        self._style_ax(ax, f"Évolution du prix / ml — {mol_name}", "Prix (€ / ml)")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.3f}"))
        all_dates = []
        all_prix = []
        for _, _, hist in selected:
            all_dates.extend(
                datetime.strptime(h["date_import"], "%Y-%m-%d") for h in hist
            )
            all_prix.extend(
                h["prix_par_unite"] for h in hist if h["prix_par_unite"] is not None
            )
        self._format_date_axis(ax, sorted(set(all_dates)))
        self._autofit_y(ax, all_prix)

        legend = ax.legend(
            fontsize=8, loc="best", framealpha=0.95,
            edgecolor="#d0d8e8", fancybox=True, title="Produits",
            title_fontsize=9,
        )
        if legend:
            legend.get_frame().set_linewidth(0.8)

        extra = ""
        if len(series) > len(selected):
            extra = f" ({len(selected)}/{len(series)} produits affichés — ceux avec le plus fort écart priorisés)"
        self._set_hint_default(
            f"Survolez un point pour voir le produit, la date et le prix / ml.{extra}"
        )

    def _plot_product(self, ax):
        code = self.prod_combo.currentData()
        nom = self.prod_combo.currentText()
        if not code:
            return
        hist = get_price_history(code)
        if not hist:
            self._msg_no_data(ax, "Aucun historique disponible pour ce produit.")
            return

        dates = [datetime.strptime(h["date_import"], "%Y-%m-%d") for h in hist]
        prix_ht = [h["prix_ht"] for h in hist]
        prix_ttc = [h["prix_ttc"] for h in hist]
        prix_ml = [h["prix_par_unite"] for h in hist]

        line_ht, = ax.plot(
            dates, prix_ht, marker="o", label="Prix HT",
            color="#1e3a6e", linewidth=2.8, markersize=10,
            markerfacecolor="#ffffff", markeredgewidth=2.5, markeredgecolor="#1e3a6e",
            zorder=5,
        )
        line_ttc, = ax.plot(
            dates, prix_ttc, marker="s", label="Prix TTC",
            color="#c0392b", linewidth=2.2, markersize=8, linestyle="--",
            markerfacecolor="#ffffff", markeredgewidth=2, markeredgecolor="#c0392b",
            zorder=5,
        )

        # Étiquettes HT sur les points
        for dt, val in zip(dates, prix_ht):
            ax.annotate(
                _fmt_euro(val),
                (mdates.date2num(dt), val),
                textcoords="offset points",
                xytext=(0, 11),
                ha="center",
                fontsize=9,
                color="#1e3a6e",
                fontweight="bold",
            )

        self._style_ax(ax, self._short_label(nom, 70), "Prix (€)")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.2f}"))
        self._format_date_axis(ax, dates)
        self._autofit_y(ax, list(prix_ht) + list(prix_ttc), min_pad_ratio=0.25)

        # Variation HT
        if len(prix_ht) >= 2 and prix_ht[0]:
            delta = prix_ht[-1] - prix_ht[0]
            pct = delta / prix_ht[0] * 100
            color = "#b45309" if delta > 0 else ("#0f766e" if delta < 0 else "#64748b")
            ax.text(
                0.98, 0.02,
                f"Δ HT {delta:+.2f} € ({pct:+.1f}%)",
                transform=ax.transAxes, ha="right", va="bottom",
                fontsize=11, color=color, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.35", fc="#ffffff", ec="#d0d8e8"),
            )

        lines = [line_ht, line_ttc]
        labels = ["Prix HT", "Prix TTC"]

        ax2 = None
        if any(p is not None for p in prix_ml):
            ax2 = ax.twinx()
            ax._twin_partner = ax2
            ax2._twin_partner = ax
            ml_dates = [d for d, p in zip(dates, prix_ml) if p is not None]
            ml_vals = [p for p in prix_ml if p is not None]
            line_ml, = ax2.plot(
                ml_dates, ml_vals, marker="^", label="Prix / ml",
                color="#059669", linewidth=2, linestyle=":", markersize=9,
                markerfacecolor="#ffffff", markeredgewidth=2, markeredgecolor="#059669",
                zorder=5,
            )
            ax2.set_ylabel("Prix / ml (€)", fontsize=12, color="#059669", fontweight="600")
            ax2.tick_params(colors="#059669")
            ax2.spines["right"].set_color("#059669")
            ax2.spines["top"].set_visible(False)
            ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.4f}"))
            lines.append(line_ml)
            labels.append("Prix / ml")

            def tip_ml(idx, x, y):
                return f"{_fmt_date(ml_dates[idx])}\nPrix / ml : {_fmt_euro(y, 4)}"

            self._hover.register(line_ml, ax2, tip_ml)

        ax.legend(lines, labels, loc="upper left", fontsize=10, framealpha=0.95, edgecolor="#d0d8e8")

        def tip_ht(idx, x, y):
            return f"{_fmt_date(dates[idx])}\nPrix HT : {_fmt_euro(y)}"

        def tip_ttc(idx, x, y):
            return f"{_fmt_date(dates[idx])}\nPrix TTC : {_fmt_euro(y)}"

        self._hover.register(line_ht, ax, tip_ht)
        self._hover.register(line_ttc, ax, tip_ttc)

        self._set_hint_default(
            "Survolez un point pour la date et le prix (HT, TTC ou / ml)."
        )

    def refresh(self):
        self._load_molecules()
