from datetime import date
from PySide6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QDateEdit, QLabel
from PySide6.QtCore import Signal, QDate
from app.utils.date_utils import DateRangePreset, get_date_range_for_preset

class DateRangePicker(QWidget):
    """
    Reusable Date Range selector component with presets and custom date edits.
    Emits date_range_changed(start_date, end_date) signal.
    """
    date_range_changed = Signal(date, date)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.preset_combo = QComboBox()
        for preset in DateRangePreset:
            self.preset_combo.addItem(preset.value, preset)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd/MM/yyyy")

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("dd/MM/yyyy")

        to_label = QLabel("to")

        layout.addWidget(QLabel("Period:"))
        layout.addWidget(self.preset_combo)
        layout.addWidget(self.start_date_edit)
        layout.addWidget(to_label)
        layout.addWidget(self.end_date_edit)

        # Set initial preset to Today
        today = date.today()
        self.start_date_edit.setDate(QDate(today.year, today.month, today.day))
        self.end_date_edit.setDate(QDate(today.year, today.month, today.day))

        # Connect signals
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self.start_date_edit.dateChanged.connect(self._on_custom_date_changed)
        self.end_date_edit.dateChanged.connect(self._on_custom_date_changed)

        self._updating = False
        self._on_preset_changed()

    def _on_preset_changed(self):
        preset = self.preset_combo.currentData()
        if not preset:
            return

        self._updating = True
        if preset != DateRangePreset.CUSTOM:
            start_d, end_d = get_date_range_for_preset(preset)
            self.start_date_edit.setDate(QDate(start_d.year, start_d.month, start_d.day))
            self.end_date_edit.setDate(QDate(end_d.year, end_d.month, end_d.day))
            self.start_date_edit.setEnabled(False)
            self.end_date_edit.setEnabled(False)
        else:
            self.start_date_edit.setEnabled(True)
            self.end_date_edit.setEnabled(True)

        self._updating = False
        self._emit_change()

    def _on_custom_date_changed(self):
        if not self._updating:
            self._emit_change()

    def _emit_change(self):
        q_start = self.start_date_edit.date()
        q_end = self.end_date_edit.date()
        s_date = date(q_start.year(), q_start.month(), q_start.day())
        e_date = date(q_end.year(), q_end.month(), q_end.day())
        self.date_range_changed.emit(s_date, e_date)

    def get_date_range(self) -> tuple[date, date]:
        q_start = self.start_date_edit.date()
        q_end = self.end_date_edit.date()
        return (
            date(q_start.year(), q_start.month(), q_start.day()),
            date(q_end.year(), q_end.month(), q_end.day())
        )
