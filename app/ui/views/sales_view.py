from datetime import date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QComboBox,
    QDoubleSpinBox, QLineEdit, QDateEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QFormLayout, QTextEdit
)
from PySide6.QtCore import Qt, QDate
from app.services.master_service import MasterService
from app.services.sales_service import SalesService
from app.services.setting_service import SettingService
from app.ui.components.date_range_picker import DateRangePicker
from app.utils.decimal_utils import format_currency, format_weight, round_weight, to_decimal

class EditSaleDialog(QDialog):
    """
    Dialog for Editing an Existing Sale (e.g. applying a discount later to a past sale).
    """
    def __init__(self, sale, parent=None):
        super().__init__(parent)
        self.sale = sale
        self.setWindowTitle(f"Edit Sale #{sale.id} & Apply Discount")
        self.resize(500, 420)

        layout = QFormLayout(self)

        q_date = QDate(sale.transaction_date.year, sale.transaction_date.month, sale.transaction_date.day)
        self.date_edit = QDateEdit(q_date)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        self.customer_combo = QComboBox()
        for c in MasterService.get_all_customers():
            self.customer_combo.addItem(c.name, c.id)
        # Select current customer
        idx = self.customer_combo.findData(sale.customer_id)
        if idx >= 0:
            self.customer_combo.setCurrentIndex(idx)

        self.item_combo = QComboBox()
        for i in MasterService.get_all_items():
            self.item_combo.addItem(i.name, i.id)
        idx_i = self.item_combo.findData(sale.item_id)
        if idx_i >= 0:
            self.item_combo.setCurrentIndex(idx_i)

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
            "gross_weight_kg": self.gross_spin.value(),
            "box_weight_kg": self.box_spin.value(),
            "rate_per_kg": self.rate_spin.value(),
            "discount_amount": self.disc_spin.value(),
            "notes": self.notes_edit.toPlainText().strip() or None
        }

class SalesView(QWidget):
    """
    Sales Management View supporting discount entry and retroactive discount editing.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
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
        self.item_combo = QComboBox()

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

        form_layout.addWidget(QLabel("Date:", self), 0, 0)
        form_layout.addWidget(self.date_edit, 0, 1)
        form_layout.addWidget(QLabel("Customer:", self), 0, 2)
        form_layout.addWidget(self.customer_combo, 0, 3)
        form_layout.addWidget(QLabel("Item / Chicken:", self), 0, 4)
        form_layout.addWidget(self.item_combo, 0, 5)

        form_layout.addWidget(QLabel("Gross Weight (KG):", self), 1, 0)
        form_layout.addWidget(self.gross_spin, 1, 1)
        form_layout.addWidget(QLabel("Box Weight (KG):", self), 1, 2)
        form_layout.addWidget(self.box_spin, 1, 3)
        form_layout.addWidget(QLabel("<b>Net Weight (AUTO):</b>", self), 1, 4)
        form_layout.addWidget(self.net_edit, 1, 5)

        form_layout.addWidget(QLabel("Rate (₹/KG):", self), 2, 0)

        rate_container = QWidget()
        rate_box = QHBoxLayout(rate_container)
        rate_box.setContentsMargins(0, 0, 0, 0)
        rate_box.setSpacing(6)
        rate_box.addWidget(self.rate_spin)

        reset_rate_btn = QPushButton("↺ Main Rate")
        reset_rate_btn.setToolTip("Reset rate to current Main Chicken Rate set in Dashboard")
        reset_rate_btn.setProperty("class", "secondaryBtn")
        reset_rate_btn.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        reset_rate_btn.clicked.connect(lambda: self.apply_default_rate(force=True))
        rate_box.addWidget(reset_rate_btn)

        form_layout.addWidget(rate_container, 2, 1)
        form_layout.addWidget(QLabel("Discount (₹):", self), 2, 2)
        form_layout.addWidget(self.disc_spin, 2, 3)
        form_layout.addWidget(QLabel("<b>Final Amount (AUTO):</b>", self), 2, 4)
        form_layout.addWidget(self.amount_edit, 2, 5)

        form_layout.addWidget(QLabel("Notes:", self), 3, 0)
        form_layout.addWidget(self.notes_edit, 3, 1, 1, 3)
        form_layout.addWidget(save_btn, 3, 5)

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

        # Sales History Table
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Date", "Customer", "Item", "Gross (KG)", "Box (KG)", "Net (KG)", "Rate (₹/KG)", "Discount (₹)", "Final Amount", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.load_combos()
        self.apply_default_rate(force=True)
        self.refresh_table()

    def apply_default_rate(self, force: bool = False):
        """Fills the rate input with the daily main chicken rate from SettingService."""
        main_rate = float(SettingService.get_main_chicken_rate())
        if force or self.rate_spin.value() == 0.0:
            self.rate_spin.setValue(main_rate)
            self._calculate_net_and_amount()

    def on_view_activated(self):
        """Called automatically when navigating to the Sales tab."""
        self.load_combos()
        # If no gross weight has been typed yet, keep rate synced with latest dashboard rate
        if self.gross_spin.value() == 0.0:
            self.apply_default_rate(force=True)
        self.refresh_table()

    def load_combos(self):
        self.customer_combo.clear()
        for c in MasterService.get_all_customers():
            self.customer_combo.addItem(c.name, c.id)

        self.item_combo.clear()
        for i in MasterService.get_all_items():
            self.item_combo.addItem(i.name, i.id)

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

        if gross <= 0:
            QMessageBox.warning(self, "Validation Error", "Gross weight must be greater than 0.")
            return
        if box > gross:
            QMessageBox.warning(self, "Validation Error", "Box weight CANNOT be greater than gross weight.")
            return

        q_date = self.date_edit.date()
        t_date = date(q_date.year(), q_date.month(), q_date.day())

        try:
            SalesService.create_sale(
                transaction_date=t_date,
                customer_id=c_id,
                item_id=i_id,
                gross_weight_kg=gross,
                box_weight_kg=box,
                rate_per_kg=rate,
                discount_amount=disc,
                notes=self.notes_edit.text()
            )
            QMessageBox.information(self, "Success", "Sale transaction saved successfully!")
            self.gross_spin.setValue(0.0)
            self.box_spin.setValue(0.0)
            self.apply_default_rate(force=True)
            self.disc_spin.setValue(0.0)
            self.notes_edit.clear()
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
            self.table.setItem(r, 4, QTableWidgetItem(format_weight(s.gross_weight_kg)))
            self.table.setItem(r, 5, QTableWidgetItem(format_weight(s.box_weight_kg)))
            self.table.setItem(r, 6, QTableWidgetItem(format_weight(s.net_weight_kg)))
            self.table.setItem(r, 7, QTableWidgetItem(format_currency(s.rate_per_kg)))
            
            disc_val = getattr(s, "discount_amount", Decimal("0.00"))
            self.table.setItem(r, 8, QTableWidgetItem(format_currency(disc_val)))
            self.table.setItem(r, 9, QTableWidgetItem(format_currency(s.total_amount)))

            # Actions column with Edit / Apply Discount button
            action_widget = QWidget()
            act_box = QHBoxLayout(action_widget)
            act_box.setContentsMargins(0, 0, 0, 0)
            act_box.setSpacing(4)

            edit_btn = QPushButton("Edit / Discount")
            edit_btn.setProperty("class", "secondaryBtn")
            edit_btn.clicked.connect(lambda _, sale_obj=s: self._edit_sale(sale_obj))

            act_box.addWidget(edit_btn)
            self.table.setCellWidget(r, 10, action_widget)

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

    def _delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selection Required", "Please select a sale row to delete.")
            return

        sale_id = int(self.table.item(row, 0).text())
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete sale record #{sale_id}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            SalesService.soft_delete_sale(sale_id)
            self.refresh_table()
