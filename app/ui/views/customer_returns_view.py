from datetime import date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QComboBox,
    QDoubleSpinBox, QSpinBox, QLineEdit, QDateEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QFormLayout, QTextEdit, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt, QDate
from app.services.master_service import MasterService
from app.services.sales_service import SalesService
from app.services.inventory_service import InventoryService
from app.services.customer_return_service import CustomerReturnService
from app.ui.components.date_range_picker import DateRangePicker
from app.ui.components.table_utils import enable_table_copy_and_tooltips, create_table_item
from app.utils.decimal_utils import format_currency, format_weight, round_weight, round_money, to_decimal

class CustomerReturnsView(QWidget):
    """
    Customer Returns Management View.
    Allows processing partial/full customer returns, specifying box count, box weight, gross, net,
    resale eligibility, and customer credit adjustments with auditable history.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

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
        self.customer_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.customer_combo.setMinimumContentsLength(10)
        self.customer_combo.currentIndexChanged.connect(self._on_customer_changed)

        # Sale combo
        self.sale_combo = QComboBox()
        self.sale_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.sale_combo.setMinimumContentsLength(12)
        self.sale_combo.currentIndexChanged.connect(self._on_sale_changed)

        # Allocation combo
        self.alloc_combo = QComboBox()
        self.alloc_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.alloc_combo.setMinimumContentsLength(12)
        self.alloc_combo.currentIndexChanged.connect(self._on_alloc_changed)

        # Boxes, Gross, Box Weight
        self.box_count_spin = QSpinBox()
        self.box_count_spin.setRange(0, 9999)
        self.box_count_spin.setValue(0)

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

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.00, 999999.00)
        self.rate_spin.setDecimals(2)
        self.rate_spin.setPrefix("₹ ")
        self.rate_spin.setAlignment(Qt.AlignRight)
        self.rate_spin.valueChanged.connect(self._recalc_math)

        self.credit_label = QLabel("₹0.00")
        self.credit_label.setStyleSheet("font-weight: bold; color: #15803d; font-size: 14px;")

        self.resale_check = QCheckBox("Restock for Resale")
        self.resale_check.setToolTip("Restores sellable inventory back to the target batch")
        self.resale_check.setChecked(True)
        self.resale_check.setStyleSheet("font-weight: 600; color: #0f172a;")

        self.reason_combo = QComboBox()
        self.reason_combo.setEditable(True)
        self.reason_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.reason_combo.setMinimumWidth(320)
        self.reason_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.reason_combo.addItems([
            "Customer Excess / Unsold",
            "Order Size Adjustment",
            "Spoiled / Damaged Chicken (Unsellable)",
            "Quality Dispute",
            "Customer Cancellation"
        ])
        if self.reason_combo.view():
            self.reason_combo.view().setTextElideMode(Qt.ElideNone)
            self.reason_combo.view().setMinimumWidth(360)
        self.reason_combo.currentTextChanged.connect(lambda text: self.reason_combo.setToolTip(text))
        self.reason_combo.setToolTip(self.reason_combo.currentText())
        if self.reason_combo.lineEdit():
            self.reason_combo.lineEdit().setPlaceholderText("Select or enter return reason")

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Optional remarks")

        save_btn = QPushButton("💾 Save Return")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self._save_return)

        # Signal connections for live math
        self.gross_spin.valueChanged.connect(self._recalc_math)
        self.box_spin.valueChanged.connect(self._recalc_math)

        # Layout form cleanly in 6 columns
        form_layout.addWidget(QLabel("Return Date:"), 0, 0)
        form_layout.addWidget(self.date_edit, 0, 1)
        form_layout.addWidget(QLabel("Customer:"), 0, 2)
        form_layout.addWidget(self.customer_combo, 0, 3)
        form_layout.addWidget(QLabel("Original Sale:"), 0, 4)
        form_layout.addWidget(self.sale_combo, 0, 5)

        form_layout.addWidget(QLabel("Target Batch Name:"), 1, 0)
        form_layout.addWidget(self.alloc_combo, 1, 1)
        form_layout.addWidget(QLabel("No. of Boxes:"), 1, 2)
        form_layout.addWidget(self.box_count_spin, 1, 3)
        form_layout.addWidget(QLabel("Gross Wt (KG):"), 1, 4)
        form_layout.addWidget(self.gross_spin, 1, 5)

        form_layout.addWidget(QLabel("Box Wt (KG):"), 2, 0)
        form_layout.addWidget(self.box_spin, 2, 1)
        form_layout.addWidget(QLabel("<b>Returned Net:</b>"), 2, 2)
        form_layout.addWidget(self.net_label, 2, 3)
        form_layout.addWidget(QLabel("<b>Sell / Return Rate:</b>"), 2, 4)
        form_layout.addWidget(self.rate_spin, 2, 5)

        form_layout.addWidget(QLabel("<b>Credit Amount:</b>"), 3, 0)
        form_layout.addWidget(self.credit_label, 3, 1)
        form_layout.addWidget(QLabel("Reason:"), 3, 2)
        form_layout.addWidget(self.reason_combo, 3, 3)
        form_layout.addWidget(QLabel("Notes:"), 3, 4)
        form_layout.addWidget(self.notes_edit, 3, 5)

        form_layout.setColumnStretch(1, 1)
        form_layout.setColumnStretch(3, 2)
        form_layout.setColumnStretch(5, 2)

        form_layout.addWidget(self.resale_check, 4, 0, 1, 4)
        form_layout.addWidget(save_btn, 4, 4, 1, 2)

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

        # Table - 14 columns displaying Boxes, Gross, Box Wt, Net, Resale, Rate, Credit, Actions
        self.table = QTableWidget(0, 14)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalHeaderLabels([
            "Return #", "Date", "Customer", "Sale Ref", "Batch Name",
            "Boxes", "Gross (KG)", "Box Wt (KG)", "Net (KG)",
            "Resale?", "Rate (₹/KG)", "Credit (₹)", "Reason & Notes", "Actions"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(95)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(12, QHeaderView.Interactive)
        self.table.setColumnWidth(12, 280)
        header.setSectionResizeMode(13, QHeaderView.Fixed)
        self.table.setColumnWidth(13, 120)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        enable_table_copy_and_tooltips(self.table)
        layout.addWidget(self.table, 1)

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
                txt = f"{alloc['batch_number']} | Sold Rate: {format_currency(alloc['rate_per_kg'])} | Returnable: {format_weight(alloc['returnable_kg'])}"
                self.alloc_combo.addItem(txt, alloc)
        else:
            self.current_sale_info = None
        self.alloc_combo.blockSignals(False)
        self._on_alloc_changed()

    def _on_alloc_changed(self):
        alloc_data = self.alloc_combo.currentData()
        if alloc_data:
            self.current_rate = alloc_data["rate_per_kg"]
            self.rate_spin.blockSignals(True)
            self.rate_spin.setValue(float(alloc_data["rate_per_kg"]))
            self.rate_spin.blockSignals(False)
            self.gross_spin.setMaximum(float(alloc_data["returnable_kg"]) * 2)
        elif self.current_sale_info and self.current_sale_info.get("sale"):
            sale_rate = self.current_sale_info["sale"].rate_per_kg
            self.current_rate = sale_rate
            self.rate_spin.blockSignals(True)
            self.rate_spin.setValue(float(sale_rate))
            self.rate_spin.blockSignals(False)
        else:
            self.current_rate = Decimal("0.00")
            self.rate_spin.blockSignals(True)
            self.rate_spin.setValue(0.0)
            self.rate_spin.blockSignals(False)
        self._recalc_math()

    def _recalc_math(self):
        gross = Decimal(str(self.gross_spin.value()))
        box = Decimal(str(self.box_spin.value()))
        rate = Decimal(str(self.rate_spin.value()))
        if box > gross:
            self.net_label.setText("INVALID (Box > Gross)")
            self.credit_label.setText("₹0.00")
            return

        net = round_weight(gross - box)
        self.net_label.setText(format_weight(net))
        credit = round_money(net * rate)
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
        box_cnt = self.box_count_spin.value()

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

        batch_id = alloc_data.get("batch_id") if alloc_data else None

        # Closed batch rule: Check if batch is closed, and prompt to reopen
        reopen_needed = False
        if batch_id:
            batch_obj = InventoryService.get_batch_by_id(batch_id)
            if batch_obj and batch_obj.status == "CLOSED":
                reply = QMessageBox.question(
                    self,
                    "Batch is Closed",
                    f"Batch '{batch_obj.batch_number}' is currently CLOSED.\n\n"
                    "Customer returns can only be accepted if the batch is reopened.\n"
                    f"Would you like to reopen Batch '{batch_obj.batch_number}' and proceed with the return?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
                reopen_needed = True

        qd = self.date_edit.date()
        ret_date = date(qd.year(), qd.month(), qd.day())
        resale = self.resale_check.isChecked()
        reason = self.reason_combo.currentText().strip()
        notes = self.notes_edit.text().strip()

        alloc_id = alloc_data.get("allocation_id") if alloc_data else None
        rate = Decimal(str(self.rate_spin.value()))
        credit = round_money(net * rate)

        line_payload = {
            "sale_batch_allocation_id": alloc_id,
            "batch_id": batch_id,
            "box_count": box_cnt,
            "returned_gross_weight_kg": gross,
            "returned_box_weight_kg": box,
            "returned_net_weight_kg": net,
            "rate_per_kg": rate,
            "financial_credit_amount": credit,
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
                notes=notes,
                reopen_if_closed=reopen_needed
            )
            reopened_msg = f"\nBatch was successfully reopened to ACTIVE." if reopen_needed else ""
            QMessageBox.information(
                self, "Success",
                f"Customer Return #{ret.return_number} saved successfully!\n"
                f"Customer account credited by {format_currency(ret.financial_credit_amount)}.{reopened_msg}"
            )
            self.box_count_spin.setValue(0)
            self.gross_spin.setValue(0.0)
            self.box_spin.setValue(0.0)
            self.notes_edit.clear()
            self._on_sale_changed()
            self.refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save customer return: {str(e)}")

    def refresh_table(self):
        start_d, end_d = self.date_picker.get_date_range()
        returns = CustomerReturnService.get_returns(start_date=start_d, end_date=end_d)

        self.table.setRowCount(0)
        for cr in returns:
            for line in cr.lines:
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, create_table_item(cr.return_number, bold=True))
                self.table.setItem(r, 1, create_table_item(cr.return_date.strftime("%d/%m/%Y"), alignment=Qt.AlignCenter))
                self.table.setItem(r, 2, create_table_item(cr.customer.name if cr.customer else ""))
                self.table.setItem(r, 3, create_table_item(f"Sale #{cr.original_sale_id}", alignment=Qt.AlignCenter))
                self.table.setItem(r, 4, create_table_item(line.batch.batch_number if line.batch else "-"))
                self.table.setItem(r, 5, create_table_item(str(getattr(line, "box_count", 0) or 0), alignment=Qt.AlignCenter))
                self.table.setItem(r, 6, create_table_item(format_weight(line.returned_gross_weight_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
                self.table.setItem(r, 7, create_table_item(format_weight(line.returned_box_weight_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
                self.table.setItem(r, 8, create_table_item(format_weight(line.returned_net_weight_kg), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))

                resale_str = "✅ Resellable" if line.resale_eligible else "❌ Unsellable"
                resale_col = Qt.darkGreen if line.resale_eligible else Qt.red
                self.table.setItem(r, 9, create_table_item(resale_str, alignment=Qt.AlignCenter, color=resale_col))

                self.table.setItem(r, 10, create_table_item(format_currency(line.rate_per_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
                self.table.setItem(r, 11, create_table_item(format_currency(line.financial_amount), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))
                reason_str = f"{line.reason or ''} {f'({cr.notes})' if cr.notes else ''}".strip()
                reason_item = create_table_item(reason_str or "-")
                if reason_str:
                    reason_item.setToolTip(reason_str)
                self.table.setItem(r, 12, reason_item)

                # Attractive action button
                action_widget = QWidget()
                act_box = QHBoxLayout(action_widget)
                act_box.setContentsMargins(6, 0, 6, 0)
                act_box.setAlignment(Qt.AlignCenter)

                del_btn = QPushButton("🗑️ Delete")
                del_btn.setProperty("class", "actionDelete")
                del_btn.setToolTip("Delete this return record and reverse stock/credit")
                del_btn.clicked.connect(lambda _, ret_id=cr.id: self._delete_return(ret_id))
                act_box.addWidget(del_btn)

                self.table.setCellWidget(r, 13, action_widget)

    def _delete_return(self, return_id: int):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete customer return record #{return_id}?\n"
            "This will reverse the restored inventory stock and customer credit.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                CustomerReturnService.soft_delete_customer_return(return_id)
                QMessageBox.information(self, "Deleted", "Customer return record deleted and stock/credit reversed.")
                self.refresh_table()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete return: {str(e)}")
