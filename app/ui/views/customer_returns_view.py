from datetime import date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QComboBox,
    QDoubleSpinBox, QSpinBox, QLineEdit, QDateEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QFormLayout, QTextEdit, QCheckBox
)
from PySide6.QtCore import Qt, QDate
from app.services.master_service import MasterService
from app.services.sales_service import SalesService
from app.services.customer_return_service import CustomerReturnService
from app.ui.components.date_range_picker import DateRangePicker
from app.utils.decimal_utils import format_currency, format_weight, round_weight, round_money, to_decimal

class CustomerReturnsView(QWidget):
    """
    Customer Returns Management View.
    Allows processing partial/full customer returns, specifying resale eligibility,
    and tracking customer credit adjustments and return history.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel("🔁 Customer Returns & Credits")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        layout.addWidget(header)

        # Return Entry Form Frame
        form_frame = QFrame()
        form_frame.setProperty("class", "cardFrame")
        form_layout = QGridLayout(form_frame)
        form_layout.setContentsMargins(15, 15, 15, 15)
        form_layout.setSpacing(10)

        # Date
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        # Customer combo
        self.customer_combo = QComboBox()
        self.customer_combo.currentIndexChanged.connect(self._on_customer_changed)

        # Sale combo
        self.sale_combo = QComboBox()
        self.sale_combo.currentIndexChanged.connect(self._on_sale_changed)

        # Allocation combo
        self.alloc_combo = QComboBox()
        self.alloc_combo.currentIndexChanged.connect(self._on_alloc_changed)

        # Return Weights
        self.gross_spin = QDoubleSpinBox()
        self.gross_spin.setRange(0.000, 999999.000)
        self.gross_spin.setDecimals(3)
        self.gross_spin.setSuffix(" KG")

        self.box_spin = QDoubleSpinBox()
        self.box_spin.setRange(0.000, 999999.000)
        self.box_spin.setDecimals(3)
        self.box_spin.setSuffix(" KG")

        self.net_label = QLabel("0.000 KG")
        self.net_label.setStyleSheet("font-weight: bold; color: #0369a1; font-size: 13px;")

        self.credit_label = QLabel("₹0.00")
        self.credit_label.setStyleSheet("font-weight: bold; color: #15803d; font-size: 14px;")

        self.resale_check = QCheckBox("Resale Eligible (restores sellable stock to batch)")
        self.resale_check.setChecked(True)
        self.resale_check.setStyleSheet("font-weight: 600; color: #0f172a;")

        self.reason_combo = QComboBox()
        self.reason_combo.setEditable(True)
        self.reason_combo.addItems([
            "Customer Excess / Unsold",
            "Order Size Adjustment",
            "Spoiled / Damaged Chicken (Unsellable)",
            "Quality Dispute",
            "Customer Cancellation"
        ])

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Optional remarks")

        save_btn = QPushButton("Save Return & Credit Customer")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self._save_return)

        # Signal connections for live math
        self.gross_spin.valueChanged.connect(self._recalc_math)
        self.box_spin.valueChanged.connect(self._recalc_math)

        # Layout form
        form_layout.addWidget(QLabel("Return Date:"), 0, 0)
        form_layout.addWidget(self.date_edit, 0, 1)
        form_layout.addWidget(QLabel("Customer:"), 0, 2)
        form_layout.addWidget(self.customer_combo, 0, 3)
        form_layout.addWidget(QLabel("Original Sale:"), 0, 4)
        form_layout.addWidget(self.sale_combo, 0, 5)

        form_layout.addWidget(QLabel("Batch Allocation:"), 1, 0)
        form_layout.addWidget(self.alloc_combo, 1, 1, 1, 2)
        form_layout.addWidget(QLabel("Returned Gross:"), 1, 3)
        form_layout.addWidget(self.gross_spin, 1, 4)
        form_layout.addWidget(QLabel("Returned Box:"), 1, 5)
        form_layout.addWidget(self.box_spin, 1, 6 if form_layout.columnCount() > 6 else 5)

        form_layout.addWidget(QLabel("<b>Returned Net:</b>"), 2, 0)
        form_layout.addWidget(self.net_label, 2, 1)
        form_layout.addWidget(QLabel("<b>Credit Amount:</b>"), 2, 2)
        form_layout.addWidget(self.credit_label, 2, 3)
        form_layout.addWidget(self.resale_check, 2, 4, 1, 2)

        form_layout.addWidget(QLabel("Reason:"), 3, 0)
        form_layout.addWidget(self.reason_combo, 3, 1, 1, 2)
        form_layout.addWidget(QLabel("Notes:"), 3, 3)
        form_layout.addWidget(self.notes_edit, 3, 4)
        form_layout.addWidget(save_btn, 3, 5)

        layout.addWidget(form_frame)

        # History Table & Filters
        filter_layout = QHBoxLayout()
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.refresh_table)
        filter_layout.addWidget(self.date_picker)
        filter_layout.addStretch()

        refresh_table_btn = QPushButton("🔄 Refresh")
        refresh_table_btn.setProperty("class", "secondaryBtn")
        refresh_table_btn.clicked.connect(self.refresh_table)
        filter_layout.addWidget(refresh_table_btn)

        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Return #", "Date", "Customer", "Sale Ref", "Batch", "Net Weight (KG)",
            "Resale?", "Credit Amount", "Reason & Notes"
        ])
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.current_sale_info = None
        self.current_rate = Decimal("0.00")
        self.load_customers()
        self.refresh_table()

    def load_combos(self):
        self.load_customers()

    def _recalc_net_and_amount(self):
        self._recalc_math()

    def on_view_activated(self):
        self.load_customers()
        self.refresh_table()

    def load_customers(self):
        cur_id = self.customer_combo.currentData()
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        for c in MasterService.get_all_customers():
            self.customer_combo.addItem(c.name, c.id)
        if cur_id:
            idx = self.customer_combo.findData(cur_id)
            if idx >= 0:
                self.customer_combo.setCurrentIndex(idx)
        self.customer_combo.blockSignals(False)
        self._on_customer_changed()

    def _on_customer_changed(self):
        c_id = self.customer_combo.currentData()
        self.sale_combo.blockSignals(True)
        self.sale_combo.clear()
        if c_id:
            sales = SalesService.get_sales(customer_id=c_id)
            for s in sales:
                txt = f"Sale #{s.id} ({s.transaction_date.strftime('%d/%m/%Y')} - {format_weight(s.net_weight_kg)})"
                self.sale_combo.addItem(txt, s.id)
        self.sale_combo.blockSignals(False)
        self._on_sale_changed()

    def _on_sale_changed(self):
        s_id = self.sale_combo.currentData()
        self.alloc_combo.blockSignals(True)
        self.alloc_combo.clear()
        if s_id:
            info = CustomerReturnService.get_returnable_sale_info(s_id)
            self.current_sale_info = info
            for alloc in info.get("allocations", []):
                txt = f"{alloc['batch_number']} (Sold: {format_weight(alloc['sold_net_kg'])}, Avail to Return: {format_weight(alloc['returnable_kg'])})"
                self.alloc_combo.addItem(txt, alloc)
        else:
            self.current_sale_info = None
        self.alloc_combo.blockSignals(False)
        self._on_alloc_changed()

    def _on_alloc_changed(self):
        alloc_data = self.alloc_combo.currentData()
        if alloc_data:
            self.current_rate = alloc_data["rate_per_kg"]
            self.gross_spin.setMaximum(float(alloc_data["returnable_kg"]))
        elif self.current_sale_info and self.current_sale_info.get("sale"):
            self.current_rate = self.current_sale_info["sale"].rate_per_kg
        else:
            self.current_rate = Decimal("0.00")
        self._recalc_math()

    def _recalc_math(self):
        gross = Decimal(str(self.gross_spin.value()))
        box = Decimal(str(self.box_spin.value()))
        if box > gross:
            self.net_label.setText("INVALID (Box > Gross)")
            self.credit_label.setText("₹0.00")
            return

        net = round_weight(gross - box)
        self.net_label.setText(format_weight(net))
        credit = round_money(net * self.current_rate)
        self.credit_label.setText(format_currency(credit))

    def _save_return(self):
        c_id = self.customer_combo.currentData()
        s_id = self.sale_combo.currentData()
        if not c_id or not s_id:
            QMessageBox.warning(self, "Validation Error", "Please select a customer and sale.")
            return

        alloc_data = self.alloc_combo.currentData()
        gross = self.gross_spin.value()
        box = self.box_spin.value()
        if gross <= 0:
            QMessageBox.warning(self, "Validation Error", "Returned gross weight must be greater than 0.")
            return
        if box > gross:
            QMessageBox.warning(self, "Validation Error", "Box weight cannot exceed gross weight.")
            return

        net = round_weight(gross - box)
        if alloc_data and net > alloc_data["returnable_kg"]:
            QMessageBox.warning(
                self, "Validation Error",
                f"Returned net weight ({net} KG) exceeds maximum returnable quantity ({alloc_data['returnable_kg']} KG)."
            )
            return

        qd = self.date_edit.date()
        ret_date = date(qd.year(), qd.month(), qd.day())
        resale = self.resale_check.isChecked()
        reason = self.reason_combo.currentText().strip()
        notes = self.notes_edit.text().strip()

        alloc_id = alloc_data.get("allocation_id") if alloc_data else None
        batch_id = alloc_data.get("batch_id") if alloc_data else None

        line_payload = {
            "sale_batch_allocation_id": alloc_id,
            "batch_id": batch_id,
            "returned_gross_weight_kg": gross,
            "returned_box_weight_kg": box,
            "returned_net_weight_kg": net,
            "rate_per_kg": self.current_rate,
            "resale_eligible": resale,
            "reason": reason,
            "notes": notes
        }

        try:
            ret = CustomerReturnService.create_customer_return(
                customer_id=c_id,
                original_sale_id=s_id,
                return_date=ret_date,
                lines_data=[line_payload],
                notes=notes
            )
            QMessageBox.information(
                self, "Success",
                f"Customer Return #{ret.return_number} saved successfully!\n"
                f"Customer account credited by {format_currency(ret.financial_credit_amount)}."
            )
            self.gross_spin.setValue(0.0)
            self.box_spin.setValue(0.0)
            self.notes_edit.clear()
            self._on_sale_changed()
            self.refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def refresh_table(self):
        start_d, end_d = self.date_picker.get_date_range()
        returns = CustomerReturnService.get_returns(start_date=start_d, end_date=end_d)

        self.table.setRowCount(0)
        for r in returns:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            self.table.setItem(row_idx, 0, QTableWidgetItem(r.return_number))
            self.table.setItem(row_idx, 1, QTableWidgetItem(r.return_date.strftime("%d/%m/%Y")))
            self.table.setItem(row_idx, 2, QTableWidgetItem(r.customer.name if r.customer else ""))
            self.table.setItem(row_idx, 3, QTableWidgetItem(f"Sale #{r.original_sale_id}"))

            batch_names = []
            resale_strs = []
            for line in r.lines:
                if line.batch:
                    batch_names.append(line.batch.batch_number)
                resale_strs.append("Yes" if line.resale_eligible else "No (Damaged)")

            self.table.setItem(row_idx, 4, QTableWidgetItem(", ".join(batch_names) or "-"))
            self.table.setItem(row_idx, 5, QTableWidgetItem(format_weight(r.total_returned_weight_kg)))
            self.table.setItem(row_idx, 6, QTableWidgetItem(", ".join(resale_strs) or "-"))
            self.table.setItem(row_idx, 7, QTableWidgetItem(format_currency(r.financial_credit_amount)))
            
            reasons = [l.reason for l in r.lines if l.reason]
            self.table.setItem(row_idx, 8, QTableWidgetItem("; ".join(reasons) or r.notes or "-"))
