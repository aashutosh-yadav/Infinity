from sqlalchemy import Column, Integer, String
from .database import Base

class URL(Base):
    __tablename__ = "url_shortner"

    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String, unique=True, index=True)
    # adding index gives id to logurl which makes the loopup O(log n)
    # adding uniques handles the duplicates 
    long_url = Column(String , unique=True , index=True)
