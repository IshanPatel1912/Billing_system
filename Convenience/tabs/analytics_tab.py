import sys
import os
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, QPushButton, QFileDialog, QMessageBox)
from PyQt6.QtCharts import QChart, QChartView, QPieSeries, QPieSlice
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QFont, QBrush
from database import Session, SaleItem, PurchaseItem, Inventory, Sale, get_current_business_details
from sqlalchemy import func, or_

# --- PDF Generation Imports ---
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

# --- FONT ATTACHMENT LOGIC ---
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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

class AnalyticsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.layout = QVBoxLayout(); self.setLayout(self.layout)
        
        # --- TITLE & EXPORT BUTTON ---
        top_layout = QHBoxLayout()
        title = QLabel("Sales Analytics & Profit Overview")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        
        btn_export = QPushButton("📄 Export Analytics Report (PDF)")
        btn_export.setStyleSheet("background-color: #d83b01; color: white; font-weight: bold; padding: 8px;")
        btn_export.clicked.connect(self.export_pdf)
        
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(btn_export)
        self.layout.addLayout(top_layout)

        # --- INFO PANEL (Hover Stats) ---
        self.info_panel = QFrame()
        self.info_panel.setStyleSheet("QFrame { background-color: #ffffff; border: 1px solid #ccc; border-radius: 8px; padding: 10px; } QLabel { font-size: 12px; color: #333; }")
        self.info_panel.setVisible(False)
        
        self.info_layout = QGridLayout(); self.info_panel.setLayout(self.info_layout)
        
        self.lbl_name = QLabel("Product:"); self.lbl_sell_qty = QLabel("Sold Qty:")
        self.lbl_avg_sell = QLabel("Avg Sell Price:"); self.lbl_avg_cost = QLabel("Avg Cost Price:")
        self.lbl_total_sell = QLabel("Total Sales:"); self.lbl_total_cost = QLabel("Total Cost (Sold):")
        self.lbl_profit_unit = QLabel("Profit/Unit:"); self.lbl_total_profit = QLabel("Total Profit:")
        
        self.info_layout.addWidget(self.lbl_name, 0, 0); self.info_layout.addWidget(self.lbl_sell_qty, 0, 1)
        self.info_layout.addWidget(self.lbl_avg_sell, 1, 0); self.info_layout.addWidget(self.lbl_avg_cost, 1, 1)
        self.info_layout.addWidget(self.lbl_total_sell, 2, 0); self.info_layout.addWidget(self.lbl_total_cost, 2, 1)
        self.info_layout.addWidget(self.lbl_profit_unit, 3, 0); self.info_layout.addWidget(self.lbl_total_profit, 3, 1)

        # --- CHART ---
        self.chart_view = QChartView(); self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.layout.addWidget(self.chart_view); self.layout.addWidget(self.info_panel)

    def load_data(self):
        session = Session()
        
        sales_data = session.query(
            SaleItem.item_name,
            func.sum(SaleItem.quantity),
            func.sum(SaleItem.amount)
        ).join(Sale).filter(
            or_(Sale.is_deleted == False, Sale.is_deleted == None)
        ).group_by(SaleItem.item_name).all()
        
        purchase_data = session.query(
            PurchaseItem.item_name,
            func.sum(PurchaseItem.quantity),
            func.sum(PurchaseItem.amount)
        ).group_by(PurchaseItem.item_name).all()
        
        session.close()

        avg_costs = {}
        for pname, pqty, pamt in purchase_data:
            if pqty > 0: avg_costs[pname] = pamt / pqty
            else: avg_costs[pname] = 0.0

        series = QPieSeries(); series.setHoleSize(0.40)
        
        bright_colors = [QColor("#FF3333"), QColor("#3366FF"), QColor("#FF33CC"), QColor("#33CC33"), 
                         QColor("#FFFF33"), QColor("#33FFFF"), QColor("#FF9933"), QColor("#9933FF"), 
                         QColor("#FF0066"), QColor("#00FF99")]

        for i, (name, sold_qty, sold_amt) in enumerate(sales_data):
            if sold_qty <= 0: continue
            
            avg_sell_price = sold_amt / sold_qty
            cost_price = avg_costs.get(name, 0.0)
            
            if cost_price == 0:
                session = Session()
                inv = session.query(Inventory).filter_by(item_name=name).first()
                if inv: cost_price = inv.cost_price
                session.close()
            
            total_cost_of_sold = cost_price * sold_qty
            total_profit = sold_amt - total_cost_of_sold
            profit_per_unit = total_profit / sold_qty if sold_qty else 0

            slice = series.append(name, sold_qty)
            color = bright_colors[i % len(bright_colors)]
            slice.setColor(color); slice.setBorderColor(QColor("white"))
            
            slice.data_name = name; slice.data_sell_qty = sold_qty
            slice.data_avg_sell = avg_sell_price; slice.data_avg_cost = cost_price
            slice.data_total_sell = sold_amt; slice.data_total_cost = total_cost_of_sold
            slice.data_profit_unit = profit_per_unit; slice.data_total_profit = total_profit
            
            slice.hovered.connect(lambda state, s=slice: self.on_slice_hover(state, s))

        chart = QChart(); chart.addSeries(series)
        chart.setTitle("Sales Overview (Quantity)"); chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.setBackgroundBrush(QBrush(QColor("white")))
        chart.legend().setVisible(True); chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight); chart.legend().setBackgroundVisible(False)
        
        font = QFont("Arial", 14); font.setBold(True); chart.setTitleFont(font)
        self.chart_view.setChart(chart)

    def on_slice_hover(self, is_hovering, slice):
        slice.setExploded(is_hovering); slice.setLabelVisible(is_hovering)
        if is_hovering:
            self.original_color = slice.color(); slice.setColor(self.original_color.lighter(130))
            self.lbl_name.setText(f"<b>Product:</b> {slice.data_name}"); self.lbl_sell_qty.setText(f"<b>Sold Qty:</b> {slice.data_sell_qty:.0f}")
            self.lbl_avg_sell.setText(f"<b>Avg Sell Price:</b> ₹{slice.data_avg_sell:.2f}"); self.lbl_avg_cost.setText(f"<b>Avg Cost Price:</b> ₹{slice.data_avg_cost:.2f}")
            self.lbl_total_sell.setText(f"<b>Total Sales:</b> ₹{slice.data_total_sell:.2f}"); self.lbl_total_cost.setText(f"<b>Total Cost:</b> ₹{slice.data_total_cost:.2f}")
            profit_color = "green" if slice.data_total_profit >= 0 else "red"
            self.lbl_profit_unit.setText(f"<b>Profit/Unit:</b> ₹{slice.data_profit_unit:.2f}"); self.lbl_total_profit.setText(f"<b>Total Profit:</b> ₹{slice.data_total_profit:.2f}")
            self.lbl_total_profit.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {profit_color};")
            self.info_panel.setVisible(True)
        else:
            if hasattr(self, 'original_color'): slice.setColor(self.original_color)
            self.info_panel.setVisible(False)

    def update_chart(self):
        self.load_data()

    # ==========================================
    # UPGRADED PREMIUM EXPORT PDF LOGIC
    # ==========================================
    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Analytics Report", "Product_Analytics_Report.pdf", "PDF Files (*.pdf)")
        if not path: return

        # 1. Fetch data
        session = Session()
        sales_data = session.query(
            SaleItem.item_name,
            func.sum(SaleItem.quantity),
            func.sum(SaleItem.amount)
        ).join(Sale).filter(
            or_(Sale.is_deleted == False, Sale.is_deleted == None)
        ).group_by(SaleItem.item_name).all()
        
        purchase_data = session.query(
            PurchaseItem.item_name,
            func.sum(PurchaseItem.quantity),
            func.sum(PurchaseItem.amount)
        ).group_by(PurchaseItem.item_name).all()
        
        avg_costs = {}
        for pname, pqty, pamt in purchase_data:
            if pqty > 0: avg_costs[pname] = pamt / pqty
            else: avg_costs[pname] = 0.0

        # 2. Build rows
        headers = ['Product Name', 'Qty Sold', 'Avg Sell', 'Avg Cost ', 'Total Sales ', 'Total Profit ']
        row_data = []
        
        overall_sales = 0.0
        overall_profit = 0.0

        for name, sold_qty, sold_amt in sales_data:
            if sold_qty <= 0: continue
            
            avg_sell_price = sold_amt / sold_qty
            cost_price = avg_costs.get(name, 0.0)
            
            if cost_price == 0:
                inv = session.query(Inventory).filter_by(item_name=name).first()
                if inv: cost_price = inv.cost_price
            
            total_cost_of_sold = cost_price * sold_qty
            total_profit = sold_amt - total_cost_of_sold
            
            overall_sales += sold_amt
            overall_profit += total_profit

            # Format numbers with commas for standard accounting readability
            row_data.append([
                name, 
                f"{sold_qty:,.0f}", 
                f"₹{avg_sell_price:,.2f}", 
                f"₹{cost_price:,.2f}", 
                f"₹{sold_amt:,.2f}", 
                f"₹{total_profit:,.2f}"
            ])

        session.close()

        # Add Grand Total Row
        if row_data:
            row_data.append(["", "", "", "GRAND TOTAL:", f"₹{overall_sales:,.2f}", f"₹{overall_profit:,.2f}"])

        # 3. Generate the Premium PDF Document
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
                    Paragraph(f"<b><font size='14' color='#d83b01'>Product Analytics Report</font></b><br/><font size='10' color='#555555'><b>Generated On:</b> {datetime.now().strftime('%d-%m-%Y %I:%M %p')}</font>", styles['RightAlign'])
                ]
            ]
            
            header_table = Table(header_table_data, colWidths=[260, 275])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ]))
            elements.append(header_table)
            
            # --- TABLE DATA SECTION ---
            table_data = [headers] + row_data
            if len(row_data) == 0:
                table_data.append(["No sales data available yet."] * len(headers))
            
            # Precisely tuned widths to fit perfectly on A4 paper
            t = Table(table_data, colWidths=[155, 60, 80, 80, 80, 80])
            
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'), 
                # -----> THIS LINE WAS FIXED TO APPLY TO THE ENTIRE TABLE <-----
                ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
            ]
            
            # Apply Zebra Striping and Bold Grand Total
            if len(row_data) > 0:
                for i in range(1, len(table_data) - 1): # Exclude the very last row (Total)
                    bg_color = colors.HexColor("#F8F9F9") if i % 2 == 0 else colors.white
                    table_style.append(('BACKGROUND', (0, i), (-1, i), bg_color))
                
                # -----> THIS LINE WAS FIXED SO GRAND TOTAL ROW STAYS ARIAL <-----
                table_style.append(('FONTNAME', (0, -1), (-1, -1), 'Arial'))
                table_style.append(('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#EAEDED")))
                
            t.setStyle(TableStyle(table_style))
            elements.append(t)
            
            # Footer Date
            elements.append(Spacer(1, 15))
            elements.append(Paragraph(f"<font size='8' color='grey'>End of Report</font>", styles['Normal']))

            doc.build(elements)
            QMessageBox.information(self, "Success", "Analytics Report Exported Successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate PDF:\n{str(e)}")