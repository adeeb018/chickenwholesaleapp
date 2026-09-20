from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

class StatCard(QFrame):
    """
    Dashboard Metric Card displaying title, value, and subtitle/breakdown.
    """
    def __init__(self, title: str, value: str = "-", subtitle: str = "", accent_color: str = "#2563eb", parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.setProperty("class", "cardFrame")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title.upper())
        self.title_label.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {accent_color}; letter-spacing: 0.5px;")

        self.val_label = QLabel(value)
        self.val_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")

        self.sub_label = QLabel(subtitle)
        self.sub_label.setStyleSheet("font-size: 12px; color: #64748b;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.val_label)
        layout.addWidget(self.sub_label)

    def set_data(self, value: str, subtitle: str = ""):
        self.val_label.setText(value)
        self.sub_label.setText(subtitle)
