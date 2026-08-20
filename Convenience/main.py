import sys
import os
import logging
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel, QDialog, 
                             QLineEdit, QPushButton, QMessageBox, QFormLayout, QHBoxLayout)
from PyQt6.QtCore import Qt

from modules.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from database import setup_database, Session, User
import bcrypt

# Import All Tabs
from tabs.sell_tab import SellTab
from tabs.purchase_tab import PurchaseTab
from tabs.expenditure_tab import ExpenditureTab
from tabs.find_bill_tab import FindBillTab
from tabs.inventory_tab import InventoryTab
from tabs.portfolio_tab import PortfolioTab
from tabs.dashboard_tab import DashboardTab
from tabs.business_detail_tab import BusinessDetailTab
from tabs.analytics_tab import AnalyticsTab 
from tabs.customer_tab import CustomerTab

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
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Invalid Login")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Convenience Store POS System")
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
        
        # Header (Removed Reminder Bell)
        header = QHBoxLayout()
        title = QLabel("POS & Inventory System")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        
        self.tabs = QTabWidget()
        
        # Initialize Tabs
        self.tab_sell = SellTab()
        self.tab_purchase = PurchaseTab()
        self.tab_expense = ExpenditureTab()
        self.tab_find = FindBillTab()
        self.tab_inventory = InventoryTab()
        self.tab_analytics = AnalyticsTab() 
        self.tab_portfolio = PortfolioTab()
        self.tab_dash = DashboardTab()
        self.tab_biz = BusinessDetailTab()
        self.tab_customer = CustomerTab()

        self.tab_find.edit_bill_signal.connect(self.open_edit_bill)

        # Add Tabs
        self.tabs.addTab(self.tab_sell, "💰 POS / Sell")
        self.tabs.addTab(self.tab_purchase, "🛒 Purchase")
        self.tabs.addTab(self.tab_expense, "💸 Expenditure")
        self.tabs.addTab(self.tab_find, "🔍 Find Bill")
        self.tabs.addTab(self.tab_inventory, "📦 Inventory")
        self.tabs.addTab(self.tab_analytics, "📈 Analytics") 
        self.tabs.addTab(self.tab_portfolio, "📊 Portfolio")
        self.tabs.addTab(self.tab_dash, "🏠 Dashboard")
        self.tabs.addTab(self.tab_customer, "👥 Customers")
        self.tabs.addTab(self.tab_biz, "⚙️ Settings")
        
        layout.addWidget(self.tabs)
        self.tabs.currentChanged.connect(self.on_tab_change)

    def keyPressEvent(self, event):
        current_tab = self.tabs.currentWidget()
        
        if event.key() == Qt.Key.Key_F5:
            if current_tab == self.tab_sell:
                self.tab_sell.reset_form()
            elif current_tab == self.tab_expense:
                self.tab_expense.load_data()
            elif current_tab == self.tab_portfolio:
                self.tab_portfolio.calculate("all")
            else:
                if hasattr(current_tab, 'load_data'): current_tab.load_data()
                elif hasattr(current_tab, 'refresh_data'): current_tab.refresh_data()
                elif hasattr(current_tab, 'load_history'): current_tab.load_history()
        
        elif event.key() == Qt.Key.Key_Delete:
            if current_tab == self.tab_sell:
                self.tab_sell.delete_item()
            elif current_tab == self.tab_purchase:
                self.tab_purchase.delete_history_item()
            elif current_tab == self.tab_expense:
                self.tab_expense.delete_selected()
            elif current_tab == self.tab_find:
                self.tab_find.delete_bill()
            elif current_tab == self.tab_inventory:
                self.tab_inventory.delete_item()

        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if hasattr(current_tab, 'save_purchase'): current_tab.save_purchase()
            elif hasattr(current_tab, 'save_expense'): current_tab.save_expense()
            elif hasattr(current_tab, 'search_bills'): current_tab.search_bills()
            
        super().keyPressEvent(event)

    def refresh_current_tab(self):
        w = self.tabs.currentWidget()
        if hasattr(w, 'refresh_data'): w.refresh_data()
        elif hasattr(w, 'load_data'): w.load_data()
        elif hasattr(w, 'load_history'): w.load_history()
        elif hasattr(w, 'search_bills'): w.search_bills()
        elif hasattr(w, 'update_chart'): w.update_chart()

    def open_edit_bill(self, bill_id):
        self.tabs.setCurrentWidget(self.tab_sell)
        self.tab_sell.load_bill_for_edit(bill_id)

    def on_tab_change(self, index):
        self.refresh_current_tab()

if __name__ == "__main__":
    try:
        # --- WINDOWS TASKBAR FIX ---
        import ctypes
        myappid = 'mycompany.possoftware.version1' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    # ==================================================
    # THE FIX: FORCE LIGHT MODE (IGNORES OS DARK MODE)
    # ==================================================
    from PyQt6.QtGui import QPalette, QColor
    
    app.setStyle("Fusion") # 'Fusion' is the cleanest, most consistent style
    
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
    # ==================================================

    setup_database()
    
    if LoginDialog().exec() == QDialog.DialogCode.Accepted:
        win = MainWindow()
        win.showMaximized()
        sys.exit(app.exec())