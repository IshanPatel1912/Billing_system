from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, 
                             QDateEdit, QGroupBox, QCompleter)
from PyQt6.QtCore import QDate, Qt, QStringListModel
from PyQt6.QtGui import QShortcut, QKeySequence, QDoubleValidator
from database import Session, Purchase, PurchaseItem, Inventory
from sqlalchemy import or_
from datetime import datetime

class TrackedItemsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_inventory_suggestions()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        group_new = QGroupBox("Add New Tracked Items (Updates Inventory)")
        group_new.setStyleSheet("QGroupBox { font-weight: bold; color: #107c10; font-size: 14px; }")
        layout_new = QVBoxLayout()

        form = QHBoxLayout()
        self.t_item = QLineEdit()
        self.t_item.setPlaceholderText("Item Name")
        self.t_item.setMinimumHeight(35)
        
        # --- NEW: AUTO-COMPLETER FOR INVENTORY ITEMS ---
        self.item_completer = QCompleter([])
        self.item_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.item_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.t_item.setCompleter(self.item_completer)
        
        self.t_qty = QLineEdit()
        self.t_qty.setPlaceholderText("Qty")
        self.t_qty.setMinimumHeight(35)
        qty_validator = QDoubleValidator(0.0, 999999.0, 2)
        qty_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.t_qty.setValidator(qty_validator)
        
        self.t_rate = QLineEdit()
        self.t_rate.setPlaceholderText("Rate (Cost)")
        self.t_rate.setMinimumHeight(35)
        rate_validator = QDoubleValidator(0.0, 999999.0, 2)
        rate_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.t_rate.setValidator(rate_validator)
        
        add_btn = QPushButton("Add to List")
        add_btn.setMinimumHeight(35)
        add_btn.clicked.connect(self.add_row)
        
        form.addWidget(self.t_item)
        form.addWidget(self.t_qty)
        form.addWidget(self.t_rate)
        form.addWidget(add_btn)
        layout_new.addLayout(form)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Item", "Qty", "Rate", "Amount"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.cellChanged.connect(self.on_cell_change)
        layout_new.addWidget(self.table)

        btns = QHBoxLayout()
        self.track_date = QDateEdit()
        self.track_date.setCalendarPopup(True)
        self.track_date.setDate(QDate.currentDate())
        self.track_date.setMinimumHeight(40)
        
        lbl_date = QLabel("Purchase Date: ")
        lbl_date.setStyleSheet("font-weight: bold;")
        btns.addWidget(lbl_date)
        btns.addWidget(self.track_date)
        
        save_btn = QPushButton("Save & Update Inventory")
        save_btn.setStyleSheet("background-color: #107c10; color: white; font-weight: bold; font-size: 14px;")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save_tracked)
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_tracked)
        
        del_btn = QPushButton("Delete Selected List Item")
        del_btn.setMinimumHeight(40)
        del_btn.clicked.connect(self.delete_row)
        
        clr_btn = QPushButton("Clear Entire List")
        clr_btn.setMinimumHeight(40)
        clr_btn.clicked.connect(lambda: self.table.setRowCount(0))
        
        btns.addWidget(save_btn, stretch=1)
        btns.addWidget(del_btn)
        btns.addWidget(clr_btn)
        layout_new.addLayout(btns)
        
        group_new.setLayout(layout_new)
        layout.addWidget(group_new)

    def load_inventory_suggestions(self):
        """Loads all existing inventory items into the Auto-Completer"""
        session = Session()
        items = session.query(Inventory.item_name).filter(
            or_(Inventory.is_deleted == False, Inventory.is_deleted == None)
        ).all()
        item_names = [item[0] for item in items if item[0]]
        self.item_completer.setModel(QStringListModel(item_names))
        session.close()

    def add_row(self):
        try:
            name = self.t_item.text().strip()
            qty_text = self.t_qty.text().strip()
            rate_text = self.t_rate.text().strip()
            
            if not name or not qty_text or not rate_text: return
            try: qty = float(qty_text)
            except ValueError: return  
            try: rate = float(rate_text)
            except ValueError: return  
            if qty <= 0 or rate < 0: return  

            self.table.blockSignals(True)
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(name))
            self.table.setItem(r, 1, QTableWidgetItem(str(qty)))
            self.table.setItem(r, 2, QTableWidgetItem(str(rate)))
            self.table.setItem(r, 3, QTableWidgetItem(f"{qty*rate:.2f}"))
            self.table.blockSignals(False)
            self.t_item.clear(); self.t_qty.clear(); self.t_rate.clear(); self.t_item.setFocus()
        except Exception: pass

    def on_cell_change(self, row, column):
        if column in [1, 2]:
            try:
                q_item = self.table.item(row, 1)
                r_item = self.table.item(row, 2)
                if q_item and r_item:
                    q_str = q_item.text().strip()
                    r_str = r_item.text().strip()
                    if q_str and r_str:
                        q = float(q_str)
                        r = float(r_str)
                        self.table.blockSignals(True)
                        target = self.table.item(row, 3)
                        if target: target.setText(f"{q*r:.2f}")
                        else: self.table.setItem(row, 3, QTableWidgetItem(f"{q*r:.2f}"))
                        self.table.blockSignals(False)
            except ValueError: pass

    def delete_row(self):
        if self.table.currentRow() >= 0: self.table.removeRow(self.table.currentRow())

    def save_tracked(self):
        if self.table.rowCount() == 0: return
        session = Session()
        try:
            total = sum(float(self.table.item(r, 3).text()) for r in range(self.table.rowCount()))
            dt = self.track_date.date().toPyDate()
            track_dt = datetime.combine(dt, datetime.now().time())
            
            p = Purchase(total_amount=total, date_time=track_dt, track_item=True, category="Tracked")
            session.add(p); session.flush()
            
            for r in range(self.table.rowCount()):
                name = self.table.item(r, 0).text()
                qty = float(self.table.item(r, 1).text())
                rate = float(self.table.item(r, 2).text())
                
                session.add(PurchaseItem(purchase_id=p.id, item_name=name, quantity=qty, rate=rate, amount=qty*rate, track_item=True))
                
                
                inv = session.query(Inventory).filter_by(item_name=name).first()
                if inv: 
                    inv.quantity += qty           # Perfectly increases existing quantity
                    inv.cost_price = rate         # Updates your inventory cost to match latest rate
                    inv.is_deleted = False        # Restores item if it was previously deleted
                else: 
                    # Adds brand new items smoothly
                    session.add(Inventory(item_name=name, quantity=qty, cost_price=rate))
                
            session.commit()
            QMessageBox.information(self, "Success", "Saved Tracked Items and Updated Inventory")
            self.table.setRowCount(0)
            self.track_date.setDate(QDate.currentDate())  
            self.load_inventory_suggestions() # Instantly refreshes the auto-completer with any new items!
        except Exception as e: 
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally: 
            session.close()