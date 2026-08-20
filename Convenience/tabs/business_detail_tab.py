from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout, 
                             QLineEdit, QPushButton, QMessageBox, QLabel, 
                             QHeaderView, QTableWidget, QTableWidgetItem, QHBoxLayout, QFileDialog)
from PyQt6.QtGui import QShortcut, QKeySequence
from database import Session, BusinessDetail, User
import bcrypt
import os

class BusinessDetailTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # --- Business Info Group ---
        biz_group = QGroupBox("Business Details")
        biz_layout = QFormLayout()
        
        self.biz_name = QLineEdit()
        self.biz_address = QLineEdit()
        self.biz_phone = QLineEdit()
        self.biz_owner = QLineEdit()
        
        # Logo Selection UI
        logo_layout = QHBoxLayout()
        self.logo_path_field = QLineEdit()
        self.logo_path_field.setPlaceholderText("Select Logo Image...")
        self.logo_path_field.setReadOnly(True) 
        
        btn_browse_logo = QPushButton("Browse")
        btn_browse_logo.clicked.connect(self.select_logo)
        
        logo_layout.addWidget(self.logo_path_field)
        logo_layout.addWidget(btn_browse_logo)
        
        biz_layout.addRow("Business Name:", self.biz_name)
        biz_layout.addRow("Address:", self.biz_address)
        biz_layout.addRow("Phone:", self.biz_phone)
        biz_layout.addRow("Owner Name:", self.biz_owner)
        biz_layout.addRow("Logo:", logo_layout) 
        
        save_biz_btn = QPushButton("Save Business Details")
        save_biz_btn.setStyleSheet("background-color: #0078d4; color: white; font-weight: bold; padding: 5px;")
        save_biz_btn.clicked.connect(self.save_business_details)
        
        # Add Ctrl+S shortcut for save business details
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_business_details)
        
        biz_layout.addWidget(save_biz_btn)
        
        biz_group.setLayout(biz_layout)
        layout.addWidget(biz_group)

        # --- User Management Group ---
        user_group = QGroupBox("User Management (Login Control)")
        user_layout = QFormLayout()
        
        self.new_user_name = QLineEdit()
        self.new_user_pass = QLineEdit()
        self.new_user_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_user_pass.setPlaceholderText("New Password")
        
        add_user_btn = QPushButton("Add User / Reset Password")
        add_user_btn.setStyleSheet("background-color: #107c10; color: white; font-weight: bold; padding: 5px;")
        add_user_btn.clicked.connect(self.add_or_update_user)
        
        user_layout.addRow("Username:", self.new_user_name)
        user_layout.addRow("Password:", self.new_user_pass)
        user_layout.addWidget(add_user_btn)
        
        user_group.setLayout(user_layout)
        layout.addWidget(user_group)

        # --- User List Table ---
        # FIX: The variable name here is 'self.user_table'
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(2)
        self.user_table.setHorizontalHeaderLabels(["ID", "Username"])
        self.user_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.user_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.user_table)
        
        # --- Delete User Button ---
        del_user_btn = QPushButton("Delete Selected User")
        del_user_btn.setStyleSheet("background-color: #d83b01; color: white; font-weight: bold; padding: 5px;")
        del_user_btn.clicked.connect(self.delete_user)
        layout.addWidget(del_user_btn)

    def load_data(self):
        session = Session()
        
        # Load Biz Details
        biz = session.query(BusinessDetail).first()
        if biz:
            self.biz_name.setText(biz.name)
            self.biz_address.setText(biz.address)
            self.biz_phone.setText(biz.phone)
            self.biz_owner.setText(biz.owner_name if biz.owner_name else "")
            self.logo_path_field.setText(biz.logo_path if biz.logo_path else "")
            
        # Load Users
        users = session.query(User).all()
        # FIX: Access 'self.user_table' instead of 'self.table'
        self.user_table.setRowCount(0)
        for u in users:
            r = self.user_table.rowCount()
            self.user_table.insertRow(r)
            self.user_table.setItem(r, 0, QTableWidgetItem(str(u.id)))
            self.user_table.setItem(r, 1, QTableWidgetItem(u.username))
            
        session.close()

    def select_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            self.logo_path_field.setText(file_path)

    def save_business_details(self):
        session = Session()
        try:
            biz = session.query(BusinessDetail).first()
            if not biz:
                biz = BusinessDetail()
                session.add(biz)
            
            biz.name = self.biz_name.text()
            biz.address = self.biz_address.text()
            biz.phone = self.biz_phone.text()
            biz.owner_name = self.biz_owner.text()
            biz.logo_path = self.logo_path_field.text()
            
            session.commit()
            QMessageBox.information(self, "Success", "Business Details & Logo Saved")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def add_or_update_user(self):
        username = self.new_user_name.text().strip()
        password = self.new_user_pass.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Username and Password required")
            return
            
        session = Session()
        try:
            user = session.query(User).filter_by(username=username).first()
            
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            if user:
                user.password_hash = hashed
                msg = "Password Updated"
            else:
                user = User(username=username, password_hash=hashed)
                session.add(user)
                msg = "User Created"
                
            session.commit()
            QMessageBox.information(self, "Success", msg)
            self.new_user_name.clear()
            self.new_user_pass.clear()
            self.load_data()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def delete_user(self):
        # FIX: Ensure consistent use of 'self.user_table'
        row = self.user_table.currentRow()
        if row == -1:
            return
        
        uid = self.user_table.item(row, 0).text()
        username = self.user_table.item(row, 1).text()
        
        if username == "admin":
             if QMessageBox.question(self, "Warning", "Deleting the 'admin' user might lock you out if no other users exist. Continue?") != QMessageBox.StandardButton.Yes:
                 return

        if QMessageBox.question(self, "Confirm", f"Are you sure you want to delete user '{username}'?") == QMessageBox.StandardButton.Yes:
            session = Session()
            try:
                session.query(User).filter_by(id=uid).delete()
                session.commit()
                self.load_data()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", str(e))
            finally:
                session.close()