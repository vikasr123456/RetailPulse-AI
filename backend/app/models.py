
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from .db import Base

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    location = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="OWNER", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False)
    sku = Column(String, index=True)
    name = Column(String, index=True)
    company = Column(String, index=True, default="RetailPulse Demo")
    brand = Column(String, index=True, default="")
    category = Column(String, index=True)
    subcategory = Column(String, index=True, default="")
    unit_price = Column(Float, default=0)
    unit_cost = Column(Float, default=0)
    currency = Column(String, default="INR")
    barcode = Column(String, index=True, default="")
    supplier = Column(String, default="")
    current_stock = Column(Float, default=0)
    lead_time_days = Column(Integer, default=7)
    safety_stock = Column(Float, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    sale_date = Column(DateTime, index=True)
    quantity = Column(Float)

class Forecast(Base):
    __tablename__ = "forecasts"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    model = Column(String)
    horizon = Column(Integer)
    mae = Column(Float)
    rmse = Column(Float)
    mape = Column(Float)
    training_start = Column(DateTime)
    training_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class ForecastValue(Base):
    __tablename__ = "forecast_values"
    id = Column(Integer, primary_key=True)
    forecast_id = Column(Integer, ForeignKey("forecasts.id"), index=True)
    forecast_date = Column(DateTime)
    value = Column(Float)

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    level = Column(String)
    title = Column(String)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
