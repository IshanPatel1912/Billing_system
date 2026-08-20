from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, 
                             QDialog, QFormLayout, QDateEdit)
from PyQt6.QtCore import QDate
from database import Session, Purchase, PurchaseItem, Inventory
from datetime import datetime

class PurchaseHistoryTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_history()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        filter_layout = QHBoxLayout()
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate())
        
        btn_filter = QPushButton("Filter Date")
        btn_filter.clicked.connect(self.load_history)
        
        btn_clear = QPushButton("Clear Filter")
        btn_clear.clicked.connect(lambda: [self.date_filter.setDate(QDate.currentDate()), self.load_history()])
        
        filter_layout.addWidget(QLabel("Date Filter:"))
        filter_layout.addWidget(self.date_filter)
        filter_layout.addWidget(btn_filter)
        filter_layout.addWidget(btn_clear)
        layout.addLayout(filter_layout)

        self.table_hist = QTableWidget()
        self.table_hist.setColumnCount(7) 
        self.table_hist.setHorizontalHeaderLabels(["ID", "Date", "Item Name", "Qty", "Rate", "Amount", "Type"])
        self.table_hist.hideColumn(0) 
        self.table_hist.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_hist.doubleClicked.connect(self.edit_history_item)
        layout.addWidget(self.table_hist)
        
        btn_del = QPushButton("Delete Selected History Item")
        btn_del.setStyleSheet("background-color: #c42b1c; color: white; padding: 10px; font-weight: bold;")
        btn_del.clicked.connect(self.delete_history_item)
        layout.addWidget(btn_del)

    def load_history(self):
        session = Session()
        query = session.query(PurchaseItem).join(Purchase).order_by(Purchase.date_time.desc())
        
        dt = self.date_filter.date().toPyDate()
        from sqlalchemy import func
        query = query.filter(func.date(Purchase.date_time) == dt)
            
        items = query.limit(100).all()
        self.table_hist.setRowCount(0)
        for i in items:
            r = self.table_hist.rowCount()
            self.table_hist.insertRow(r)
            self.table_hist.setItem(r, 0, QTableWidgetItem(str(i.id)))
            self.table_hist.setItem(r, 1, QTableWidgetItem(i.purchase.date_time.strftime("%d-%m-%Y")))
            self.table_hist.setItem(r, 2, QTableWidgetItem(i.item_name))
            self.table_hist.setItem(r, 3, QTableWidgetItem(str(i.quantity)))
            self.table_hist.setItem(r, 4, QTableWidgetItem(str(i.rate)))
            self.table_hist.setItem(r, 5, QTableWidgetItem(f"{i.amount:.2f}"))
            
            type_str = "📦 Tracked" if i.track_item else "📝 General"
            self.table_hist.setItem(r, 6, QTableWidgetItem(type_str))
            
        session.close()

    def edit_history_item(self):
        row = self.table_hist.currentRow()
        if row == -1: return
        item_id = self.table_hist.item(row, 0).text()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit History Item")
        form = QFormLayout(dialog)
        
        e_name = QLineEdit(self.table_hist.item(row, 2).text())
        e_qty = QLineEdit(self.table_hist.item(row, 3).text())
        e_rate = QLineEdit(self.table_hist.item(row, 4).text())
        
        form.addRow("Name:", e_name)
        form.addRow("Qty:", e_qty)
        form.addRow("Rate:", e_rate)
        
        btn_save = QPushButton("Save Changes")
        btn_save.clicked.connect(lambda: dialog.accept())
        form.addWidget(btn_save)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            session = Session()
            try:
                item = session.query(PurchaseItem).filter_by(id=item_id).first()
                if item:
                    old_qty = item.quantity
                    old_name = item.item_name
                    
                    new_qty = float(e_qty.text())
                    new_name = e_name.text().strip()
                    new_rate = float(e_rate.text())
                    
                    item.item_name = new_name
                    item.quantity = new_qty
                    item.rate = new_rate
                    item.amount = item.quantity * item.rate
                    
                    # LOGIC: Only update inventory if it was a Tracked Item
                    if item.track_item:
                        if old_name == new_name:
                            inv = session.query(Inventory).filter_by(item_name=old_name).first()
                            if inv: inv.quantity += (new_qty - old_qty)
                        else:
                            old_inv = session.query(Inventory).filter_by(item_name=old_name).first()
                            if old_inv: old_inv.quantity -= old_qty
                            new_inv = session.query(Inventory).filter_by(item_name=new_name).first()
                            if new_inv: new_inv.quantity += new_qty
                            else: session.add(Inventory(item_name=new_name, quantity=new_qty))
                    
                    
                    purch = session.query(Purchase).filter_by(id=item.purchase_id).first()
                    all_items = session.query(PurchaseItem).filter_by(purchase_id=item.purchase_id).all()
                    purch.total_amount = sum(i.amount for i in all_items)
                    
                    session.commit()
                    self.load_history()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
            finally:
                session.close()

    def delete_history_item(self):
        row = self.table_hist.currentRow()
        if row == -1: return
        
        if QMessageBox.question(self, "Confirm", "Delete selected item?") == QMessageBox.StandardButton.Yes:
            item_id = self.table_hist.item(row, 0).text()
            session = Session()
            try:
                item = session.query(PurchaseItem).filter_by(id=item_id).first()
                if item:
                    pid = item.purchase_id
                    
                    # LOGIC: If tracked, revert inventory
                    if item.track_item:
                        inv = session.query(Inventory).filter_by(item_name=item.item_name).first()
                        if inv: inv.quantity -= item.quantity
                    
                    session.delete(item)
                    
                    
                    all_items = session.query(PurchaseItem).filter_by(purchase_id=pid).all()
                    purch = session.query(Purchase).filter_by(id=pid).first()
                    if purch: purch.total_amount = sum(i.amount for i in all_items)
                    
                    session.commit()
                    self.load_history()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", str(e))
            finally:
                session.close()