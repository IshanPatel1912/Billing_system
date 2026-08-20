from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, 
                             QGroupBox, QDateEdit)
from PyQt6.QtCore import QDate
from PyQt6.QtGui import QShortcut, QKeySequence, QDoubleValidator
from database import Session, Purchase, PurchaseItem
from datetime import datetime

class PurchaseTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        group_new = QGroupBox("Add General Purchase (Expenses Only - NO Inventory Update)")
        group_new.setStyleSheet("QGroupBox { font-weight: bold; color: #d83b01; font-size: 14px; }")
        layout_new = QVBoxLayout()
        
        form = QHBoxLayout()
        self.p_item = QLineEdit()
        self.p_item.setPlaceholderText("Item Description")
        self.p_item.setMinimumHeight(35)
        
        self.p_qty = QLineEdit()
        self.p_qty.setPlaceholderText("Qty")
        self.p_qty.setMinimumHeight(35)
        qty_validator = QDoubleValidator(0.0, 999999.0, 2)
        qty_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.p_qty.setValidator(qty_validator)
        
        self.p_rate = QLineEdit()
        self.p_rate.setPlaceholderText("Rate")
        self.p_rate.setMinimumHeight(35)
        rate_validator = QDoubleValidator(0.0, 999999.0, 2)
        rate_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.p_rate.setValidator(rate_validator)
        
        add_btn = QPushButton("Add to List")
        add_btn.setMinimumHeight(35)
        add_btn.clicked.connect(self.add_row)
        
        form.addWidget(QLabel("Item:")); form.addWidget(self.p_item)
        form.addWidget(QLabel("Qty:")); form.addWidget(self.p_qty)
        form.addWidget(QLabel("Rate:")); form.addWidget(self.p_rate)
        form.addWidget(add_btn)
        layout_new.addLayout(form)

        
        self.table_temp = QTableWidget()
        self.table_temp.setColumnCount(4)
        self.table_temp.setHorizontalHeaderLabels(["Item", "Qty", "Rate", "Amount"])
        self.table_temp.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_temp.cellChanged.connect(self.on_cell_change)
        layout_new.addWidget(self.table_temp)

        save_layout = QHBoxLayout()
        self.purchase_date = QDateEdit()
        self.purchase_date.setCalendarPopup(True)
        self.purchase_date.setDate(QDate.currentDate())
        self.purchase_date.setMinimumHeight(40)
        
        save_btn = QPushButton("Save General Purchase")
        save_btn.setStyleSheet("background-color: #d83b01; color: white; font-weight: bold; font-size: 14px;")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save_purchase)
        
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_purchase)
        
        lbl_date = QLabel("Purchase Date: ")
        lbl_date.setStyleSheet("font-weight: bold;")
        save_layout.addWidget(lbl_date)
        save_layout.addWidget(self.purchase_date)
        save_layout.addWidget(save_btn, stretch=1)
        
        layout_new.addLayout(save_layout)
        group_new.setLayout(layout_new)
        layout.addWidget(group_new)
        
        
    def add_row(self):
        try:
            name = self.p_item.text().strip()
            qty_text = self.p_qty.text().strip()
            rate_text = self.p_rate.text().strip()
            
            if not name or not qty_text or not rate_text: return
            try: qty = float(qty_text)
            except ValueError: return  
            try: rate = float(rate_text)
            except ValueError: return  
            if qty <= 0 or rate < 0: return  
            
            amt = qty * rate

            self.table_temp.blockSignals(True)
            r = self.table_temp.rowCount()
            self.table_temp.insertRow(r)
            self.table_temp.setItem(r, 0, QTableWidgetItem(name))
            self.table_temp.setItem(r, 1, QTableWidgetItem(str(qty)))
            self.table_temp.setItem(r, 2, QTableWidgetItem(str(rate)))
            self.table_temp.setItem(r, 3, QTableWidgetItem(f"{amt:.2f}"))
            self.table_temp.blockSignals(False)
            
            self.p_item.clear(); self.p_qty.clear(); self.p_rate.clear(); self.p_item.setFocus()
        except Exception: pass

    def on_cell_change(self, row, column):
        if column in [1, 2]:
            try:
                q_item = self.table_temp.item(row, 1)
                r_item = self.table_temp.item(row, 2)
                if q_item and r_item:
                    qty_text = q_item.text().strip() if q_item.text() else ""
                    rate_text = r_item.text().strip() if r_item.text() else ""
                    if qty_text and rate_text:
                        try:
                            qty = float(qty_text)
                            rate = float(rate_text)
                            if qty <= 0 or rate < 0: return  
                            
                            amt = qty * rate
                            self.table_temp.blockSignals(True)
                            amt_item = self.table_temp.item(row, 3)
                            if amt_item: amt_item.setText(f"{amt:.2f}")
                            else: self.table_temp.setItem(row, 3, QTableWidgetItem(f"{amt:.2f}"))
                            self.table_temp.blockSignals(False)
                        except ValueError: pass
            except Exception: pass

    def save_purchase(self):
        if self.table_temp.rowCount() == 0: return
        session = Session()
        try:
            total = sum(float(self.table_temp.item(r, 3).text()) for r in range(self.table_temp.rowCount()))
            dt = self.purchase_date.date().toPyDate()
            purchase_dt = datetime.combine(dt, datetime.now().time())
            
            purchase = Purchase(total_amount=total, date_time=purchase_dt, track_item=False, category="General")
            session.add(purchase); session.flush()

            for r in range(self.table_temp.rowCount()):
                name = self.table_temp.item(r, 0).text()
                qty = float(self.table_temp.item(r, 1).text())
                rate = float(self.table_temp.item(r, 2).text())
                amt = float(self.table_temp.item(r, 3).text())
                session.add(PurchaseItem(purchase_id=purchase.id, item_name=name, quantity=qty, rate=rate, amount=amt, track_item=False))
                
            session.commit()
            QMessageBox.information(self, "Success", "General Purchase Saved (Inventory NOT Updated)")
            self.table_temp.setRowCount(0)
            self.purchase_date.setDate(QDate.currentDate())
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()