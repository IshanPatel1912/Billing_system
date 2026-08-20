import os
import sys
import threading
import tempfile
import configparser
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QGroupBox, QFormLayout, QMessageBox, QCheckBox, QComboBox, 
                             QGridLayout, QCompleter)
from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtGui import QShortcut, QKeySequence, QDoubleValidator
from sqlalchemy import func
from database import Session, Sale, SaleItem, Inventory, Customer, get_current_business_details
from modules.pdf_generator import generate_bill_pdf

# --- CONFIGURATION ---
config = configparser.ConfigParser()
config.read('config.ini')
RAW_POPPLER_PATH = config.get('SETTINGS', 'poppler_path', fallback=r'poppler\Library\bin')

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class SellTab(QWidget):
    def __init__(self):
        super().__init__()
        self.current_bill_id = None
        self.init_ui()
        self.generate_new_bill_id()

    def init_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # --- 1. Bill Details & Customer ---
        details_group = QGroupBox("Bill Details & Customer")
        details_layout = QFormLayout()
        
        row1 = QHBoxLayout()
        self.bill_id_label = QLabel()
        self.bill_id_label.setStyleSheet("font-weight: bold; color: blue; font-size: 14px;")
        self.date_label = QLabel(datetime.now().strftime("%d-%m-%Y %I:%M %p"))
        row1.addWidget(QLabel("Bill ID:")); row1.addWidget(self.bill_id_label)
        row1.addStretch()
        row1.addWidget(QLabel("Date:")); row1.addWidget(self.date_label)
        details_layout.addRow(row1)

        # Customer Section (Optional for retail)
        row2 = QHBoxLayout()
        self.cust_name = QLineEdit()
        self.cust_name.setPlaceholderText("Customer Name (Optional)")
        
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.cust_name.setCompleter(self.completer)
        
        self.completer.activated.connect(self.load_customer_mobiles)
        self.cust_name.returnPressed.connect(self.load_customer_mobiles)

        self.mobile = QComboBox()
        self.mobile.setEditable(True) 
        self.mobile.setPlaceholderText("Mobile Number (Optional)")
        self.mobile.setMinimumWidth(150)
        
        row2.addWidget(QLabel("Name:")); row2.addWidget(self.cust_name)
        row2.addWidget(QLabel("Mobile:")); row2.addWidget(self.mobile)
        details_layout.addRow(row2)
        details_group.setLayout(details_layout)
        main_layout.addWidget(details_group)

        # --- 2. Add Item Section ---
        item_group = QGroupBox("Add Item")
        item_layout = QGridLayout()
        item_layout.setContentsMargins(10, 10, 10, 10)
        item_layout.setSpacing(10)
        
        item_layout.addWidget(QLabel("Product Name:"), 0, 0)
        item_layout.addWidget(QLabel("Quantity:"), 0, 1)
        item_layout.addWidget(QLabel("MRP (Select):"), 0, 2)
        
        self.item_combo = QComboBox()
        self.item_combo.setEditable(True)
        self.item_combo.setPlaceholderText("Select Product")
        self.item_combo.setMinimumWidth(250)
        self.item_combo.currentIndexChanged.connect(self.on_item_select)
        
        self.qty = QLineEdit("1.0")
        self.qty.setFixedWidth(80)
        self.qty.returnPressed.connect(self.focus_mrp)
        
        self.rate = QComboBox()
        self.rate.setEditable(True) 
        self.rate.setFixedWidth(120)
        
        add_btn = QPushButton("Add Item")
        add_btn.setStyleSheet("height: 25px; font-weight: bold;") 
        add_btn.clicked.connect(self.add_item)
        
        del_btn = QPushButton("Delete Item")
        del_btn.setStyleSheet("height: 25px; background-color: #d32f2f; color: white; font-weight: bold;")
        del_btn.clicked.connect(self.delete_item)

        self.rate.lineEdit().returnPressed.connect(self.add_item)

        item_layout.addWidget(self.item_combo, 1, 0)
        item_layout.addWidget(self.qty, 1, 1)
        item_layout.addWidget(self.rate, 1, 2)
        item_layout.addWidget(add_btn, 1, 3)
        item_layout.addWidget(del_btn, 1, 4)
        
        item_layout.setColumnStretch(5, 1)

        QWidget.setTabOrder(self.item_combo, self.qty)
        QWidget.setTabOrder(self.qty, self.rate)
        QWidget.setTabOrder(self.rate, add_btn)

        item_group.setLayout(item_layout)
        main_layout.addWidget(item_group)

        # --- 3. Table ---
        self.table = QTableWidget(); self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Sr.", "Item Name", "Qty", "Rate", "Amount"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self.edit_item)
        main_layout.addWidget(self.table)

        # --- 4. Bottom Section (CASH & CHANGE CALCULATOR) ---
        bottom_layout = QHBoxLayout()
        self.paid_chk = QCheckBox("Mark as Paid")
        self.paid_chk.setChecked(True) # Usually true for retail
        self.whatsapp_chk = QCheckBox("Send WhatsApp")
        
        self.clear_btn = QPushButton("Clear Form"); self.clear_btn.clicked.connect(self.reset_form)
        
        # Fast Cash UI
        self.cash_label = QLabel("Cash Received: ₹")
        self.cash_input = QLineEdit()
        self.cash_input.setPlaceholderText("0.00")
        self.cash_input.setFixedWidth(80)
        self.cash_input.setValidator(QDoubleValidator(0.0, 999999.0, 2))
        self.cash_input.textChanged.connect(self.calculate_total)
        
        self.change_label = QLabel("Change: ₹0.00")
        self.change_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #107c10; padding-right: 15px;")
        
        self.discount_label = QLabel("Discount (%):")
        self.discount_input = QLineEdit("0.00"); self.discount_input.setFixedWidth(60)
        self.discount_input.textChanged.connect(self.calculate_total)
        
        self.total_label = QLabel("Total: 0.00")
        self.total_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #d32f2f; padding-right: 15px;")

        self.save_btn = QPushButton("Save Bill")
        self.save_btn.setStyleSheet("background-color: #107c10; color: white; padding: 10px; font-weight: bold; font-size: 14px;")
        self.save_btn.clicked.connect(self.save_bill)
        
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_bill)
        
        self.f5_shortcut = QShortcut(QKeySequence("F5"), self)
        self.f5_shortcut.activated.connect(self.reset_form)
        
        bottom_layout.addWidget(self.paid_chk)
        bottom_layout.addWidget(self.whatsapp_chk)
        bottom_layout.addWidget(self.clear_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.discount_label); bottom_layout.addWidget(self.discount_input)
        bottom_layout.addWidget(self.total_label)
        bottom_layout.addWidget(self.cash_label); bottom_layout.addWidget(self.cash_input)
        bottom_layout.addWidget(self.change_label)
        bottom_layout.addWidget(self.save_btn)
        main_layout.addLayout(bottom_layout)
        
        self.refresh_data()

    def refresh_data(self):
        session = Session()
        items = session.query(Inventory.item_name).distinct().all()
        self.item_combo.blockSignals(True)
        self.item_combo.clear()
        for i in items:
            self.item_combo.addItem(i.item_name)
        self.item_combo.setCurrentIndex(-1)
        self.item_combo.blockSignals(False)

        customers = session.query(Customer.name).distinct().all()
        cust_names = [c.name for c in customers if c.name]
        self.completer.setModel(QStringListModel(cust_names))
        session.close()

    def load_customer_mobiles(self):
        name = self.cust_name.text().strip()
        if not name: return
        session = Session()
        customers = session.query(Customer).filter_by(name=name).all()
        session.close()

        self.mobile.blockSignals(True)
        self.mobile.clear()
        found = False
        for c in customers:
            if c.mobile:
                self.mobile.addItem(c.mobile)
                found = True
        self.mobile.blockSignals(False)
        
        if found:
            self.mobile.showPopup(); self.mobile.setFocus()
        else:
            self.mobile.setEditText(""); self.mobile.setFocus()

    def on_item_select(self):
        name = self.item_combo.currentText().strip().title()
        if not name: return
        session = Session()
        items = session.query(Inventory).filter(func.lower(Inventory.item_name) == name.lower(), Inventory.quantity > 0).all()
        session.close()
        
        self.rate.blockSignals(True)
        self.rate.clear()
        for i in items:
            self.rate.addItem(str(i.mrp))
        self.rate.blockSignals(False)
        
        self.qty.setFocus()
        self.qty.selectAll()

    def focus_mrp(self):
        self.rate.setFocus()

    def generate_new_bill_id(self):
        session = Session()
        today = datetime.now().strftime('%Y%m%d')
        bills_today = session.query(Sale).filter(Sale.bill_id.like(f"INV-{today}-%")).all()
        numbers = [int(b.bill_id.split('-')[-1]) for b in bills_today if b.bill_id.split('-')[-1].isdigit()]
        next_num = max(numbers) + 1 if numbers else 1
        bill_id = f"INV-{today}-{next_num:04d}"
        self.bill_id_label.setText(bill_id)
        session.close()
        return bill_id

    def add_item(self):
        try:
            name = self.item_combo.currentText().strip().title()
            if not name: return QMessageBox.warning(self, "Error", "Select a product")
            
            qty = float(self.qty.text())
            rate_txt = self.rate.currentText().strip()
            if not rate_txt: rate_txt = "0.0"
            rate = float(rate_txt)
            amount = qty * rate
            
            session = Session()
            inv = session.query(Inventory).filter(func.lower(Inventory.item_name) == name.lower(), Inventory.mrp == rate).first()
            session.close()
            
            if inv:
                if inv.quantity < qty:
                    QMessageBox.warning(self, "Insufficient Stock", f"Only {inv.quantity} available for this item at Price {rate}")
                    return
            else:
                session = Session()
                name_exists = session.query(Inventory).filter(func.lower(Inventory.item_name) == name.lower()).first()
                session.close()
                if name_exists:
                    QMessageBox.warning(self, "Stock Error", "This price variation is not in stock or invalid.")
                    return

            self.table.blockSignals(True)
            row_to_update = -1
            for r in range(self.table.rowCount()):
                existing_name = self.table.item(r, 1).text()
                existing_rate = float(self.table.item(r, 3).text())
                if existing_name.lower() == name.lower() and existing_rate == rate:
                    row_to_update = r
                    break
            
            if row_to_update != -1:
                current_qty = float(self.table.item(row_to_update, 2).text())
                new_qty = current_qty + qty
                if inv and inv.quantity < new_qty:
                     QMessageBox.warning(self, "Insufficient Stock", f"Total quantity ({new_qty}) exceeds stock ({inv.quantity})")
                     self.table.blockSignals(False)
                     return

                new_amt = new_qty * rate
                self.table.setItem(row_to_update, 2, QTableWidgetItem(f"{new_qty:.2f}"))
                self.table.setItem(row_to_update, 4, QTableWidgetItem(f"{new_amt:.2f}"))
            else:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
                self.table.setItem(row, 1, QTableWidgetItem(name))
                self.table.setItem(row, 2, QTableWidgetItem(f"{qty:.2f}"))
                self.table.setItem(row, 3, QTableWidgetItem(f"{rate:.2f}"))
                self.table.setItem(row, 4, QTableWidgetItem(f"{amount:.2f}"))
            
            self.table.blockSignals(False)
            self.calculate_total()
            self.item_combo.setCurrentIndex(-1)
            self.rate.clear(); self.rate.setEditText("0.00")
            self.qty.setText("1.0")
            self.item_combo.setFocus()
            
        except ValueError: QMessageBox.warning(self, "Input Error", "Invalid Qty or Rate")

    def edit_item(self, index):
        row = index.row()
        name = self.table.item(row, 1).text()
        qty = self.table.item(row, 2).text()
        rate = self.table.item(row, 3).text()
        
        self.table.removeRow(row)
        self.table.blockSignals(True)
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setText(str(i + 1))
        self.table.blockSignals(False)
        self.calculate_total()
        
        self.item_combo.setCurrentText(name)
        self.qty.setText(qty)
        self.rate.setCurrentText(rate)
        self.qty.setFocus()
        self.qty.selectAll()

    def delete_item(self):
        row = self.table.currentRow()
        if row > -1:
            self.table.removeRow(row)
            self.table.blockSignals(True)
            for i in range(self.table.rowCount()):
                self.table.item(i, 0).setText(str(i + 1))
            self.table.blockSignals(False)
            self.calculate_total()
        else:
            QMessageBox.information(self, "Info", "Select a row to delete.")

    def calculate_total(self):
        subtotal = 0.0
        for r in range(self.table.rowCount()):
            try: subtotal += float(self.table.item(r, 4).text())
            except: pass
        
        disc_pct = 0.0
        try: disc_pct = float(self.discount_input.text())
        except: pass
        
        net = subtotal - (subtotal * (disc_pct / 100.0))
        self.total_label.setText(f"Total: {net:.2f}")

        # --- CASH & CHANGE LOGIC ---
        cash_given = 0.0
        if self.cash_input.text().strip():
            try: cash_given = float(self.cash_input.text())
            except: pass
            
        if cash_given > 0:
            change = cash_given - net
            if change >= 0:
                self.change_label.setText(f"Change: ₹{change:.2f}")
                self.change_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #107c10; padding-right: 15px;")
            else:
                self.change_label.setText(f"Short: ₹{abs(change):.2f}")
                self.change_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #d83b01; padding-right: 15px;")
        else:
            self.change_label.setText("Change: ₹0.00")
            self.change_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #107c10; padding-right: 15px;")

        return subtotal, disc_pct, net

    def save_bill(self):
        mobile = self.mobile.currentText().strip()
        name = self.cust_name.text().strip()

        if self.table.rowCount() == 0: return QMessageBox.warning(self, "Error", "Bill is empty")
        session = Session()
        try:
            bill_id = self.bill_id_label.text() if self.current_bill_id else self.generate_new_bill_id()
            
            if mobile or name:
                cust = session.query(Customer).filter_by(mobile=mobile).first() if mobile else None
                if cust: 
                    if name: cust.name = name
                    cust.last_visit = datetime.now()
                else: 
                    session.add(Customer(mobile=mobile, name=name, last_visit=datetime.now()))

            if self.current_bill_id:
                old_items = session.query(SaleItem).filter_by(sale_bill_id=bill_id).all()
                for item in old_items:
                    inv = session.query(Inventory).filter(
                        func.lower(Inventory.item_name) == item.item_name.lower(), 
                        Inventory.mrp == item.rate
                    ).first()
                    
                    if inv:
                        inv.quantity += item.quantity
                    else:
                        new_inv = Inventory(item_name=item.item_name, quantity=item.quantity, mrp=item.rate, cost_price=0.0)
                        session.add(new_inv)
                
                session.query(SaleItem).filter_by(sale_bill_id=bill_id).delete()
                session.query(Sale).filter_by(bill_id=bill_id).delete()

            sub, disc, net = self.calculate_total()
            sale = Sale(bill_id=bill_id, customer_name=name, mobile_number=mobile,
                        subtotal=sub, discount_percent=disc, net_total=net, 
                        paid_status=self.paid_chk.isChecked())
            session.add(sale)

            pdf_items = []
            for r in range(self.table.rowCount()):
                iname = self.table.item(r, 1).text()
                iqty = float(self.table.item(r, 2).text())
                irate = float(self.table.item(r, 3).text())
                iamt = float(self.table.item(r, 4).text())
                session.add(SaleItem(sale_bill_id=bill_id, sr_no=r+1, item_name=iname, quantity=iqty, rate=irate, amount=iamt))
                
                inv = session.query(Inventory).filter(func.lower(Inventory.item_name) == iname.lower(), Inventory.mrp == irate).first()
                if inv: 
                    inv.quantity -= iqty
                    if inv.quantity <= 0:
                        session.delete(inv)
                
                pdf_items.append({'sr_no': r+1, 'item_name': iname, 'quantity': iqty, 'rate': irate, 'amount': iamt})
            
            session.commit()
            QMessageBox.information(self, "Success", f"Bill {bill_id} Saved!")

            if self.whatsapp_chk.isChecked() and mobile:
                temp_dir = tempfile.gettempdir()
                temp_pdf_path = os.path.join(temp_dir, f"Bill_{bill_id}.pdf")
                biz = get_current_business_details()
                
                # Removed 'car_number', 'car_model', 'car_km' from the PDF data
                bill_data = {'bill_id': bill_id, 'date_time': datetime.now(), 'customer_name': name,
                             'mobile_number': mobile, 'items': pdf_items, 'discount_percent': disc}
                             
                generate_bill_pdf(bill_data, biz, temp_pdf_path)
                self.send_whatsapp_legacy(mobile, temp_pdf_path, bill_id, net)
                QMessageBox.information(self, "WhatsApp", "WhatsApp process started. Please wait...")

            self.reset_form()
            self.refresh_data() 
            
        except Exception as e:
            session.rollback(); QMessageBox.critical(self, "Error", str(e))
        finally: session.close()

    def send_whatsapp_legacy(self, number, pdf_path, bill_id, amount):
        def run():
            try:
                import pywhatkit as kit
                import webbrowser
                from pdf2image import convert_from_path
                
                chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
                if os.path.exists(chrome_path):
                    webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(chrome_path))
                    kit.core.core.browser = 'chrome'
                
                clean_mob = number.replace(" ", "").replace("-", "")
                if len(clean_mob) == 10 and clean_mob.isdigit():
                    final_mob = "+91" + clean_mob
                else:
                    final_mob = "+" + clean_mob if not clean_mob.startswith("+") else clean_mob

                poppler_path = resource_path(os.path.join('poppler', 'Library', 'bin'))
                if not os.path.exists(poppler_path):
                    poppler_path = os.path.abspath(RAW_POPPLER_PATH)

                images = convert_from_path(pdf_path, poppler_path=poppler_path)
                if images:
                    img_path = pdf_path.replace(".pdf", ".png")
                    images[0].save(img_path, "PNG")
                    abs_img_path = os.path.abspath(img_path)
                    
                    caption = (f"Invoice: {bill_id}\n"
                               f"Customer: {self.cust_name.text()}\n"
                               f"Total: {amount:.2f}\n"
                               f"Thank you!")
                    
                    kit.sendwhats_image(final_mob, abs_img_path, caption, 20, True, 5)
                    
                    try: os.remove(pdf_path); os.remove(img_path)
                    except: pass
                    
            except Exception as e:
                logging.error(f"WhatsApp Error: {str(e)}")
                
        threading.Thread(target=run, daemon=True).start()

    def reset_form(self):
        self.current_bill_id = None
        self.generate_new_bill_id()
        self.save_btn.setText("Save Bill")
        self.table.setRowCount(0)
        self.cust_name.clear()
        self.mobile.clear(); self.mobile.setEditText("")
        self.item_combo.setCurrentIndex(-1)
        self.qty.setText("1.0")
        self.rate.clear(); self.rate.setEditText("0.00")
        self.discount_input.setText("0.00")
        self.cash_input.clear() # Added to clear cash input
        self.paid_chk.setChecked(True)
        self.whatsapp_chk.setChecked(False)
        self.calculate_total()
    
    def load_bill_for_edit(self, bill_id):
        session = Session()
        sale = session.query(Sale).filter_by(bill_id=bill_id).first()
        if not sale: session.close(); return
        self.current_bill_id = bill_id
        self.bill_id_label.setText(bill_id)
        self.cust_name.setText(sale.customer_name); self.mobile.setEditText(sale.mobile_number)
        self.paid_chk.setChecked(sale.paid_status); self.discount_input.setText(str(sale.discount_percent))
        self.save_btn.setText("Update Bill")
        self.table.setRowCount(0); self.table.blockSignals(True)
        for item in sale.items:
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(item.sr_no)))
            self.table.setItem(r, 1, QTableWidgetItem(item.item_name))
            self.table.setItem(r, 2, QTableWidgetItem(str(item.quantity)))
            self.table.setItem(r, 3, QTableWidgetItem(str(item.rate)))
            self.table.setItem(r, 4, QTableWidgetItem(str(item.amount)))
        self.table.blockSignals(False); self.calculate_total(); session.close()