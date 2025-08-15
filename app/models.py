from sqlalchemy import Column, String, Float, DateTime
from datetime import datetime, timezone
from app.database import Base

class Rate(Base):
    __tablename__ = "rates"

    base = Column(String, primary_key=True)
    currency = Column(String, primary_key=True)
    rate = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
