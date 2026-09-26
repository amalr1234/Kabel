from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, default="consultant")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, index=True)
    system = Column(String, index=True)
    priority = Column(String, index=True)
    status = Column(String, default="open")
    resolution = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolver = Column(String, nullable=True)
    resolution_time_hours = Column(Float, nullable=True)
    feedback_score = Column(Float, nullable=True)
    source = Column(String, default="ServiceNow", nullable=True)
    source_reliability = Column(Float, default=0.90, nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    category = Column(String, index=True)
    system = Column(String, index=True)
    file_path = Column(String, nullable=True)
    chunk_count = Column(Integer, default=0)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    solution_id = Column(String, nullable=False, index=True)
    rating = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    detail = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SolutionUsage(Base):
    __tablename__ = "solution_usage"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text, nullable=False)
    solution_id = Column(String, nullable=False)
    match_score = Column(Integer, nullable=False)
    confidence = Column(String, nullable=False)
    feedback_rating = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

