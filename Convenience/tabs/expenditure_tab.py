from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDateEdit)
from PyQt6.QtCore import QDate
from database import Session, Expenditure
from datetime import datetime

class ExpenditureTab(QWidget):
    def __init__(self):
        super().__init__()
        self.current_id = None
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(); self.setLayout(layout)

        form = QHBoxLayout()
        self.desc = QLineEdit(); self.desc.setPlaceholderText("Description")
        self.amt = QLineEdit(); self.amt.setPlaceholderText("Amount")
        self.btn_action = QPushButton("Add Expense"); self.btn_action.clicked.connect(self.save_expense)
        form.addWidget(self.desc); form.addWidget(self.amt); form.addWidget(self.btn_action)
        layout.addLayout(form)

        filter_layout = QHBoxLayout()
        self.date_edit = QDateEdit(); self.date_edit.setCalendarPopup(True); self.date_edit.setDate(QDate.currentDate())
        btn_filter = QPushButton("Filter Date"); btn_filter.clicked.connect(self.load_data)
        btn_del = QPushButton("Delete Selected"); btn_del.clicked.connect(self.delete_selected)
        filter_layout.addWidget(QLabel("Date:")); filter_layout.addWidget(self.date_edit)
        filter_layout.addWidget(btn_filter); filter_layout.addWidget(btn_del)
        layout.addLayout(filter_layout)

        self.table = QTableWidget(); self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Date", "Description", "Amount"])
        self.table.hideColumn(0)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemClicked.connect(self.populate_form)
        layout.addWidget(self.table)

    def save_expense(self):
        try:
            d = self.desc.text().strip(); a = float(self.amt.text())
            session = Session()
            if self.current_id: # Update
                exp = session.query(Expenditure).filter_by(id=self.current_id).first()
                if exp: exp.description = d; exp.amount = a
                self.current_id = None; self.btn_action.setText("Add Expense")
            else: # Add
                session.add(Expenditure(description=d, amount=a, date_time=datetime.now()))
            session.commit(); session.close()
            self.desc.clear(); self.amt.clear(); self.load_data()
        except: QMessageBox.warning(self, "Error", "Invalid Amount")

    def populate_form(self, item):
        row = item.row()
        self.current_id = self.table.item(row, 0).text()
        self.desc.setText(self.table.item(row, 2).text())
        self.amt.setText(self.table.item(row, 3).text())
        self.btn_action.setText("Update Expense")

    def delete_selected(self):
        row = self.table.currentRow()
        if row == -1: return
        if QMessageBox.question(self, "Confirm", "Delete?") == QMessageBox.StandardButton.Yes:
            eid = self.table.item(row, 0).text()
            session = Session()
            session.query(Expenditure).filter_by(id=eid).delete()
            session.commit(); session.close()
            self.load_data()

    def load_data(self):
        session = Session()
        dt = self.date_edit.date().toPyDate()
        from sqlalchemy import func
        exps = session.query(Expenditure).filter(func.date(Expenditure.date_time) == dt).all()
        self.table.setRowCount(0)
        for e in exps:
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(e.id)))
            self.table.setItem(r, 1, QTableWidgetItem(e.date_time.strftime("%d-%m-%Y")))
            self.table.setItem(r, 2, QTableWidgetItem(e.description))
            self.table.setItem(r, 3, QTableWidgetItem(str(e.amount)))
        session.close()