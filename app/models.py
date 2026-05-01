from sqlalchemy import Column, Integer, String
from .database import Base

class URL(Base):
    __tablename__ = "url_shortener" 

    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String, unique=True, index=True)
    long_url = Column(String , unique=True , index=True)
