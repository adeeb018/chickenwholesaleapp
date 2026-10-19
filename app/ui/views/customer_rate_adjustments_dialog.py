from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QComboBox,
    QDoubleSpinBox, QLineEdit, QDateEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QCheckBox, QGroupBox, QButtonGroup, QListWidget, QListWidgetItem,
    QWidget
)
from PySide6.QtCore import Qt, QDate
from app.services.master_service import MasterService
from app.services.setting_service import SettingService
from app.services.customer_rate_adjustment_service import (
    CustomerRateAdjustmentService, DAYS_OF_WEEK_LIST, DAYS_OF_WEEK_FULL
)
from app.ui.components.table_utils import enable_table_copy_and_tooltips, create_table_item
from app.utils.decimal_utils import format_currency

class AddRateAdjustmentDialog(QDialog):
    """
    Dialog for creating a new party/customer differential rate adjustment
    supporting single or multiple customer selection in one go.
    """
    def __init__(self, preselected_customer_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Customer Rate Adjustment (Single or Multiple)")
        self.resize(600, 620)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. Customer Multi-Selection Group
        cust_group = QGroupBox("Select Customers / Parties (Single or Multiple Parties in One Go)*")
        cust_layout = QVBoxLayout(cust_group)
        cust_layout.setSpacing(6)

        # Search bar and quick toggle buttons
        top_select_bar = QHBoxLayout()
        self.cust_search_input = QLineEdit()
        self.cust_search_input.setPlaceholderText("🔍 Search customers...")
        self.cust_search_input.textChanged.connect(self._filter_customer_list)

        self.btn_select_all_cust = QPushButton("☑️ Select All")
        self.btn_select_all_cust.setProperty("class", "secondaryBtn")
        self.btn_select_all_cust.setStyleSheet("padding: 4px 8px; font-size: 11px;")
        self.btn_select_all_cust.clicked.connect(self._select_all_customers)

        self.btn_clear_cust = QPushButton("⏹️ Clear")
        self.btn_clear_cust.setProperty("class", "secondaryBtn")
        self.btn_clear_cust.setStyleSheet("padding: 4px 8px; font-size: 11px;")
        self.btn_clear_cust.clicked.connect(self._clear_all_customers)

        self.cust_count_badge = QLabel("0 selected")
        self.cust_count_badge.setStyleSheet("""
            color: #1e40af;
            background-color: #dbeafe;
            border-radius: 10px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: bold;
        """)

        top_select_bar.addWidget(self.cust_search_input, stretch=2)
        top_select_bar.addWidget(self.btn_select_all_cust)
        top_select_bar.addWidget(self.btn_clear_cust)
        top_select_bar.addWidget(self.cust_count_badge)

        cust_layout.addLayout(top_select_bar)

        # Scrollable Customer List Widget with Checkboxes
        self.customer_list = QListWidget()
        self.customer_list.setMaximumHeight(130)
        self.customer_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: #ffffff;
                padding: 4px;
            }
            QListWidget::item {
                padding: 3px 6px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #f1f5f9;
            }
        """)
        self.customer_list.itemChanged.connect(self._update_customer_count)

        customers = MasterService.get_all_customers()
        for c in customers:
            phone_str = f" ({c.phone})" if c.phone else ""
            item = QListWidgetItem(f"{c.name}{phone_str}")
            item.setData(Qt.UserRole, c.id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

            if preselected_customer_id and c.id == preselected_customer_id:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

            self.customer_list.addItem(item)

        cust_layout.addWidget(self.customer_list)
        layout.addWidget(cust_group)
        self._update_customer_count()

        # 2. Rate Adjustment Amount
        adj_frame = QFrame()
        adj_frame.setProperty("class", "cardFrame")
        adj_layout = QVBoxLayout(adj_frame)
        adj_layout.setSpacing(6)

        adj_header = QLabel("<b>Rate Adjustment (₹ per KG relative to Main Benchmark Rate)*:</b>")
        adj_layout.addWidget(adj_header)

        adj_row = QHBoxLayout()
        self.adj_spin = QDoubleSpinBox()
        self.adj_spin.setRange(-999.00, 999.00)
        self.adj_spin.setDecimals(2)
        self.adj_spin.setPrefix("₹ ")
        self.adj_spin.setSuffix(" / KG")
        self.adj_spin.setValue(-5.00)
        self.adj_spin.setStyleSheet("""
            QDoubleSpinBox {
                font-size: 15px;
                font-weight: bold;
                color: #1e3a8a;
                background-color: #ffffff;
                border: 2px solid #93c5fd;
                border-radius: 6px;
                padding: 6px 10px;
                min-width: 140px;
            }
        """)
        self.adj_spin.valueChanged.connect(self._update_preview)

        self.preview_label = QLabel()
        self.preview_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #059669;")

        adj_row.addWidget(self.adj_spin)
        adj_row.addWidget(self.preview_label)
        adj_row.addStretch()
        adj_layout.addLayout(adj_row)

        hint = QLabel("💡 Tip: Enter negative values for discounts (e.g. -5.00) or positive for surcharges (e.g. +2.00).")
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        adj_layout.addWidget(hint)

        layout.addWidget(adj_frame)

        # 3. Date Range & Quick Presets
        date_group = QGroupBox("Applicable Date Period")
        date_layout = QVBoxLayout(date_group)
        date_layout.setSpacing(8)

        # Quick preset buttons
        preset_layout = QHBoxLayout()
        presets = [
            ("Today", self._preset_today),
            ("This Week", self._preset_this_week),
            ("Next Week", self._preset_next_week),
            ("This Month", self._preset_this_month),
            ("Next Month", self._preset_next_month),
        ]
        for name, callback in presets:
            btn = QPushButton(name)
            btn.setProperty("class", "secondaryBtn")
            btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")
            btn.clicked.connect(callback)
            preset_layout.addWidget(btn)
        preset_layout.addStretch()
        date_layout.addLayout(preset_layout)

        # Start and End Date Inputs
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("From Date:"))
        self.start_date_edit = QDateEdit(QDate.currentDate())
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.start_date_edit.dateChanged.connect(self._validate_dates)

        range_layout.addWidget(self.start_date_edit)
        range_layout.addWidget(QLabel("To Date:"))
        self.end_date_edit = QDateEdit(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.end_date_edit.dateChanged.connect(self._validate_dates)

        range_layout.addWidget(self.end_date_edit)
        range_layout.addStretch()
        date_layout.addLayout(range_layout)

        layout.addWidget(date_group)

        # 4. Days of Week Filter
        days_group = QGroupBox("Applicable Days of Week (Optional Day Filter)")
        days_layout = QVBoxLayout(days_group)
        days_layout.setSpacing(6)

        # Quick day toggles
        day_btn_layout = QHBoxLayout()
        btn_all_days = QPushButton("All 7 Days")
        btn_all_days.setProperty("class", "secondaryBtn")
        btn_all_days.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        btn_all_days.clicked.connect(self._select_all_days)

        btn_weekdays = QPushButton("Weekdays (Mon-Fri)")
        btn_weekdays.setProperty("class", "secondaryBtn")
        btn_weekdays.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        btn_weekdays.clicked.connect(self._select_weekdays)

        btn_weekends = QPushButton("Weekends (Sat-Sun)")
        btn_weekends.setProperty("class", "secondaryBtn")
        btn_weekends.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        btn_weekends.clicked.connect(self._select_weekends)

        day_btn_layout.addWidget(btn_all_days)
        day_btn_layout.addWidget(btn_weekdays)
        day_btn_layout.addWidget(btn_weekends)
        day_btn_layout.addStretch()
        days_layout.addLayout(day_btn_layout)

        # Checkboxes for each day
        checks_layout = QHBoxLayout()
        self.day_checkboxes = {}
        day_labels = [("Mon", "MON"), ("Tue", "TUE"), ("Wed", "WED"), ("Thu", "THU"), ("Fri", "FRI"), ("Sat", "SAT"), ("Sun", "SUN")]
        for short_name, code in day_labels:
            cb = QCheckBox(short_name)
            cb.setChecked(True)
            self.day_checkboxes[code] = cb
            checks_layout.addWidget(cb)
        days_layout.addLayout(checks_layout)

        layout.addWidget(days_group)

        # 5. Notes / Reason
        notes_box = QHBoxLayout()
        notes_box.addWidget(QLabel("Notes / Reason:"))
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("e.g. Weekend Discount, October Bulk Contract, Festival Offer")
        notes_box.addWidget(self.notes_edit)
        layout.addLayout(notes_box)

        # 6. Action Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Rate Adjustment")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self._on_save)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        # Default to This Week preset and update preview
        self._preset_this_week()
        self._update_preview()

    def _update_preview(self):
        main_rate = SettingService.get_main_chicken_rate()
        adj = Decimal(str(self.adj_spin.value()))
        effective = max(Decimal("0.00"), main_rate + adj)
        sign = "+" if adj >= 0 else ""
        self.preview_label.setText(
            f"Preview with Market Rate ({format_currency(main_rate)}): {sign}{format_currency(adj)} ➔ Effective: {format_currency(effective)} / KG"
        )

    def _validate_dates(self):
        if self.start_date_edit.date() > self.end_date_edit.date():
            self.end_date_edit.setDate(self.start_date_edit.date())

    def _preset_today(self):
        today = QDate.currentDate()
        self.start_date_edit.setDate(today)
        self.end_date_edit.setDate(today)

    def _preset_this_week(self):
        today = date.today()
        # Monday of current week
        start_d = today - timedelta(days=today.weekday())
        end_d = start_d + timedelta(days=6)
        self.start_date_edit.setDate(QDate(start_d.year, start_d.month, start_d.day))
        self.end_date_edit.setDate(QDate(end_d.year, end_d.month, end_d.day))

    def _preset_next_week(self):
        today = date.today()
        start_d = today - timedelta(days=today.weekday()) + timedelta(days=7)
        end_d = start_d + timedelta(days=6)
        self.start_date_edit.setDate(QDate(start_d.year, start_d.month, start_d.day))
        self.end_date_edit.setDate(QDate(end_d.year, end_d.month, end_d.day))

    def _preset_this_month(self):
        today = date.today()
        start_d = date(today.year, today.month, 1)
        # Find last day of month
        if today.month == 12:
            end_d = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_d = date(today.year, today.month + 1, 1) - timedelta(days=1)
        self.start_date_edit.setDate(QDate(start_d.year, start_d.month, start_d.day))
        self.end_date_edit.setDate(QDate(end_d.year, end_d.month, end_d.day))

    def _preset_next_month(self):
        today = date.today()
        if today.month == 12:
            start_d = date(today.year + 1, 1, 1)
            end_d = date(today.year + 1, 2, 1) - timedelta(days=1)
        else:
            next_m = today.month + 1
            start_d = date(today.year, next_m, 1)
            if next_m == 12:
                end_d = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                end_d = date(today.year, next_m + 1, 1) - timedelta(days=1)
        self.start_date_edit.setDate(QDate(start_d.year, start_d.month, start_d.day))
        self.end_date_edit.setDate(QDate(end_d.year, end_d.month, end_d.day))

    def _select_all_days(self):
        for cb in self.day_checkboxes.values():
            cb.setChecked(True)

    def _select_weekdays(self):
        for code, cb in self.day_checkboxes.items():
            cb.setChecked(code in ["MON", "TUE", "WED", "THU", "FRI"])

    def _select_weekends(self):
        for code, cb in self.day_checkboxes.items():
            cb.setChecked(code in ["SAT", "SUN"])

    def _update_customer_count(self):
        count = len(self.get_selected_customer_ids())
        total = self.customer_list.count()
        self.cust_count_badge.setText(f"{count} / {total} selected")
        if count > 0:
            self.cust_count_badge.setStyleSheet("""
                color: #166534;
                background-color: #dcfce7;
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: bold;
            """)
        else:
            self.cust_count_badge.setStyleSheet("""
                color: #475569;
                background-color: #f1f5f9;
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: bold;
            """)

    def _filter_customer_list(self, text: str):
        text_lower = text.strip().lower()
        for i in range(self.customer_list.count()):
            item = self.customer_list.item(i)
            matches = text_lower in item.text().lower()
            item.setHidden(not matches)

    def _select_all_customers(self):
        self.customer_list.blockSignals(True)
        for i in range(self.customer_list.count()):
            item = self.customer_list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)
        self.customer_list.blockSignals(False)
        self._update_customer_count()

    def _clear_all_customers(self):
        self.customer_list.blockSignals(True)
        for i in range(self.customer_list.count()):
            item = self.customer_list.item(i)
            item.setCheckState(Qt.Unchecked)
        self.customer_list.blockSignals(False)
        self._update_customer_count()

    def get_selected_customer_ids(self) -> List[int]:
        ids = []
        for i in range(self.customer_list.count()):
            item = self.customer_list.item(i)
            if item.checkState() == Qt.Checked:
                ids.append(item.data(Qt.UserRole))
        return ids

    def _on_save(self):
        c_ids = self.get_selected_customer_ids()
        if not c_ids:
            QMessageBox.warning(self, "Validation Error", "Please select at least one customer.")
            return

        selected_days = [code for code, cb in self.day_checkboxes.items() if cb.isChecked()]
        if not selected_days:
            QMessageBox.warning(self, "Validation Error", "Please select at least one applicable day of the week.")
            return

        sq = self.start_date_edit.date()
        eq = self.end_date_edit.date()
        start_d = date(sq.year(), sq.month(), sq.day())
        end_d = date(eq.year(), eq.month(), eq.day())

        if start_d > end_d:
            QMessageBox.warning(self, "Validation Error", "Start date cannot be after end date.")
            return

        adj_val = self.adj_spin.value()
        notes = self.notes_edit.text().strip() or None

        try:
            created = CustomerRateAdjustmentService.create_adjustments_for_customers(
                customer_ids=c_ids,
                adjustment_per_kg=adj_val,
                start_date=start_d,
                end_date=end_d,
                days_of_week=selected_days,
                notes=notes
            )
            QMessageBox.information(
                self,
                "Adjustments Saved",
                f"Rate adjustment of {format_currency(adj_val)}/KG successfully applied to {len(created)} customer(s) in one go!"
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save rate adjustments: {str(e)}")


class CustomerRateAdjustmentsDialog(QDialog):
    """
    Management Dialog to view, filter, add, and remove Customer Rate Adjustments.
    """
    def __init__(self, preselected_customer_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.preselected_customer_id = preselected_customer_id
        self.setWindowTitle("Party Rate Adjustments Manager")
        self.resize(920, 520)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header Title
        title_box = QVBoxLayout()
        header = QLabel("🏷️ Customer / Party Rate Adjustments")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #0f172a;")
        subtitle = QLabel("Set differential pricing per customer for specific date ranges, weeks, months, or days of week.")
        subtitle.setStyleSheet("color: #64748b; font-size: 12px;")
        title_box.addWidget(header)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)

        # Top Control Bar
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Filter by Customer:"))

        self.customer_filter_combo = QComboBox()
        self.customer_filter_combo.addItem("All Customers / Parties", None)
        for c in MasterService.get_all_customers():
            self.customer_filter_combo.addItem(c.name, c.id)

        if preselected_customer_id:
            idx = self.customer_filter_combo.findData(preselected_customer_id)
            if idx >= 0:
                self.customer_filter_combo.setCurrentIndex(idx)

        self.customer_filter_combo.currentIndexChanged.connect(self.refresh_table)
        top_bar.addWidget(self.customer_filter_combo)

        top_bar.addStretch()

        self.add_btn = QPushButton("+ New Rate Adjustment")
        self.add_btn.setProperty("class", "primaryBtn")
        self.add_btn.clicked.connect(self._on_add_adjustment)
        top_bar.addWidget(self.add_btn)

        self.clear_btn = QPushButton("🗑️ Remove All for Party")
        self.clear_btn.setProperty("class", "dangerBtn")
        self.clear_btn.clicked.connect(self._on_clear_customer_adjustments)
        top_bar.addWidget(self.clear_btn)

        layout.addLayout(top_bar)

        # Table of Adjustments
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Customer / Party", "Adjustment (₹/KG)", "Period (From - To)", "Days of Week", "Notes / Reason", "Status", "Action"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 120)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        enable_table_copy_and_tooltips(self.table)
        layout.addWidget(self.table, 1)

        # Close button
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setProperty("class", "secondaryBtn")
        close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(close_btn)
        layout.addLayout(bottom_bar)

        self.refresh_table()

    def refresh_table(self):
        c_id = self.customer_filter_combo.currentData()
        self.clear_btn.setEnabled(c_id is not None)

        adjustments = CustomerRateAdjustmentService.get_adjustments(customer_id=c_id)
        self.table.setRowCount(0)
        today = date.today()

        for adj in adjustments:
            r = self.table.rowCount()
            self.table.insertRow(r)

            # ID
            self.table.setItem(r, 0, create_table_item(str(adj.id), alignment=Qt.AlignCenter))

            # Customer Name
            c_name = adj.customer.name if adj.customer else f"Customer #{adj.customer_id}"
            self.table.setItem(r, 1, create_table_item(c_name, bold=True))

            # Adjustment (₹/KG)
            sign = "+" if adj.adjustment_per_kg >= 0 else ""
            adj_str = f"{sign}{format_currency(adj.adjustment_per_kg)}/KG"
            adj_col = Qt.darkGreen if adj.adjustment_per_kg < 0 else Qt.darkRed
            self.table.setItem(r, 2, create_table_item(adj_str, alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True, color=adj_col))

            # Period
            period_str = f"{adj.start_date.strftime('%d/%m/%Y')}  ➔  {adj.end_date.strftime('%d/%m/%Y')}"
            self.table.setItem(r, 3, create_table_item(period_str, alignment=Qt.AlignCenter))

            # Days of Week
            days_str = adj.days_of_week or "ALL DAYS"
            if days_str == "MON,TUE,WED,THU,FRI,SAT,SUN":
                days_str = "All 7 Days"
            self.table.setItem(r, 4, create_table_item(days_str, alignment=Qt.AlignCenter))

            # Reason
            self.table.setItem(r, 5, create_table_item(adj.notes or "-"))

            # Status Badge
            if not adj.is_active:
                status_str = "Inactive"
                stat_col = Qt.gray
            elif adj.end_date < today:
                status_str = "Expired"
                stat_col = Qt.darkRed
            elif adj.start_date > today:
                status_str = "Scheduled"
                stat_col = Qt.darkYellow
            else:
                status_str = "Active Now"
                stat_col = Qt.darkGreen
            self.table.setItem(r, 6, create_table_item(status_str, alignment=Qt.AlignCenter, color=stat_col))

            # Action: Remove button
            action_widget = QWidget()
            act_box = QHBoxLayout(action_widget)
            act_box.setContentsMargins(6, 0, 6, 0)
            act_box.setAlignment(Qt.AlignCenter)

            remove_btn = QPushButton("🗑️ Remove")
            remove_btn.setProperty("class", "actionDelete")
            remove_btn.setToolTip("Remove rate adjustment for this customer")
            remove_btn.clicked.connect(lambda _, aid=adj.id, name=c_name: self._on_delete_adjustment(aid, name))
            act_box.addWidget(remove_btn)
            self.table.setCellWidget(r, 7, action_widget)

    def _on_add_adjustment(self):
        c_id = self.customer_filter_combo.currentData()
        dlg = AddRateAdjustmentDialog(preselected_customer_id=c_id, parent=self)
        if dlg.exec():
            self.refresh_table()

    def _on_delete_adjustment(self, adjustment_id: int, customer_name: str):
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove this rate adjustment for {customer_name}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            CustomerRateAdjustmentService.delete_adjustment(adjustment_id)
            self.refresh_table()

    def _on_clear_customer_adjustments(self):
        c_id = self.customer_filter_combo.currentData()
        c_name = self.customer_filter_combo.currentText()
        if not c_id:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Bulk Removal",
            f"Are you sure you want to remove ALL active rate adjustments for {c_name}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            count = CustomerRateAdjustmentService.delete_adjustments_for_customer(c_id)
            QMessageBox.information(self, "Adjustments Removed", f"Successfully removed {count} rate adjustment(s) for {c_name}.")
            self.refresh_table()
