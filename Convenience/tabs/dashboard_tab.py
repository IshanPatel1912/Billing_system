from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QGroupBox, QHBoxLayout, QDateEdit, QPushButton)
from PyQt6.QtCore import QDate
from datetime import datetime
from database import Session, Sale, Purchase, Expenditure
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(); self.setLayout(layout)
        
        date_layout = QHBoxLayout()
        self.date_selector = QDateEdit()
        self.date_selector.setCalendarPopup(True)
        self.date_selector.setDate(QDate.currentDate())
        
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_data)
        
        date_layout.addWidget(QLabel("Select Date:"))
        date_layout.addWidget(self.date_selector)
        date_layout.addWidget(btn_refresh)
        layout.addLayout(date_layout)
        
        self.lbl_today = QLabel(f"Dashboard - {self.date_selector.date().toPyDate().strftime('%d-%m-%Y')}")
        layout.addWidget(self.lbl_today)
        self.stats_label = QLabel("Loading..."); layout.addWidget(self.stats_label)
        
        grp_p = QGroupBox("Today's Itemized Purchases")
        v1 = QVBoxLayout()
        self.table_p = QTableWidget(); self.table_p.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_p.setColumnCount(3); self.table_p.setHorizontalHeaderLabels(["Time", "Item Name", "Amount"])
        self.table_p.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        v1.addWidget(self.table_p)
        grp_p.setLayout(v1)
        layout.addWidget(grp_p)
        
        grp_e = QGroupBox("Today's Expenses")
        v2 = QVBoxLayout()
        self.table_e = QTableWidget(); self.table_e.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_e.setColumnCount(2); self.table_e.setHorizontalHeaderLabels(["Description", "Amount"])
        self.table_e.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        v2.addWidget(self.table_e)
        grp_e.setLayout(v2)
        layout.addWidget(grp_e)

        self.refresh_data()

    def refresh_data(self):
        session = Session()
        selected_date = self.date_selector.date().toPyDate()
        date_str = selected_date.strftime('%Y-%m-%d')
        
        self.lbl_today.setText(f"Dashboard - {selected_date.strftime('%d-%m-%Y')}")
        
        # --- MODIFIED: FILTER PAID BILLS AND EXCLUDE RECYCLED ---
        total = session.query(func.sum(Sale.net_total)).filter(
            func.date(Sale.date_time) == date_str, 
            Sale.paid_status == True,
            or_(Sale.is_deleted == False, Sale.is_deleted == None)
        ).scalar() or 0
        
        count = session.query(Sale).filter(
            func.date(Sale.date_time) == date_str,
            Sale.paid_status == True,
            or_(Sale.is_deleted == False, Sale.is_deleted == None)
        ).count()
        
        self.stats_label.setText(f"Selected Date Paid Sales: {count} | Revenue (Paid Only): {total:.2f}")
        # --------------------------------------------------------
        
        purchases = session.query(Purchase).options(joinedload(Purchase.items)).filter(func.date(Purchase.date_time) == date_str).all()
        self.table_p.setRowCount(0)
        for p in purchases:
            time_str = p.date_time.strftime("%H:%M")
            for item in p.items:
                r = self.table_p.rowCount(); self.table_p.insertRow(r)
                self.table_p.setItem(r, 0, QTableWidgetItem(time_str))
                self.table_p.setItem(r, 1, QTableWidgetItem(item.item_name))
                self.table_p.setItem(r, 2, QTableWidgetItem(str(item.amount)))
            
        es = session.query(Expenditure).filter(func.date(Expenditure.date_time) == date_str).all()
        self.table_e.setRowCount(0)
        for e in es:
            r = self.table_e.rowCount(); self.table_e.insertRow(r)
            self.table_e.setItem(r, 0, QTableWidgetItem(e.description))
            self.table_e.setItem(r, 1, QTableWidgetItem(str(e.amount)))
        session.close()