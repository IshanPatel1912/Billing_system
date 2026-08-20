import os
import sys
import threading
import configparser
import logging 
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QGroupBox, QFormLayout, QMessageBox, QCheckBox, QComboBox, QCompleter)
from PyQt6.QtCore import Qt, QStringListModel, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from database import Session, Sale, SaleItem, Inventory, ServiceReminder, Customer, CustomerCar, get_current_business_details
from modules.pdf_generator import generate_bill_pdf

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

APP_NAME = "BillingSystem"
if sys.platform == 'win32':
    app_data_dir = os.path.join(os.environ['APPDATA'], APP_NAME)
else:
    app_data_dir = os.path.join(os.path.expanduser('~'), '.' + APP_NAME)

if not os.path.exists(app_data_dir):
    os.makedirs(app_data_dir)

LOG_FILE_PATH = os.path.join(app_data_dir, 'whatsapp_error.log')
logging.basicConfig(filename=LOG_FILE_PATH, level=logging.ERROR, format='%(asctime)s %(message)s')

config = configparser.ConfigParser()
config.read('config.ini')
RAW_POPPLER_PATH = config.get('SETTINGS', 'poppler_path', fallback=r'poppler\Library\bin')


class RefreshableLineEdit(QLineEdit):
    def __init__(self, parent=None, refresh_callback=None):
        super().__init__(parent)
        self.refresh_callback = refresh_callback

    def focusInEvent(self, event):
        
        if self.refresh_callback:
            self.refresh_callback()
        super().focusInEvent(event)

class SellTab(QWidget):
    bill_saved = pyqtSignal() 

    def __init__(self):
        super().__init__()
        self.current_bill_id = None
        self.whatsapp_warmed_up = False 
        
        self.init_ui()
        self.generate_new_bill_id()
        self.setup_customer_completers()
        # Initial setup (also runs when clicked)
        self.setup_item_completer() 

    def init_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

       
        details_group = QGroupBox("Bill Details")
        details_layout = QFormLayout()
        
        row1 = QHBoxLayout()
        self.bill_id_label = QLabel()
        self.bill_id_label.setStyleSheet("font-weight: bold; color: blue; font-size: 14px;")
        self.date_label = QLabel(datetime.now().strftime("%d-%m-%Y %I:%M %p"))
        row1.addWidget(QLabel("Bill ID:")); row1.addWidget(self.bill_id_label)
        row1.addStretch()
        row1.addWidget(QLabel("Date:")); row1.addWidget(self.date_label)
        details_layout.addRow(row1)

        row2 = QHBoxLayout()
        
        self.cust_name = QLineEdit()
        self.cust_name.setPlaceholderText("Customer Name (Type to suggest)")
        self.cust_name.setMinimumWidth(250)
        self.cust_name.editingFinished.connect(self.on_customer_name_edit)

        self.mobile = QComboBox()
        self.mobile.setEditable(True)
        self.mobile.setPlaceholderText("Mobile No.")
        self.mobile.setMinimumWidth(150)
        self.mobile.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.mobile.currentIndexChanged.connect(self.on_mobile_change)
        
        self.car_model = QComboBox()
        self.car_model.setEditable(True)
        self.car_model.setPlaceholderText("Car Model (Select or Type)")
        self.car_model.currentIndexChanged.connect(self.on_car_select)

        self.car_no = QLineEdit()
        self.car_no.setPlaceholderText("Car Number")
        self.car_no.setFixedWidth(100)
        
        self.car_km = QLineEdit()
        self.car_km.setPlaceholderText("KM Reading")
        self.car_km.setFixedWidth(80)
        
        row2.addWidget(QLabel("Name:")); row2.addWidget(self.cust_name)
        row2.addWidget(QLabel("Mobile:")); row2.addWidget(self.mobile)
        row2.addWidget(QLabel("Car No:")); row2.addWidget(self.car_no)
        row2.addWidget(QLabel("Model:")); row2.addWidget(self.car_model)
        row2.addWidget(QLabel("KM:")); row2.addWidget(self.car_km)
        details_layout.addRow(row2)
        details_group.setLayout(details_layout)
        main_layout.addWidget(details_group)

        
        item_group = QGroupBox("Add Item")
        item_layout = QHBoxLayout()
        
        
        self.item_name = RefreshableLineEdit(refresh_callback=self.setup_item_completer)
        self.item_name.setPlaceholderText("Item Name (Click to refresh suggestions)")
        
        self.qty = QLineEdit("1.0"); self.qty.setFixedWidth(80)
        self.rate = QLineEdit("0.00"); self.rate.setFixedWidth(100)
        
        add_btn = QPushButton("Add Item"); add_btn.clicked.connect(self.add_item)
        self.rate.returnPressed.connect(self.add_item)

        item_layout.addWidget(QLabel("Item:")); item_layout.addWidget(self.item_name)
        item_layout.addWidget(QLabel("Qty:")); item_layout.addWidget(self.qty)
        item_layout.addWidget(QLabel("Rate:")); item_layout.addWidget(self.rate)
        item_layout.addWidget(add_btn)
        item_group.setLayout(item_layout)
        main_layout.addWidget(item_group)

        
        self.table = QTableWidget(); self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Sr.", "Item Name", "Qty", "Rate", "Amount"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.cellChanged.connect(self.on_cell_change)
        main_layout.addWidget(self.table)

        
        bottom_layout = QHBoxLayout()
        self.whatsapp_chk = QCheckBox("Send WhatsApp")
        self.whatsapp_chk.setChecked(True)
        self.reminder_chk = QCheckBox("Next Service Reminder")
        self.paid_chk = QCheckBox("Mark as Paid")
        self.paid_chk.setChecked(True)
        
        self.clear_btn = QPushButton("Clear Form"); self.clear_btn.clicked.connect(self.reset_form)
        self.save_btn = QPushButton("Save Bill")
        self.save_btn.setStyleSheet("background-color: #107c10; color: white; padding: 10px; font-weight: bold;")
        self.save_btn.clicked.connect(self.save_bill)
        
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_bill)
        
        self.discount_label = QLabel("Discount (%):")
        self.discount_input = QLineEdit("0.00"); self.discount_input.setFixedWidth(60)
        self.discount_input.textChanged.connect(self.calculate_total)
        
        self.total_label = QLabel("Total: 0.00")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #d32f2f;")

        bottom_layout.addWidget(self.whatsapp_chk); bottom_layout.addWidget(self.reminder_chk)
        bottom_layout.addWidget(self.paid_chk); bottom_layout.addWidget(self.clear_btn)
        bottom_layout.addStretch(); bottom_layout.addWidget(self.discount_label); bottom_layout.addWidget(self.discount_input); bottom_layout.addWidget(self.total_label); bottom_layout.addWidget(self.save_btn)
        main_layout.addLayout(bottom_layout)

    
    def setup_customer_completers(self):
        session = Session()
        names = [c.name for c in session.query(Customer.name).distinct().all() if c.name]
        session.close()

        self.completer = QCompleter(names, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.cust_name.setCompleter(self.completer)
        self.completer.activated.connect(self.on_customer_name_edit)

    def setup_item_completer(self):
        """Loads all inventory item names into the autocomplete logic. Refreshes on click."""
        session = Session()
        
        items = [i.item_name for i in session.query(Inventory.item_name).all() if i.item_name]
        session.close()

        self.item_completer = QCompleter(items, self)
        self.item_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.item_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.item_name.setCompleter(self.item_completer)
        
        
        self.item_completer.activated.connect(self.on_item_select)

    def on_item_select(self, text):
        """Auto-fill rate when item is selected"""
        session = Session()
        item = session.query(Inventory).filter_by(item_name=text).first()
        if item:
            self.rate.setText(str(item.mrp))
        session.close()

   
    def on_customer_name_edit(self):
        name = self.cust_name.text().strip()
        if not name: return

        session = Session()
        customers = session.query(Customer).filter(Customer.name == name).all()
        session.close()

        if not customers: return 

        self.mobile.blockSignals(True) 
        self.mobile.clear()
        
        mobiles = [c.mobile for c in customers]
        self.mobile.addItems(mobiles)

        if len(customers) == 1:
            self.mobile.setCurrentIndex(0)
            self.mobile.blockSignals(False)
            self.on_mobile_change() 
        else:
            self.mobile.setCurrentText("") 
            self.mobile.blockSignals(False)
            self.mobile.showPopup() 
            self.mobile.setFocus()

    def on_mobile_change(self):
        name = self.cust_name.text().strip()
        mobile = self.mobile.currentText().strip()
        if not name or not mobile: return

        session = Session()
        customer = session.query(Customer).filter_by(name=name, mobile=mobile).first()
        
        self.car_model.blockSignals(True)
        self.car_model.clear()
        
        if customer:
            cars = session.query(CustomerCar).filter_by(customer_id=customer.id).all()
            for car in cars:
                display_text = f"{car.car_model} ({car.car_number})"
                self.car_model.addItem(display_text, [car.car_model, car.car_number])
        
        self.car_model.blockSignals(False)
    def delete_selected_item(self):
        
        current_row = self.table.currentRow()
        
        if current_row >= 0:
            
            self.table.removeRow(current_row)
            
            
            self.table.blockSignals(True)
            for row in range(self.table.rowCount()):
                self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.table.blockSignals(False)
            
            
            self.calculate_total()
        else:
            QMessageBox.warning(self, "Selection Error", "Please click on an item in the table to delete it.")

    def on_car_select(self):
        index = self.car_model.currentIndex()
        if index >= 0:
            data = self.car_model.itemData(index)
            if data:
                model, number = data
                self.car_model.setEditText(model)
                self.car_no.setText(number)

    def save_customer_data(self, session, name, mobile, car_no, car_model):
        if not name or not mobile: return

        customer = session.query(Customer).filter_by(name=name, mobile=mobile).first()
        if not customer:
            customer = Customer(name=name, mobile=mobile)
            session.add(customer)
            session.flush() 
            current_names = self.completer.model().stringList()
            if name not in current_names:
                current_names.append(name)
                self.completer.setModel(QStringListModel(current_names))

        if car_no:
            existing_car = session.query(CustomerCar).filter_by(customer_id=customer.id, car_number=car_no).first()
            if not existing_car:
                session.add(CustomerCar(customer_id=customer.id, car_model=car_model, car_number=car_no))

    

    def generate_new_bill_id(self):
        session = Session()
        today = datetime.now().strftime('%Y%m%d')
        bills_today = session.query(Sale).filter(Sale.bill_id.like(f"INV-{today}-%")).all()
        if bills_today:
            numbers = []
            for bill in bills_today:
                try: num = int(bill.bill_id.split('-')[-1]); numbers.append(num)
                except ValueError: pass
            next_num = max(numbers) + 1 if numbers else 1
        else:
            next_num = 1
        bill_id = f"INV-{today}-{next_num:04d}"
        self.bill_id_label.setText(bill_id)
        session.close()
        return bill_id

    def add_item(self):
        try:
            name = self.item_name.text().strip()
            qty = float(self.qty.text())
            rate = float(self.rate.text())
            if not name: return

            
            session = Session()
            inv_item = session.query(Inventory).filter_by(item_name=name).first()
            
            if inv_item:
                # If item exists in inventory, check stock
                if qty > inv_item.quantity:
                    QMessageBox.warning(self, "Stock Alert", 
                        f"Insufficient Stock!\n\n"
                        f"Item: {name}\n"
                        f"Available: {inv_item.quantity}\n"
                        f"Requested: {qty}")
                    session.close()
                    return # STOP here, do not add item
            session.close()
            

            amount = qty * rate
            
            self.table.blockSignals(True)
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(f"{qty:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{rate:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{amount:.2f}"))
            self.table.blockSignals(False)
            
            self.calculate_total()
            self.item_name.clear(); self.qty.setText("1.0"); self.rate.setText("0.00"); self.item_name.setFocus()
            
        except ValueError: QMessageBox.warning(self, "Input Error", "Invalid Qty or Rate")

    def on_cell_change(self, row, column):
        if column in [2, 3]: 
            try:
                q_item = self.table.item(row, 2)
                r_item = self.table.item(row, 3)
                if q_item and r_item and q_item.text() and r_item.text():
                    qty = float(q_item.text())
                    rate = float(r_item.text())
                    amt = qty * rate
                    self.table.blockSignals(True)
                    target = self.table.item(row, 4)
                    if target: target.setText(f"{amt:.2f}")
                    else: self.table.setItem(row, 4, QTableWidgetItem(f"{amt:.2f}"))
                    self.table.blockSignals(False)
                    self.calculate_total()
            except ValueError: pass

    def calculate_total(self):
        subtotal = 0.0
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 4)
            if item and item.text():
                try: subtotal += float(item.text())
                except: pass
        
        discount_percent = 0.0
        try: discount_percent = float(self.discount_input.text())
        except: pass
        
        discount_amount = subtotal * (discount_percent / 100.0)
        net_total = subtotal - discount_amount
        
        self.total_label.setText(f"Total: {net_total:.2f}")
        return subtotal, discount_percent, net_total

    def save_bill(self):
        if self.table.rowCount() == 0: return QMessageBox.warning(self, "Error", "Bill is empty")
        session = Session()
        try:
            bill_id = self.bill_id_label.text() if self.current_bill_id else self.generate_new_bill_id()
            is_edit_mode = self.current_bill_id is not None
            
            c_name = self.cust_name.text()
            c_mobile = self.mobile.currentText()
            c_model = self.car_model.currentText()
            c_no = self.car_no.text()
            c_km = self.car_km.text() 

            self.save_customer_data(session, c_name, c_mobile, c_no, c_model)

            if is_edit_mode:
                # Restore Inventory of OLD items first
                old_sale = session.query(Sale).filter_by(bill_id=bill_id).first()
                if old_sale:
                    for old_item in old_sale.items:
                        if old_item.is_tracked:
                            inv = session.query(Inventory).filter_by(item_name=old_item.item_name).first()
                            if inv:
                                inv.quantity += old_item.quantity
                            else:
                                session.add(Inventory(item_name=old_item.item_name, quantity=old_item.quantity, 
                                                      cost_price=0, mrp=old_item.rate))
                    
                    session.query(SaleItem).filter_by(sale_bill_id=bill_id).delete()
                    session.query(ServiceReminder).filter_by(bill_id=bill_id).delete()
                    
                    subtotal, discount_percent, net_total = self.calculate_total()
                    old_sale.customer_name = c_name
                    old_sale.mobile_number = c_mobile
                    old_sale.car_number = c_no
                    old_sale.car_model = c_model
                    old_sale.car_km = c_km
                    old_sale.subtotal = subtotal
                    old_sale.discount_percent = discount_percent
                    old_sale.net_total = net_total
                    old_sale.paid_status = self.paid_chk.isChecked()
            else:
                subtotal, discount_percent, net_total = self.calculate_total()
                sale = Sale(bill_id=bill_id, customer_name=c_name, mobile_number=c_mobile,
                            car_number=c_no, car_model=c_model, 
                            car_km=c_km, subtotal=subtotal, discount_percent=discount_percent, net_total=net_total, 
                            date_time=datetime.now(), paid_status=self.paid_chk.isChecked())
                session.add(sale)

            for row in range(self.table.rowCount()):
                name = self.table.item(row, 1).text()
                qty = float(self.table.item(row, 2).text())
                rate = float(self.table.item(row, 3).text())
                amt = float(self.table.item(row, 4).text())
                
                inv = session.query(Inventory).filter_by(item_name=name).first()
                is_tracked_flag = False
                if inv:
                    is_tracked_flag = True
                    inv.quantity -= qty
                    if inv.quantity <= 0:
                        session.delete(inv)
                
                session.add(SaleItem(sale_bill_id=bill_id, sr_no=row+1, item_name=name, 
                                     quantity=qty, rate=rate, amount=amt, is_tracked=is_tracked_flag))

            if self.reminder_chk.isChecked():
                due = datetime.now() + timedelta(days=364)
                session.add(ServiceReminder(bill_id=bill_id, car_number=c_no, customer_name=c_name, mobile_number=c_mobile, service_due_date=due))

            session.commit()
            self.bill_saved.emit()
            self.setup_item_completer() # Refresh suggestions

            if self.whatsapp_chk.isChecked():
                import tempfile
                temp_dir = tempfile.gettempdir()
                temp_pdf_path = os.path.join(temp_dir, f"Bill_{bill_id}.pdf")
                biz = get_current_business_details()
                
                pdf_items = []
                for row in range(self.table.rowCount()):
                    pdf_items.append({
                        'sr_no': row+1,
                        'item_name': self.table.item(row, 1).text(),
                        'quantity': float(self.table.item(row, 2).text()),
                        'rate': float(self.table.item(row, 3).text()),
                        'amount': float(self.table.item(row, 4).text())
                    })
                
                bill_data = {'bill_id': bill_id, 'date_time': datetime.now(), 'customer_name': c_name,
                                'mobile_number': c_mobile, 'car_number': c_no, 'car_model': c_model,
                                'car_km': c_km, 'items': pdf_items, 'discount_percent': discount_percent}

                generate_bill_pdf(bill_data, biz, temp_pdf_path)
                _, _, net_total = self.calculate_total()
                
                self.send_whatsapp_legacy(c_mobile, temp_pdf_path, bill_id, net_total, c_name, c_model, c_no, c_km)
                action_str = "Updated" if is_edit_mode else "Saved"
                QMessageBox.information(self, "Success", f"Bill {bill_id} {action_str} & WhatsApp Initiated!")
            else:
                if is_edit_mode:
                    QMessageBox.information(self, "Success", "Bill Updated Successfully")
                else:
                    QMessageBox.information(self, "Success", f"Bill {bill_id} Saved!")

            self.reset_form()
            
        except Exception as e:
            session.rollback(); QMessageBox.critical(self, "Error", str(e))
        finally: session.close()

    def send_whatsapp_legacy(self, number, pdf_path, bill_id, amount, c_name, c_model, c_no, c_km):
        def run():
            try:
                import pywhatkit as kit
                import webbrowser
                from pdf2image import convert_from_path
                
                chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
                if os.path.exists(chrome_path):
                    webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(chrome_path))
                    kit.core.core.browser = 'chrome'
                
                biz = get_current_business_details()
                country_code = "+91"
                
                poppler_path = resource_path(os.path.join('poppler', 'Library', 'bin'))
                if not os.path.exists(poppler_path):
                    poppler_path = os.path.abspath(RAW_POPPLER_PATH)

                images = convert_from_path(pdf_path, poppler_path=poppler_path)
                if images:
                    img_path = pdf_path.replace(".pdf", ".png")
                    images[0].save(img_path, "PNG")
                    abs_img_path = os.path.abspath(img_path)
                    
                    caption = (f"Invoice: {bill_id}\n"
                               f"Customer Name: {c_name}\n"
                               f"Car: {c_model} ({c_km} KM)\n"
                               f"Car Number: {c_no}\n"
                               f"Total: ₹{amount:.2f}\n"
                               f"Thank you for your business!")
                    
                    if not self.whatsapp_warmed_up:
                        wait_seconds = 45 
                        self.whatsapp_warmed_up = True
                    else:
                        wait_seconds = 20 
                    
                    kit.sendwhats_image(f"{country_code}{number}", abs_img_path, caption, wait_seconds, True, 5)
                    try:
                        os.remove(pdf_path); os.remove(img_path)
                    except: pass
            except Exception as e:
                logging.error(f"WhatsApp Thread Error: {str(e)}")
        threading.Thread(target=run, daemon=True).start()

    def reset_form(self):
        self.current_bill_id = None
        self.generate_new_bill_id()
        self.save_btn.setText("Save Bill")
        self.table.setRowCount(0)
        self.cust_name.clear()
        self.mobile.clear()
        self.mobile.setCurrentText("")
        self.car_model.clear()
        self.car_model.setCurrentText("")
        self.car_no.clear()
        self.car_km.clear()
        self.item_name.clear()
        self.rate.setText("0.00")
        self.qty.setText("1.0")
        self.discount_input.setText("0.00")
        self.paid_chk.setChecked(True); self.whatsapp_chk.setChecked(True)
        self.calculate_total()
        self.setup_customer_completers()
        self.setup_item_completer() 

    def load_bill_for_edit(self, bill_id):
        session = Session()
        sale = session.query(Sale).filter_by(bill_id=bill_id).first()
        if not sale: session.close(); return
        
        self.current_bill_id = bill_id
        self.bill_id_label.setText(bill_id)
        self.cust_name.setText(sale.customer_name)
        self.mobile.setEditText(sale.mobile_number)
        self.car_model.setEditText(sale.car_model or "")
        self.car_no.setText(sale.car_number)
        self.car_km.setText(sale.car_km)
        self.paid_chk.setChecked(sale.paid_status)
        self.discount_input.setText(str(sale.discount_percent))
        self.save_btn.setText("Update Bill")
        
        self.table.setRowCount(0)
        self.table.blockSignals(True)
        for item in sale.items:
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(item.sr_no)))
            self.table.setItem(r, 1, QTableWidgetItem(item.item_name))
            self.table.setItem(r, 2, QTableWidgetItem(str(item.quantity)))
            self.table.setItem(r, 3, QTableWidgetItem(str(item.rate)))
            self.table.setItem(r, 4, QTableWidgetItem(str(item.amount)))
        self.table.blockSignals(False)
        
        self.calculate_total()
        session.close()