import sys
import os
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QMessageBox, QFileDialog, QFormLayout, QGroupBox)
from PyQt6.QtCore import Qt
from database import Session, Customer, get_current_business_details
from sqlalchemy import func

# --- PDF Generation Imports ---
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- FONT ATTACHMENT LOGIC ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

try:
    font_path = resource_path("arial.ttf")
    pdfmetrics.registerFont(TTFont('Arial', font_path))
except Exception as e:
    print(f"Warning: Could not load Arial font. Make sure arial.ttf is in your main folder. Error: {e}")

# ==========================================
# MAIN CUSTOMER TAB
# ==========================================
class CustomerTab(QWidget):
    def __init__(self):
        super().__init__()
        self.current_customer_id = None
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(); self.setLayout(layout)
        
        # --- TOP CONTROLS ---
        top_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Name or Mobile...")
        self.search_input.textChanged.connect(self.load_data)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_data)
        
        self.export_btn = QPushButton("📄 Export Customer Report (PDF)")
        self.export_btn.setStyleSheet("background-color: #d83b01; color: white; font-weight: bold; padding: 5px 15px;")
        self.export_btn.clicked.connect(self.export_pdf)
        
        top_layout.addWidget(self.search_input)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addWidget(self.export_btn)
        layout.addLayout(top_layout)

        # --- TABLE ---
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Customer Name", "Mobile Number", "Last Visit"])
        self.table.hideColumn(0) # Hide ID column
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemClicked.connect(self.load_customer_to_form)
        layout.addWidget(self.table)

        # --- FORM SECTION ---
        form_group = QGroupBox("Add / Edit Customer")
        form_group.setStyleSheet("font-weight: bold; color: #005a9e;")
        form_layout = QHBoxLayout()
        
        self.cust_name = QLineEdit()
        self.cust_name.setPlaceholderText("Enter Name")
        
        self.cust_mobile = QLineEdit()
        self.cust_mobile.setPlaceholderText("Enter Mobile Number")
        
        self.save_btn = QPushButton("Save Customer")
        self.save_btn.setStyleSheet("background-color: #107c10; color: white; padding: 8px; font-weight: bold;")
        self.save_btn.clicked.connect(self.save_customer)
        
        self.clear_btn = QPushButton("Clear Form")
        self.clear_btn.clicked.connect(self.clear_form)
        
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setStyleSheet("background-color: #d32f2f; color: white; padding: 8px; font-weight: bold;")
        self.delete_btn.clicked.connect(self.delete_customer)
        
        form_layout.addWidget(QLabel("Name:")); form_layout.addWidget(self.cust_name)
        form_layout.addWidget(QLabel("Mobile:")); form_layout.addWidget(self.cust_mobile)
        form_layout.addWidget(self.save_btn)
        form_layout.addWidget(self.clear_btn)
        form_layout.addWidget(self.delete_btn)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

    def load_data(self):
        search_txt = self.search_input.text().strip().lower()
        session = Session()
        query = session.query(Customer)
        
        if search_txt:
            query = query.filter(
                func.lower(Customer.name).contains(search_txt) |
                Customer.mobile.contains(search_txt)
            )
            
        customers = query.order_by(Customer.name).all()
        
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for c in customers:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(c.id)))
            self.table.setItem(r, 1, QTableWidgetItem(c.name or "N/A"))
            self.table.setItem(r, 2, QTableWidgetItem(c.mobile or "N/A"))
            
            visit_date = c.last_visit.strftime("%d-%m-%Y %I:%M %p") if c.last_visit else "Never"
            self.table.setItem(r, 3, QTableWidgetItem(visit_date))
            
        self.table.blockSignals(False)
        session.close()

    def load_customer_to_form(self, item):
        row = item.row()
        self.current_customer_id = self.table.item(row, 0).text()
        name = self.table.item(row, 1).text()
        mobile = self.table.item(row, 2).text()
        
        self.cust_name.setText(name if name != "N/A" else "")
        self.cust_mobile.setText(mobile if mobile != "N/A" else "")
        self.save_btn.setText("Update Customer")

    def clear_form(self):
        self.current_customer_id = None
        self.cust_name.clear()
        self.cust_mobile.clear()
        self.save_btn.setText("Save Customer")
        self.table.clearSelection()

    def save_customer(self):
        name = self.cust_name.text().strip()
        mobile = self.cust_mobile.text().strip()
        
        if not name and not mobile:
            QMessageBox.warning(self, "Error", "Please enter a name or mobile number.")
            return
            
        session = Session()
        try:
            if self.current_customer_id:
                # Edit Existing Customer
                cust = session.query(Customer).filter_by(id=self.current_customer_id).first()
                if cust:
                    cust.name = name
                    cust.mobile = mobile
                    session.commit()
                    QMessageBox.information(self, "Success", "Customer updated successfully.")
            else:
                # Add New Customer
                if mobile:
                    existing = session.query(Customer).filter_by(mobile=mobile).first()
                    if existing:
                        QMessageBox.warning(self, "Warning", "Customer with this mobile number already exists.")
                        session.close()
                        return
                        
                new_cust = Customer(name=name, mobile=mobile, last_visit=datetime.now())
                session.add(new_cust)
                session.commit()
                QMessageBox.information(self, "Success", "Customer added successfully.")
            
            self.clear_form()
            self.load_data()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def delete_customer(self):
        if not self.current_customer_id:
            QMessageBox.warning(self, "Warning", "Please click on a customer from the table to delete.")
            return
            
        if QMessageBox.question(self, "Confirm Delete", "Are you sure you want to delete this customer?") == QMessageBox.StandardButton.Yes:
            session = Session()
            try:
                session.query(Customer).filter_by(id=self.current_customer_id).delete()
                session.commit()
                self.clear_form()
                self.load_data()
                QMessageBox.information(self, "Success", "Customer deleted successfully.")
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to delete customer: {e}")
            finally:
                session.close()

    # ==========================================
    # PREMIUM PDF EXPORT LOGIC
    # ==========================================
    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Customer Report", "Customer_Directory_Report.pdf", "PDF Files (*.pdf)")
        if not path: return

        session = Session()
        customers = session.query(Customer).order_by(Customer.name).all()
        
        headers = ['S.No.', 'Customer Name', 'Mobile Number', 'Last Visit Date']
        row_data = []

        for index, c in enumerate(customers, 1):
            visit_date = c.last_visit.strftime("%d-%m-%Y %I:%M %p") if c.last_visit else "Never"
            row_data.append([
                str(index),
                c.name or "N/A",
                c.mobile or "N/A",
                visit_date
            ])
            
        session.close()

        try:
            doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30)
            elements = []
            styles = getSampleStyleSheet()
            
            if 'RightAlign' not in styles:
                styles.add(ParagraphStyle(name='RightAlign', parent=styles['Normal'], alignment=TA_RIGHT))

            biz = get_current_business_details()
            biz_name = biz.name if biz and biz.name else "POS System"
            biz_phone = biz.phone if biz and biz.phone else ""

            header_table_data = [
                [
                    Paragraph(f"<b><font size='16' color='#2C3E50'>{biz_name}</font></b><br/><font size='10' color='#555555'>{biz_phone}</font>", styles['Normal']),
                    Paragraph(f"<b><font size='14' color='#d83b01'>Customer Directory</font></b><br/><font size='10' color='#555555'><b>Total Customers:</b> {len(customers)}</font>", styles['RightAlign'])
                ]
            ]
            
            header_table = Table(header_table_data, colWidths=[260, 275])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ]))
            elements.append(header_table)
            
            table_data = [headers] + row_data
            if len(row_data) == 0:
                table_data.append(["No customers found.", "", "", ""])
                
            t = Table(table_data, colWidths=[50, 200, 140, 145])
            
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),  
                ('ALIGN', (0, 1), (0, -1), 'CENTER'), # Center S.No.
                ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
            ]
            
            # Zebra Striping
            if len(row_data) > 0:
                for i in range(1, len(table_data)): 
                    bg_color = colors.HexColor("#F8F9F9") if i % 2 == 0 else colors.white
                    table_style.append(('BACKGROUND', (0, i), (-1, i), bg_color))
                
            t.setStyle(TableStyle(table_style))
            elements.append(t)
            
            elements.append(Spacer(1, 15))
            elements.append(Paragraph(f"<font size='8' color='grey'>Report Generated On: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}</font>", styles['Normal']))

            doc.build(elements)
            QMessageBox.information(self, "Success", "Customer Report Exported Successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate PDF:\n{str(e)}")