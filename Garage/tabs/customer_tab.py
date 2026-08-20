from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, 
                             QGroupBox, QFileDialog, QGridLayout, QCompleter)
from PyQt6.QtCore import Qt, QStringListModel
from database import Session, Customer, CustomerCar
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from sqlalchemy import or_

class CustomerTab(QWidget):
    def __init__(self):
        super().__init__()
        self.current_id = None
        self.init_ui()
        self.load_customers()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # 1. CUSTOMER & CAR INPUT FORM
        group_form = QGroupBox("Manage Customer Details")
        group_form.setStyleSheet("QGroupBox { font-weight: bold; color: #005a9e; font-size: 14px; }")
        form_layout = QVBoxLayout()
        
        # -- Customer Basic Details --
        basic_layout = QHBoxLayout()
        self.c_name = QLineEdit()
        self.c_name.setPlaceholderText("Customer Name")
        self.c_name.setMinimumHeight(35)
        
        self.c_mobile = QLineEdit()
        self.c_mobile.setPlaceholderText("Mobile Number")
        self.c_mobile.setMinimumHeight(35)

        # --- AUTO-COMPLETE SUGGESTIONS SETUP ---
        self.name_completer = QCompleter([])
        self.name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.name_completer.setFilterMode(Qt.MatchFlag.MatchContains) # Allows matching middle of names
        self.c_name.setCompleter(self.name_completer)
        self.name_completer.activated.connect(self.load_customer_by_name)

        self.mobile_completer = QCompleter([])
        self.mobile_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.c_mobile.setCompleter(self.mobile_completer)
        self.mobile_completer.activated.connect(self.load_customer_by_mobile)

        basic_layout.addWidget(QLabel("Name:")); basic_layout.addWidget(self.c_name)
        basic_layout.addWidget(QLabel("Mobile:")); basic_layout.addWidget(self.c_mobile)
        form_layout.addLayout(basic_layout)

        # -- Car Details Section --
        car_group = QGroupBox("Attached Cars (Add as many as needed)")
        car_group.setStyleSheet("QGroupBox { font-weight: normal; color: #333; }")
        car_layout = QVBoxLayout()
        
        car_input_layout = QHBoxLayout()
        self.car_model_input = QLineEdit()
        self.car_model_input.setPlaceholderText("Car Model (e.g. Swift)")
        self.car_model_input.setMinimumHeight(30)
        
        self.car_number_input = QLineEdit()
        self.car_number_input.setPlaceholderText("Car Number (e.g. GJ05 AB 1234)")
        self.car_number_input.setMinimumHeight(30)
        
        btn_add_car = QPushButton("➕ Add Car to List")
        btn_add_car.setMinimumHeight(30)
        btn_add_car.clicked.connect(self.add_car_to_form)
        
        car_input_layout.addWidget(self.car_model_input)
        car_input_layout.addWidget(self.car_number_input)
        car_input_layout.addWidget(btn_add_car)
        car_layout.addLayout(car_input_layout)

        self.car_table = QTableWidget()
        self.car_table.setColumnCount(2)
        self.car_table.setHorizontalHeaderLabels(["Car Model", "Car Number"])
        self.car_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.car_table.setFixedHeight(120) 
        car_layout.addWidget(self.car_table)

        btn_remove_car = QPushButton("❌ Remove Selected Car from List")
        btn_remove_car.clicked.connect(self.remove_car_from_form)
        car_layout.addWidget(btn_remove_car)
        
        car_group.setLayout(car_layout)
        form_layout.addWidget(car_group)

        # -- Save / Clear Buttons --
        btn_layout = QHBoxLayout()
        self.btn_action = QPushButton("Save Customer & Cars")
        self.btn_action.setMinimumHeight(40)
        self.btn_action.setStyleSheet("background-color: #005a9e; color: white; font-weight: bold;")
        self.btn_action.clicked.connect(self.save_customer)
        
        btn_clear = QPushButton("Clear Form")
        btn_clear.setMinimumHeight(40)
        btn_clear.clicked.connect(self.clear_form)
        
        btn_layout.addWidget(self.btn_action)
        btn_layout.addWidget(btn_clear)
        form_layout.addLayout(btn_layout)

        group_form.setLayout(form_layout)
        layout.addWidget(group_form)

        # 2. MAIN CUSTOMERS TABLE
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Customer Name", "Mobile Number", "Attached Cars"])
        self.table.hideColumn(0)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(True) 
        self.table.itemClicked.connect(self.populate_form)
        layout.addWidget(self.table)

        # 3. BOTTOM ACTIONS (EXPORT / DELETE)
        action_layout = QHBoxLayout()
        btn_export = QPushButton("📄 Export Customers (PDF)")
        btn_export.setStyleSheet("background-color: #d83b01; color: white; font-weight: bold; padding: 10px;")
        btn_export.clicked.connect(self.export_pdf)
        
        btn_delete = QPushButton("Delete Selected Customer")
        btn_delete.setStyleSheet("background-color: #c42b1c; color: white; font-weight: bold; padding: 10px;")
        btn_delete.clicked.connect(self.delete_customer)
        
        action_layout.addWidget(btn_export)
        action_layout.addWidget(btn_delete)
        layout.addLayout(action_layout)

    # --- AUTO-COMPLETE POPULATE LOGIC ---
    def load_customer_by_name(self, name_text):
        session = Session()
        customer = session.query(Customer).filter(
            Customer.name == name_text,
            or_(Customer.is_deleted == False, Customer.is_deleted == None)
        ).first()
        if customer:
            self.load_customer_into_form(customer)
        session.close()

    def load_customer_by_mobile(self, mobile_text):
        session = Session()
        customer = session.query(Customer).filter(
            Customer.mobile == mobile_text,
            or_(Customer.is_deleted == False, Customer.is_deleted == None)
        ).first()
        if customer:
            self.load_customer_into_form(customer)
        session.close()

    def load_customer_into_form(self, customer):
        # A helper function that takes a customer from the database and fills the screen
        self.current_id = str(customer.id)
        self.c_name.setText(customer.name)
        self.c_mobile.setText(customer.mobile if customer.mobile else "")
        
        # Load the cars into the mini-table
        self.car_table.setRowCount(0)
        for car in customer.cars:
            r = self.car_table.rowCount()
            self.car_table.insertRow(r)
            self.car_table.setItem(r, 0, QTableWidgetItem(car.car_model))
            self.car_table.setItem(r, 1, QTableWidgetItem(car.car_number))
            
        self.btn_action.setText("Update Customer & Cars")

    # --- CAR MINI-LIST LOGIC ---
    def add_car_to_form(self):
        model = self.car_model_input.text().strip()
        number = self.car_number_input.text().strip()
        if not model and not number: return
        
        r = self.car_table.rowCount()
        self.car_table.insertRow(r)
        self.car_table.setItem(r, 0, QTableWidgetItem(model))
        self.car_table.setItem(r, 1, QTableWidgetItem(number))
        
        self.car_model_input.clear()
        self.car_number_input.clear()
        self.car_model_input.setFocus()

    def remove_car_from_form(self):
        row = self.car_table.currentRow()
        if row >= 0:
            self.car_table.removeRow(row)

    # --- DATABASE LOGIC ---
    def save_customer(self):
        name = self.c_name.text().strip()
        mobile = self.c_mobile.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Error", "Customer name is required.")
            return

        session = Session()
        try:
            if self.current_id:
                # Update existing customer
                customer = session.query(Customer).filter_by(id=self.current_id).first()
                if customer:
                    customer.name = name
                    customer.mobile = mobile
            else:
                # Add new customer
                customer = Customer(name=name, mobile=mobile)
                session.add(customer)
                session.flush() # Get the new ID immediately
            
            # Wipe old cars and save the exact list currently in the mini-table
            session.query(CustomerCar).filter_by(customer_id=customer.id).delete()
            
            for r in range(self.car_table.rowCount()):
                c_model = self.car_table.item(r, 0).text()
                c_num = self.car_table.item(r, 1).text()
                session.add(CustomerCar(customer_id=customer.id, car_model=c_model, car_number=c_num))
            
            session.commit()
            self.clear_form()
            self.load_customers() # This also updates the Auto-Complete lists!
            QMessageBox.information(self, "Success", "Customer & Cars saved successfully.")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def populate_form(self, item):
        row = item.row()
        self.current_id = self.table.item(row, 0).text()
        
        session = Session()
        customer = session.query(Customer).filter_by(id=self.current_id).first()
        if customer:
            self.load_customer_into_form(customer)
        session.close()

    def clear_form(self):
        self.current_id = None
        self.c_name.clear()
        self.c_mobile.clear()
        self.car_model_input.clear()
        self.car_number_input.clear()
        self.car_table.setRowCount(0)
        self.btn_action.setText("Save Customer & Cars")

    def delete_customer(self):
        row = self.table.currentRow()
        if row == -1: return
        
        if QMessageBox.question(self, "Confirm", "Delete this customer AND all their attached cars?") == QMessageBox.StandardButton.Yes:
            c_id = self.table.item(row, 0).text()
            session = Session()
            try:
                session.query(CustomerCar).filter_by(customer_id=c_id).delete()
                session.query(Customer).filter_by(id=c_id).delete()
                session.commit()
                self.clear_form()
                self.load_customers()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", str(e))
            finally:
                session.close()

    def load_customers(self):
        session = Session()
        customers = session.query(Customer).filter(
            or_(Customer.is_deleted == False, Customer.is_deleted == None)
        ).order_by(Customer.name).all()
        
        self.table.setRowCount(0)
        names_list = []
        mobiles_list = []

        for c in customers:
            # Build list for Auto-Completer
            if c.name and c.name not in names_list:
                names_list.append(c.name)
            if c.mobile and c.mobile not in mobiles_list:
                mobiles_list.append(c.mobile)

            # Build the Main View Table
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(c.id)))
            self.table.setItem(r, 1, QTableWidgetItem(c.name))
            self.table.setItem(r, 2, QTableWidgetItem(c.mobile if c.mobile else "N/A"))
            
            car_strings = []
            for car in c.cars:
                if car.car_model and car.car_number:
                    car_strings.append(f"🚗 {car.car_model}  |  🔢 {car.car_number}")
                elif car.car_model:
                    car_strings.append(f"🚗 {car.car_model}")
                elif car.car_number:
                    car_strings.append(f"🔢 {car.car_number}")
            
            final_car_string = "\n".join(car_strings) if car_strings else "No Cars Attached"
            self.table.setItem(r, 3, QTableWidgetItem(final_car_string))
            
        self.table.resizeRowsToContents()
        
        # Update the Auto-Complete models with fresh database data
        self.name_completer.setModel(QStringListModel(names_list))
        self.mobile_completer.setModel(QStringListModel(mobiles_list))
        
        session.close()

    # --- EXPORT ---
    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Customers PDF", "Customer_Directory.pdf", "PDF Files (*.pdf)")
        if not path: return
        
        session = Session()
        customers = session.query(Customer).filter(
            or_(Customer.is_deleted == False, Customer.is_deleted == None)
        ).order_by(Customer.name).all()

        try:
            doc = SimpleDocTemplate(path, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            elements.append(Paragraph("<b><font color='#005a9e'>Customer & Vehicle Directory</font></b>", styles['Title']))
            elements.append(Spacer(1, 15))
            
            table_data = [['Sr No.', 'Customer Name', 'Mobile Number', 'Attached Cars']]
            for idx, c in enumerate(customers, start=1):
                car_strings = []
                for car in c.cars:
                    if car.car_model and car.car_number:
                        car_strings.append(f"<b>{car.car_model}</b> ({car.car_number})")
                    else:
                        car_strings.append(car.car_model or car.car_number)
                
                final_car_string = "<br/>".join(car_strings) if car_strings else "None"
                cars_text = Paragraph(final_car_string, styles['Normal'])
                
                table_data.append([str(idx), c.name, c.mobile if c.mobile else "N/A", cars_text])
                
            if len(table_data) > 1:
                t = Table(table_data, colWidths=[40, 150, 90, 200])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#005a9e")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                elements.append(t)
            else:
                elements.append(Paragraph("No customers recorded yet.", styles['Normal']))
                
            doc.build(elements)
            QMessageBox.information(self, "Success", "Customer Directory Exported Successfully")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate PDF:\n{str(e)}")
        finally:
            session.close()