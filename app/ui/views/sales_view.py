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
from app.services.setting_service import SettingService
from app.services.customer_rate_adjustment_service import CustomerRateAdjustmentService
from app.services.inventory_service import InventoryService
from app.services.customer_return_service import CustomerReturnService
from app.ui.views.customer_rate_adjustments_dialog import CustomerRateAdjustmentsDialog
from app.ui.components.date_range_picker import DateRangePicker
from app.utils.decimal_utils import format_currency, format_weight, round_weight, round_money, to_decimal

class MultiBatchSaleDialog(QDialog):
    """
    Dialog allowing the user to allocate chicken sales across multiple batches
    (e.g., 30 kg from Batch A and 70 kg from Batch C).
    """
    def __init__(self, item_id: int, default_rate: Decimal, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.default_rate = default_rate
        self.allocations_data = []

        self.setWindowTitle("Multi-Batch Sale Allocation")
        self.resize(1040, 560)
        self.setMinimumSize(960, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        info_lbl = QLabel(
            "<b>Multi-Batch Allocation:</b> Divide this sale across one or multiple available batches. "
            "Available sellable stock is automatically checked and updated per batch."
        )
        info_lbl.setStyleSheet("color: #334155; font-size: 13px; background-color: #f1f5f9; padding: 10px 14px; border-radius: 6px; border: 1px solid #cbd5e1;")
        layout.addWidget(info_lbl)

        # Allocations Table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Batch / Inventory Source", "Boxes", "Gross Wt (KG)", "Box Wt (KG)", "Net Wt (KG)", "Rate (₹/KG)", "Amount (₹)", "Action"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setSectionResizeMode(0, QHeaderView.Stretch)

        self.table.setColumnWidth(1, 90)   # Boxes
        self.table.setColumnWidth(2, 125)  # Gross (KG)
        self.table.setColumnWidth(3, 125)  # Box (KG)
        self.table.setColumnWidth(4, 125)  # Net (KG)
        self.table.setColumnWidth(5, 120)  # Rate (₹/KG)
        self.table.setColumnWidth(6, 130)  # Amount (₹)
        self.table.setColumnWidth(7, 95)   # Action

        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        add_row_btn = QPushButton("➕ Add Batch Allocation")
        add_row_btn.setProperty("class", "secondaryBtn")
        add_row_btn.setStyleSheet("font-size: 13px; font-weight: bold; padding: 6px 14px;")
        add_row_btn.clicked.connect(self._add_row)
        btn_row.addWidget(add_row_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Summary Bar
        summary_frame = QFrame()
        summary_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        sum_layout = QHBoxLayout(summary_frame)
        sum_layout.setSpacing(20)

        self.total_boxes_lbl = QLabel("Total Boxes: 0")
        self.total_boxes_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #334155;")

        self.total_gross_lbl = QLabel("Gross: 0.000 KG")
        self.total_gross_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #334155;")

        self.total_net_lbl = QLabel("Total Net: 0.000 KG")
        self.total_net_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #0369a1; background: #e0f2fe; padding: 4px 10px; border-radius: 4px;")

        self.total_amt_lbl = QLabel("Total Amount: ₹0.00")
        self.total_amt_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #15803d; background: #dcfce7; padding: 4px 10px; border-radius: 4px;")

        sum_layout.addWidget(self.total_boxes_lbl)
        sum_layout.addWidget(self.total_gross_lbl)
        sum_layout.addStretch()
        sum_layout.addWidget(self.total_net_lbl)
        sum_layout.addWidget(self.total_amt_lbl)
        layout.addWidget(summary_frame)

        # Actions
        actions_row = QHBoxLayout()
        actions_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryBtn")
        cancel_btn.setStyleSheet("min-width: 90px; padding: 6px 14px;")
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QPushButton("✓ Apply Allocations")
        confirm_btn.setProperty("class", "primaryBtn")
        confirm_btn.setStyleSheet("min-width: 140px; padding: 6px 16px; font-weight: bold;")
        confirm_btn.clicked.connect(self._validate_and_accept)

        actions_row.addWidget(cancel_btn)
        actions_row.addWidget(confirm_btn)
        layout.addLayout(actions_row)

        # Load available batches
        self.available_batches = InventoryService.get_sellable_batches(item_id=self.item_id)
        if self.available_batches:
            self._add_row()
        else:
            QMessageBox.warning(self, "No Stock", "No active batches with available stock found for this item.")

    def _add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)

        batch_combo = QComboBox()
        batch_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        batch_combo.setStyleSheet("""
            QComboBox {
                font-size: 13px;
                font-weight: 600;
                padding: 4px 8px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background-color: #ffffff;
            }
        """)
        for b in self.available_batches:
            batch_combo.addItem(
                f"{b.batch_number} (Avail: {format_weight(b.current_stock_kg)})",
                b.id
            )

        box_count_spin = QSpinBox()
        box_count_spin.setRange(0, 9999)
        box_count_spin.setValue(0)
        box_count_spin.setAlignment(Qt.AlignRight)
        box_count_spin.setStyleSheet("""
            QSpinBox {
                font-size: 13px;
                font-weight: 600;
                padding: 4px 6px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background-color: #ffffff;
            }
        """)

        gross_spin = QDoubleSpinBox()
        gross_spin.setRange(0.000, 999999.000)
        gross_spin.setDecimals(3)
        gross_spin.setSuffix(" KG")
        gross_spin.setAlignment(Qt.AlignRight)
        gross_spin.setStyleSheet("""
            QDoubleSpinBox {
                font-size: 13px;
                font-weight: 600;
                padding: 4px 6px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background-color: #ffffff;
            }
        """)

        box_spin = QDoubleSpinBox()
        box_spin.setRange(0.000, 999999.000)
        box_spin.setDecimals(3)
        box_spin.setSuffix(" KG")
        box_spin.setAlignment(Qt.AlignRight)
        box_spin.setStyleSheet("""
            QDoubleSpinBox {
                font-size: 13px;
                font-weight: 600;
                padding: 4px 6px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background-color: #ffffff;
            }
        """)

        net_lbl = QLabel("0.000 KG")
        net_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        net_lbl.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #0369a1;
                background-color: #f0f9ff;
                border: 1px solid #bae6fd;
                border-radius: 5px;
                padding: 4px 8px;
            }
        """)

        rate_spin = QDoubleSpinBox()
        rate_spin.setRange(0.00, 999999.00)
        rate_spin.setDecimals(2)
        rate_spin.setPrefix("₹ ")
        rate_spin.setValue(float(self.default_rate))
        rate_spin.setAlignment(Qt.AlignRight)
        rate_spin.setStyleSheet("""
            QDoubleSpinBox {
                font-size: 13px;
                font-weight: 600;
                padding: 4px 6px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background-color: #ffffff;
            }
        """)

        amt_lbl = QLabel("₹0.00")
        amt_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        amt_lbl.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #15803d;
                background-color: #f0fdf4;
                border: 1px solid #bbf7d0;
                border-radius: 5px;
                padding: 4px 8px;
            }
        """)

        del_container = QWidget()
        del_layout = QHBoxLayout(del_container)
        del_layout.setContentsMargins(4, 4, 4, 4)
        del_layout.setAlignment(Qt.AlignCenter)
        del_btn = QPushButton("🗑️ Delete")
        del_btn.setProperty("class", "actionDelete")
        del_btn.setStyleSheet("font-size: 11px; font-weight: 700; min-height: 26px; padding: 3px 8px; border-radius: 5px;")
        del_btn.clicked.connect(self._on_remove_clicked)
        del_layout.addWidget(del_btn)

        # Auto-calc connections - all call unified _recalculate_all
        gross_spin.valueChanged.connect(self._recalculate_all)
        box_spin.valueChanged.connect(self._recalculate_all)
        rate_spin.valueChanged.connect(self._recalculate_all)
        box_count_spin.valueChanged.connect(self._recalculate_all)

        self.table.setCellWidget(r, 0, batch_combo)
        self.table.setCellWidget(r, 1, box_count_spin)
        self.table.setCellWidget(r, 2, gross_spin)
        self.table.setCellWidget(r, 3, box_spin)
        self.table.setCellWidget(r, 4, net_lbl)
        self.table.setCellWidget(r, 5, rate_spin)
        self.table.setCellWidget(r, 6, amt_lbl)
        self.table.setCellWidget(r, 7, del_container)

        self._recalculate_all()

    def _remove_row(self, row_idx: int):
        if self.table.rowCount() <= 1:
            QMessageBox.information(self, "Notice", "At least one allocation row is required.")
            return
        if 0 <= row_idx < self.table.rowCount():
            self.table.removeRow(row_idx)
            self._recalculate_all()

    def _on_remove_clicked(self):
        btn = self.sender()
        if not btn:
            return
        for r in range(self.table.rowCount()):
            widget = self.table.cellWidget(r, 7)
            if widget and (widget == btn or widget.isAncestorOf(btn)):
                self._remove_row(r)
                break

    def _recalculate_all(self):
        tot_boxes = 0
        tot_gross = Decimal("0.000")
        tot_box = Decimal("0.000")
        tot_net = Decimal("0.000")
        tot_amt = Decimal("0.00")

        for r in range(self.table.rowCount()):
            box_count_spin = self.table.cellWidget(r, 1)
            gross_spin = self.table.cellWidget(r, 2)
            box_spin = self.table.cellWidget(r, 3)
            net_lbl = self.table.cellWidget(r, 4)
            rate_spin = self.table.cellWidget(r, 5)
            amt_lbl = self.table.cellWidget(r, 6)

            if not (box_count_spin and gross_spin and box_spin and net_lbl and rate_spin and amt_lbl):
                continue

            b_cnt = box_count_spin.value()
            gross = Decimal(str(gross_spin.value()))
            box = Decimal(str(box_spin.value()))
            rate = Decimal(str(rate_spin.value()))

            tot_boxes += b_cnt
            tot_gross += gross
            tot_box += box

            if box > gross:
                net_lbl.setText("Box > Gross")
                net_lbl.setStyleSheet("""
                    QLabel {
                        font-size: 12px;
                        font-weight: bold;
                        color: #dc2626;
                        background-color: #fef2f2;
                        border: 1px solid #fecaca;
                        border-radius: 5px;
                        padding: 4px 6px;
                    }
                """)
                amt_lbl.setText("₹0.00")
            else:
                net = gross - box
                net_lbl.setText(format_weight(net))
                net_lbl.setStyleSheet("""
                    QLabel {
                        font-size: 13px;
                        font-weight: bold;
                        color: #0369a1;
                        background-color: #f0f9ff;
                        border: 1px solid #bae6fd;
                        border-radius: 5px;
                        padding: 4px 8px;
                    }
                """)
                amt = round_money(net * rate)
                amt_lbl.setText(format_currency(amt))
                tot_net += net
                tot_amt += amt

        self.total_boxes_lbl.setText(f"Total Boxes: {tot_boxes}")
        self.total_gross_lbl.setText(f"Gross: {format_weight(tot_gross)}")
        self.total_net_lbl.setText(f"Total Net: {format_weight(tot_net)}")
        self.total_amt_lbl.setText(f"Total Amount: {format_currency(tot_amt)}")

    def _validate_and_accept(self):
        allocs = []
        batch_net_usage = {}

        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Empty", "Please add at least one batch allocation.")
            return

        for r in range(self.table.rowCount()):
            combo = self.table.cellWidget(r, 0)
            box_cnt = self.table.cellWidget(r, 1).value()
            gross = Decimal(str(self.table.cellWidget(r, 2).value()))
            box = Decimal(str(self.table.cellWidget(r, 3).value()))
            rate = Decimal(str(self.table.cellWidget(r, 5).value()))

            batch_id = combo.currentData()
            if not batch_id:
                QMessageBox.warning(self, "Validation Error", f"Row {r+1}: Please select a batch.")
                return

            if gross <= 0:
                QMessageBox.warning(self, "Validation Error", f"Row {r+1}: Gross weight must be greater than 0.")
                return
            if box > gross:
                QMessageBox.warning(self, "Validation Error", f"Row {r+1}: Box weight cannot exceed gross weight.")
                return

            net = gross - box
            if net <= 0:
                QMessageBox.warning(self, "Validation Error", f"Row {r+1}: Net weight must be greater than 0.")
                return

            batch_net_usage[batch_id] = batch_net_usage.get(batch_id, Decimal("0.000")) + net
            allocs.append({
                "batch_id": batch_id,
                "batch_number": combo.currentText().split(" (")[0],
                "box_count": box_cnt,
                "gross_weight_kg": gross,
                "box_weight_kg": box,
                "net_weight_kg": net,
                "rate_per_kg": rate,
                "amount": round_money(net * rate)
            })

        # Validate against available stock
        batches_dict = {b.id: b for b in self.available_batches}
        for b_id, req_net in batch_net_usage.items():
            b_obj = batches_dict.get(b_id)
            if b_obj and req_net > b_obj.current_stock_kg:
                QMessageBox.warning(
                    self, "Insufficient Stock",
                    f"Selected net quantity of {format_weight(req_net)} exceeds available stock "
                    f"of {format_weight(b_obj.current_stock_kg)} for {b_obj.batch_number}."
                )
                return

        self.allocations_data = allocs
        self.accept()

    def get_allocations(self):
        return self.allocations_data


class QuickSaleReturnDialog(QDialog):
    """
    Dialog allowing the user to initiate a customer return directly from an existing sale record.
    """
    def __init__(self, sale_id: int, parent=None):
        super().__init__(parent)
        self.sale_id = sale_id
        self.setWindowTitle(f"Record Customer Return for Sale #{sale_id}")
        self.resize(520, 500)

        info = CustomerReturnService.get_returnable_sale_info(sale_id)
        if not info:
            QMessageBox.critical(self, "Error", f"Sale #{sale_id} not found.")
            self.reject()
            return

        self.sale = info["sale"]
        self.allocations = info["allocations"]

        layout = QFormLayout(self)
        layout.setSpacing(10)

        # Sale Summary Banner
        banner = QLabel(
            f"<b>Customer:</b> {self.sale.customer.name} | "
            f"<b>Date:</b> {self.sale.transaction_date.strftime('%d/%m/%Y')} | "
            f"<b>Item:</b> {self.sale.item.name}<br>"
            f"<b>Net Sold:</b> {format_weight(self.sale.net_weight_kg)} | "
            f"<b>Rate:</b> {format_currency(self.sale.rate_per_kg)}"
        )
        banner.setStyleSheet("""
            background-color: #f0f9ff;
            border: 1px solid #bae6fd;
            border-radius: 6px;
            padding: 8px;
            color: #0369a1;
        """)
        layout.addRow(banner)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        layout.addRow("Return Date:", self.date_edit)

        # Allocation Selector (if multiple)
        self.alloc_combo = QComboBox()
        for a in self.allocations:
            self.alloc_combo.addItem(
                f"{a['batch_number']} (Returnable: {format_weight(a['returnable_kg'])})",
                a
            )
        layout.addRow("Target Batch / Allocation:", self.alloc_combo)

        self.box_count_spin = QSpinBox()
        self.box_count_spin.setRange(0, 9999)
        self.box_count_spin.setValue(0)
        layout.addRow("Returned Boxes:", self.box_count_spin)

        self.gross_spin = QDoubleSpinBox()
        self.gross_spin.setRange(0.001, 999999.000)
        self.gross_spin.setDecimals(3)
        self.gross_spin.setSuffix(" KG")
        layout.addRow("Returned Gross (KG):", self.gross_spin)

        self.box_spin = QDoubleSpinBox()
        self.box_spin.setRange(0.000, 999999.000)
        self.box_spin.setDecimals(3)
        self.box_spin.setSuffix(" KG")
        layout.addRow("Returned Box (KG):", self.box_spin)

        self.net_lbl = QLabel("0.000 KG")
        self.net_lbl.setStyleSheet("font-weight: bold; color: #0369a1;")
        layout.addRow("Returned Net (AUTO):", self.net_lbl)

        self.resale_check = QCheckBox("Accepted for Resale (Restores stock to batch)")
        self.resale_check.setChecked(True)
        self.resale_check.setStyleSheet("font-weight: bold; color: #15803d;")
        layout.addRow("Resale Eligibility:", self.resale_check)

        self.reason_combo = QComboBox()
        self.reason_combo.addItems([
            "Excess Order / Customer Returned",
            "Quality Issue / Customer Rejected",
            "Spoiled / Unfit for Sale",
            "Weighing Discrepancy",
            "Other Reason"
        ])
        layout.addRow("Return Reason:", self.reason_combo)

        self.credit_spin = QDoubleSpinBox()
        self.credit_spin.setRange(0.00, 999999.00)
        self.credit_spin.setDecimals(2)
        self.credit_spin.setPrefix("₹ ")
        layout.addRow("Financial Credit (₹):", self.credit_spin)

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Optional remarks")
        layout.addRow("Notes:", self.notes_edit)

        # Connections
        self.gross_spin.valueChanged.connect(self._recalc)
        self.box_spin.valueChanged.connect(self._recalc)
        self.alloc_combo.currentIndexChanged.connect(self._recalc)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        submit_btn = QPushButton("Submit Return & Credit Customer")
        submit_btn.setProperty("class", "primaryBtn")
        submit_btn.clicked.connect(self._submit)

        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(submit_btn)
        layout.addRow(btn_box)

        self._recalc()

    def _recalc(self):
        gross = Decimal(str(self.gross_spin.value()))
        box = Decimal(str(self.box_spin.value()))
        if box > gross:
            self.net_lbl.setText("Box > Gross")
            self.net_lbl.setStyleSheet("color: #ef4444; font-weight: bold;")
            self.credit_spin.setValue(0.0)
            return

        net = gross - box
        self.net_lbl.setText(format_weight(net))
        self.net_lbl.setStyleSheet("font-weight: bold; color: #0369a1;")

        alloc_data = self.alloc_combo.currentData()
        rate = alloc_data["rate_per_kg"] if alloc_data else self.sale.rate_per_kg
        credit = round_money(net * rate)
        self.credit_spin.setValue(float(credit))

    def _submit(self):
        gross = Decimal(str(self.gross_spin.value()))
        box = Decimal(str(self.box_spin.value()))
        if gross <= 0:
            QMessageBox.warning(self, "Validation Error", "Gross weight must be greater than 0.")
            return
        if box > gross:
            QMessageBox.warning(self, "Validation Error", "Box weight cannot exceed gross weight.")
            return

        net = gross - box
        alloc_data = self.alloc_combo.currentData()
        returnable = alloc_data["returnable_kg"] if alloc_data else self.sale.net_weight_kg

        if net > returnable:
            QMessageBox.warning(
                self, "Limit Exceeded",
                f"Entered return net weight ({format_weight(net)}) exceeds remaining returnable quantity "
                f"({format_weight(returnable)}) for this allocation."
            )
            return

        qd = self.date_edit.date()
        ret_date = date(qd.year(), qd.month(), qd.day())
        credit_amt = Decimal(str(self.credit_spin.value()))

        lines_data = [{
            "sale_batch_allocation_id": alloc_data["allocation_id"] if alloc_data else None,
            "batch_id": alloc_data["batch_id"] if alloc_data else None,
            "returned_gross_weight_kg": gross,
            "returned_box_weight_kg": box,
            "box_count": self.box_count_spin.value(),
            "resale_eligible": self.resale_check.isChecked(),
            "return_reason": self.reason_combo.currentText(),
            "financial_credit_amount": credit_amt,
            "notes": self.notes_edit.text().strip() or None
        }]

        # Check closed batch requirement
        reopen_needed = False
        target_batch_id = alloc_data["batch_id"] if alloc_data else None
        if target_batch_id:
            b = InventoryService.get_batch_by_id(target_batch_id)
            if b and b.status == "CLOSED":
                reply = QMessageBox.question(
                    self,
                    "Batch is Closed - Reopen Batch?",
                    f"Target batch '{b.batch_number}' is currently CLOSED.\n\n"
                    "Customer returns can only be accepted if the batch is reopened.\n\n"
                    "Would you like to reopen this closed batch now and proceed with the return?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
                reopen_needed = True

        try:
            cr = CustomerReturnService.create_customer_return(
                customer_id=self.sale.customer_id,
                original_sale_id=self.sale.id,
                return_date=ret_date,
                lines_data=lines_data,
                notes=self.notes_edit.text().strip() or None,
                reopen_if_closed=reopen_needed
            )
            reopen_msg = "\n(Batch was successfully reopened to receive return stock.)" if reopen_needed else ""
            QMessageBox.information(
                self, "Success",
                f"Customer Return #{cr.return_number} recorded successfully!{reopen_msg}\n"
                f"Customer credit of {format_currency(cr.total_credit_amount)} posted."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to record customer return: {str(e)}")


class EditSaleDialog(QDialog):
    """
    Dialog for Editing an Existing Sale (e.g. modifying rate, discount, boxes, weights).
    """
    def __init__(self, sale, parent=None):
        super().__init__(parent)
        self.sale = sale
        self.setWindowTitle(f"Edit Sale #{sale.id} & Apply Discount")
        self.resize(500, 440)

        layout = QFormLayout(self)

        q_date = QDate(sale.transaction_date.year, sale.transaction_date.month, sale.transaction_date.day)
        self.date_edit = QDateEdit(q_date)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        self.customer_combo = QComboBox()
        for c in MasterService.get_all_customers():
            self.customer_combo.addItem(c.name, c.id)
        idx = self.customer_combo.findData(sale.customer_id)
        if idx >= 0:
            self.customer_combo.setCurrentIndex(idx)

        self.item_combo = QComboBox()
        for i in MasterService.get_all_items():
            self.item_combo.addItem(i.name, i.id)
        idx_i = self.item_combo.findData(sale.item_id)
        if idx_i >= 0:
            self.item_combo.setCurrentIndex(idx_i)

        self.box_count_spin = QSpinBox()
        self.box_count_spin.setRange(0, 99999)
        self.box_count_spin.setValue(int(getattr(sale, "box_count", 0) or 0))

        self.gross_spin = QDoubleSpinBox()
        self.gross_spin.setRange(0.001, 999999.000)
        self.gross_spin.setDecimals(3)
        self.gross_spin.setSuffix(" KG")
        self.gross_spin.setValue(float(sale.gross_weight_kg))

        self.box_spin = QDoubleSpinBox()
        self.box_spin.setRange(0.000, 999999.000)
        self.box_spin.setDecimals(3)
        self.box_spin.setSuffix(" KG")
        self.box_spin.setValue(float(sale.box_weight_kg))

        self.net_label = QLabel("0.000 KG")
        self.net_label.setStyleSheet("font-weight: bold; color: #0369a1;")

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.00, 999999.00)
        self.rate_spin.setDecimals(2)
        self.rate_spin.setPrefix("₹ ")
        self.rate_spin.setValue(float(sale.rate_per_kg))

        disc_val = float(getattr(sale, "discount_amount", 0.00))
        self.disc_spin = QDoubleSpinBox()
        self.disc_spin.setRange(0.00, 999999.00)
        self.disc_spin.setDecimals(2)
        self.disc_spin.setPrefix("₹ ")
        self.disc_spin.setValue(disc_val)

        self.final_amt_label = QLabel("₹0.00")
        self.final_amt_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #15803d;")

        self.notes_edit = QTextEdit(sale.notes if sale.notes else "")
        self.notes_edit.setMaximumHeight(60)

        # Connect signals for auto calculation
        self.gross_spin.valueChanged.connect(self._recalc)
        self.box_spin.valueChanged.connect(self._recalc)
        self.rate_spin.valueChanged.connect(self._recalc)
        self.disc_spin.valueChanged.connect(self._recalc)

        layout.addRow("Transaction Date:", self.date_edit)
        layout.addRow("Customer:", self.customer_combo)
        layout.addRow("Chicken Item:", self.item_combo)
        layout.addRow("Number of Boxes:", self.box_count_spin)
        layout.addRow("Gross Weight (KG):", self.gross_spin)
        layout.addRow("Box Weight (KG):", self.box_spin)
        layout.addRow("Net Weight (AUTO):", self.net_label)
        layout.addRow("Rate (₹/KG):", self.rate_spin)
        layout.addRow("Discount Amount (₹):", self.disc_spin)
        layout.addRow("Final Sale Amount (AUTO):", self.final_amt_label)
        layout.addRow("Notes:", self.notes_edit)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Update Sale & Apply Discount")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)

        layout.addRow(btn_layout)
        self._recalc()

    def _recalc(self):
        gross = Decimal(str(self.gross_spin.value()))
        box = Decimal(str(self.box_spin.value()))
        if box > gross:
            self.net_label.setText("INVALID (Box > Gross)")
            self.final_amt_label.setText("₹0.00")
            return

        net = gross - box
        self.net_label.setText(format_weight(net))

        rate = Decimal(str(self.rate_spin.value()))
        disc = Decimal(str(self.disc_spin.value()))
        gross_amt = net * rate
        final_amt = gross_amt - disc
        if final_amt < 0:
            self.final_amt_label.setText("INVALID (Disc > Gross)")
        else:
            self.final_amt_label.setText(format_currency(final_amt))

    def get_data(self):
        qd = self.date_edit.date()
        return {
            "transaction_date": date(qd.year(), qd.month(), qd.day()),
            "customer_id": self.customer_combo.currentData(),
            "item_id": self.item_combo.currentData(),
            "box_count": self.box_count_spin.value(),
            "gross_weight_kg": self.gross_spin.value(),
            "box_weight_kg": self.box_spin.value(),
            "rate_per_kg": self.rate_spin.value(),
            "discount_amount": self.disc_spin.value(),
            "notes": self.notes_edit.toPlainText().strip() or None
        }


class SalesView(QWidget):
    """
    Sales Management View supporting batch-wise inventory allocation, multi-batch splitting,
    rate adjustments, and customer returns.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.multi_batch_allocations = None  # Holds multi-batch allocation dict if split is used

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QLabel("Sales Management")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        layout.addWidget(header)

        # Fast Sales Entry Form
        form_frame = QFrame()
        form_frame.setProperty("class", "cardFrame")
        form_layout = QGridLayout(form_frame)
        form_layout.setSpacing(10)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        self.customer_combo = QComboBox()
        self.customer_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.customer_combo.setMinimumContentsLength(10)

        self.item_combo = QComboBox()
        self.item_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.item_combo.setMinimumContentsLength(10)

        # Batch Selection & Multi-Batch Split Button
        batch_container = QWidget()
        batch_box = QHBoxLayout(batch_container)
        batch_box.setContentsMargins(0, 0, 0, 0)
        batch_box.setSpacing(6)

        self.batch_combo = QComboBox()
        self.batch_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.batch_combo.setMinimumContentsLength(16)
        self.batch_combo.currentIndexChanged.connect(self._on_batch_changed)
        batch_box.addWidget(self.batch_combo, 1)

        self.split_btn = QPushButton("🔀 Multi-Batch Split")
        self.split_btn.setToolTip("Divide this sale across multiple batches")
        self.split_btn.setProperty("class", "secondaryBtn")
        self.split_btn.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        self.split_btn.clicked.connect(self._open_multi_batch_dialog)
        batch_box.addWidget(self.split_btn)

        self.clear_split_btn = QPushButton("✖ Clear Split")
        self.clear_split_btn.setToolTip("Cancel multi-batch allocation and return to single batch")
        self.clear_split_btn.setProperty("class", "secondaryBtn")
        self.clear_split_btn.setStyleSheet("padding: 5px 8px; font-size: 11px; color: #dc2626;")
        self.clear_split_btn.setVisible(False)
        self.clear_split_btn.clicked.connect(self._clear_multi_batch)
        batch_box.addWidget(self.clear_split_btn)

        self.box_count_spin = QSpinBox()
        self.box_count_spin.setRange(0, 99999)
        self.box_count_spin.setValue(0)

        self.gross_spin = QDoubleSpinBox()
        self.gross_spin.setRange(0.000, 999999.000)
        self.gross_spin.setDecimals(3)
        self.gross_spin.setSuffix(" KG")

        self.box_spin = QDoubleSpinBox()
        self.box_spin.setRange(0.000, 999999.000)
        self.box_spin.setDecimals(3)
        self.box_spin.setSuffix(" KG")

        self.net_edit = QLineEdit("0.000 KG")
        self.net_edit.setReadOnly(True)
        self.net_edit.setStyleSheet("font-weight: bold; color: #0369a1; background-color: #f0f9ff;")

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.00, 999999.00)
        self.rate_spin.setDecimals(2)
        self.rate_spin.setPrefix("₹ ")

        self.disc_spin = QDoubleSpinBox()
        self.disc_spin.setRange(0.00, 999999.00)
        self.disc_spin.setDecimals(2)
        self.disc_spin.setPrefix("₹ ")

        self.amount_edit = QLineEdit("₹0.00")
        self.amount_edit.setReadOnly(True)
        self.amount_edit.setStyleSheet("font-weight: bold; color: #15803d; background-color: #f0fdf4;")

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Notes/Remarks")

        save_btn = QPushButton("Save Sale")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self._save_sale)

        # Signal connections for live auto-math
        self.gross_spin.valueChanged.connect(self._calculate_net_and_amount)
        self.box_spin.valueChanged.connect(self._calculate_net_and_amount)
        self.rate_spin.valueChanged.connect(self._calculate_net_and_amount)
        self.disc_spin.valueChanged.connect(self._calculate_net_and_amount)

        # Form layout placement
        form_layout.addWidget(QLabel("Date:", self), 0, 0)
        form_layout.addWidget(self.date_edit, 0, 1)
        form_layout.addWidget(QLabel("Customer:", self), 0, 2)

        cust_container = QWidget()
        cust_box = QHBoxLayout(cust_container)
        cust_box.setContentsMargins(0, 0, 0, 0)
        cust_box.setSpacing(4)
        cust_box.addWidget(self.customer_combo)

        manage_adj_btn = QPushButton("🏷️ Rate Adj.")
        manage_adj_btn.setToolTip("Manage Custom Rate Adjustments for Customers")
        manage_adj_btn.setProperty("class", "secondaryBtn")
        manage_adj_btn.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        manage_adj_btn.clicked.connect(self._open_rate_adjustments_from_sales)
        cust_box.addWidget(manage_adj_btn)

        form_layout.addWidget(cust_container, 0, 3)
        form_layout.addWidget(QLabel("Item / Chicken:", self), 0, 4)
        form_layout.addWidget(self.item_combo, 0, 5)

        form_layout.addWidget(QLabel("<b>Batch / Allocation:</b>", self), 1, 0)
        form_layout.addWidget(batch_container, 1, 1, 1, 3)
        form_layout.addWidget(QLabel("No. of Boxes:", self), 1, 4)
        form_layout.addWidget(self.box_count_spin, 1, 5)

        form_layout.addWidget(QLabel("Gross Weight (KG):", self), 2, 0)
        form_layout.addWidget(self.gross_spin, 2, 1)
        form_layout.addWidget(QLabel("Box Weight (KG):", self), 2, 2)
        form_layout.addWidget(self.box_spin, 2, 3)
        form_layout.addWidget(QLabel("<b>Net Weight (AUTO):</b>", self), 2, 4)
        form_layout.addWidget(self.net_edit, 2, 5)

        form_layout.addWidget(QLabel("Rate (₹/KG):", self), 3, 0)

        rate_container = QWidget()
        rate_box = QHBoxLayout(rate_container)
        rate_box.setContentsMargins(0, 0, 0, 0)
        rate_box.setSpacing(6)
        rate_box.addWidget(self.rate_spin)

        reset_rate_btn = QPushButton("↺ Default Rate")
        reset_rate_btn.setToolTip("Reset rate to customer's default rate")
        reset_rate_btn.setProperty("class", "secondaryBtn")
        reset_rate_btn.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        reset_rate_btn.clicked.connect(lambda: self.apply_default_rate(force=True))
        rate_box.addWidget(reset_rate_btn)

        form_layout.addWidget(rate_container, 3, 1)
        form_layout.addWidget(QLabel("Discount (₹):", self), 3, 2)
        form_layout.addWidget(self.disc_spin, 3, 3)
        form_layout.addWidget(QLabel("<b>Final Amount:</b>", self), 3, 4)
        form_layout.addWidget(self.amount_edit, 3, 5)

        # Rate Adjustment Information Banner
        self.adj_info_frame = QFrame()
        self.adj_info_frame.setProperty("class", "cardFrame")
        adj_info_layout = QHBoxLayout(self.adj_info_frame)
        adj_info_layout.setContentsMargins(10, 6, 10, 6)
        self.adj_info_label = QLabel()
        self.adj_info_label.setWordWrap(True)
        adj_info_layout.addWidget(self.adj_info_label)

        form_layout.addWidget(self.adj_info_frame, 4, 0, 1, 6)

        form_layout.addWidget(QLabel("Notes:", self), 5, 0)
        form_layout.addWidget(self.notes_edit, 5, 1, 1, 4)
        form_layout.addWidget(save_btn, 5, 5)

        # Connect customer and date changes to auto-adjust rate
        self.customer_combo.currentIndexChanged.connect(self._on_customer_or_date_changed)
        self.date_edit.dateChanged.connect(self._on_customer_or_date_changed)
        self.item_combo.currentIndexChanged.connect(self._on_item_changed)

        layout.addWidget(form_frame)

        # Table Filter & Actions
        filter_layout = QHBoxLayout()
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.refresh_table)

        filter_layout.addWidget(self.date_picker)
        filter_layout.addStretch()

        delete_btn = QPushButton("Delete Selected")
        delete_btn.setProperty("class", "dangerBtn")
        delete_btn.clicked.connect(self._delete_selected)
        filter_layout.addWidget(delete_btn)

        layout.addLayout(filter_layout)

        # Sales History Table - 13 columns including Batch/Allocation & Return action
        self.table = QTableWidget(0, 13)
        self.table.setHorizontalHeaderLabels([
            "ID", "Date", "Customer", "Item", "Boxes", "Gross (KG)", "Box (KG)",
            "Net (KG)", "Rate (₹/KG)", "Discount (₹)", "Final Amount", "Batch / Allocation", "Actions"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(11, QHeaderView.Stretch)
        header.setSectionResizeMode(12, QHeaderView.Fixed)
        self.table.setColumnWidth(12, 270)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        self.load_combos()
        self.apply_default_rate(force=True)
        self.refresh_table()

    def _on_item_changed(self):
        self._load_batches()

    def _load_batches(self):
        item_id = self.item_combo.currentData()
        self.batch_combo.blockSignals(True)
        self.batch_combo.clear()

        sellable_batches = InventoryService.get_sellable_batches(item_id=item_id) if item_id else []
        if sellable_batches:
            self.batch_combo.addItem("-- Select Batch --", None)
            for b in sellable_batches:
                self.batch_combo.addItem(
                    f"{b.batch_number} (Stock: {format_weight(b.current_stock_kg)} | {b.purchase_date.strftime('%d/%m')})",
                    b.id
                )
            # Default to first batch if available
            self.batch_combo.setCurrentIndex(1)
        else:
            self.batch_combo.addItem("⚠️ No Active Batches with Stock", None)

        self.batch_combo.blockSignals(False)

    def _on_batch_changed(self):
        pass

    def _open_multi_batch_dialog(self):
        item_id = self.item_combo.currentData()
        if not item_id:
            QMessageBox.warning(self, "Item Required", "Please select a chicken item first.")
            return

        rate = Decimal(str(self.rate_spin.value()))
        dlg = MultiBatchSaleDialog(item_id=item_id, default_rate=rate, parent=self)
        if dlg.exec() == QDialog.Accepted:
            allocs = dlg.get_allocations()
            if allocs:
                self.multi_batch_allocations = allocs
                tot_boxes = sum((a["box_count"] for a in allocs), 0)
                tot_gross = sum((a["gross_weight_kg"] for a in allocs), Decimal("0.000"))
                tot_box = sum((a["box_weight_kg"] for a in allocs), Decimal("0.000"))

                self.box_count_spin.setValue(tot_boxes)
                self.gross_spin.setValue(float(tot_gross))
                self.box_spin.setValue(float(tot_box))
                self.gross_spin.setEnabled(False)
                self.box_spin.setEnabled(False)
                self.box_count_spin.setEnabled(False)
                self.batch_combo.setEnabled(False)
                self.clear_split_btn.setVisible(True)

                batch_summary = ", ".join([f"{a['batch_number']}: {format_weight(a['net_weight_kg'])}" for a in allocs])
                self.split_btn.setText(f"🔀 Split ({len(allocs)} Batches)")
                self.split_btn.setToolTip("Multi-Batch Split Allocation:\n" + "\n".join([f"• {a['batch_number']}: Net {format_weight(a['net_weight_kg'])} ({a['box_count']} boxes)" for a in allocs]))
                self.split_btn.setStyleSheet("padding: 5px 8px; font-size: 11px; background-color: #e0f2fe; color: #0284c7; font-weight: bold;")
                self._calculate_net_and_amount()

    def _clear_multi_batch(self):
        self.multi_batch_allocations = None
        self.gross_spin.setEnabled(True)
        self.box_spin.setEnabled(True)
        self.box_count_spin.setEnabled(True)
        self.batch_combo.setEnabled(True)
        self.clear_split_btn.setVisible(False)
        self.split_btn.setText("🔀 Multi-Batch Split")
        self.split_btn.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        self._calculate_net_and_amount()

    def apply_default_rate(self, force: bool = False):
        """Fills the rate input with the customer's effective rate (or daily main rate if no adjustment)."""
        c_id = self.customer_combo.currentData()
        qd = self.date_edit.date()
        t_date = date(qd.year(), qd.month(), qd.day())

        if c_id:
            eff_rate, adj, main_rate = CustomerRateAdjustmentService.get_effective_rate_for_customer(c_id, t_date)
        else:
            main_rate = SettingService.get_main_chicken_rate()
            eff_rate, adj = main_rate, None

        if force or self.rate_spin.value() == 0.0:
            self.rate_spin.setValue(float(eff_rate))
            self._calculate_net_and_amount()

        self._update_adjustment_banner(eff_rate, adj, main_rate)

    def _on_customer_or_date_changed(self):
        """Triggered when customer or date changes to re-evaluate differential rate."""
        if self.gross_spin.value() == 0.0:
            self.apply_default_rate(force=True)
        else:
            c_id = self.customer_combo.currentData()
            qd = self.date_edit.date()
            t_date = date(qd.year(), qd.month(), qd.day())
            if c_id:
                eff_rate, adj, main_rate = CustomerRateAdjustmentService.get_effective_rate_for_customer(c_id, t_date)
            else:
                main_rate = SettingService.get_main_chicken_rate()
                eff_rate, adj = main_rate, None
            self._update_adjustment_banner(eff_rate, adj, main_rate)

    def _update_adjustment_banner(self, eff_rate: Decimal, adj, main_rate: Decimal):
        if adj:
            sign = "+" if adj.adjustment_per_kg >= 0 else ""
            reason_part = f" | Notes: {adj.notes}" if adj.notes else ""
            if adj.adjustment_per_kg < 0:
                self.adj_info_frame.setStyleSheet("""
                    QFrame {
                        background-color: #f0fdf4;
                        border: 1.5px solid #86efac;
                        border-left: 5px solid #16a34a;
                        border-radius: 6px;
                        padding: 6px 12px;
                    }
                """)
                self.adj_info_label.setStyleSheet("color: #15803d; font-size: 12px; font-weight: 600;")
                self.adj_info_label.setText(
                    f"🏷️ <b>Special Party Discount:</b> {sign}{format_currency(adj.adjustment_per_kg)}/KG applied "
                    f"(Benchmark: {format_currency(main_rate)} ➔ Default Rate: {format_currency(eff_rate)}/KG{reason_part})"
                )
            else:
                self.adj_info_frame.setStyleSheet("""
                    QFrame {
                        background-color: #f0f9ff;
                        border: 1.5px solid #7dd3fc;
                        border-left: 5px solid #0284c7;
                        border-radius: 6px;
                        padding: 6px 12px;
                    }
                """)
                self.adj_info_label.setStyleSheet("color: #0369a1; font-size: 12px; font-weight: 600;")
                self.adj_info_label.setText(
                    f"🏷️ <b>Party Rate Adjustment:</b> {sign}{format_currency(adj.adjustment_per_kg)}/KG applied "
                    f"(Benchmark: {format_currency(main_rate)} ➔ Default Rate: {format_currency(eff_rate)}/KG{reason_part})"
                )
        else:
            self.adj_info_frame.setStyleSheet("""
                QFrame {
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-left: 5px solid #94a3b8;
                    border-radius: 6px;
                    padding: 6px 12px;
                }
            """)
            self.adj_info_label.setStyleSheet("color: #64748b; font-size: 12px;")
            self.adj_info_label.setText(
                f"ℹ️ <b>Standard Benchmark Rate:</b> {format_currency(main_rate)}/KG (No party rate adjustment active for this date)"
            )

    def _open_rate_adjustments_from_sales(self):
        c_id = self.customer_combo.currentData()
        dlg = CustomerRateAdjustmentsDialog(preselected_customer_id=c_id, parent=self)
        dlg.exec()
        self.apply_default_rate(force=True)

    def on_view_activated(self):
        """Called automatically when navigating to the Sales tab."""
        self.load_combos()
        if self.gross_spin.value() == 0.0:
            self.apply_default_rate(force=True)
        self.refresh_table()

    def load_combos(self):
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        for c in MasterService.get_all_customers():
            self.customer_combo.addItem(c.name, c.id)
        self.customer_combo.blockSignals(False)

        self.item_combo.blockSignals(True)
        self.item_combo.clear()
        for i in MasterService.get_all_items():
            self.item_combo.addItem(i.name, i.id)
        self.item_combo.blockSignals(False)

        self._load_batches()

    def _calculate_net_and_amount(self):
        gross = Decimal(str(self.gross_spin.value()))
        box = Decimal(str(self.box_spin.value()))

        if box > gross:
            self.net_edit.setText("INVALID (Box > Gross)")
            self.amount_edit.setText("₹0.00")
            return

        net = gross - box
        self.net_edit.setText(format_weight(net))

        rate = Decimal(str(self.rate_spin.value()))
        disc = Decimal(str(self.disc_spin.value()))
        gross_amt = net * rate

        if disc > gross_amt:
            self.amount_edit.setText("INVALID (Disc > Gross)")
            return

        final_amt = gross_amt - disc
        self.amount_edit.setText(format_currency(final_amt))

    def _save_sale(self):
        c_id = self.customer_combo.currentData()
        i_id = self.item_combo.currentData()
        if not c_id or not i_id:
            QMessageBox.warning(self, "Validation Error", "Please select a customer and chicken item.")
            return

        gross = self.gross_spin.value()
        box = self.box_spin.value()
        rate = self.rate_spin.value()
        disc = self.disc_spin.value()
        box_count = self.box_count_spin.value()

        if gross <= 0:
            QMessageBox.warning(self, "Validation Error", "Gross weight must be greater than 0.")
            return
        if box > gross:
            QMessageBox.warning(self, "Validation Error", "Box weight CANNOT be greater than gross weight.")
            return

        q_date = self.date_edit.date()
        t_date = date(q_date.year(), q_date.month(), q_date.day())

        # Determine batch allocation
        batch_id = None
        allocations = None

        if self.multi_batch_allocations:
            allocations = self.multi_batch_allocations
        else:
            batch_id = self.batch_combo.currentData()
            # If sellable batches exist, batch_id selection is enforced
            all_sellable = InventoryService.get_sellable_batches(item_id=i_id)
            if all_sellable and not batch_id:
                QMessageBox.warning(
                    self, "Batch Required",
                    "Please select an active batch or use Multi-Batch Split to allocate inventory for this sale."
                )
                return

        try:
            SalesService.create_sale(
                transaction_date=t_date,
                customer_id=c_id,
                item_id=i_id,
                gross_weight_kg=gross,
                box_weight_kg=box,
                rate_per_kg=rate,
                discount_amount=disc,
                box_count=box_count,
                notes=self.notes_edit.text(),
                allocations=allocations,
                batch_id=batch_id
            )
            QMessageBox.information(self, "Success", "Sale transaction recorded successfully!")
            self._clear_multi_batch()
            self.box_count_spin.setValue(0)
            self.gross_spin.setValue(0.0)
            self.box_spin.setValue(0.0)
            self.apply_default_rate(force=True)
            self.disc_spin.setValue(0.0)
            self.notes_edit.clear()
            self._load_batches()
            self.refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save sale: {str(e)}")

    def refresh_table(self):
        start_d, end_d = self.date_picker.get_date_range()
        sales = SalesService.get_sales(start_date=start_d, end_date=end_d)

        self.table.setRowCount(0)
        for s in sales:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(s.id)))
            self.table.setItem(r, 1, QTableWidgetItem(s.transaction_date.strftime("%d/%m/%Y")))
            self.table.setItem(r, 2, QTableWidgetItem(s.customer.name if s.customer else ""))
            self.table.setItem(r, 3, QTableWidgetItem(s.item.name if s.item else ""))

            # Columns: 0:ID, 1:Date, 2:Customer, 3:Item, 4:Boxes, 5:Gross, 6:Box, 7:Net, 8:Rate, 9:Discount, 10:Final Amount, 11:Batch/Allocation, 12:Actions
            self.table.setItem(r, 4, QTableWidgetItem(str(getattr(s, "box_count", 0) or 0)))
            self.table.setItem(r, 5, QTableWidgetItem(format_weight(s.gross_weight_kg)))
            self.table.setItem(r, 6, QTableWidgetItem(format_weight(s.box_weight_kg)))
            self.table.setItem(r, 7, QTableWidgetItem(format_weight(s.net_weight_kg)))
            self.table.setItem(r, 8, QTableWidgetItem(format_currency(s.rate_per_kg)))

            disc_val = getattr(s, "discount_amount", Decimal("0.00"))
            self.table.setItem(r, 9, QTableWidgetItem(format_currency(disc_val)))
            self.table.setItem(r, 10, QTableWidgetItem(format_currency(s.total_amount)))

            # Batch / Allocations column
            if s.allocations:
                alloc_str = ", ".join([
                    f"{a.batch.batch_number if a.batch else f'Batch #{a.batch_id}'} ({format_weight(a.net_weight_kg)})"
                    for a in s.allocations
                ])
                item_batch = QTableWidgetItem(f"🔀 Split ({len(s.allocations)}): {alloc_str}")
                item_batch.setToolTip("Multi-Batch Allocations:\n" + "\n".join([
                    f"• {a.batch.batch_number if a.batch else f'Batch #{a.batch_id}'}: Net {format_weight(a.net_weight_kg)}, Boxes: {getattr(a, 'box_count', 0)}"
                    for a in s.allocations
                ]))
                item_batch.setForeground(Qt.darkBlue)
            elif hasattr(s, "batch") and s.batch:
                alloc_str = s.batch.batch_number
                item_batch = QTableWidgetItem(alloc_str)
                item_batch.setToolTip(f"Single Batch: {alloc_str}")
            else:
                item_batch = QTableWidgetItem("-")

            self.table.setItem(r, 11, item_batch)

            # Actions column with Return, Edit, and Delete buttons
            action_widget = QWidget()
            act_box = QHBoxLayout(action_widget)
            act_box.setContentsMargins(4, 2, 4, 2)
            act_box.setSpacing(6)
            act_box.setAlignment(Qt.AlignCenter)

            ret_btn = QPushButton("🔁 Return")
            ret_btn.setProperty("class", "actionReturn")
            ret_btn.setToolTip("Record customer return against this sale")
            ret_btn.clicked.connect(lambda _, sale_id=s.id: self._open_sale_return(sale_id))
            act_box.addWidget(ret_btn)

            edit_btn = QPushButton("✏️ Edit")
            edit_btn.setProperty("class", "actionEdit")
            edit_btn.setToolTip("Edit rate, weights, or discount")
            edit_btn.clicked.connect(lambda _, sale_obj=s: self._edit_sale(sale_obj))
            act_box.addWidget(edit_btn)

            del_btn = QPushButton("🗑️ Delete")
            del_btn.setProperty("class", "actionDelete")
            del_btn.setToolTip("Delete this sale record")
            del_btn.clicked.connect(lambda _, sale_id=s.id: self._delete_sale_by_id(sale_id))
            act_box.addWidget(del_btn)

            self.table.setCellWidget(r, 12, action_widget)

    def _open_sale_return(self, sale_id: int):
        dlg = QuickSaleReturnDialog(sale_id=sale_id, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._load_batches()
            self.refresh_table()

    def _edit_sale(self, sale):
        dlg = EditSaleDialog(sale=sale, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                SalesService.update_sale(sale_id=sale.id, **data)
                QMessageBox.information(self, "Success", f"Sale #{sale.id} updated successfully!")
                self.refresh_table()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update sale: {str(e)}")

    def _delete_sale_by_id(self, sale_id: int):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete sale record #{sale_id}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                SalesService.soft_delete_sale(sale_id)
                self._load_batches()
                self.refresh_table()
                QMessageBox.information(self, "Success", f"Sale #{sale_id} deleted successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete sale: {str(e)}")

    def _delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selection Required", "Please select a sale row to delete.")
            return

        sale_id = int(self.table.item(row, 0).text())
        self._delete_sale_by_id(sale_id)
