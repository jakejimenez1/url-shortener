from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

## Defines a table called urls in the DB
## Each instance of URL is a row in urls table
class URL(Base):
    __tablename__ = "urls"
    
    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(Text, nullable=False)
    short_code = Column(String(10), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    expires_at = Column(DateTime, nullable=True)
    click_count = Column(Integer, default=0)
    
    clicks = relationship("Click", back_populates="url", cascade="all, delete-orphan")

## Defines a clicks table in the DB
## Each instance corresponds to a click on a URL
class Click(Base):
    __tablename__ = "clicks"
    
    id = Column(Integer, primary_key=True, index=True)
    url_id = Column(Integer, ForeignKey("urls.id"), nullable=False, index=True)
    clicked_at = Column(DateTime, default=datetime.now, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    referrer = Column(Text, nullable=True)
    
    url = relationship("URL", back_populates="clicks")