import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QLineEdit, QHBoxLayout, QPushButton,
                             QMessageBox, QDialog, QAbstractItemView)
from PyQt6.QtCore import Qt
from datetime import datetime

from database import Session, Inventory

class AddOpeningStockDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add / Update Stock")
        self.resize(500, 400) 
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Add multiple items below. Double-click to edit."))
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Item Name", "Quantity"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 100)
        
        self.add_rows(1)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        add_row_btn = QPushButton("➕ Add Row")
        add_row_btn.clicked.connect(lambda: self.add_rows(1))
        
        save_btn = QPushButton("💾 Save All Stock")
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        save_btn.clicked.connect(self.save_stock)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(add_row_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def add_rows(self, count):
        current_rows = self.table.rowCount()
        for i in range(count):
            self.table.insertRow(current_rows + i)
            self.table.setItem(current_rows + i, 1, QTableWidgetItem("0"))

    def save_stock(self):
        session = Session()
        added_count = 0
        updated_count = 0
        
        try:
            for row in range(self.table.rowCount()):
                name_item = self.table.item(row, 0)
                qty_item = self.table.item(row, 1)
                
                if not name_item or not name_item.text().strip():
                    continue
                    
                name = name_item.text().strip()
                qty_text = qty_item.text().strip() if qty_item else "0"
                
                try:
                    qty = float(qty_text)
                except ValueError:
                    QMessageBox.warning(self, "Error", f"Invalid Quantity for item '{name}'")
                    return

                inv = session.query(Inventory).filter_by(item_name=name, is_deleted=False).first()
                if inv:
                    # UPDATE EXISTING
                    inv.quantity += qty
                    updated_count += 1
                else:
                    # CREATE NEW
                    new_inv = Inventory(
                        item_name=name, 
                        quantity=qty
                    )
                    session.add(new_inv)
                    added_count += 1
            
            session.commit()
            QMessageBox.information(self, "Success", f"Stock Added!\n\nNew Items: {added_count}\nUpdated Items: {updated_count}")
            self.accept()
            
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

class InventoryTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Inventory...")
        self.search_input.textChanged.connect(self.load_data)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_data)
        
        self.add_stock_btn = QPushButton("➕ Add / Update Stock")
        self.add_stock_btn.setStyleSheet("background-color: #008CBA; color: white;")
        self.add_stock_btn.clicked.connect(self.open_add_stock_dialog)
        
        top_layout.addWidget(self.search_input)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addWidget(self.add_stock_btn)
        layout.addLayout(top_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Item Name", "Quantity"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 150)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        self.setLayout(layout)

    def delete_selected_item(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            item_name = self.table.item(current_row, 0).text()
            reply = QMessageBox.question(self, 'Confirm Delete', 
                                         f"Are you sure you want to completely delete '{item_name}'?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                         QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                session = Session()
                try:
                    item_to_delete = session.query(Inventory).filter_by(item_name=item_name, is_deleted=False).first()
                    if item_to_delete:
                        # SOFT DELETE ONLY
                        item_to_delete.is_deleted = True
                        
                        session.commit()
                        QMessageBox.information(self, "Success", f"'{item_name}' deleted.")
                        self.load_data() 
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", f"Failed to delete: {str(e)}")
                finally:
                    session.close()
        else:
            QMessageBox.warning(self, "Selection Error", "Please click on an item to delete it.")

    def open_add_stock_dialog(self):
        dialog = AddOpeningStockDialog(self)
        if dialog.exec():
            self.load_data()

    def load_data(self):
        search_txt = self.search_input.text().strip().lower()
        session = Session()
        query = session.query(Inventory).filter(Inventory.is_deleted == False)
        
        if search_txt:
            query = query.filter(Inventory.item_name.contains(search_txt))
            
        items = query.order_by(Inventory.item_name).all()
        
        self.table.setRowCount(0)
        for row, item in enumerate(items):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(item.item_name))
            self.table.setItem(row, 1, QTableWidgetItem(str(item.quantity)))
            
        session.close()