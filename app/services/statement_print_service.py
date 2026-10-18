from datetime import datetime
from decimal import Decimal
from typing import Union, Optional
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from PySide6.QtGui import QTextDocument, QPageLayout
from PySide6.QtCore import QMarginsF
from app.domain.models import CustomerStatement, ProviderStatement
from app.utils.decimal_utils import format_currency, format_weight

class StatementPrintService:
    """
    Service for generating print-ready HTML statements and handling
    system printing and PDF export routines.
    """

    @staticmethod
    def generate_customer_statement_html(stmt: CustomerStatement) -> str:
        """Generates clean, professional print-ready HTML for a customer statement."""
        total_discount = sum(
            (entry.discount_amount for entry in stmt.ledger_entries if entry.discount_amount),
            Decimal("0.00")
        )
        now_str = datetime.now().strftime("%d/%m/%Y %I:%M %p")
        start_str = stmt.start_date.strftime("%d/%m/%Y")
        end_str = stmt.end_date.strftime("%d/%m/%Y")

        rows_html = []
        # Row 0: Opening Balance
        rows_html.append(f"""
            <tr style="background-color: #f1f5f9; font-weight: bold;">
                <td style="text-align: center;">{start_str}</td>
                <td>OPENING BALANCE</td>
                <td style="text-align: right;">-</td>
                <td style="text-align: right;">-</td>
                <td style="text-align: right;">-</td>
                <td style="text-align: right;">-</td>
                <td style="text-align: right;">-</td>
                <td style="text-align: right;">{format_currency(stmt.period_opening_balance)}</td>
            </tr>
        """)

        for entry in stmt.ledger_entries[1:]:
            d_str = entry.entry_date.strftime("%d/%m/%Y")
            desc = entry.description or "-"
            w_str = format_weight(entry.net_weight_kg) if entry.net_weight_kg else "-"
            r_str = format_currency(entry.rate_per_kg) if entry.rate_per_kg else "-"

            if entry.transaction_type == "SALE" or entry.debit > 0:
                disc = entry.discount_amount or Decimal("0.00")
                if entry.net_weight_kg and entry.rate_per_kg:
                    gross_sale = entry.net_weight_kg * entry.rate_per_kg
                else:
                    gross_sale = entry.debit + disc

                sale_str = format_currency(gross_sale)
                disc_str = format_currency(disc) if disc > 0 else "-"
                rec_str = "-"
            elif entry.transaction_type == "PAYMENT_RECEIVED" or entry.credit > 0:
                sale_str = "-"
                disc_str = "-"
                rec_str = format_currency(entry.credit)
            else:
                sale_str = "-"
                disc_str = "-"
                rec_str = "-"

            bal_str = format_currency(entry.running_balance)

            rows_html.append(f"""
                <tr>
                    <td style="text-align: center;">{d_str}</td>
                    <td>{desc}</td>
                    <td style="text-align: right;">{w_str}</td>
                    <td style="text-align: right;">{r_str}</td>
                    <td style="text-align: right;">{sale_str}</td>
                    <td style="text-align: right;">{disc_str}</td>
                    <td style="text-align: right;">{rec_str}</td>
                    <td style="text-align: right; font-weight: 500;">{bal_str}</td>
                </tr>
            """)

        # Totals footer row
        total_disc_cell = format_currency(total_discount) if total_discount > 0 else "-"
        rows_html.append(f"""
            <tr style="background-color: #e2e8f0; font-weight: bold; border-top: 2px solid #0f172a;">
                <td colspan="2" style="text-align: center;">TOTALS / SUMMARY</td>
                <td style="text-align: right;">{format_weight(stmt.total_net_weight_kg)}</td>
                <td style="text-align: right;">-</td>
                <td style="text-align: right;">{format_currency(stmt.total_sales_amount + total_discount)}</td>
                <td style="text-align: right;">{total_disc_cell}</td>
                <td style="text-align: right;">{format_currency(stmt.total_payments)}</td>
                <td style="text-align: right; color: #1e3a8a;">{format_currency(stmt.closing_balance)}</td>
            </tr>
        """)

        tbody_html = "".join(rows_html)

        disc_summary_row = ""
        if total_discount > 0:
            disc_summary_row = f"""
                <tr>
                    <td style="color: #475569;">Total Discounts Given:</td>
                    <td style="text-align: right; font-weight: bold; color: #dc2626;">- {format_currency(total_discount)}</td>
                </tr>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                color: #0f172a;
                font-size: 9pt;
                line-height: 1.35;
                margin: 0;
                padding: 0;
            }}
            .header-banner {{
                border-bottom: 2px solid #0f172a;
                padding-bottom: 8px;
                margin-bottom: 12px;
            }}
            .company-name {{
                font-size: 16pt;
                font-weight: bold;
                color: #0f172a;
                letter-spacing: 0.5px;
            }}
            .company-tagline {{
                font-size: 8pt;
                color: #475569;
            }}
            .statement-title {{
                font-size: 12pt;
                font-weight: bold;
                color: #1e40af;
                text-align: right;
            }}
            .info-table {{
                width: 100%;
                margin-bottom: 12px;
            }}
            .summary-box {{
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 8px 12px;
                margin-bottom: 14px;
            }}
            .summary-box table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .summary-box td {{
                padding: 3px 6px;
                font-size: 8.5pt;
            }}
            table.data-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 6px;
                margin-bottom: 16px;
            }}
            table.data-table th {{
                background-color: #1e293b;
                color: #ffffff;
                border: 1px solid #0f172a;
                padding: 5px 6px;
                font-size: 8pt;
                font-weight: 600;
                text-transform: uppercase;
            }}
            table.data-table td {{
                border: 1px solid #cbd5e1;
                padding: 4px 6px;
                font-size: 8pt;
            }}
            table.data-table tr:nth-child(even) {{
                background-color: #f8fafc;
            }}
            .footer-table {{
                width: 100%;
                margin-top: 25px;
                border-top: 1px dashed #cbd5e1;
                padding-top: 10px;
                font-size: 8pt;
                color: #64748b;
            }}
        </style>
        </head>
        <body>
            <div class="header-banner">
                <table style="width: 100%;">
                    <tr>
                        <td style="vertical-align: top;">
                            <div class="company-name">🐔 CHICKEN WHOLESALE</div>
                            <div class="company-tagline">Wholesale Distribution & Farm Supplies</div>
                        </td>
                        <td style="vertical-align: top; text-align: right;">
                            <div class="statement-title">CUSTOMER STATEMENT</div>
                            <div style="font-size: 8pt; color: #64748b;">Period: {start_str} to {end_str}</div>
                            <div style="font-size: 7.5pt; color: #94a3b8;">Printed on: {now_str}</div>
                        </td>
                    </tr>
                </table>
            </div>

            <table class="info-table">
                <tr>
                    <td style="width: 60%; vertical-align: top;">
                        <div style="font-size: 10pt; font-weight: bold; color: #0f172a;">{stmt.customer_name.upper()}</div>
                        <div>Phone: {stmt.phone or 'N/A'}</div>
                        <div>Address: {stmt.address or 'N/A'}</div>
                    </td>
                    <td style="width: 40%; vertical-align: top;">
                        <div class="summary-box">
                            <table>
                                <tr>
                                    <td style="color: #475569;">Opening Balance:</td>
                                    <td style="text-align: right; font-weight: bold;">{format_currency(stmt.period_opening_balance)}</td>
                                </tr>
                                <tr>
                                    <td style="color: #475569;">Total Sales ({format_weight(stmt.total_net_weight_kg)}):</td>
                                    <td style="text-align: right; font-weight: bold;">{format_currency(stmt.total_sales_amount)}</td>
                                </tr>
                                {disc_summary_row}
                                <tr>
                                    <td style="color: #475569;">Total Payments Received:</td>
                                    <td style="text-align: right; font-weight: bold; color: #15803d;">{format_currency(stmt.total_payments)}</td>
                                </tr>
                                <tr style="border-top: 1px solid #cbd5e1; background-color: #f0fdf4;">
                                    <td style="font-weight: bold; color: #166534;">Outstanding / Closing:</td>
                                    <td style="text-align: right; font-weight: bold; color: #166534; font-size: 9.5pt;">{format_currency(stmt.closing_balance)}</td>
                                </tr>
                            </table>
                        </div>
                    </td>
                </tr>
            </table>

            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width: 10%; text-align: center;">Date</th>
                        <th style="width: 25%; text-align: left;">Item / Description</th>
                        <th style="width: 11%; text-align: right;">Net Wt (KG)</th>
                        <th style="width: 10%; text-align: right;">Rate (₹)</th>
                        <th style="width: 12%; text-align: right;">Sale Amt (₹)</th>
                        <th style="width: 10%; text-align: right;">Discount (₹)</th>
                        <th style="width: 11%; text-align: right;">Received (₹)</th>
                        <th style="width: 11%; text-align: right;">Balance (₹)</th>
                    </tr>
                </thead>
                <tbody>
                    {tbody_html}
                </tbody>
            </table>

            <table class="footer-table">
                <tr>
                    <td style="width: 60%; vertical-align: bottom;">
                        <i>* Note: Box weight is strictly deducted for all wholesale client billing.</i><br>
                        Thank you for your business!
                    </td>
                    <td style="width: 40%; text-align: right; vertical-align: bottom;">
                        <br><br>
                        ____________________________<br>
                        <b>Authorized Signatory</b>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    @staticmethod
    def generate_provider_statement_html(stmt: ProviderStatement) -> str:
        """Generates clean, professional print-ready HTML for a provider statement."""
        now_str = datetime.now().strftime("%d/%m/%Y %I:%M %p")
        start_str = stmt.start_date.strftime("%d/%m/%Y")
        end_str = stmt.end_date.strftime("%d/%m/%Y")

        rows_html = []
        # Row 0: Opening Balance
        rows_html.append(f"""
            <tr style="background-color: #f1f5f9; font-weight: bold;">
                <td style="text-align: center;">{start_str}</td>
                <td>OPENING BALANCE</td>
                <td style="text-align: right;">-</td>
                <td style="text-align: right;">-</td>
                <td style="text-align: right;">-</td>
                <td style="text-align: right;">-</td>
                <td style="text-align: right;">{format_currency(stmt.period_opening_balance)}</td>
            </tr>
        """)

        for entry in stmt.ledger_entries[1:]:
            d_str = entry.entry_date.strftime("%d/%m/%Y")
            desc = entry.description or "-"
            w_str = format_weight(entry.net_weight_kg) if entry.net_weight_kg else "-"
            r_str = format_currency(entry.rate_per_kg) if entry.rate_per_kg else "-"

            if entry.transaction_type == "PURCHASE" or entry.credit > 0:
                pur_str = format_currency(entry.credit)
                paid_str = "-"
            elif entry.transaction_type == "PAYMENT_MADE" or entry.debit > 0:
                pur_str = "-"
                paid_str = format_currency(entry.debit)
            else:
                pur_str = "-"
                paid_str = "-"

            bal_str = format_currency(entry.running_balance)

            rows_html.append(f"""
                <tr>
                    <td style="text-align: center;">{d_str}</td>
                    <td>{desc}</td>
                    <td style="text-align: right;">{w_str}</td>
                    <td style="text-align: right;">{r_str}</td>
                    <td style="text-align: right;">{pur_str}</td>
                    <td style="text-align: right;">{paid_str}</td>
                    <td style="text-align: right; font-weight: 500;">{bal_str}</td>
                </tr>
            """)

        # Totals footer row
        rows_html.append(f"""
            <tr style="background-color: #e2e8f0; font-weight: bold; border-top: 2px solid #0f172a;">
                <td colspan="2" style="text-align: center;">TOTALS / SUMMARY</td>
                <td style="text-align: right;">{format_weight(stmt.total_purchase_weight_kg)}</td>
                <td style="text-align: right;">-</td>
                <td style="text-align: right;">{format_currency(stmt.total_purchases_amount)}</td>
                <td style="text-align: right;">{format_currency(stmt.total_payments)}</td>
                <td style="text-align: right; color: #1e3a8a;">{format_currency(stmt.closing_balance)}</td>
            </tr>
        """)

        tbody_html = "".join(rows_html)

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                color: #0f172a;
                font-size: 9pt;
                line-height: 1.35;
                margin: 0;
                padding: 0;
            }}
            .header-banner {{
                border-bottom: 2px solid #0f172a;
                padding-bottom: 8px;
                margin-bottom: 12px;
            }}
            .company-name {{
                font-size: 16pt;
                font-weight: bold;
                color: #0f172a;
                letter-spacing: 0.5px;
            }}
            .company-tagline {{
                font-size: 8pt;
                color: #475569;
            }}
            .statement-title {{
                font-size: 12pt;
                font-weight: bold;
                color: #1e40af;
                text-align: right;
            }}
            .info-table {{
                width: 100%;
                margin-bottom: 12px;
            }}
            .summary-box {{
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 8px 12px;
                margin-bottom: 14px;
            }}
            .summary-box table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .summary-box td {{
                padding: 3px 6px;
                font-size: 8.5pt;
            }}
            table.data-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 6px;
                margin-bottom: 16px;
            }}
            table.data-table th {{
                background-color: #1e293b;
                color: #ffffff;
                border: 1px solid #0f172a;
                padding: 5px 6px;
                font-size: 8pt;
                font-weight: 600;
                text-transform: uppercase;
            }}
            table.data-table td {{
                border: 1px solid #cbd5e1;
                padding: 4px 6px;
                font-size: 8pt;
            }}
            table.data-table tr:nth-child(even) {{
                background-color: #f8fafc;
            }}
            .footer-table {{
                width: 100%;
                margin-top: 25px;
                border-top: 1px dashed #cbd5e1;
                padding-top: 10px;
                font-size: 8pt;
                color: #64748b;
            }}
        </style>
        </head>
        <body>
            <div class="header-banner">
                <table style="width: 100%;">
                    <tr>
                        <td style="vertical-align: top;">
                            <div class="company-name">🐔 CHICKEN WHOLESALE</div>
                            <div class="company-tagline">Wholesale Distribution & Farm Supplies</div>
                        </td>
                        <td style="vertical-align: top; text-align: right;">
                            <div class="statement-title">PROVIDER ACCOUNT STATEMENT</div>
                            <div style="font-size: 8pt; color: #64748b;">Period: {start_str} to {end_str}</div>
                            <div style="font-size: 7.5pt; color: #94a3b8;">Printed on: {now_str}</div>
                        </td>
                    </tr>
                </table>
            </div>

            <table class="info-table">
                <tr>
                    <td style="width: 60%; vertical-align: top;">
                        <div style="font-size: 10pt; font-weight: bold; color: #0f172a;">{stmt.provider_name.upper()}</div>
                        <div>Phone: {stmt.phone or 'N/A'}</div>
                        <div>Address: {stmt.address or 'N/A'}</div>
                    </td>
                    <td style="width: 40%; vertical-align: top;">
                        <div class="summary-box">
                            <table>
                                <tr>
                                    <td style="color: #475569;">Opening Balance:</td>
                                    <td style="text-align: right; font-weight: bold;">{format_currency(stmt.period_opening_balance)}</td>
                                </tr>
                                <tr>
                                    <td style="color: #475569;">Total Purchases ({format_weight(stmt.total_purchase_weight_kg)}):</td>
                                    <td style="text-align: right; font-weight: bold;">{format_currency(stmt.total_purchases_amount)}</td>
                                </tr>
                                <tr>
                                    <td style="color: #475569;">Total Payments Made:</td>
                                    <td style="text-align: right; font-weight: bold; color: #15803d;">{format_currency(stmt.total_payments)}</td>
                                </tr>
                                <tr style="border-top: 1px solid #cbd5e1; background-color: #eff6ff;">
                                    <td style="font-weight: bold; color: #1d4ed8;">Payable / Closing Balance:</td>
                                    <td style="text-align: right; font-weight: bold; color: #1d4ed8; font-size: 9.5pt;">{format_currency(stmt.closing_balance)}</td>
                                </tr>
                            </table>
                        </div>
                    </td>
                </tr>
            </table>

            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width: 12%; text-align: center;">Date</th>
                        <th style="width: 32%; text-align: left;">Item / Description</th>
                        <th style="width: 14%; text-align: right;">Weight (KG)</th>
                        <th style="width: 12%; text-align: right;">Rate (₹)</th>
                        <th style="width: 15%; text-align: right;">Purchase Amt (₹)</th>
                        <th style="width: 15%; text-align: right;">Amount Paid (₹)</th>
                        <th style="width: 15%; text-align: right;">Balance (₹)</th>
                    </tr>
                </thead>
                <tbody>
                    {tbody_html}
                </tbody>
            </table>

            <table class="footer-table">
                <tr>
                    <td style="width: 60%; vertical-align: bottom;">
                        <i>Computer generated supplier statement.</i>
                    </td>
                    <td style="width: 40%; text-align: right; vertical-align: bottom;">
                        <br><br>
                        ____________________________<br>
                        <b>Authorized Signatory</b>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    @classmethod
    def print_statement(cls, stmt: Union[CustomerStatement, ProviderStatement], parent=None, is_provider: bool = False):
        """
        Opens Print Preview Dialog allowing inspection, printer selection, and printing.
        """
        html = cls.generate_provider_statement_html(stmt) if is_provider else cls.generate_customer_statement_html(stmt)

        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)

        doc = QTextDocument()
        doc.setHtml(html)

        dialog = QPrintPreviewDialog(printer, parent)
        title = f"Print Statement — {stmt.provider_name if is_provider else stmt.customer_name}"
        dialog.setWindowTitle(title)
        dialog.resize(950, 750)
        dialog.paintRequested.connect(doc.print_)
        dialog.exec()

    @classmethod
    def export_pdf(cls, stmt: Union[CustomerStatement, ProviderStatement], parent=None, is_provider: bool = False) -> Optional[str]:
        """
        Interactive Save-As PDF dialog and generator.
        """
        name = stmt.provider_name if is_provider else stmt.customer_name
        sanitized_name = "".join(c if c.isalnum() else "_" for c in name).strip("_")
        default_filename = f"{'Provider' if is_provider else 'Customer'}_Statement_{sanitized_name}_{stmt.start_date.strftime('%Y%m%d')}_{stmt.end_date.strftime('%Y%m%d')}.pdf"

        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            "Save Statement as PDF",
            default_filename,
            "PDF Files (*.pdf)"
        )

        if not file_path:
            return None

        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

        html = cls.generate_provider_statement_html(stmt) if is_provider else cls.generate_customer_statement_html(stmt)

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)

        doc = QTextDocument()
        doc.setHtml(html)
        doc.print_(printer)

        if parent:
            QMessageBox.information(
                parent,
                "PDF Exported",
                f"Statement exported successfully to:\n{file_path}"
            )

        return file_path
