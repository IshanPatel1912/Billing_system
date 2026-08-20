import os
import sys
import bcrypt
import configparser
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

config = configparser.ConfigParser()
config.read('config.ini')


APP_NAME = "BillingSystem"

if sys.platform == 'win32':
    # This completely bypasses the Windows Store sandbox and forces the REAL AppData folder
    user_home = os.path.expanduser('~') # Gets C:\Users\<YourName>
    app_data_dir = os.path.join(user_home, 'AppData', 'Roaming', APP_NAME)
else:
    app_data_dir = os.path.join(os.path.expanduser('~'), '.' + APP_NAME)


if not os.path.exists(app_data_dir):
    os.makedirs(app_data_dir)

DATABASE_PATH = os.path.join(app_data_dir, 'billing_data.db')
Base = declarative_base()


class Sale(Base):
    __tablename__ = 'sales'
    bill_id = Column(String, primary_key=True)
    date_time = Column(DateTime, default=datetime.utcnow)
    customer_name = Column(String, nullable=True, index=True)
    mobile_number = Column(String, nullable=True, index=True)
    car_number = Column(String, nullable=True)
    car_model = Column(String, nullable=True)
    car_km = Column(String, nullable=True)
    subtotal = Column(Float, default=0.0)
    discount_percent = Column(Float, default=0.0)
    net_total = Column(Float, default=0.0)
    paid_status = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")

class SaleItem(Base):
    __tablename__ = 'sale_items'
    id = Column(Integer, primary_key=True)
    sale_bill_id = Column(String, ForeignKey('sales.bill_id'))
    sr_no = Column(Integer)
    item_name = Column(String)
    quantity = Column(Float)
    rate = Column(Float)
    amount = Column(Float)
    is_tracked = Column(Boolean, default=False) 
    is_deleted = Column(Boolean, default=False)
    sale = relationship("Sale", back_populates="items")

class Purchase(Base):
    __tablename__ = 'purchases'
    id = Column(Integer, primary_key=True)
    date_time = Column(DateTime, default=datetime.utcnow)
    total_amount = Column(Float, default=0.0)
    track_item = Column(Boolean, default=False)
    category = Column(String, nullable=True)
    is_deleted = Column(Boolean, default=False)
    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")

class PurchaseItem(Base):
    __tablename__ = 'purchase_items'
    id = Column(Integer, primary_key=True)
    purchase_id = Column(Integer, ForeignKey('purchases.id'))
    sr_no = Column(Integer, nullable=True) 
    item_name = Column(String)
    quantity = Column(Float)
    rate = Column(Float) 
    amount = Column(Float)
    category = Column(String, nullable=True)
    track_item = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    purchase = relationship("Purchase", back_populates="items")

class Expenditure(Base):
    __tablename__ = 'expenditures'
    id = Column(Integer, primary_key=True)
    date_time = Column(DateTime, default=datetime.utcnow)
    sr_no_daily = Column(Integer, nullable=True)
    description = Column(String)
    amount = Column(Float)
    is_deleted = Column(Boolean, default=False)

class Inventory(Base):
    __tablename__ = 'inventory'
    id = Column(Integer, primary_key=True)
    item_name = Column(String, unique=True)
    quantity = Column(Float, default=0.0)
    cost_price = Column(Float, default=0.0) 
    mrp = Column(Float, default=0.0)   
    is_deleted = Column(Boolean, default=False)     

class ServiceReminder(Base):
    __tablename__ = 'service_reminders'
    id = Column(Integer, primary_key=True)
    bill_id = Column(String, ForeignKey('sales.bill_id'))
    car_number = Column(String)
    customer_name = Column(String)
    mobile_number = Column(String)
    service_due_date = Column(DateTime)
    is_notified = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)

class BusinessDetail(Base):
    __tablename__ = 'business_details'
    id = Column(Integer, primary_key=True)
    name = Column(String, default="Your Business Name")
    address = Column(String, default="123 Business Street, City")
    phone = Column(String, default="+1234567890")
    owner_name = Column(String, default="Owner Name")
    logo_path = Column(String, nullable=True)
    is_deleted = Column(Boolean, default=False)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="admin")
    is_deleted = Column(Boolean, default=False)

class Customer(Base):
    __tablename__ = 'customers'
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    mobile = Column(String, index=True)
    is_deleted = Column(Boolean, default=False)

class CustomerCar(Base):
    __tablename__ = 'customer_cars'
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'))
    car_model = Column(String)
    car_number = Column(String)
    is_deleted = Column(Boolean, default=False)
    customer = relationship("Customer", backref="cars")

def get_current_business_details():
    session = Session()
    details = session.query(BusinessDetail).first()
    session.close()
    return details

def setup_database():
    engine = create_engine(f'sqlite:///{DATABASE_PATH}')
    
    with engine.begin() as conn: 
        tables_to_upgrade = [
            'sales', 'sale_items', 'purchases', 'purchase_items', 
            'expenditures', 'inventory', 'service_reminders', 
            'business_details', 'users', 'customers', 'customer_cars'
        ]
        
        for table in tables_to_upgrade:
            try:
                result = conn.execute(text(f"PRAGMA table_info({table})"))
                cols = [row[1] for row in result.fetchall()]
                
                if cols and 'is_deleted' not in cols:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
            except Exception:
                pass 

    
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    
    if session.query(BusinessDetail).count() == 0: 
        session.add(BusinessDetail())
        session.commit()

    
    if session.query(User).count() == 0:
        hashed = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt())
        session.add(User(username="admin", password_hash=hashed.decode('utf-8')))
        session.commit()

    session.close()
    return SessionLocal, engine

Session, engine = setup_database()