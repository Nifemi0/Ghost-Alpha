from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import datetime

DATABASE_URL = "sqlite:///./poly.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(String, index=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    initial_price = Column(Float)
    final_price = Column(Float, nullable=True)
    last_trade_price = Column(Float, nullable=True)
    clob_token_id = Column(String)  # [NEW] For historical price lookups
    momentum_24h = Column(Float, nullable=True) # [NEW] Price change in first 24h
    outcome = Column(Boolean, nullable=True)
    volume = Column(Float)
    category = Column(String, nullable=True)
    news_summary = Column(String, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
