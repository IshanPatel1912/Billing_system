from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout, 
                             QLineEdit, QPushButton, QMessageBox, QLabel, 
                             QHeaderView, QTableWidget, QTableWidgetItem, QHBoxLayout, QFileDialog)
from PyQt6.QtGui import QShortcut, QKeySequence
from datetime import datetime
import bcrypt
import os

from database import Session, BusinessDetail, User

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
        
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_business_details)
        
        biz_layout.addWidget(save_biz_btn)
        biz_group.setLayout(biz_layout)
        layout.addWidget(biz_group)

        # --- User Management Group ---
        user_group = QGroupBox("User Management (Login Control)")
        user_layout = QVBoxLayout()
        
        form_user = QFormLayout()
        self.new_user_name = QLineEdit()
        self.new_user_name.setPlaceholderText("Username")
        self.new_user_pass = QLineEdit()
        self.new_user_pass.setPlaceholderText("New Password")
        self.new_user_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form_user.addRow("User:", self.new_user_name)
        form_user.addRow("Pass:", self.new_user_pass)
        
        add_user_btn = QPushButton("Add User / Reset Password")
        add_user_btn.setStyleSheet("background-color: #107c10; color: white; font-weight: bold; padding: 5px;")
        add_user_btn.clicked.connect(self.add_or_update_user)
        user_layout.addLayout(form_user)
        user_layout.addWidget(add_user_btn)

        self.user_table = QTableWidget()
        self.user_table.setColumnCount(2)
        self.user_table.setHorizontalHeaderLabels(["ID", "Username"])
        self.user_table.hideColumn(0)
        self.user_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.user_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        user_layout.addWidget(self.user_table)

        del_user_btn = QPushButton("Delete Selected User")
        del_user_btn.setStyleSheet("background-color: #d83b01; color: white; font-weight: bold; padding: 5px;")
        del_user_btn.clicked.connect(self.delete_user)
        user_layout.addWidget(del_user_btn)
        
        user_group.setLayout(user_layout)
        layout.addWidget(user_group)

    def select_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.logo_path_field.setText(file_path)

    def load_data(self):
        session = Session()
        biz = session.query(BusinessDetail).first()
        if biz:
            self.biz_name.setText(biz.name if biz.name else "")
            self.biz_address.setText(biz.address if biz.address else "")
            self.biz_phone.setText(biz.phone if biz.phone else "")
            self.biz_owner.setText(biz.owner_name if biz.owner_name else "")
            self.logo_path_field.setText(biz.logo_path if biz.logo_path else "")
            
        users = session.query(User).filter_by(is_deleted=False).all()
        self.user_table.setRowCount(0)
        for u in users:
            r = self.user_table.rowCount()
            self.user_table.insertRow(r)
            self.user_table.setItem(r, 0, QTableWidgetItem(str(u.id)))
            self.user_table.setItem(r, 1, QTableWidgetItem(u.username))
        session.close()

    def save_business_details(self):
        session = Session()
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
        session.close()
        QMessageBox.information(self, "Success", "Business details updated successfully.")

    def add_or_update_user(self):
        u = self.new_user_name.text().strip()
        p = self.new_user_pass.text().strip()
        if not u or not p: return

        hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        session = Session()
        user = session.query(User).filter_by(username=u).first()
        if user:
            user.password_hash = hashed
            user.is_deleted = False 
            msg = "Password updated."
        else:
            session.add(User(username=u, password_hash=hashed))
            msg = "New user added."
        session.commit()
        session.close()
        self.new_user_name.clear()
        self.new_user_pass.clear()
        self.load_data()
        QMessageBox.information(self, "Success", msg)

    def delete_user(self):
        r = self.user_table.currentRow()
        if r == -1: return
        uid = self.user_table.item(r, 0).text()
        session = Session()
        user = session.query(User).filter_by(id=uid).first()
        if user:
            if user.username == 'admin':
                QMessageBox.warning(self, "Warning", "Cannot delete the default admin user.")
            else:
                user.is_deleted = True
                session.commit()
        session.close()
        self.load_data()