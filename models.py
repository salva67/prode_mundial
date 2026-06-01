from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

# Usar ruta absoluta para que funcione tanto local como en Streamlit Cloud
DB_PATH = os.path.join(os.path.dirname(__file__), "prode.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    predictions = relationship("Prediction", back_populates="user", lazy="dynamic")


class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    stage = Column(String(40), nullable=False)
    group = Column(String(5))
    slot = Column(Integer)
    home_team = Column(String(60), nullable=False)
    away_team = Column(String(60), nullable=False)
    home_score = Column(Integer)
    away_score = Column(Integer)
    status = Column(String(20), default="pendiente")
    predictions = relationship("Prediction", back_populates="match", lazy="dynamic")


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    home_score = Column(Integer, nullable=False)
    away_score = Column(Integer, nullable=False)
    points = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="predictions")
    match = relationship("Match", back_populates="predictions")
    __table_args__ = (UniqueConstraint("user_id", "match_id"),)


def init_db():
    Base.metadata.create_all(engine)
