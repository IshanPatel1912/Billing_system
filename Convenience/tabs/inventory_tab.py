import sys
import os
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QHeaderView, QMessageBox, QDialog, QLabel, 
                             QLineEdit, QHBoxLayout, QAbstractItemView, QFileDialog)
from PyQt6.QtCore import Qt
from database import Session, Inventory, get_current_business_details
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
    """Get absolute path to resource, works for dev and for PyInstaller .exe"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Attach the Arial font so the ₹ symbol works!
try:
    font_path = resource_path("arial.ttf")
    pdfmetrics.registerFont(TTFont('Arial', font_path))
except Exception as e:
    print(f"Warning: Could not load Arial font. Make sure arial.ttf is in your main folder. Error: {e}")

# ==========================================
# DIALOG FOR ADDING OPENING STOCK
# ==========================================
class AddOpeningStockDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Opening Stock (Bulk Entry)")
        self.resize(600, 400) 
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Add multiple items below. Double-click to edit."))
        
        self.table = QTableWidget()
        self.table.setColumnCount(3) 
        self.table.setHorizontalHeaderLabels(["Item Name", "Quantity", "MRP"])
        
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        
        self.add_rows(5)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        add_row_btn = QPushButton("➕ Add Row"); add_row_btn.clicked.connect(lambda: self.add_rows(1))
        save_btn = QPushButton("💾 Save All Stock"); save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        save_btn.clicked.connect(self.save_stock)
        close_btn = QPushButton("Close"); close_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(add_row_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def add_rows(self, count):
        current_rows = self.table.rowCount()
        for i in range(count):
            self.table.insertRow(current_rows + i)
            self.table.setItem(current_rows + i, 1, QTableWidgetItem("0"))   
            self.table.setItem(current_rows + i, 2, QTableWidgetItem("0.0")) 

    def save_stock(self):
        session = Session()
        added_count = 0
        updated_count = 0
        
        try:
            for row in range(self.table.rowCount()):
                name_item = self.table.item(row, 0)
                qty_item = self.table.item(row, 1)
                mrp_item = self.table.item(row, 2)
                
                if not name_item or not name_item.text().strip(): continue
                    
                name = name_item.text().strip().title() 
                qty_text = qty_item.text().strip() if qty_item else "0"
                mrp_text = mrp_item.text().strip() if mrp_item else "0.0"
                
                try:
                    qty = float(qty_text)
                    mrp = float(mrp_text)
                except ValueError:
                    QMessageBox.warning(self, "Error", f"Invalid Quantity or MRP for item '{name}'")
                    return

                inv = session.query(Inventory).filter(func.lower(Inventory.item_name) == name.lower()).first()
                
                if inv:
                    inv.quantity += qty
                    if mrp > 0: inv.mrp = mrp 
                    updated_count += 1
                else:
                    new_inv = Inventory(item_name=name, quantity=qty, mrp=mrp)
                    session.add(new_inv)
                    added_count += 1
            
            session.commit()
            QMessageBox.information(self, "Success", f"Stock Added!\n\nNew Items: {added_count}\nUpdated Items: {updated_count}")
            self.accept()
            
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

# ==========================================
# MAIN INVENTORY TAB
# ==========================================
class InventoryTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(); self.setLayout(layout)
        
        # --- TOP HEADER CONTROLS ---
        top_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Inventory...")
        self.search_input.textChanged.connect(self.load_data)
        
        self.refresh_btn = QPushButton("Refresh"); self.refresh_btn.clicked.connect(self.load_data)
        
        self.add_stock_btn = QPushButton("➕ Add Opening Stock")
        self.add_stock_btn.setStyleSheet("background-color: #008CBA; color: white; font-weight: bold;")
        self.add_stock_btn.clicked.connect(self.open_add_stock_dialog)

        self.export_btn = QPushButton("📄 Export Stock Report (PDF)")
        self.export_btn.setStyleSheet("background-color: #d83b01; color: white; font-weight: bold;")
        self.export_btn.clicked.connect(self.export_pdf)
        
        top_layout.addWidget(self.search_input)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addWidget(self.add_stock_btn)
        top_layout.addWidget(self.export_btn)
        layout.addLayout(top_layout)

        # --- TABLE ---
        self.table = QTableWidget(); self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Item Name", "Available Qty", "Cost Price", "MRP"])
        self.table.hideColumn(0) 
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        btn_del = QPushButton("Delete Selected Item"); btn_del.clicked.connect(self.delete_item)
        layout.addWidget(btn_del)

    def open_add_stock_dialog(self):
        dialog = AddOpeningStockDialog(self)
        if dialog.exec():
            self.load_data()

    def load_data(self):
        search_txt = self.search_input.text().strip().lower()
        session = Session()
        query = session.query(Inventory)
        
        if search_txt:
            query = query.filter(Inventory.item_name.contains(search_txt))
            
        items = query.all()
        
        self.table.setRowCount(0)
        for i in items:
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(i.id)))
            self.table.setItem(r, 1, QTableWidgetItem(i.item_name))
            self.table.setItem(r, 2, QTableWidgetItem(str(i.quantity)))
            self.table.setItem(r, 3, QTableWidgetItem(str(i.cost_price)))
            self.table.setItem(r, 4, QTableWidgetItem(str(i.mrp)))
        session.close()

    def delete_item(self):
        row = self.table.currentRow()
        if row == -1: return
        if QMessageBox.question(self, "Confirm", "Delete?") == QMessageBox.StandardButton.Yes:
            iid = self.table.item(row, 0).text()
            session = Session()
            session.query(Inventory).filter_by(id=iid).delete()
            session.commit(); session.close(); self.load_data()

    # ==========================================
    # UPGRADED PREMIUM PDF EXPORT
    # ==========================================
    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Inventory Report", "Inventory_Stock_Report.pdf", "PDF Files (*.pdf)")
        if not path: return

        # 1. Fetch current inventory
        session = Session()
        items = session.query(Inventory).order_by(Inventory.item_name).all()
        
        headers = ['Item Name', 'Qty in Stock', 'Cost Price', 'MRP', 'Total Value (Cost)']
        row_data = []
        total_stock_value = 0.0

        for item in items:
            qty = item.quantity or 0.0
            cost = item.cost_price or 0.0
            mrp = item.mrp or 0.0
            total_value = qty * cost
            
            total_stock_value += total_value

            row_data.append([
                item.item_name,
                f"{qty:,.2f}",
                f"₹{cost:,.2f}",
                f"₹{mrp:,.2f}",
                f"₹{total_value:,.2f}"
            ])
            
        session.close()

        # Add Grand Total Row
        if row_data:
            row_data.append(["", "", "", "TOTAL STOCK VALUE:", f"₹{total_stock_value:,.2f}"])

        # 2. Build the PDF
        try:
            doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30)
            elements = []
            styles = getSampleStyleSheet()
            
            if 'RightAlign' not in styles:
                styles.add(ParagraphStyle(name='RightAlign', parent=styles['Normal'], alignment=TA_RIGHT))

            biz = get_current_business_details()
            biz_name = biz.name if biz and biz.name else "POS System"
            biz_phone = biz.phone if biz and biz.phone else ""

            # --- HEADER SECTION ---
            header_table_data = [
                [
                    Paragraph(f"<b><font size='16' color='#2C3E50'>{biz_name}</font></b><br/><font size='10' color='#555555'>{biz_phone}</font>", styles['Normal']),
                    Paragraph(f"<b><font size='14' color='#008CBA'>Current Inventory Report</font></b><br/><font size='10' color='#555555'><b>Generated On:</b> {datetime.now().strftime('%d-%m-%Y %I:%M %p')}</font>", styles['RightAlign'])
                ]
            ]
            
            header_table = Table(header_table_data, colWidths=[260, 275])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ]))
            elements.append(header_table)
            
            # --- TABLE SECTION ---
            table_data = [headers] + row_data
            if len(row_data) == 0:
                table_data.append(["Your inventory is currently empty."] * len(headers))
                
            t = Table(table_data, colWidths=[215, 80, 80, 80, 80])
            
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),  
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'), 
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
            
            # Add Zebra Striping and Total Row Highlighting
            if len(row_data) > 0:
                for i in range(1, len(table_data) - 1): 
                    bg_color = colors.HexColor("#F8F9F9") if i % 2 == 0 else colors.white
                    table_style.append(('BACKGROUND', (0, i), (-1, i), bg_color))
                
                table_style.append(('FONTNAME', (0, -1), (-1, -1), 'Arial'))
                table_style.append(('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#EAEDED")))
                
            t.setStyle(TableStyle(table_style))
            elements.append(t)
            
            # Footer Date
            elements.append(Spacer(1, 15))
            elements.append(Paragraph(f"<font size='8' color='grey'>End of Report</font>", styles['Normal']))

            doc.build(elements)
            QMessageBox.information(self, "Success", "Inventory Stock Report Exported Successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate PDF:\n{str(e)}")