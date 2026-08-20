from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, 
                             QGroupBox, QDateEdit, QCompleter)
from PyQt6.QtCore import QDate, Qt, QStringListModel
from database import Session, Purchase, PurchaseItem, Inventory
from datetime import datetime
from sqlalchemy import func

class PurchaseTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_history()
        self.update_completer()

    def init_ui(self):
        layout = QVBoxLayout(); self.setLayout(layout)

        # --- 1. New Purchase / Stock Entry ---
        group_new = QGroupBox("Add New Stock / Purchase")
        group_new.setStyleSheet("font-weight: bold; color: #107c10;")
        layout_new = QVBoxLayout()
        
        form = QHBoxLayout()
        self.p_item = QLineEdit()
        self.p_item.setPlaceholderText("Item Name (Auto-fills)")
        
        # Setup Auto-Complete
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.p_item.setCompleter(self.completer)
        
        self.completer.activated.connect(self.fill_details)
        self.p_item.returnPressed.connect(self.fill_details)

        self.p_qty = QLineEdit(); self.p_qty.setPlaceholderText("Qty")
        self.p_cost = QLineEdit(); self.p_cost.setPlaceholderText("Cost Price")
        self.p_mrp = QLineEdit(); self.p_mrp.setPlaceholderText("MRP (Sell Price)")
        
        add_btn = QPushButton("Add to Stock"); add_btn.clicked.connect(self.save_purchase)
        
        form.addWidget(QLabel("Item:")); form.addWidget(self.p_item)
        form.addWidget(QLabel("Qty:")); form.addWidget(self.p_qty)
        form.addWidget(QLabel("Cost:")); form.addWidget(self.p_cost)
        form.addWidget(QLabel("MRP:")); form.addWidget(self.p_mrp)
        form.addWidget(add_btn)
        layout_new.addLayout(form)
        group_new.setLayout(layout_new)
        layout.addWidget(group_new)

        # --- 2. Purchase History ---
        group_hist = QGroupBox("Purchase History")
        layout_hist = QVBoxLayout()
        
        filter_layout = QHBoxLayout()
        self.date_filter = QDateEdit(); self.date_filter.setCalendarPopup(True); self.date_filter.setDate(QDate.currentDate())
        btn_filter = QPushButton("Filter Date"); btn_filter.clicked.connect(self.load_history)
        
        filter_layout.addWidget(QLabel("Date:")); filter_layout.addWidget(self.date_filter)
        filter_layout.addWidget(btn_filter)
        layout_hist.addLayout(filter_layout)

        self.table_hist = QTableWidget(); self.table_hist.setColumnCount(6)
        self.table_hist.setHorizontalHeaderLabels(["ID", "Date", "Item Name", "Qty", "Cost", "MRP"])
        self.table_hist.hideColumn(0)
        self.table_hist.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        self.table_hist.doubleClicked.connect(self.edit_history_item)
        
        layout_hist.addWidget(self.table_hist)
        
        btn_del = QPushButton("Delete Selected"); btn_del.clicked.connect(self.delete_history_item)
        layout_hist.addWidget(btn_del)
        
        group_hist.setLayout(layout_hist)
        layout.addWidget(group_hist)

    # --- CRITICAL FIX: Refresh Data When Tab is Clicked ---
    def showEvent(self, event):
        super().showEvent(event)
        self.update_completer()
        self.load_history()

    def update_completer(self):
        """Refreshes the suggestion list from Inventory"""
        session = Session()
        items = session.query(Inventory.item_name).distinct().all()
        item_names = [i.item_name for i in items if i.item_name]
        self.completer.setModel(QStringListModel(item_names))
        session.close()

    def fill_details(self):
        """Auto-fills Cost and MRP based on the entered item name"""
        name = self.p_item.text().strip()
        if not name: return
        
        session = Session()
        inv = session.query(Inventory).filter(func.lower(Inventory.item_name) == name.lower()).first()
        
        if inv:
            self.p_cost.setText(str(inv.cost_price))
            self.p_mrp.setText(str(inv.mrp))
            self.p_qty.setFocus()
        
        session.close()

    def save_purchase(self):
        session = Session()
        try:
            name = self.p_item.text().strip().title()
            qty = float(self.p_qty.text())
            cost = float(self.p_cost.text())
            mrp = float(self.p_mrp.text())
            
            if not name: return

            # --- MERGE LOGIC ---
            today = datetime.now().date()
            existing_item = session.query(PurchaseItem).join(Purchase).filter(
                func.date(Purchase.date_time) == today,
                func.lower(PurchaseItem.item_name) == name.lower(),
                PurchaseItem.cost_price == cost,
                PurchaseItem.mrp == mrp
            ).first()

            if existing_item:
                # UPDATE EXISTING PURCHASE ENTRY
                existing_item.quantity += qty
                existing_item.amount = existing_item.quantity * cost
                existing_item.purchase.total_amount += (qty * cost)
                
                # Update Inventory (Find by Name ONLY to avoid Duplicates)
                inv = session.query(Inventory).filter(func.lower(Inventory.item_name) == name.lower()).first()
                if inv:
                    inv.quantity += qty
                    inv.cost_price = cost
                    inv.mrp = mrp # Update MRP to latest
                else:
                    inv = Inventory(item_name=name, quantity=qty, cost_price=cost, mrp=mrp)
                    session.add(inv)
                
                msg = "Stock Merged & Updated"
            else:
                # CREATE NEW PURCHASE ENTRY
                purch = Purchase(total_amount=qty*cost, date_time=datetime.now(), category="Stock")
                session.add(purch)
                session.flush()
                
                p_item = PurchaseItem(purchase_id=purch.id, item_name=name, quantity=qty, cost_price=cost, mrp=mrp, amount=qty*cost)
                session.add(p_item)
                
                # --- CRITICAL FIX: Find Inventory by Name ONLY ---
                inv = session.query(Inventory).filter(func.lower(Inventory.item_name) == name.lower()).first()
                if inv:
                    inv.quantity += qty
                    inv.cost_price = cost
                    inv.mrp = mrp # Always update MRP to latest purchase
                else:
                    inv = Inventory(item_name=name, quantity=qty, cost_price=cost, mrp=mrp)
                    session.add(inv)
                
                msg = "Stock Added & Inventory Updated"
                
            session.commit()
            QMessageBox.information(self, "Success", msg)
            self.p_item.clear(); self.p_qty.clear(); self.p_cost.clear(); self.p_mrp.clear()
            
            self.load_history()
            self.update_completer()
            
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid Numbers")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def edit_history_item(self, index):
        """Called on double-click: Deletes item from DB/Inventory and puts it back in inputs"""
        row = index.row()
        item_id = self.table_hist.item(row, 0).text()
        
        session = Session()
        item = session.query(PurchaseItem).filter_by(id=item_id).first()
        
        if item:
            # 1. Populate Inputs
            self.p_item.setText(item.item_name)
            self.p_qty.setText(str(item.quantity))
            self.p_cost.setText(str(item.cost_price))
            self.p_mrp.setText(str(item.mrp))
            
            # 2. Revert Inventory (Find by Name Only)
            inv = session.query(Inventory).filter(func.lower(Inventory.item_name) == item.item_name.lower()).first()
            if inv:
                inv.quantity -= item.quantity
                if inv.quantity <= 0:
                    session.delete(inv)
            
            # 3. Delete Purchase Record
            count = session.query(PurchaseItem).filter_by(purchase_id=item.purchase_id).count()
            if count <= 1:
                session.query(Purchase).filter_by(id=item.purchase_id).delete()
            else:
                parent = session.query(Purchase).filter_by(id=item.purchase_id).first()
                if parent: parent.total_amount -= item.amount
            
            session.delete(item)
            session.commit()
            
            self.load_history()
            self.update_completer()
            self.p_item.setFocus()
            
        session.close()

    def load_history(self):
        session = Session()
        dt = self.date_filter.date().toPyDate()
        items = session.query(PurchaseItem).join(Purchase).filter(func.date(Purchase.date_time) == dt).all()
        
        self.table_hist.setRowCount(0)
        for i in items:
            r = self.table_hist.rowCount(); self.table_hist.insertRow(r)
            self.table_hist.setItem(r, 0, QTableWidgetItem(str(i.id)))
            self.table_hist.setItem(r, 1, QTableWidgetItem(i.purchase.date_time.strftime("%d-%m-%Y")))
            self.table_hist.setItem(r, 2, QTableWidgetItem(i.item_name))
            self.table_hist.setItem(r, 3, QTableWidgetItem(str(i.quantity)))
            self.table_hist.setItem(r, 4, QTableWidgetItem(str(i.cost_price)))
            self.table_hist.setItem(r, 5, QTableWidgetItem(str(i.mrp)))
        session.close()

    def delete_history_item(self):
        row = self.table_hist.currentRow()
        if row == -1: return
        if QMessageBox.question(self, "Confirm", "Delete this entry? (Stock will reduce)") == QMessageBox.StandardButton.Yes:
            pid = self.table_hist.item(row, 0).text()
            session = Session()
            item = session.query(PurchaseItem).filter_by(id=pid).first()
            if item:
                # Revert Inventory (Find by Name Only)
                inv = session.query(Inventory).filter(func.lower(Inventory.item_name) == item.item_name.lower()).first()
                if inv: 
                    inv.quantity -= item.quantity
                    if inv.quantity <= 0:
                        session.delete(inv)
                
                count = session.query(PurchaseItem).filter_by(purchase_id=item.purchase_id).count()
                if count <= 1:
                    session.query(Purchase).filter_by(id=item.purchase_id).delete()
                
                session.delete(item)
                session.commit()
            session.close()
            self.load_history()
            self.update_completer()