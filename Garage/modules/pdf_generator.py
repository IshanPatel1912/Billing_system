# modules/pdf_generator.py

import os
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch

def generate_bill_pdf(bill_data, business_details, output_filename):
    """
    Generates a professional PDF invoice with teal branding.
    """
    # --- CONFIGURATION ---
    THEME_COLOR = HexColor('#2AA2B8')  # Teal Brand Color
    TEXT_COLOR = HexColor('#2c3e50')   # Dark Grey
    
    # Document Setup
    doc = SimpleDocTemplate(
        output_filename, 
        pagesize=A4,
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.5*inch, bottomMargin=0.5*inch
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    style_normal = styles['Normal']
    style_normal.textColor = TEXT_COLOR
    style_normal.fontSize = 10
    style_normal.leading = 14

    style_heading = ParagraphStyle(
        'CustomHeading', 
        parent=styles['Heading1'], 
        textColor=THEME_COLOR, 
        fontSize=24, 
        alignment=TA_RIGHT,
        spaceAfter=10
    )
    
    Story = []

    # --- 1. HEADER SECTION ---
    logo_path = getattr(business_details, 'logo_path', None)
    if logo_path and os.path.exists(logo_path):
        logo_img = Image(logo_path, width=0.8*inch, height=0.8*inch)
    else:
        logo_img = Paragraph(f"<b>{business_details.name[:2]}</b>", style_heading)

    biz_info = Paragraph(
        f"<b><font size=12>{business_details.name}</font></b><br/>"
        f"{business_details.address}<br/>"
        f"Phone: {business_details.phone}<br/>"
        f"Owner: {business_details.owner_name}",
        style_normal
    )
    
    invoice_title = Paragraph("INVOICE", style_heading)
    invoice_details = Paragraph(
        f"<b>Invoice #:</b> {bill_data['bill_id']}<br/>"
        f"<b>Date:</b> {bill_data['date_time'].strftime('%d-%m-%Y')}<br/>"
        f"<b>Time:</b> {bill_data['date_time'].strftime('%I:%M %p')}",
        ParagraphStyle('InvoiceMeta', parent=style_normal, alignment=TA_RIGHT, leading=14)
    )

    left_sub_data = [[logo_img, biz_info]]
    left_sub_table = Table(left_sub_data, colWidths=[1*inch, 3*inch])
    left_sub_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
    ]))

    header_data = [[left_sub_table, [invoice_title, invoice_details]]]
    header_table = Table(header_data, colWidths=[4.2*inch, 3*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('LINEBELOW', (0,0), (-1,0), 2, THEME_COLOR),
        ('BOTTOMPADDING', (0,0), (-1,0), 15),
    ]))
    
    Story.append(header_table)
    Story.append(Spacer(1, 20))

    # --- 2. BILL TO SECTION ---
    customer_info = Paragraph(
        f"<font color='{THEME_COLOR.hexval()}'><b>BILL TO:</b></font><br/>"
        f"<b>{bill_data.get('customer_name', 'Walk-in Customer')}</b><br/>"
        f"Phone: {bill_data.get('mobile_number', 'N/A')}<br/>"
        f"Vehicle: {bill_data.get('car_model', 'N/A')} ({bill_data.get('car_number', 'N/A')})<br/>"
        f"KM Reading: {bill_data.get('car_km', 'N/A')}",
        style_normal
    )
    
    cust_table = Table([[customer_info]], colWidths=[7.2*inch])
    cust_table.setStyle(TableStyle([('LEFTPADDING', (0,0), (-1,-1), 5)]))
    Story.append(cust_table)
    Story.append(Spacer(1, 15))

    # --- 3. ITEMS TABLE ---
    col_widths = [0.6*inch, 3.7*inch, 0.8*inch, 1.0*inch, 1.1*inch]
    table_data = [["Sr.", "Item Description", "Qty.", "Rate", "Amount"]]
    
    total_amount = Decimal('0.00')
    
    for item in bill_data['items']:
        try:
            amt = Decimal(str(item['amount']))
            rate = Decimal(str(item['rate']))
            qty = Decimal(str(item['quantity']))
        except:
            amt = Decimal('0.00'); rate = Decimal('0.00'); qty = Decimal('0.00')
            
        total_amount += amt
        table_data.append([
            str(item['sr_no']),
            Paragraph(item['item_name'], style_normal),
            f"{qty:g}",
            f"{rate:,.2f}",
            f"{amt:,.2f}"
        ])

    MIN_ROWS = 12
    current_rows = len(bill_data['items'])
    if current_rows < MIN_ROWS:
        empty_rows_needed = MIN_ROWS - current_rows
        for _ in range(empty_rows_needed):
            table_data.append(["", "", "", "", ""])

    disc_pct = Decimal(str(bill_data.get('discount_percent', 0)))
    disc_amt = (total_amount * (disc_pct / 100)).quantize(Decimal('0.01'))
    net_payable = total_amount - disc_amt

    table_data.append(["", "", "", "Sub Total:", f"{total_amount:,.2f}"])
    table_data.append(["", "", "", f"Discount ({disc_pct}%):", f"- {disc_amt:,.2f}"])
    table_data.append(["", "", "", "Grand Total:", f"{net_payable:,.2f}"])

    item_table = Table(table_data, colWidths=col_widths)
    
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), THEME_COLOR),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('TOPPADDING', (0,0), (-1,0), 10),
        ('ALIGN', (0,1), (0,-1), 'CENTER'),
        ('ALIGN', (1,1), (1,-1), 'LEFT'),
        ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('GRID', (0,0), (-1,-4), 0.5, colors.lightgrey),
        ('LINEABOVE', (3,-3), (-1,-3), 1, THEME_COLOR),
        ('FONTNAME', (3,-3), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (3,-3), (3,-1), 'RIGHT'),
        ('BACKGROUND', (3,-1), (-1,-1), colors.whitesmoke),
        ('TEXTCOLOR', (3,-1), (-1,-1), THEME_COLOR),
    ]
    
    item_table.setStyle(TableStyle(t_style))
    Story.append(item_table)
    Story.append(Spacer(1, 30))

    # --- 4. FOOTER ---
    terms_text = (
        "<b>Terms & Conditions:</b><br/>"
        "1. Goods once sold will not be taken back.<br/>"
        "2. Warranty as per manufacturer terms.<br/>"
        "3. Subject to local jurisdiction."
    )
    
    footer_data = [[
        Paragraph(terms_text, style_normal),
        Paragraph(f"<b>Authorized Signature</b><br/><br/><br/>_______________________<br/>{business_details.name}", 
                  ParagraphStyle('Sign', parent=style_normal, alignment=TA_CENTER))
    ]]
    
    footer_table = Table(footer_data, colWidths=[4.5*inch, 2.7*inch])
    footer_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (1,0), (1,0), 'CENTER')]))
    Story.append(footer_table)
    
    doc.build(Story)
    return output_filename