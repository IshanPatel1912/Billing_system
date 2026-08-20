import csv
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QMessageBox, QFileDialog, QDateEdit, QDialog, QFormLayout)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QShortcut, QKeySequence
from database import Session, Sale, Purchase, Expenditure
from sqlalchemy import func, or_
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ==========================================
# POPUP DIALOG FOR DATE RANGE SELECTION
# ==========================================
class DateRangeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Report Date Range")
        self.setFixedSize(300, 150)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        
        today = QDate.currentDate()
        first_day = QDate(today.year(), today.month(), 1)
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(first_day)
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(today)

        form.addRow("Start Date:", self.start_date)
        form.addRow("End Date:", self.end_date)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Generate Report")
        btn_ok.setStyleSheet("background-color: #0078d4; color: white; font-weight: bold;")
        btn_ok.clicked.connect(self.accept)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def get_dates(self):
        s = self.start_date.date().toPyDate()
        e = self.end_date.date().toPyDate()
        start_dt = datetime(s.year, s.month, s.day, 0, 0, 0)
        end_dt = datetime(e.year, e.month, e.day, 23, 59, 59)
        
        date_string = f"{s.strftime('%d-%m-%Y')} to {e.strftime('%d-%m-%Y')}"
        return start_dt, end_dt, date_string

# ==========================================
# MAIN PORTFOLIO TAB
# ==========================================
class PortfolioTab(QWidget):
    def __init__(self):
        super().__init__()
        self.stats = {} 
        self.init_ui()
        self.calculate("all")

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        filter_layout = QHBoxLayout()
        btn_today = QPushButton("Today"); btn_today.clicked.connect(lambda: self.calculate("day"))
        btn_month = QPushButton("This Month"); btn_month.clicked.connect(lambda: self.calculate("month"))
        btn_year = QPushButton("This Year"); btn_year.clicked.connect(lambda: self.calculate("year"))
        btn_all = QPushButton("All Time"); btn_all.clicked.connect(lambda: self.calculate("all"))
        
        filter_layout.addWidget(btn_today); filter_layout.addWidget(btn_month)
        filter_layout.addWidget(btn_year); filter_layout.addWidget(btn_all)
        layout.addLayout(filter_layout)

        self.lbl_sales = QLabel("Total Sales (Paid): 0.00")
        self.lbl_purch = QLabel("Total Purchases: 0.00")
        self.lbl_exp = QLabel("Total Expenses: 0.00")
        self.lbl_profit = QLabel("Net Profit: 0.00")
        
        font = self.lbl_sales.font(); font.setPointSize(16); font.setBold(True)
        for l in [self.lbl_sales, self.lbl_purch, self.lbl_exp, self.lbl_profit]:
            l.setFont(font); layout.addWidget(l)

        btn_recalc = QPushButton("🔄 Recalculate Screen Stats"); btn_recalc.clicked.connect(lambda: self.calculate("all"))
        layout.addWidget(btn_recalc)
        layout.addStretch()

        export_title = QLabel("Export Detailed Transaction Reports (Selects Date Range)")
        export_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #005a9e;")
        layout.addWidget(export_title)

        export_layout1 = QHBoxLayout()
        btn_sell_pdf = QPushButton("📑 Sell Report (PDF)")
        btn_sell_pdf.setStyleSheet("background-color: #107c10; color: white; font-weight: bold; padding: 8px;")
        btn_sell_pdf.clicked.connect(self.export_sell_pdf)

        btn_purch_pdf = QPushButton("📑 Purchase Report (PDF)")
        btn_purch_pdf.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; padding: 8px;")
        btn_purch_pdf.clicked.connect(self.export_purch_pdf)

        btn_exp_pdf = QPushButton("📑 Expenditure Report (PDF)")
        btn_exp_pdf.setStyleSheet("background-color: #d83b01; color: white; font-weight: bold; padding: 8px;")
        btn_exp_pdf.clicked.connect(self.export_exp_pdf)

        export_layout1.addWidget(btn_sell_pdf)
        export_layout1.addWidget(btn_purch_pdf)
        export_layout1.addWidget(btn_exp_pdf)
        
        export_layout2 = QHBoxLayout()
        btn_all_pdf = QPushButton("📑 All Over Report (PDF)")
        btn_all_pdf.setStyleSheet("background-color: #0078d4; color: white; font-weight: bold; padding: 8px;")
        btn_all_pdf.clicked.connect(self.export_all_pdf)

        btn_all_csv = QPushButton("📄 All Over Report (CSV)")
        btn_all_csv.setStyleSheet("background-color: #4b4b4b; color: white; font-weight: bold; padding: 8px;")
        btn_all_csv.clicked.connect(self.export_all_csv)

        export_layout2.addWidget(btn_all_pdf)
        export_layout2.addWidget(btn_all_csv)

        layout.addLayout(export_layout1)
        layout.addLayout(export_layout2)

    def calculate(self, period):
        session = Session()
        
        q_s = session.query(func.sum(Sale.net_total)).filter(
            Sale.paid_status == True,
            or_(Sale.is_deleted == False, Sale.is_deleted == None)
        )
        q_p = session.query(func.sum(Purchase.total_amount))
        q_e = session.query(func.sum(Expenditure.amount))
        
        now = datetime.now()
        start_dt = None; end_dt = None
        
        if period == "day": start_dt = datetime(now.year, now.month, now.day)
        elif period == "month": start_dt = datetime(now.year, now.month, 1)
        elif period == "year": start_dt = datetime(now.year, 1, 1)

        if start_dt:
            q_s = q_s.filter(Sale.date_time >= start_dt)
            q_p = q_p.filter(Purchase.date_time >= start_dt)
            q_e = q_e.filter(Expenditure.date_time >= start_dt)

        s = q_s.scalar() or 0.0
        p = q_p.scalar() or 0.0
        e = q_e.scalar() or 0.0
        session.close()
        
        profit = s - p - e
        
        self.lbl_sales.setText(f"Total Sales (Paid): {s:,.2f}")
        self.lbl_purch.setText(f"Total Purchases: {p:,.2f}")
        self.lbl_exp.setText(f"Total Expenses: {e:,.2f}")
        self.lbl_profit.setText(f"Net Profit: {profit:,.2f}")
        
        if profit >= 0: self.lbl_profit.setStyleSheet("color: green")
        else: self.lbl_profit.setStyleSheet("color: red")

    def get_filtered_query(self, session, model, start_dt, end_dt):
        query = session.query(model)
        if model == Sale:
            query = query.filter(Sale.paid_status == True, or_(Sale.is_deleted == False, Sale.is_deleted == None))
        if start_dt and end_dt:
            query = query.filter(model.date_time >= start_dt, model.date_time <= end_dt)
        return query.order_by(model.date_time).all()

    def get_all_transactions(self, start_dt, end_dt):
        session = Session()
        sales = self.get_filtered_query(session, Sale, start_dt, end_dt)
        purchases = self.get_filtered_query(session, Purchase, start_dt, end_dt)
        expenses = self.get_filtered_query(session, Expenditure, start_dt, end_dt)

        transactions = []
        sales_total = 0.0
        purchases_total = 0.0
        expenses_total = 0.0

        for s in sales:
            transactions.append([s.date_time, 'Sale', s.bill_id, s.net_total, 0.0])
            sales_total += s.net_total
            
        for p in purchases:
            # We fetch the exact items purchased and format them
            items_str = ", ".join([f"{item.item_name} (x{item.quantity})" for item in p.items]) if p.items else (p.category or 'General')
            transactions.append([p.date_time, 'Purchase', items_str, 0.0, p.total_amount])
            purchases_total += p.total_amount
            
        for e in expenses:
            transactions.append([e.date_time, 'Expense', e.description, 0.0, e.amount])
            expenses_total += e.amount

        transactions.sort(key=lambda x: x[0]) 
        session.close() # Close session only after fetching p.items
        
        profit = sales_total - purchases_total - expenses_total
        return transactions, sales_total, purchases_total, expenses_total, profit

    def build_pdf_document(self, path, title, headers, row_data, date_string, col_widths=None, num_total_rows=1):
        try:
            doc = SimpleDocTemplate(path, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            elements.append(Paragraph(f"<b><font color='#005a9e'>{title}</font></b>", styles['Title']))
            elements.append(Paragraph(f"<b>Period Filtered:</b> {date_string}", styles['Normal']))
            elements.append(Spacer(1, 15))
            
            table_data = [headers] + row_data
            if len(row_data) == 0:
                table_data.append(["No transactions found for this period."] * len(headers))
                num_total_rows = 1 
            
            t = Table(table_data, colWidths=col_widths) 
            
            # Base table styling
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#005a9e")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            
            # Make the Total Rows bold
            if len(row_data) > 0:
                table_style.append(('FONTNAME', (0, -num_total_rows), (-1, -1), 'Helvetica-Bold'))
                
            t.setStyle(TableStyle(table_style))
            elements.append(t)
            doc.build(elements)
            QMessageBox.information(self, "Success", f"{title} Exported Successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate PDF:\n{str(e)}")

    def export_sell_pdf(self):
        dialog = DateRangeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            start_dt, end_dt, date_str = dialog.get_dates()
            path, _ = QFileDialog.getSaveFileName(self, "Save Sell Report", "Sell_Report.pdf", "PDF Files (*.pdf)")
            if not path: return
            
            session = Session()
            sales = self.get_filtered_query(session, Sale, start_dt, end_dt)
            session.close()

            headers = ['Date & Time', 'Bill ID', 'Customer', 'Net Total']
            row_data = [[s.date_time.strftime("%d-%m-%Y %H:%M"), s.bill_id, s.customer_name or "Retail", f"{s.net_total:.2f}"] for s in sales]
            
            if row_data:
                total_sales = sum(s.net_total for s in sales)
                row_data.append(["", "", "GRAND TOTAL:", f"{total_sales:.2f}"])
                
            self.build_pdf_document(path, "Detailed Sales Report", headers, row_data, date_str, col_widths=[120, 150, 150, 80], num_total_rows=1)

    def export_purch_pdf(self):
        dialog = DateRangeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            start_dt, end_dt, date_str = dialog.get_dates()
            path, _ = QFileDialog.getSaveFileName(self, "Save Purchase Report", "Purchase_Report.pdf", "PDF Files (*.pdf)")
            if not path: return
            
            session = Session()
            purchases = self.get_filtered_query(session, Purchase, start_dt, end_dt)

            headers = ['Date & Time', 'Items Purchased', 'Total Amount']
            row_data = []
            total_purchases = 0.0
            
            styles = getSampleStyleSheet()
            for p in purchases:
                # Get the detailed items and wrap them so they fit in the PDF nicely
                items_str = ", ".join([f"{item.item_name} (x{item.quantity})" for item in p.items]) if p.items else (p.category or "General")
                items_para = Paragraph(items_str, styles['Normal'])
                
                row_data.append([p.date_time.strftime("%d-%m-%Y %H:%M"), items_para, f"{p.total_amount:.2f}"])
                total_purchases += p.total_amount
                
            session.close()

            if row_data:
                row_data.append(["", "GRAND TOTAL:", f"{total_purchases:.2f}"])
                
            self.build_pdf_document(path, "Detailed Purchases Report", headers, row_data, date_str, col_widths=[120, 280, 100], num_total_rows=1)

    def export_exp_pdf(self):
        dialog = DateRangeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            start_dt, end_dt, date_str = dialog.get_dates()
            path, _ = QFileDialog.getSaveFileName(self, "Save Expenditure Report", "Expenditure_Report.pdf", "PDF Files (*.pdf)")
            if not path: return
            
            session = Session()
            expenses = self.get_filtered_query(session, Expenditure, start_dt, end_dt)
            session.close()

            headers = ['Date & Time', 'Description', 'Amount']
            row_data = [[e.date_time.strftime("%d-%m-%Y %H:%M"), e.description, f"{e.amount:.2f}"] for e in expenses]
            
            if row_data:
                total_exp = sum(e.amount for e in expenses)
                row_data.append(["", "GRAND TOTAL:", f"{total_exp:.2f}"])
                
            self.build_pdf_document(path, "Detailed Expenditures Report", headers, row_data, date_str, col_widths=[150, 250, 100], num_total_rows=1)

    def export_all_pdf(self):
        dialog = DateRangeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            start_dt, end_dt, date_str = dialog.get_dates()
            path, _ = QFileDialog.getSaveFileName(self, "Save All Over Report", "AllOver_Report.pdf", "PDF Files (*.pdf)")
            if not path: return

            txns, s_tot, p_tot, e_tot, profit = self.get_all_transactions(start_dt, end_dt)
            headers = ['Date', 'Type', 'Description / Items', 'Income (+)', 'Expense (-)']
            
            row_data = []
            styles = getSampleStyleSheet()
            for t in txns:
                # Wrap description in paragraph to handle long lists of purchased items
                desc_para = Paragraph(str(t[2]), styles['Normal'])
                row_data.append([t[0].strftime("%d-%m-%y %H:%M"), t[1], desc_para, f"{t[3]:.2f}" if t[3] else "-", f"{t[4]:.2f}" if t[4] else "-"])
            
            if row_data:
                row_data.append(["", "", "TOTALS:", f"{s_tot:.2f}", f"{(p_tot + e_tot):.2f}"])
                row_data.append(["", "", "NET PROFIT:", f"{profit:.2f}", ""])
            
            self.build_pdf_document(path, "Complete Transaction History", headers, row_data, date_str, col_widths=[90, 70, 200, 70, 70], num_total_rows=2)

    def export_all_csv(self):
        dialog = DateRangeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            start_dt, end_dt, date_str = dialog.get_dates()
            path, _ = QFileDialog.getSaveFileName(self, "Save All Over Report (CSV)", "AllOver_Report.csv", "CSV Files (*.csv)")
            if not path: return
            
            txns, s_tot, p_tot, e_tot, profit = self.get_all_transactions(start_dt, end_dt)
            try:
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Business Portfolio Report - All Transactions"])
                    writer.writerow(["Period", date_str])
                    writer.writerow([])
                    
                    writer.writerow(['Date & Time', 'Transaction Type', 'Description / Items', 'Income Amount (+)', 'Expense Amount (-)'])
                    for t in txns:
                        writer.writerow([t[0].strftime("%d-%m-%Y %H:%M:%S"), t[1], t[2], t[3], t[4]])
                        
                    writer.writerow([])
                    writer.writerow(["TOTALS", "", "", s_tot, p_tot + e_tot])
                    writer.writerow(["NET PROFIT", "", "", profit])
                    
                QMessageBox.information(self, "Success", "Complete CSV Report Exported Successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save CSV:\n{str(e)}")