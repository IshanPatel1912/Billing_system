import sys
import os
import logging
import ctypes
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel, QDialog, 
                             QLineEdit, QPushButton, QMessageBox, QFormLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt


from modules.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from database import setup_database, Session, User, ServiceReminder, get_current_business_details
from datetime import datetime
from PyQt6.QtGui import QIcon
import bcrypt
import threading

# Import All Tabs
from tabs.sell_tab import SellTab
from tabs.purchase_tab import PurchaseTab
from tabs.expenditure_tab import ExpenditureTab
from tabs.find_bill_tab import FindBillTab
from tabs.inventory_tab import InventoryTab
from tabs.portfolio_tab import PortfolioTab
from tabs.dashboard_tab import DashboardTab
from tabs.business_detail_tab import BusinessDetailTab
from tabs.tracked_items_tab import TrackedItemsTab
from tabs.purchase_history_tab import PurchaseHistoryTab
from tabs.customer_tab import CustomerTab


WHATSAPP_PROCESS = None

def launch_whatsapp_background():
    """Launches WhatsApp Web in a separate Chrome process."""
    global WHATSAPP_PROCESS
    try:
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
        ]
        
        chrome_exe = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_exe = path
                break
        
        if chrome_exe:
            WHATSAPP_PROCESS = subprocess.Popen([chrome_exe, "--new-window", "https://web.whatsapp.com"])
            print("WhatsApp Web launched in background.")
        else:
            print("Chrome not found. WhatsApp background launch skipped.")
            
    except Exception as e:
        print(f"Failed to launch WhatsApp: {e}")

def close_whatsapp_background():
    """Closes the WhatsApp browser window we opened."""
    global WHATSAPP_PROCESS
    if WHATSAPP_PROCESS:
        try:
            WHATSAPP_PROCESS.terminate()
            print("WhatsApp Web closed.")
        except Exception as e:
            print(f"Error closing WhatsApp: {e}")

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        self.setFixedSize(300, 150)
        layout = QVBoxLayout()
        form = QFormLayout()
        
        self.user = QLineEdit(); self.user.setPlaceholderText("Username")
        self.pwd = QLineEdit(); self.pwd.setPlaceholderText("Password"); self.pwd.setEchoMode(QLineEdit.EchoMode.Password)
        
        form.addRow("User:", self.user)
        form.addRow("Pass:", self.pwd)
        
        btn = QPushButton("Login")
        btn.clicked.connect(self.check_login)
        
        layout.addLayout(form)
        layout.addWidget(btn)
        self.setLayout(layout)

    def check_login(self):
        u = self.user.text()
        p = self.pwd.text()
        session = Session()
        user = session.query(User).filter_by(username=u).first()
        session.close()
        
        if user and bcrypt.checkpw(p.encode(), user.password_hash.encode()):
            launch_whatsapp_background()
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Invalid Login")

class ReminderDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Service Reminders Due")
        self.resize(700, 400)
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget(); self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Customer", "Car", "Mobile", "Due Date"])
        self.table.hideColumn(0)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        btns = QHBoxLayout()
        btn_mark = QPushButton("✅ Mark Notified")
        btn_mark.clicked.connect(self.mark_notified)
        
        btn_wa = QPushButton("📤 Send WhatsApp Reminder")
        btn_wa.setStyleSheet("background-color: #25D366; color: white; font-weight: bold;")
        btn_wa.clicked.connect(self.send_wa)
        
        btns.addWidget(btn_mark)
        btns.addWidget(btn_wa)
        layout.addLayout(btns)
        
        self.load_reminders()

    def load_reminders(self):
        session = Session()
        rems = session.query(ServiceReminder).filter(ServiceReminder.service_due_date <= datetime.now(), ServiceReminder.is_notified == False).all()
        self.table.setRowCount(0)
        for r in rems:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(r.id)))
            self.table.setItem(row, 1, QTableWidgetItem(r.customer_name))
            self.table.setItem(row, 2, QTableWidgetItem(r.car_number))
            self.table.setItem(row, 3, QTableWidgetItem(r.mobile_number))
            self.table.setItem(row, 4, QTableWidgetItem(r.service_due_date.strftime("%d-%m-%Y")))
        session.close()

    def mark_notified(self):
        row = self.table.currentRow()
        if row == -1: return
        rid = self.table.item(row, 0).text()
        
        session = Session()
        r = session.query(ServiceReminder).filter_by(id=rid).first()
        if r: 
            r.is_notified = True
            session.commit()
        session.close()
        self.load_reminders()

    def send_wa(self):
        row = self.table.currentRow()
        if row == -1: 
            QMessageBox.warning(self, "Select", "Please select a row first.")
            return
            
        customer_name = self.table.item(row, 1).text()
        car_number = self.table.item(row, 2).text()
        mobile = self.table.item(row, 3).text()
        due_date = self.table.item(row, 4).text()
        rid = self.table.item(row, 0).text()
        
        biz = get_current_business_details()
        biz_name = biz.name if biz else "Service Center"
        country_code = "+91"

        message = (f"🔔 Vehicle Service Reminder\n"
                   f"Hello {customer_name},\n"
                   f"This is a reminder that the next service of your vehicle is due.\n"
                   f"🚗 Car Number: {car_number}\n"
                   f"📅 Service Due Date: {due_date}\n"
                   f"Please contact us for booking.\n"
                   f"Thank you!\n"
                   f"– {biz_name}")

        def run():
            try:
                import pywhatkit as kit
                kit.sendwhatmsg_instantly(f"{country_code}{mobile}", message, 15, True, 4)
            except Exception:
                logger.exception("WhatsApp Error while sending reminder to %s", mobile)
        
        threading.Thread(target=run, daemon=True).start()
        
        session = Session()
        r = session.query(ServiceReminder).filter_by(id=rid).first()
        if r: 
            r.is_notified = True
            session.commit()
        session.close()
        
        QMessageBox.information(self, "Sending", "WhatsApp initiated... Please wait for browser.")
        self.load_reminders()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern Billing System")
        self.resize(1200, 800)
        
    
        
        self.setStyleSheet("""
            QMainWindow { background-color: #f3f3f3; }
            QTabWidget::pane { border: 1px solid #ccc; background: white; }
            QTabBar::tab { background: #ddd; padding: 10px 20px; border-radius: 4px; margin-right: 2px; }
            QTabBar::tab:selected { background: #0078d4; color: white; font-weight: bold; }
            QLineEdit, QTableWidget { border: 1px solid #ccc; padding: 5px; }
            QComboBox { padding: 5px; }
        """)


        central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("Billing & Inventory System"))
        self.btn_bell = QPushButton("🔔 Reminders")
        self.btn_bell.setStyleSheet("background-color: #ffcccb; font-weight: bold; padding: 5px 15px;")
        self.btn_bell.clicked.connect(self.show_reminders)
        header.addStretch()
        header.addWidget(self.btn_bell)
        layout.addLayout(header)
        
        self.tabs = QTabWidget()
        
        self.tab_sell = SellTab()
        self.tab_purchase = PurchaseTab()
        self.tab_expense = ExpenditureTab()
        self.tab_find = FindBillTab()
        self.tab_inventory = InventoryTab()
        self.tab_tracked = TrackedItemsTab()
        self.tab_portfolio = PortfolioTab()
        self.tab_dash = DashboardTab()
        self.tab_purchase_history = PurchaseHistoryTab()
        self.tab_customer_tab = CustomerTab()
        self.tab_biz = BusinessDetailTab()

        self.tab_find.edit_bill_signal.connect(self.open_edit_bill)

        self.tabs.addTab(self.tab_sell, "💰 Sell")
        self.tabs.addTab(self.tab_purchase, "🛒 Gen.Purchase")
        self.tabs.addTab(self.tab_tracked, "📋 Tracked Items Purchase")
        self.tabs.addTab(self.tab_expense, "💸 Expenditure")
        self.tabs.addTab(self.tab_purchase_history, "🕰️ Purchase History")
        self.tabs.addTab(self.tab_find, "🔍 Find Bill")
        self.tabs.addTab(self.tab_inventory, "📦 Inventory")
        self.tabs.addTab(self.tab_portfolio, "📊 Portfolio")
        self.tabs.addTab(self.tab_dash, "🏠 Dashboard")
        self.tabs.addTab(self.tab_customer_tab, "👥 Customers")
        self.tabs.addTab(self.tab_biz, "⚙️ Settings")
        
        layout.addWidget(self.tabs)
        self.tabs.currentChanged.connect(self.on_tab_change)
        self.check_reminders()

    def keyPressEvent(self, event):
        current_tab = self.tabs.currentWidget()
        
        if event.key() == Qt.Key.Key_F5:
            if current_tab == self.tab_sell:
                self.tab_sell.reset_form()
            elif current_tab == self.tab_customer_tab:
                self.tab_customer_tab.clear_form()
            elif current_tab == self.tab_expense:
                self.tab_expense.load_data()
            elif current_tab == self.tab_tracked:
                self.tab_tracked.clear_list()
            elif current_tab == self.tab_portfolio:
                self.tab_portfolio.calculate("all")
            else:
                if hasattr(current_tab, 'load_data'): current_tab.load_data()
                elif hasattr(current_tab, 'refresh_data'): current_tab.refresh_data()
                elif hasattr(current_tab, 'load_history'): current_tab.load_history()
        
        elif event.key() == Qt.Key.Key_Delete:
            if current_tab == self.tab_sell:
                self.tab_sell.delete_selected_item()
            elif current_tab == self.tab_purchase_history:    
                self.tab_purchase_history.delete_history_item()
            elif current_tab == self.tab_purchase:
                self.tab_purchase.delete_history_item()
            elif current_tab == self.tab_expense:
                self.tab_expense.delete_selected()
            elif current_tab == self.tab_find:
                self.tab_find.delete_bill()
            elif current_tab == self.tab_tracked:
                self.tab_tracked.delete_row()
            elif current_tab == self.tab_inventory:
                self.tab_inventory.delete_selected_item()
            elif current_tab == self.tab_customer_tab:    
                self.tab_customer_tab.remove_car_from_form()
            elif current_tab == self.tab_customer_tab:    
                self.tab_customer_tab.delete_customer()

        elif event.key() == Qt.Key.Key_S and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            if current_tab == self.tab_customer_tab:
                self.tab_customer_tab.save_customer() 

        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if hasattr(current_tab, 'add_item'): current_tab.add_item()
            elif hasattr(current_tab, 'add_row'): current_tab.add_row()
            elif hasattr(current_tab, 'save_expense'): current_tab.save_expense()
            elif hasattr(current_tab, 'search_bills'): current_tab.search_bills()
            
        super().keyPressEvent(event)

    def refresh_current_tab(self):
        w = self.tabs.currentWidget()
        if hasattr(w, 'refresh_data'): w.refresh_data()
        elif hasattr(w, 'load_data'): w.load_data()
        elif hasattr(w, 'load_history'): w.load_history()
        elif hasattr(w, 'search_bills'): w.search_bills()
        self.check_reminders()
    
    def open_edit_bill(self, bill_id):
        self.tabs.setCurrentWidget(self.tab_sell)
        self.tab_sell.load_bill_for_edit(bill_id)

    def on_tab_change(self, index):
        self.refresh_current_tab()

    def show_reminders(self):
        ReminderDialog(self).exec()
        self.check_reminders()

    def check_reminders(self):
        session = Session()
        count = session.query(ServiceReminder).filter(ServiceReminder.service_due_date <= datetime.now(), ServiceReminder.is_notified == False).count()
        session.close()
        self.btn_bell.setText(f"🔔 Reminders ({count})")
        if count > 0:
            self.btn_bell.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; padding: 5px 15px; border-radius: 4px;")
        else:
            self.btn_bell.setStyleSheet("background-color: #e0e0e0; color: #333; padding: 5px 15px; border-radius: 4px;")
    
    def closeEvent(self, event):
        """Handle window close event to kill WhatsApp browser."""
        close_whatsapp_background()
        event.accept()

if __name__ == "__main__":
    try:
        import ctypes
        myappid = 'mycompany.billingsoftware.version1' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    try:
        app = QApplication(sys.argv)
        
        
        from PyQt6.QtGui import QPalette, QColor
        
        app.setStyle("Fusion") 
        
        light_palette = QPalette()
        light_palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        light_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        light_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        light_palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
        light_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        
        app.setPalette(light_palette)
    
        from PyQt6.QtGui import QIcon
        import os
        
        # This guarantees Python finds the icon no matter how you launch the app
        icon_path = resource_path("app_icon.ico") 
        
        app_icon = QIcon(icon_path) 
        app.setWindowIcon(app_icon)
        
        setup_database()

        if LoginDialog().exec() == QDialog.DialogCode.Accepted:
            win = MainWindow()
            win.setWindowIcon(app_icon)
            win.showMaximized() 
            sys.exit(app.exec())
    except Exception:
        logger.exception('Unhandled exception in application')
        raise