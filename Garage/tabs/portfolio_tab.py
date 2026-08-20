import csv
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QMessageBox, QFileDialog, QDateEdit, QDialog, QFormLayout, QDialogButtonBox)
from PyQt6.QtCore import QDate
from PyQt6.QtGui import QShortcut, QKeySequence
from database import Session, Sale, Purchase, Expenditure
from sqlalchemy import func, or_
from datetime import datetime, time
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

class DateRangeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Report Date Range")
        self.resize(300, 150)
        
        layout = QFormLayout(self)
        
        self.start_date = QDateEdit(QDate.currentDate().addDays(-30)) 
        self.start_date.setCalendarPopup(True)
        
        self.end_date = QDateEdit(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        
        layout.addRow("Start Date:", self.start_date)
        layout.addRow("End Date:", self.end_date)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
    def get_dates(self):
        return self.start_date.date().toPyDate(), self.end_date.date().toPyDate()

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
        btn_today = QPushButton("Today")
        btn_today.clicked.connect(lambda: self.calculate("day"))
        
        btn_month = QPushButton("This Month")
        btn_month.clicked.connect(lambda: self.calculate("month"))
        
        btn_year = QPushButton("This Year")
        btn_year.clicked.connect(lambda: self.calculate("year"))
        
        btn_all = QPushButton("All Time")
        btn_all.clicked.connect(lambda: self.calculate("all"))
        
        filter_layout.addWidget(btn_today)
        filter_layout.addWidget(btn_month)
        filter_layout.addWidget(btn_year)
        filter_layout.addWidget(btn_all)
        layout.addLayout(filter_layout)

        custom_date_layout = QHBoxLayout()
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate())
        
        btn_custom_date = QPushButton("Filter by Selected Date")
        btn_custom_date.clicked.connect(lambda: self.calculate("custom"))
        
        custom_date_layout.addWidget(QLabel("Custom Date:"))
        custom_date_layout.addWidget(self.date_filter)
        custom_date_layout.addWidget(btn_custom_date)
        layout.addLayout(custom_date_layout)

        self.lbl_sales = QLabel("Total Sales: 0.00")
        self.lbl_purch = QLabel("Total Purchases: 0.00")
        self.lbl_exp = QLabel("Total Expenses: 0.00")
        self.lbl_profit = QLabel("Net Profit: 0.00")
        
        font = self.lbl_sales.font()
        font.setPointSize(16)
        font.setBold(True)
        
        for l in [self.lbl_sales, self.lbl_purch, self.lbl_exp, self.lbl_profit]:
            l.setFont(font)
            layout.addWidget(l)

        btn_recalc = QPushButton("🔄 Recalculate Stats")
        btn_recalc.clicked.connect(lambda: self.calculate("all"))
        layout.addWidget(btn_recalc)
        
        layout.addStretch()


        export_layout = QHBoxLayout()
        
        btn_csv = QPushButton("📄 Detailed Date-by-Date Report (CSV)")
        btn_csv.setStyleSheet("background-color: #107c10; color: white; font-weight: bold; padding: 8px;")
        btn_csv.clicked.connect(self.export_detailed_csv)
        
        btn_pdf = QPushButton("📑 Detailed Date-by-Date Report (PDF)")
        btn_pdf.setStyleSheet("background-color: #d83b01; color: white; font-weight: bold; padding: 8px;")
        btn_pdf.clicked.connect(self.export_detailed_pdf)
        
        export_layout.addWidget(btn_csv)
        export_layout.addWidget(btn_pdf)
        layout.addLayout(export_layout)

        export_layout2 = QHBoxLayout()
        
        btn_paid_rep = QPushButton("✅ Credit Report (PDF)")
        btn_paid_rep.setStyleSheet("background-color: #2e8b57; color: white; font-weight: bold; padding: 8px;")
        btn_paid_rep.clicked.connect(self.export_paid_report)
        
        btn_purch_rep = QPushButton("🛒 Purchase Report (PDF)")
        btn_purch_rep.setStyleSheet("background-color: #005a9e; color: white; font-weight: bold; padding: 8px;")
        btn_purch_rep.clicked.connect(self.export_purchase_report)
        
        btn_exp_rep = QPushButton("💸 Expenditure Report (PDF)")
        btn_exp_rep.setStyleSheet("background-color: #5c2d91; color: white; font-weight: bold; padding: 8px;")
        btn_exp_rep.clicked.connect(self.export_expenditure_report)
        
        export_layout2.addWidget(btn_paid_rep)
        export_layout2.addWidget(btn_purch_rep)
        export_layout2.addWidget(btn_exp_rep)
        layout.addLayout(export_layout2)

    def calculate(self, period):
        session = Session()
        
        q_s = session.query(func.sum(Sale.net_total)).filter(
            Sale.paid_status == True,
            or_(Sale.is_deleted == False, Sale.is_deleted == None)
        )
        
        q_p = session.query(func.sum(Purchase.total_amount)).filter(
            or_(Purchase.is_deleted == False, Purchase.is_deleted == None)
        )
        q_e = session.query(func.sum(Expenditure.amount)).filter(
            or_(Expenditure.is_deleted == False, Expenditure.is_deleted == None)
        )
        
        now = datetime.now()
        start_dt = None
        end_dt = None
        
        if period == "day": 
            start_dt = datetime(now.year, now.month, now.day)
        elif period == "month": 
            start_dt = datetime(now.year, now.month, 1)
        elif period == "year": 
            start_dt = datetime(now.year, 1, 1)
        elif period == "custom":
            selected_date = self.date_filter.date().toPyDate()
            start_dt = datetime(selected_date.year, selected_date.month, selected_date.day)
            end_dt = datetime(selected_date.year, selected_date.month, selected_date.day, 23, 59, 59)
        
        if period == "custom":
            q_s = q_s.filter(Sale.date_time >= start_dt, Sale.date_time <= end_dt)
            q_p = q_p.filter(Purchase.date_time >= start_dt, Purchase.date_time <= end_dt)
            q_e = q_e.filter(Expenditure.date_time >= start_dt, Expenditure.date_time <= end_dt)
        elif start_dt:
            q_s = q_s.filter(Sale.date_time >= start_dt)
            q_p = q_p.filter(Purchase.date_time >= start_dt)
            q_e = q_e.filter(Expenditure.date_time >= start_dt)

        s = q_s.scalar() or 0.0
        p = q_p.scalar() or 0.0
        e = q_e.scalar() or 0.0
        session.close()
        
        profit = s - p - e
        
        self.lbl_sales.setText(f"Total Sales :{s:,.2f}")
        self.lbl_purch.setText(f"Total Purchases: {p:,.2f}")
        self.lbl_exp.setText(f"Total Expenses: {e:,.2f}")
        self.lbl_profit.setText(f"Net Profit: {profit:,.2f}")
        
        if profit >= 0:
            self.lbl_profit.setStyleSheet("color: green")
        else:
            self.lbl_profit.setStyleSheet("color: red")

    def get_daily_detailed_data(self, start_dt, end_dt):
        """Fetches all items and groups them by exact date into detailed lists."""
        session = Session()
        
        sales = session.query(Sale).filter(
            Sale.paid_status == True,
            or_(Sale.is_deleted == False, Sale.is_deleted == None),
            Sale.date_time >= start_dt, Sale.date_time <= end_dt
        ).order_by(Sale.date_time).all()
        
        purchases = session.query(Purchase).filter(
            or_(Purchase.is_deleted == False, Purchase.is_deleted == None),
            Purchase.date_time >= start_dt, Purchase.date_time <= end_dt
        ).order_by(Purchase.date_time).all()
        
        expenses = session.query(Expenditure).filter(
            or_(Expenditure.is_deleted == False, Expenditure.is_deleted == None),
            Expenditure.date_time >= start_dt, Expenditure.date_time <= end_dt
        ).order_by(Expenditure.date_time).all()
        
        daily_data = {}

        def init_date(d):
            if d not in daily_data:
                daily_data[d] = {
                    'sales_list': [], 'purch_list': [], 'exp_list': [], 
                    't_sales': 0.0, 't_purch': 0.0, 't_exp': 0.0
                }

        for s in sales:
            d = s.date_time.date()
            init_date(d)
            cust = s.customer_name if s.customer_name else "Cash"
            daily_data[d]['sales_list'].append({
                'time': s.date_time.strftime('%H:%M'),
                'details': f"Bill: {s.bill_id} ({cust})",
                'amount': s.net_total
            })
            daily_data[d]['t_sales'] += s.net_total

        for p in purchases:
            d = p.date_time.date()
            init_date(d)
            if p.items:
                item_names = ", ".join([str(item.item_name) for item in p.items])
            else:
                item_names = f"PUR-{p.id}"
                
            daily_data[d]['purch_list'].append({
                'time': p.date_time.strftime('%H:%M'),
                'details': item_names,
                'amount': p.total_amount
            })
            daily_data[d]['t_purch'] += p.total_amount

        for e in expenses:
            d = e.date_time.date()
            init_date(d)
            daily_data[d]['exp_list'].append({
                'time': e.date_time.strftime('%H:%M'),
                'details': e.description,
                'amount': e.amount
            })
            daily_data[d]['t_exp'] += e.amount

        session.close()
        return daily_data

    def export_detailed_csv(self):
        dialog = DateRangeDialog(self)
        if not dialog.exec():
            return
            
        start_date, end_date = dialog.get_dates()
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)

        path, _ = QFileDialog.getSaveFileName(self, "Save Detailed CSV", f"Detailed_Report_{start_date}_to_{end_date}.csv", "CSV Files (*.csv)")
        if not path:
            return

        daily_data = self.get_daily_detailed_data(start_dt, end_dt)

        try:
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                
                writer.writerow(["Detailed Business Report"])
                writer.writerow(["Period", f"{start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}"])
                writer.writerow([])
                
                total_s, total_p, total_e = 0.0, 0.0, 0.0
                
                for d in sorted(daily_data.keys()):
                    writer.writerow([f"--- DATE: {d.strftime('%d-%m-%Y')} ---"])
                    writer.writerow(["Type", "Time", "Details", "Amount (Rs)"])
                    
                    for s in daily_data[d]['sales_list']:
                        writer.writerow(["Credit", s['time'], s['details'], f"{s['amount']:.2f}"])
                        
                    for p in daily_data[d]['purch_list']:
                        writer.writerow(["Purchase", p['time'], p['details'], f"{p['amount']:.2f}"])
                        
                    for e in daily_data[d]['exp_list']:
                        writer.writerow(["Expense", e['time'], e['details'], f"{e['amount']:.2f}"])
                        
                    
                    t_s = daily_data[d]['t_sales']
                    t_p = daily_data[d]['t_purch']
                    t_e = daily_data[d]['t_exp']
                    d_profit = t_s - t_p - t_e
                    
                    writer.writerow([])
                    writer.writerow([f"Daily Summary for {d.strftime('%d-%m-%Y')}:", f"Total Credit: {t_s:.2f}", f"Total Debit: {(t_p + t_e):.2f}", f"Net Profit: {d_profit:.2f}"])
                    writer.writerow([])
                    
                    total_s += t_s
                    total_p += t_p
                    total_e += t_e
                
                
                writer.writerow(["="*50])
                writer.writerow(["GRAND TOTALS FOR PERIOD"])
                writer.writerow(["Total Purchases", f"{total_p:.2f}"])
                writer.writerow(["Total Expenses", f"{total_e:.2f}"])
                writer.writerow(["Total Debit", f"{total_p + total_e: .2f}"])
                writer.writerow(["Total Credit", f"{total_s:.2f}"])
                writer.writerow(["Total Net Profit", f"{(total_s - total_p - total_e):.2f}"])

            QMessageBox.information(self, "Success", "Detailed CSV Exported Successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save CSV:\n{str(e)}")

    def export_detailed_pdf(self):
        dialog = DateRangeDialog(self)
        if not dialog.exec():
            return
            
        start_date, end_date = dialog.get_dates()
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        
        path, _ = QFileDialog.getSaveFileName(self, "Save Detailed PDF", f"Detailed_Report_{start_date}_to_{end_date}.pdf", "PDF Files (*.pdf)")
        if not path:
            return
            
        try:
            daily_data = self.get_daily_detailed_data(start_dt, end_dt)

            doc = SimpleDocTemplate(path, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            # Title
            elements.append(Paragraph(f"<b>Detailed Transaction Report</b>", styles['Title']))
            elements.append(Paragraph(f"<b>Period:</b> {start_dt.strftime('%d-%m-%Y')} to {end_dt.strftime('%d-%m-%Y')}", styles['Normal']))
            elements.append(Spacer(1, 15))
            
            total_s, total_p, total_e = 0.0, 0.0, 0.0
            
            for d in sorted(daily_data.keys()):
                
                elements.append(Paragraph(f"<b>Date: {d.strftime('%d-%m-%Y')}</b>", styles['Heading3']))
                
                table_data = [['Type', 'Time', 'Details', 'Amount (Rs)']]
                
                # Add rows for this date and wrap text in Paragraph objects to prevent overflow
                for s in daily_data[d]['sales_list']:
                    detail_text = Paragraph(s['details'], styles['Normal'])
                    table_data.append(['Credit', s['time'], detail_text, f"{s['amount']:,.2f}"])
                    
                for p in daily_data[d]['purch_list']:
                    detail_text = Paragraph(p['details'], styles['Normal'])
                    table_data.append(['Purchase', p['time'], detail_text, f"{p['amount']:,.2f}"])
                    
                for e in daily_data[d]['exp_list']:
                    detail_text = Paragraph(e['details'], styles['Normal'])
                    table_data.append(['Expense', e['time'], detail_text, f"{e['amount']:,.2f}"])

                if len(table_data) > 1:
                    
                    t = Table(table_data, colWidths=[70, 50, 260, 100])
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0078d4")),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ]))
                    elements.append(t)
                
                
                t_s = daily_data[d]['t_sales']
                t_p = daily_data[d]['t_purch']
                t_e = daily_data[d]['t_exp']
                d_profit = t_s - t_p - t_e
                
                total_s += t_s
                total_p += t_p
                total_e += t_e
                
                summary_text = (f"<font color='green'><b>Credit:</b> {t_s:,.2f}</font> | "
                                f"<font color='red'><b>Debit:</b> {(t_p + t_e):,.2f}</font> | "
                                f"<b>Net Profit:</b> {d_profit:,.2f}")
                
                elements.append(Spacer(1, 5))
                elements.append(Paragraph(summary_text, styles['Normal']))
                elements.append(Spacer(1, 20))

            
            elements.append(Paragraph("<b>Grand Totals for Selected Period</b>", styles['Heading2']))
            net_profit = total_s - total_p - total_e
            
            summary_data = [
                ['Metric', 'Amount (Rs)'],
                ['Total Purchases', f"{total_p:,.2f}"],
                ['Total Expenses', f"{total_e:,.2f}"],
                ['Total Debit', f"{total_e + total_p:,.2f}"],
                ['Total Credit', f"{total_s:,.2f}"],
                ['Net Profit', f"{net_profit:,.2f}"]
            ]
            
            summary_table = Table(summary_data, colWidths=[200, 150])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgreen if net_profit >= 0 else colors.lightcoral),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(summary_table)

            doc.build(elements)
            QMessageBox.information(self, "Success", "Detailed PDF Exported Successfully")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate PDF report:\n{str(e)}")

    
    def export_paid_report(self):
        dialog = DateRangeDialog(self)
        if not dialog.exec(): return
        start_date, end_date = dialog.get_dates()
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        
        path, _ = QFileDialog.getSaveFileName(self, "Save Credit Report", f"Credit_Report_{start_date}_to_{end_date}.pdf", "PDF Files (*.pdf)")
        if not path: return
        
        try:
            session = Session()
            paid_bills = session.query(Sale).filter(
                Sale.paid_status == True,  # ONLY PAID BILLS
                or_(Sale.is_deleted == False, Sale.is_deleted == None),
                Sale.date_time >= start_dt, Sale.date_time <= end_dt
            ).order_by(Sale.date_time).all()
            session.close()

            doc = SimpleDocTemplate(path, pagesize=A4)
            elements, styles = [], getSampleStyleSheet()
            
            elements.append(Paragraph(f"<b><font color='#2e8b57'>Credit Report</font></b>", styles['Title']))
            elements.append(Paragraph(f"<b>Period:</b> {start_dt.strftime('%d-%m-%Y')} to {end_dt.strftime('%d-%m-%Y')}", styles['Normal']))
            elements.append(Spacer(1, 15))
            
            table_data = [['Sr No.', 'Date', 'Time', 'Bill ID & Customer', 'Amount (Rs)']]
            grand_total = 0.0
            
            for idx, c in enumerate(paid_bills, start=1):
                cust = c.customer_name if c.customer_name else "Cash"
                detail_text = Paragraph(f"{c.bill_id} ({cust})", styles['Normal'])
                table_data.append([str(idx), c.date_time.strftime('%d-%m-%Y'), c.date_time.strftime('%H:%M'), detail_text, f"{c.net_total:,.2f}"])
                grand_total += c.net_total
                
           
            table_data.append(['', '', '', 'GRAND TOTAL', f"{grand_total:,.2f}"])

            t = Table(table_data, colWidths=[50, 80, 60, 200, 90])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2e8b57")),  # Green color for paid bills
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'), # Center Sr No.
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                # Grand Total Styling
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ]))
            elements.append(t)
            doc.build(elements)
            QMessageBox.information(self, "Success", "Credit Report Exported Successfully")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate Credit report:\n{str(e)}")

    
    def export_purchase_report(self):
        dialog = DateRangeDialog(self)
        if not dialog.exec(): return
        start_date, end_date = dialog.get_dates()
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        
        path, _ = QFileDialog.getSaveFileName(self, "Save Purchase Report", f"Purchase_Report_{start_date}_to_{end_date}.pdf", "PDF Files (*.pdf)")
        if not path: return

        try:
            session = Session()
            purchases = session.query(Purchase).filter(
                or_(Purchase.is_deleted == False, Purchase.is_deleted == None),
                Purchase.date_time >= start_dt, Purchase.date_time <= end_dt
            ).order_by(Purchase.date_time).all()

            doc = SimpleDocTemplate(path, pagesize=A4)
            elements, styles = [], getSampleStyleSheet()
            
            elements.append(Paragraph(f"<b><font color='#005a9e'>Detailed Purchase Report</font></b>", styles['Title']))
            elements.append(Paragraph(f"<b>Period:</b> {start_dt.strftime('%d-%m-%Y')} to {end_dt.strftime('%d-%m-%Y')}", styles['Normal']))
            elements.append(Spacer(1, 15))
            
            table_data = [['Sr\nNo.', 'Date', 'Time', 'Item Name', 'Qty', 'Rate\n(Rs)', 'Amount\n(Rs)', 'Saved Into']]
            grand_total = 0.0
            sr_no = 1
            
            for p in purchases:
                if p.items:
                    for item in p.items:
                        target = "Inventory" if item.track_item else "General"
                        table_data.append([
                            str(sr_no), p.date_time.strftime('%d-%m-%y'), p.date_time.strftime('%H:%M'),
                            Paragraph(item.item_name, styles['Normal']), f"{item.quantity:g}", f"{item.rate:,.2f}", f"{item.amount:,.2f}", target
                        ])
                        grand_total += item.amount
                        sr_no += 1
                else:
                    table_data.append([
                        str(sr_no), p.date_time.strftime('%d-%m-%y'), p.date_time.strftime('%H:%M'),
                        Paragraph("Purchase Entry (No Items)", styles['Normal']), "-", "-", f"{p.total_amount:,.2f}", p.category or "General"
                    ])
                    grand_total += p.total_amount
                    sr_no += 1
                    
            session.close()

            table_data.append(['', '', '', 'GRAND TOTAL', '', '', f"{grand_total:,.2f}", ''])

            t = Table(table_data, colWidths=[30, 60, 40, 140, 40, 50, 60, 60])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#005a9e")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (4, 0), (6, -1), 'RIGHT'), 
                ('ALIGN', (0, 0), (0, -1), 'CENTER'), 
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ]))
            elements.append(t)
            doc.build(elements)
            QMessageBox.information(self, "Success", "Purchase Report Exported Successfully")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate Purchase report:\n{str(e)}")

    
    def export_expenditure_report(self):
        dialog = DateRangeDialog(self)
        if not dialog.exec(): return
        start_date, end_date = dialog.get_dates()
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        
        path, _ = QFileDialog.getSaveFileName(self, "Save Expenditure Report", f"Expenditure_Report_{start_date}_to_{end_date}.pdf", "PDF Files (*.pdf)")
        if not path: return

        try:
            session = Session()
            expenses = session.query(Expenditure).filter(
                or_(Expenditure.is_deleted == False, Expenditure.is_deleted == None),
                Expenditure.date_time >= start_dt, Expenditure.date_time <= end_dt
            ).order_by(Expenditure.date_time).all()
            session.close()

            doc = SimpleDocTemplate(path, pagesize=A4)
            elements, styles = [], getSampleStyleSheet()
            
            elements.append(Paragraph(f"<b><font color='#5c2d91'>Expenditure Report</font></b>", styles['Title']))
            elements.append(Paragraph(f"<b>Period:</b> {start_dt.strftime('%d-%m-%Y')} to {end_dt.strftime('%d-%m-%Y')}", styles['Normal']))
            elements.append(Spacer(1, 15))
            
            table_data = [['Sr No.', 'Date', 'Time', 'Expenditure Detail', 'Amount (Rs)']]
            grand_total = 0.0
            
            for idx, e in enumerate(expenses, start=1):
                detail_text = Paragraph(e.description, styles['Normal'])
                table_data.append([str(idx), e.date_time.strftime('%d-%m-%Y'), e.date_time.strftime('%H:%M'), detail_text, f"{e.amount:,.2f}"])
                grand_total += e.amount
                
            table_data.append(['', '', '', 'GRAND TOTAL', f"{grand_total:,.2f}"])

            t = Table(table_data, colWidths=[50, 80, 60, 200, 90])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#5c2d91")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'), 
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ]))
            elements.append(t)
            doc.build(elements)
            QMessageBox.information(self, "Success", "Expenditure Report Exported Successfully")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate Expenditure report:\n{str(e)}")