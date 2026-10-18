# Chicken Wholesale Shop Management Desktop Application

A production-quality, cross-platform Python desktop application (**PySide6 / Qt6 + SQLite + SQLAlchemy**) built for managing daily chicken wholesale business operations.

---

## 1. Features & Business Capabilities

* **Purchases Management**: Record chicken purchases from providers (Weight in KG, Rate in ₹/KG, Total Amount). Enforces mandatory **Voucher Numbers** for CASH payments and optional bank references for BANK payments.
* **Sales Management**: Record sales to customers with automatic **Net Weight** computation (`Net Weight = Gross Weight - Box Weight`) and automatic amount computation (`Net Weight × Rate`). Prevents invalid box weight (`Box Weight > Gross Weight`).
* **Reports Hub Statements & Analytics**:
  * **Customer-Facing Statement**: Displays Date, Item/Description, Net Weight, Rate, Sale Amount (occurred), Customer Discount, Amount Received, and Running Balance. Positive/negative amounts are completely separated into dedicated accounting columns. **Box Weight is strictly hidden**.
  * **Provider Statement (Supplier-Facing)**: Displays Date, Item/Description, Weight in KG, Rate in ₹/KG, Purchase Amount (occurred), Amount Paid, and Running Balance.
  * **Internal Shop Sales Report**: Displays Gross Weight, Box Weight, Net Weight, Rate, Discounts, and Final Amount for internal shop calculations.
  * **Weight Loss Analysis**: Analyzes chicken weight discrepancy between purchases and net sales.
* **Customer & Provider Accounting**:
  * Track master records and initial **Opening Balances**.
  * Chronological ledger with period-based opening balance calculations (calculates accurate opening balance as of any selected start date by aggregating all prior sales/purchases and payments).
* **Payment Voucher Scoping**: Separate payment tables for Customer Payment Vouchers and Purchase Payment Vouchers. Global voucher search lookup.
* **Stock Weight Loss Analysis**:
  * `Weight Loss (KG) = Total Purchased Weight (KG) - Total Sold Net Weight (KG)`
  * `Weight Loss (%) = (Weight Loss KG / Total Purchased Weight KG) × 100`
* **Executive Dashboard**: Real-time KPI metric cards (Purchases, Sales, Payments Received, Weight Loss %, Total Receivables, Total Payables) with interactive date range filtering (Today, Yesterday, This Week, Previous Week, This Month, Previous Month, Custom Range).
* **Database Backup & Restore**: Safe SQLite online backup and restore routines with pre-restore safety backups.

---

## 2. Technology Stack & Project Structure

* **UI Framework**: PySide6 (Qt for Python) with custom QSS theme styling.
* **Database & ORM**: SQLite with SQLAlchemy 2.0 (configured with Write-Ahead Logging `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON`).
* **Decimal Safety**: All monetary values use 2 decimal places (`Decimal('0.00')`); all weights use 3 decimal places (`Decimal('0.000')` for gram precision).

```
app/
├── config/
│   └── settings.py           # Cross-platform AppDirs data path resolution
├── database/
│   ├── base.py               # Declarative base & Timestamp/SoftDelete mixins
│   ├── connection.py         # Engine, session factory & WAL configuration
│   ├── models.py             # SQLAlchemy models
│   └── repositories/         # Repository pattern data access layer
├── domain/
│   ├── models.py             # Domain DTOs
│   ├── accounting.py         # Financial ledger & period balance calculation engine
│   └── weight_loss.py        # Stock weight loss calculation engine
├── services/                 # Business logic service wrappers
├── ui/                       # PySide6 desktop views, sidebar navigation & widgets
└── utils/                    # Decimal currency/weight formatters & date helpers
```

---

## 3. macOS Development Setup

1. **Clone or Open Repository**:
   ```bash
   cd /path/to/mujeeb's_app
   ```

2. **Create and Activate Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Sample Data Generator (Optional)**:
   ```bash
   PYTHONPATH=. python3 seed_data.py
   ```

5. **Launch the Desktop Application**:
   ```bash
   PYTHONPATH=. python3 app/main.py
   ```

---

## 4. Running Automated Tests

Run the complete `pytest` test suite:

```bash
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
```

Test coverage includes:
- Net weight and box weight validation (`Box > Gross` rejection)
- Amount auto-calculation (`Net Weight × Rate`)
- Mandatory cash voucher rules & optional bank references
- Period-based opening balance calculations
- Customer & provider ledger chronological tracking
- Stock weight loss & percentage math
- Database backup and restore integrity

---

## 5. Building Windows Executable (.exe)

The application is fully cross-platform and can be packaged into a standalone `.exe` on a Windows machine:

1. **On Windows**, open Command Prompt / PowerShell in the project directory:
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run PyInstaller using the included spec file**:
   ```cmd
   pyinstaller ChickenWholesale.spec --noconfirm
   ```

3. The compiled executable will be generated at:
   ```
   dist\ChickenWholesale.exe
   ```

---

## 6. Database Location & Backup

* **macOS Database Path**:
  `~/Library/Application Support/ChickenWholesale/chicken_wholesale.db`
* **Windows Database Path**:
  `%APPDATA%\ChickenWholesale\chicken_wholesale.db`

### Backup & Restore
* Open **Settings & Backup** from the sidebar navigation.
* Click **Create Database Backup...** to export a copy of the database.
* Click **Restore Database from File...** to restore a previous backup. A safety pre-restore copy is created automatically before any restore operation.
