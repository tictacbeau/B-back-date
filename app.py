import sys
import os
import json
import datetime
import math
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QFileDialog,
    QDialog, QComboBox, QFormLayout, QDialogButtonBox, QMessageBox,
    QFrame, QTextEdit, QDateEdit, QHeaderView
)
from PyQt6.QtGui import QIcon, QClipboard

import parser_utils
import data_handler

# Constants for config saving
CONFIG_FILE = "rule_config.json"

class MappingDialog(QDialog):
    """
    Dialog prompting user to map input file columns to the standard expected fields.
    """
    def __init__(self, file_columns, auto_guesses, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Map Bank Report Columns")
        self.setMinimumWidth(400)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f1f5f9;
            }
            QLabel {
                color: #e2e8f0;
                font-weight: bold;
            }
            QComboBox {
                background-color: #1e293b;
                color: #f1f5f9;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 6px;
                min-width: 200px;
            }
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        self.info_label = QLabel("We identified the columns below. Please map them to standard fields:")
        self.info_label.setStyleSheet("font-weight: normal; margin-bottom: 10px; color: #94a3b8;")
        self.layout.addWidget(self.info_label)
        
        self.form_layout = QFormLayout()
        self.dropdowns = {}
        
        # Define fields
        self.fields = [
            (data_handler.FIELD_TX_DATE, True),
            (data_handler.FIELD_VALUE, True),
            (data_handler.FIELD_COUNTERPARTY, True),
            (data_handler.FIELD_CATEGORY, False),
            (data_handler.FIELD_CLEAR_DATE, True)
        ]
        
        # Populating columns option list
        combobox_options = [""] + file_columns
        
        for field, required in self.fields:
            cb = QComboBox()
            cb.addItems(combobox_options)
            
            # Select auto-guess if possible
            guessed_col = auto_guesses.get(field)
            if guessed_col in file_columns:
                cb.setCurrentIndex(file_columns.index(guessed_col) + 1)
                
            label_text = f"{field} *" if required else field
            self.form_layout.addRow(QLabel(label_text), cb)
            self.dropdowns[field] = cb
            
        self.layout.addLayout(self.form_layout)
        
        # Confirm / Cancel buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        
        self.layout.addWidget(self.buttons)
        
    def validate_and_accept(self):
        # Validate that required fields are selected
        mappings = {}
        for field, required in self.fields:
            val = self.dropdowns[field].currentText()
            if required and not val:
                QMessageBox.warning(self, "Validation Error", f"The field '{field}' is required and must be mapped.")
                return
            mappings[field] = val if val else None
            
        self.mappings = mappings
        self.accept()


class DropZone(QFrame):
    """
    Drag and drop frame that handles files, text drops, and paste (Ctrl+V).
    """
    def __init__(self, on_data_loaded_callback, parent=None):
        super().__init__(parent)
        self.on_data_loaded = on_data_loaded_callback
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.set_style_normal()
        
        self.layout = QVBoxLayout(self)
        self.label = QLabel("Drag & Drop email file (.eml, .txt, .html) here\nOR paste email content (Ctrl+V)", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #94a3b8; font-size: 14px; font-weight: bold;")
        self.layout.addWidget(self.label)
        
    def set_style_normal(self):
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #475569;
                border-radius: 8px;
                background-color: #1e293b;
                min-height: 120px;
            }
        """)
        
    def set_style_active(self):
        self.setStyleSheet("""
            QFrame {
                border: 2px solid #3b82f6;
                border-radius: 8px;
                background-color: #0f172a;
                min-height: 120px;
            }
        """)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            self.set_style_active()
            event.acceptProposedAction()
            
    def dragLeaveEvent(self, event):
        self.set_style_normal()
        
    def dropEvent(self, event):
        self.set_style_normal()
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if os.path.exists(file_path):
                    self.on_data_loaded(file_path=file_path)
                    event.acceptProposedAction()
        elif event.mimeData().hasText():
            text = event.mimeData().text()
            self.on_data_loaded(text_content=text)
            event.acceptProposedAction()

    def keyPressEvent(self, event):
        # Handle Paste (Ctrl + V)
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_V:
            clipboard = QApplication.clipboard()
            text = clipboard.text()
            if text:
                self.on_data_loaded(text_content=text)
        else:
            super().keyPressEvent(event)


class ProcessDialog(QDialog):
    """
    Modal popup for processing a single line item sequentially.
    """
    def __init__(self, item_index, item_data, total_items, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.email_date = None
        self.setWindowTitle(f"Line Item {item_index + 1} of {total_items} – {item_data['Counterparty']}")
        self.setMinimumWidth(550)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f1f5f9;
            }
            QLabel {
                color: #cbd5e1;
            }
            QPushButton {
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton#btnConfirm {
                background-color: #22c55e;
                color: white;
            }
            QPushButton#btnConfirm:hover {
                background-color: #16a34a;
            }
            QPushButton#btnCancel {
                background-color: #475569;
                color: white;
            }
            QPushButton#btnCancel:hover {
                background-color: #334155;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        
        # Transaction Details Summary Cards
        details_frame = QFrame()
        details_frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 6px;
                padding: 10px;
                margin-bottom: 10px;
            }
        """)
        details_layout = QHBoxLayout(details_frame)
        
        info_text = (
            f"<b>Value:</b> {item_data['Value']} | "
            f"<b>Category:</b> {item_data['Category']}<br>"
            f"<b>Txn Date:</b> {item_data['TransactionDate']} | "
            f"<b>Clearance Date:</b> {item_data['BankClearanceDate']}"
        )
        info_label = QLabel(info_text)
        info_label.setStyleSheet("font-size: 13px; line-height: 1.4;")
        details_layout.addWidget(info_label)
        self.layout.addWidget(details_frame)
        
        # Drag & Drop Zone
        self.drop_zone = DropZone(self.load_email_data, self)
        self.layout.addWidget(self.drop_zone)
        
        # Status Label showing date extraction result
        self.status_label = QLabel("No email loaded. Drag & drop file or paste content above.")
        self.status_label.setStyleSheet("color: #94a3b8; font-style: italic; margin-top: 5px;")
        self.layout.addWidget(self.status_label)
        
        # Date selection field (for adjustments)
        self.date_layout = QHBoxLayout()
        self.date_layout.addWidget(QLabel("Extracted / Manual Email Sent Date:"))
        
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setStyleSheet("""
            QDateEdit {
                background-color: #1e293b;
                color: #f1f5f9;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        
        # Pre-fill clearance date as baseline if no date loaded
        clear_dt = datetime.datetime.strptime(item_data['BankClearanceDate'], "%Y-%m-%d") if item_data['BankClearanceDate'] else datetime.datetime.now()
        self.date_edit.setDate(QDate(clear_dt.year, clear_dt.month, clear_dt.day))
        self.date_layout.addWidget(self.date_edit)
        
        self.layout.addLayout(self.date_layout)
        
        # Buttons
        self.btn_layout = QHBoxLayout()
        self.btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_confirm = QPushButton("Confirm", self)
        self.btn_confirm.setObjectName("btnConfirm")
        self.btn_confirm.clicked.connect(self.confirm_and_accept)
        
        self.btn_layout.addWidget(self.btn_cancel)
        self.btn_layout.addWidget(self.btn_confirm)
        self.layout.addLayout(self.btn_layout)
        
    def load_email_data(self, file_path=None, text_content=None):
        dt = None
        source = ""
        if file_path:
            dt = parser_utils.extract_date_from_eml(file_path)
            source = f"file '{os.path.basename(file_path)}'"
            if not dt:
                # Fallback to reading as text if parsing fails (could be txt/html)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text_content = f.read()
                except Exception:
                    pass
        
        if not dt and text_content:
            dt = parser_utils.extract_date_from_text(text_content)
            source = "pasted/text content"
            
        if dt:
            self.email_date = dt.date()
            self.date_edit.setDate(QDate(dt.year, dt.month, dt.day))
            self.status_label.setText(f"✓ Successfully extracted date from {source}: {self.email_date}")
            self.status_label.setStyleSheet("color: #22c55e; font-weight: bold; margin-top: 5px;")
        else:
            self.status_label.setText("⚠ Could not extract date automatically. Please adjust manually.")
            self.status_label.setStyleSheet("color: #ef4444; font-weight: bold; margin-top: 5px;")
            
    def confirm_and_accept(self):
        qdate = self.date_edit.date()
        self.email_date = datetime.date(qdate.year, qdate.month, qdate.day)
        self.accept()


class RuleBuilderApp(QMainWindow):
    """
    Main application window.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Remittance Day Delta Rule Builder")
        self.setMinimumSize(1000, 700)
        
        # State variables
        self.transactions = []
        self.file_path = None
        self.columns = []
        self.mappings = {}
        
        # UI Stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #e2e8f0;
            }
            QLabel#titleLabel {
                font-size: 20px;
                font-weight: bold;
                color: #3b82f6;
            }
            QLabel#statusLabel {
                font-size: 13px;
                color: #94a3b8;
            }
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #64748b;
            }
            QPushButton#btnExport {
                background-color: #10b981;
            }
            QPushButton#btnExport:hover {
                background-color: #059669;
            }
            QPushButton#btnProcessAll {
                background-color: #f59e0b;
                color: #0f172a;
            }
            QPushButton#btnProcessAll:hover {
                background-color: #d97706;
            }
            QTableWidget {
                background-color: #1e293b;
                gridline-color: #334155;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #0f172a;
                color: #cbd5e1;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #334155;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #38bdf8;
                font-family: Consolas, monospace;
                font-size: 13px;
                padding: 8px;
            }
        """)
        
        self.init_ui()
        self.load_rule_config()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Header block
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        
        title_label = QLabel("Remittance Day Delta Rule Builder")
        title_label.setObjectName("titleLabel")
        title_box.addWidget(title_label)
        
        self.file_label = QLabel("No Bank Report Loaded")
        self.file_label.setObjectName("statusLabel")
        title_box.addWidget(self.file_label)
        
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        
        # Action Buttons
        self.btn_load = QPushButton("Load Bank Report", self)
        self.btn_load.clicked.connect(self.load_bank_report)
        header_layout.addWidget(self.btn_load)
        
        self.btn_process_all = QPushButton("Process All", self)
        self.btn_process_all.setObjectName("btnProcessAll")
        self.btn_process_all.setEnabled(False)
        self.btn_process_all.clicked.connect(self.process_all_items)
        header_layout.addWidget(self.btn_process_all)
        
        self.btn_calculate = QPushButton("Calculate Rules", self)
        self.btn_calculate.setEnabled(False)
        self.btn_calculate.clicked.connect(self.calculate_rules)
        header_layout.addWidget(self.btn_calculate)
        
        self.btn_export = QPushButton("Export Data", self)
        self.btn_export.setObjectName("btnExport")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_data)
        header_layout.addWidget(self.btn_export)
        
        main_layout.addLayout(header_layout)
        
        # Table widget to display transactions
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Action", "Transaction Date", "Value", "Counterparty",
            "Category", "Bank Clearance Date", "Email Sent Date", "Day Delta"
        ])
        
        # Enable manual editing on Email Sent Date column
        self.table.itemChanged.connect(self.handle_table_item_changed)
        
        # Set columns resize modes
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 100)
        
        main_layout.addWidget(self.table)
        
        # Lower Rule Builder box
        rule_layout = QVBoxLayout()
        rule_header_label = QLabel("Generated Remittance Lookback Rules")
        rule_header_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #3b82f6; margin-top: 10px;")
        rule_layout.addWidget(rule_header_label)
        
        self.rule_display = QTextEdit()
        self.rule_display.setReadOnly(True)
        self.rule_display.setPlaceholderText("Rule suggestions will be computed here after items are processed.")
        rule_layout.addWidget(self.rule_display)
        
        main_layout.addLayout(rule_layout)
        
    def load_bank_report(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Bank Report", "", "Excel / CSV Files (*.csv *.xlsx *.xls)"
        )
        if not file_path:
            return
            
        try:
            # Read columns
            cols = data_handler.load_file_columns(file_path)
            guesses = data_handler.guess_column_mappings(cols)
            
            # Map headers
            dlg = MappingDialog(cols, guesses, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.file_path = file_path
                self.columns = cols
                self.mappings = dlg.mappings
                
                # Load transactions
                self.transactions = data_handler.process_loaded_dataframe(file_path, self.mappings)
                
                self.file_label.setText(f"Loaded: {os.path.basename(file_path)} ({len(self.transactions)} items)")
                self.populate_table()
                
                self.btn_process_all.setEnabled(True)
                self.btn_calculate.setEnabled(True)
                self.btn_export.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"An error occurred while loading the report:\n{str(e)}")
            
    def populate_table(self):
        try:
            self.table.itemChanged.disconnect(self.handle_table_item_changed)
        except (TypeError, RuntimeError):
            pass
        
        self.table.setRowCount(len(self.transactions))
        for row_idx, tx in enumerate(self.transactions):
            # Process Button or Done Label
            if tx["Status"] == "Processed":
                status_widget = QLabel("✓ Mapped")
                status_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                status_widget.setStyleSheet("color: #22c55e; font-weight: bold;")
                self.table.setCellWidget(row_idx, 0, status_widget)
            else:
                btn = QPushButton("Process")
                btn.clicked.connect(lambda checked, idx=row_idx: self.process_single_item(idx))
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2563eb;
                        padding: 4px 8px;
                        font-size: 11px;
                        font-weight: normal;
                    }
                    QPushButton:hover {
                        background-color: #1d4ed8;
                    }
                """)
                self.table.setCellWidget(row_idx, 0, btn)
                
            # Populate text fields
            # Mapped columns
            self.table.setItem(row_idx, 1, self.make_readonly_item(tx["TransactionDate"]))
            self.table.setItem(row_idx, 2, self.make_readonly_item(tx["Value"]))
            self.table.setItem(row_idx, 3, self.make_readonly_item(tx["Counterparty"]))
            self.table.setItem(row_idx, 4, self.make_readonly_item(tx["Category"]))
            self.table.setItem(row_idx, 5, self.make_readonly_item(tx["BankClearanceDate"]))
            
            # Email date (editable)
            email_date_item = QTableWidgetItem(tx["EmailSentDate"])
            # Only enable text edit
            email_date_item.setFlags(email_date_item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row_idx, 6, email_date_item)
            
            # Day Delta (readonly)
            self.table.setItem(row_idx, 7, self.make_readonly_item(tx["DayDelta"]))
            
        self.table.itemChanged.connect(self.handle_table_item_changed)
        
    def make_readonly_item(self, val):
        item = QTableWidgetItem(str(val))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item
        
    def process_single_item(self, row_idx):
        tx = self.transactions[row_idx]
        dlg = ProcessDialog(row_idx, tx, len(self.transactions), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if dlg.email_date:
                self.update_row_date(row_idx, dlg.email_date)
                self.populate_table()
                
    def process_all_items(self):
        """
        Iterates through the rows one at a time sequentially.
        """
        processed_count = 0
        for row_idx, tx in enumerate(self.transactions):
            if tx["Status"] == "Pending":
                dlg = ProcessDialog(row_idx, tx, len(self.transactions), self)
                # Scroll to the row we are processing
                self.table.scrollToItem(self.table.item(row_idx, 1))
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    if dlg.email_date:
                        self.update_row_date(row_idx, dlg.email_date)
                        processed_count += 1
                        # Repopulate table to show current progress
                        self.populate_table()
                else:
                    # User cancelled the sequential process loop
                    break
        
        if processed_count > 0:
            self.calculate_rules()
            QMessageBox.information(self, "Processing Finished", f"Finished processing {processed_count} transaction item(s).")
            
    def update_row_date(self, row_idx, email_date):
        tx = self.transactions[row_idx]
        tx["EmailSentDate"] = email_date.strftime("%Y-%m-%d")
        
        # Calculate Delta
        if tx["BankClearanceDate"]:
            try:
                clear_dt = datetime.datetime.strptime(tx["BankClearanceDate"], "%Y-%m-%d").date()
                delta = (clear_dt - email_date).days
                tx["DayDelta"] = str(delta)
            except Exception:
                tx["DayDelta"] = ""
        else:
            tx["DayDelta"] = ""
            
        tx["Status"] = "Processed"
        
    def handle_table_item_changed(self, item):
        row_idx = item.row()
        col_idx = item.column()
        
        # Email Sent Date is column index 6
        if col_idx == 6:
            new_date_str = item.text().strip()
            tx = self.transactions[row_idx]
            
            if not new_date_str:
                tx["EmailSentDate"] = ""
                tx["DayDelta"] = ""
                tx["Status"] = "Pending"
            else:
                parsed_dt = parser_utils.parse_date_string(new_date_str)
                if parsed_dt:
                    self.update_row_date(row_idx, parsed_dt.date())
                else:
                    QMessageBox.warning(self, "Invalid Date Format", f"Failed to parse '{new_date_str}'. Please use standard format like YYYY-MM-DD.")
                    
            # Refresh to show calculated delta
            self.populate_table()
            self.calculate_rules()
            
    def calculate_rules(self):
        """
        Analyzes the day deltas of processed items and generates recommendations.
        """
        processed_txs = [t for t in self.transactions if t["Status"] == "Processed" and t["DayDelta"] != ""]
        if not processed_txs:
            self.rule_display.setText("No processed data with valid deltas yet. Process transactions to calculate rules.")
            return
            
        # Group by Category
        categories_data = {}
        for tx in processed_txs:
            cat = tx["Category"]
            if not cat:
                cat = "Standard"
            try:
                delta = int(tx["DayDelta"])
            except ValueError:
                continue
            
            if cat not in categories_data:
                categories_data[cat] = []
            categories_data[cat].append(delta)
            
        if not categories_data:
            self.rule_display.setText("Could not extract numerical deltas to calculate rules.")
            return
            
        # Check if single lookback rule applies:
        # "If no Category column or all rows have the same category -> output a single static lookback rule"
        # Let's check: if only one category exists OR all deltas by category are identical OR the user mapped no Category.
        # Wait, if Category columns was mapped, check how many unique categories there are.
        # Also, check if all categories have identical deltas.
        has_category_column = (self.mappings.get(data_handler.FIELD_CATEGORY) is not None)
        unique_categories = list(categories_data.keys())
        
        rule_lines = []
        rule_lines.append("// Generated Remittance Day Delta Rules")
        rule_lines.append(f"// Calculated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        rule_lines.append("")
        
        config_to_save = {}
        
        if not has_category_column or len(unique_categories) <= 1:
            # Single Category lookback rule
            all_deltas = []
            for deltas in categories_data.values():
                all_deltas.extend(deltas)
            
            avg_delta = sum(all_deltas) / len(all_deltas)
            max_delta = max(all_deltas)
            # suggested lookback = average delta + 2 day safety margin, capped to max observed or rounded up.
            # Let's say: Suggested Lookback = max(all_deltas) or ceil(avg_delta) + 2. Let's suggest Max Delta + 1 day to catch everything.
            suggested_lookback = max(0, max_delta)
            
            rule_text = f"Search for emails sent {suggested_lookback} days before the bank clearance date."
            
            rule_lines.append("GLOBAL LOOKBACK RULE:")
            rule_lines.append(f"  {rule_text}")
            rule_lines.append(f"  (Average Delta: {avg_delta:.1f} days, Maximum Observed Delay: {max_delta} days)")
            
            config_to_save["type"] = "single"
            config_to_save["rule"] = rule_text
            config_to_save["average_delta"] = avg_delta
            config_to_save["suggested_lookback"] = suggested_lookback
        else:
            # Multi-category lookback matrix
            rule_lines.append("CONDITIONAL REMITTANCE LOOKBACK MATRIX:")
            rule_lines.append(f"{'Category':<20} | {'Avg Delay':<10} | {'Max Delay':<10} | {'Suggested Lookback'}")
            rule_lines.append("-" * 70)
            
            category_rules = {}
            for cat, deltas in categories_data.items():
                avg_delta = sum(deltas) / len(deltas)
                max_delta = max(deltas)
                suggested = max(0, max_delta) # Safe margin captures the maximum delay observed
                rule_lines.append(f"{cat:<20} | {avg_delta:.1f} days  | {max_delta:<10} | Search emails {suggested} days before bank clearance")
                category_rules[cat] = {
                    "avg_delta": avg_delta,
                    "max_delta": max_delta,
                    "suggested_lookback": suggested
                }
            
            config_to_save["type"] = "matrix"
            config_to_save["matrix"] = category_rules
            
        rule_output = "\n".join(rule_lines)
        self.rule_display.setText(rule_output)
        
        # Save to local configuration file
        config_to_save["timestamp"] = datetime.datetime.now().isoformat()
        config_to_save["raw_text"] = rule_output
        self.save_rule_config(config_to_save)
        
    def save_rule_config(self, config_data):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            print(f"Error saving rule configuration: {e}")
            
    def load_rule_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                raw_text = config.get("raw_text", "")
                if raw_text:
                    self.rule_display.setText(raw_text)
            except Exception as e:
                print(f"Error loading rule configuration: {e}")
                
    def export_data(self):
        if not self.transactions:
            return
            
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Transaction Data", "Remittance_Deltas_Export", "CSV Files (*.csv);;Excel Files (*.xlsx)"
        )
        if not file_path:
            return
            
        # Ensure correct extension matches filter if user didn't write it
        _, ext = os.path.splitext(file_path)
        if not ext:
            if "csv" in selected_filter.lower():
                file_path += ".csv"
            else:
                file_path += ".xlsx"
                
        try:
            data_handler.export_transactions(file_path, self.transactions, self.columns, self.mappings)
            QMessageBox.information(self, "Export Successful", f"Transaction data successfully saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = RuleBuilderApp()
    window.show()
    sys.exit(app.exec())
