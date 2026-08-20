import os
import subprocess
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, 
                             QFileDialog, QDateEdit, QAbstractItemView, QCheckBox, QCompleter) # Added QCompleter
from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence, QColor, QBrush
from database import Session, Sale, SaleItem, Inventory, get_current_business_details
from modules.pdf_generator import generate_bill_pdf
from sqlalchemy import func, or_
from datetime import datetime

class SortableTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, sort_value=None):
        super().__init__(text)
        self.sort_value = sort_value
    def __lt__(self, other):
        if (self.sort_value is not None) and (other.sort_value is not None):
            return self.sort_value < other.sort_value
        return super().__lt__(other)

class FindBillTab(QWidget):
    edit_bill_signal = pyqtSignal(str) 

    def __init__(self):
        super().__init__()
        self.processing_lock = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        search_layout = QHBoxLayout()
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Bill ID", "Customer Name", "Car Number", "Car Model", "Mobile Number"])
        self.filter_combo.currentTextChanged.connect(self.update_completer)
        
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Status", "Paid", "Unpaid"])
        self.status_filter.setMinimumWidth(150)
        self.status_filter.currentIndexChanged.connect(self.search_bills)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search term...")
        self.update_completer(self.filter_combo.currentText()) 
        
        btn_search = QPushButton("Search"); btn_search.clicked.connect(self.search_bills)
        self.search_input.returnPressed.connect(self.search_bills)
        
        search_layout.addWidget(QLabel("Search By:"))
        search_layout.addWidget(self.filter_combo)
        search_layout.addWidget(QLabel("Status:"))
        search_layout.addWidget(self.status_filter)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(btn_search)
        layout.addLayout(search_layout)

        # Date & Recycle Bin
        date_layout = QHBoxLayout()
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate())
        
        btn_date_filter = QPushButton("Filter by Date")
        btn_date_filter.clicked.connect(self.search_bills)
        
        btn_clear_date = QPushButton("Clear Date Filter")
        btn_clear_date.clicked.connect(lambda: [self.date_filter.setDate(QDate.currentDate()), self.search_bills()])
        
        self.chk_recycle = QCheckBox("🗑️ Show Recycle Bin")
        self.chk_recycle.setStyleSheet("color: red; font-weight: bold;")
        self.chk_recycle.stateChanged.connect(self.toggle_recycle_mode)

        date_layout.addWidget(QLabel("Date Filter:"))
        date_layout.addWidget(self.date_filter)
        date_layout.addWidget(btn_date_filter)
        date_layout.addWidget(btn_clear_date)
        date_layout.addStretch()
        date_layout.addWidget(self.chk_recycle)
        layout.addLayout(date_layout)

        # Table
        self.table = QTableWidget(); self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Bill ID", "Date", "Customer", "Car No", "Total", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.doubleClicked.connect(self.edit_bill)
        layout.addWidget(self.table)
        
        layout.addWidget(QLabel("(Hold Ctrl/Shift to select multiple)"))

        # Buttons
        actions = QHBoxLayout()
        self.btn_print = QPushButton("🖨️ Print Selected"); self.btn_print.clicked.connect(self.direct_print_bill)
        self.btn_save = QPushButton("💾 Save PDF As..."); self.btn_save.clicked.connect(self.save_pdf_as)
        self.btn_edit = QPushButton("✏️ Edit Selected"); self.btn_edit.clicked.connect(self.edit_bill)
        
        self.btn_delete = QPushButton("🗑️ Delete Selected")
        try: self.btn_delete.clicked.disconnect() 
        except: pass
        self.btn_delete.clicked.connect(self.delete_bill)
        
        self.btn_restore = QPushButton("♻️ Restore Selected")
        self.btn_restore.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_restore.clicked.connect(self.restore_bills)
        self.btn_restore.setVisible(False)

        actions.addWidget(self.btn_print)
        actions.addWidget(self.btn_save)
        actions.addWidget(self.btn_edit)
        actions.addWidget(self.btn_restore)
        actions.addWidget(self.btn_delete)
        layout.addLayout(actions)
        
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_pdf_as)
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(self.direct_print_bill)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self.delete_bill)

    def update_completer(self, category_text):
        """Fetches distinct values from database based on the selected category"""
        session = Session()
        items = []
        try:
            if category_text == "Customer Name":
                data = session.query(Sale.customer_name).distinct().all()
                items = [r[0] for r in data if r[0]]
            elif category_text == "Mobile Number":
                data = session.query(Sale.mobile_number).distinct().all()
                items = [r[0] for r in data if r[0]]
            elif category_text == "Car Number":
                data = session.query(Sale.car_number).distinct().all()
                items = [r[0] for r in data if r[0]]
            elif category_text == "Car Model":
                data = session.query(Sale.car_model).distinct().all()
                items = [r[0] for r in data if r[0]]
            elif category_text == "Bill ID":
                data = session.query(Sale.bill_id).distinct().all()
                items = [r[0] for r in data if r[0]]

            completer = QCompleter(items, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains) # Allows matching 'Honda' in 'New Honda City'
            self.search_input.setCompleter(completer)
            
        except Exception as e:
            print(f"Error updating suggestions: {e}")
        finally:
            session.close()

    def toggle_recycle_mode(self):
        is_recycle = self.chk_recycle.isChecked()
        if is_recycle:
            self.btn_restore.setVisible(True)
            self.btn_delete.setText("❌ Permanently Delete")
            self.btn_delete.setStyleSheet("background-color: #d32f2f; color: white;")
            self.btn_edit.setEnabled(False)
            self.btn_print.setEnabled(False)
        else:
            self.btn_restore.setVisible(False)
            self.btn_delete.setText("🗑️ Delete Selected")
            self.btn_delete.setStyleSheet("")
            self.btn_edit.setEnabled(True)
            self.btn_print.setEnabled(True)
        self.search_bills()

    def search_bills(self):
        self.table.setSortingEnabled(False)
        txt = self.search_input.text().strip()
        search_by = self.filter_combo.currentText()
        status_filter = self.status_filter.currentText()
        is_recycle = self.chk_recycle.isChecked()
        
        session = Session()
        query = session.query(Sale)
        
        if is_recycle:
            query = query.filter(Sale.is_deleted == True)
        else:
            query = query.filter((Sale.is_deleted == False) | (Sale.is_deleted == None))

        if txt:
            if search_by == "Bill ID": query = query.filter(Sale.bill_id.contains(txt))
            elif search_by == "Customer Name": query = query.filter(Sale.customer_name.contains(txt))
            elif search_by == "Car Number": query = query.filter(Sale.car_number.contains(txt))
            elif search_by == "Mobile Number": query = query.filter(Sale.mobile_number.contains(txt))
            elif search_by == "Car Model": query = query.filter(Sale.car_model.contains(txt)) # --- ADDED CAR MODEL FILTER ---
        
        if status_filter == "Paid": query = query.filter(Sale.paid_status == True)
        elif status_filter == "Unpaid": query = query.filter(Sale.paid_status == False)
        
        sender = self.sender()
        if sender and isinstance(sender, QPushButton) and sender.text() == "Filter by Date":
             dt = self.date_filter.date().toPyDate()
             query = query.filter(func.date(Sale.date_time) == dt)
        
        results = query.order_by(Sale.date_time.desc()).limit(100).all()
        
        self.table.setRowCount(0)
        for s in results:
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(s.bill_id))
            date_str = s.date_time.strftime("%d-%m-%Y")
            self.table.setItem(r, 1, SortableTableWidgetItem(date_str, s.date_time))
            self.table.setItem(r, 2, QTableWidgetItem(s.customer_name))
            self.table.setItem(r, 3, QTableWidgetItem(s.car_number))
            self.table.setItem(r, 4, SortableTableWidgetItem(f"{s.net_total:.2f}", s.net_total))
            
            status_text = "Paid" if s.paid_status else "Unpaid"
            status_item = QTableWidgetItem(status_text)
            if s.paid_status: status_item.setForeground(QBrush(QColor("green")))
            else: status_item.setForeground(QBrush(QColor("red"))); status_item.setData(Qt.ItemDataRole.FontRole, self.font().bold)
            self.table.setItem(r, 5, status_item)

        session.close()
        self.table.setSortingEnabled(True)

    def get_selected_ids(self):
        rows = set()
        for index in self.table.selectedIndexes():
            rows.add(index.row())
        ids = []
        for row in rows:
            item = self.table.item(row, 0)
            if item: ids.append(item.text())
        return ids

    def _generate_pdf_data(self, bid):
        session = Session()
        sale = session.query(Sale).filter_by(bill_id=bid).first()
        data = None; biz = None
        if sale:
            biz = get_current_business_details()
            items = [{'sr_no': i.sr_no, 'item_name': i.item_name, 'quantity': i.quantity, 'rate': i.rate, 'amount': i.amount} for i in sale.items]
            car_num = sale.car_number if sale.car_number else "N/A"
            car_km = sale.car_km if sale.car_km else ""
            data = {'bill_id': sale.bill_id, 'date_time': sale.date_time, 'customer_name': sale.customer_name,
                    'mobile_number': sale.mobile_number, 'car_number': car_num, 'car_km': car_km, 'items': items}
        session.close()
        return data, biz

    def direct_print_bill(self):
        if self.chk_recycle.isChecked(): return 
        bids = self.get_selected_ids()
        if not bids: QMessageBox.warning(self, "Select", "Please select at least one bill."); return
        count = len(bids)
        if count > 5:
            if QMessageBox.question(self, "Confirm", f"Print {count} bills?") != QMessageBox.StandardButton.Yes: return

        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(edge_path): edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

        for bid in bids:
            data, biz = self._generate_pdf_data(bid)
            if not data: continue
            temp_dir = os.environ['TEMP']; temp_pdf = os.path.join(temp_dir, f"Print_{bid}.pdf")
            generate_bill_pdf(data, biz, temp_pdf)
            try:
                if os.path.exists(edge_path): subprocess.run([edge_path, "--print-to-default", temp_pdf], check=True)
                else: os.startfile(temp_pdf, "print")
            except Exception: pass
        QMessageBox.information(self, "Printing", f"Sent {count} documents to printer.")

    def save_pdf_as(self):
        ids = self.get_selected_ids()
        if not ids: return
        bid = ids[0] 
        data, biz = self._generate_pdf_data(bid)
        if data:
            path, _ = QFileDialog.getSaveFileName(self, "Save Bill PDF", f"Bill_{bid}.pdf", "PDF Files (*.pdf)")
            if path:
                generate_bill_pdf(data, biz, path)
                QMessageBox.information(self, "Success", "PDF Saved Successfully")

    def edit_bill(self):
        if self.chk_recycle.isChecked(): return
        ids = self.get_selected_ids()
        if not ids: return
        bid = ids[0]
        self.edit_bill_signal.emit(bid)

    def restore_bills(self):
        """Restore bills from Recycle Bin AND deduct items from Inventory."""
        if self.processing_lock: return
        self.processing_lock = True
        
        try:
            bids = self.get_selected_ids()
            if not bids: return
            
            session = Session()
            for bid in bids:
                sale = session.query(Sale).filter_by(bill_id=bid).first()
                if sale:
                    if not sale.is_deleted: continue
                    
                    sale.is_deleted = False
                    
                    # --- DEDUCT STOCK AGAIN ---
                    for item in sale.items:
                        # Only deduct if it is a tracked item
                        if item.is_tracked:
                            name = item.item_name.strip()
                            inv = session.query(Inventory).filter_by(item_name=name).first()
                            
                            if not inv:
                                inv = Inventory(item_name=name, quantity=0, cost_price=0, mrp=item.rate)
                                session.add(inv)
                                session.flush()
                                
                            inv.quantity -= item.quantity
                            
                            if inv.quantity <= 0:
                                session.delete(inv) 
            
            session.commit(); session.close()
            QMessageBox.information(self, "Success", "Bills Restored & Inventory Updated!")
            self.search_bills()
            
        finally:
            self.processing_lock = False

    def delete_bill(self):
        if self.processing_lock: return
        self.processing_lock = True
        
        try:
            bids = self.get_selected_ids()
            if not bids: return
            
            is_recycle_mode = self.chk_recycle.isChecked()
            count = len(bids)
            
            if is_recycle_mode:
                if QMessageBox.question(self, "Confirm Permanent Delete", f"Are you sure you want to PERMANENTLY delete {count} bill(s)?\nThis cannot be undone!") == QMessageBox.StandardButton.Yes:
                    session = Session()
                    for bid in bids: session.query(Sale).filter_by(bill_id=bid).delete()
                    session.commit(); session.close()
                    self.search_bills()
            else:
                if QMessageBox.question(self, "Confirm Delete", f"Move {count} bill(s) to Recycle Bin?\nInventory will be RESTORED.") == QMessageBox.StandardButton.Yes:
                    session = Session()
                    for bid in bids:
                        sale = session.query(Sale).filter_by(bill_id=bid).first()
                        
                        if not sale or sale.is_deleted: continue
                        
                        sale.is_deleted = True
                        
                        # --- RESTORE STOCK ---
                        for item in sale.items:
                            if item.is_tracked:
                                name = item.item_name.strip()
                                inv = session.query(Inventory).filter_by(item_name=name).first()
                                
                                if inv:
                                    inv.quantity += item.quantity
                                else:
                                    new_inv = Inventory(item_name=name, quantity=item.quantity, cost_price=0, mrp=item.rate)
                                    session.add(new_inv)
                                    session.flush() 
                    
                    session.commit(); session.close()
                    self.search_bills()
        finally:
            self.processing_lock = False