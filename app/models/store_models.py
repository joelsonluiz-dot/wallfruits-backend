from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Enum as SqEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.connection import Base
import enum

class ProductStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    OUT_OF_STOCK = "out_of_stock"
    ARCHIVED = "archived"

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class ProductCategory(Base):
    __tablename__ = "store_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    icon = Column(String(50), nullable=True)  # emoji or icon class
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "store_products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), index=True, nullable=False)
    slug = Column(String(255), unique=True, index=True) 
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    promotional_price = Column(Float, nullable=True)
    
    stock_quantity = Column(Integer, default=0)
    sku = Column(String(100), unique=True, nullable=True)
    
    status = Column(SqEnum(ProductStatus), default=ProductStatus.DRAFT)
    is_featured = Column(Boolean, default=False)
    
    # Detalhes agrícolas específicos
    specifications = Column(JSON, default={})  # Peso, Origem, Safra, Certificações
    images = Column(JSON, default=[])          # Lista de URLs
    
    category_id = Column(Integer, ForeignKey("store_categories.id"))
    supplier_id = Column(Integer, ForeignKey("users.id"))  # Quem publicou
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    category = relationship("ProductCategory", back_populates="products")
    supplier = relationship("User", backref="store_products")
    order_items = relationship("OrderItem", back_populates="product")

class Order(Base):
    __tablename__ = "store_orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"))
    
    total_amount = Column(Float, default=0.0)
    status = Column(SqEnum(OrderStatus), default=OrderStatus.PENDING)
    payment_method = Column(String(50), nullable=True)
    payment_details = Column(JSON, default={})
    shipping_address = Column(JSON, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    customer = relationship("User", backref="store_orders")


class OrderItem(Base):
    __tablename__ = "store_order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("store_orders.id"))
    product_id = Column(Integer, ForeignKey("store_products.id"))
    
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)  # Preço no momento da compra
    subtotal = Column(Float, nullable=False)
    
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
