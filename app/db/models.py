from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass
class Session(Base):
    __tablename__='sessions'; id: Mapped[int]=mapped_column(primary_key=True); title: Mapped[str]=mapped_column(String(200),default='New session'); status: Mapped[str]=mapped_column(String(30),default='idle'); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
class Message(Base):
    __tablename__='messages'; id: Mapped[int]=mapped_column(primary_key=True); session_id: Mapped[int]=mapped_column(ForeignKey('sessions.id')); role: Mapped[str]=mapped_column(String(30)); content: Mapped[str|None]=mapped_column(Text,nullable=True); tool_call_id: Mapped[str|None]=mapped_column(String(100),nullable=True); tool_calls: Mapped[str|None]=mapped_column(Text,nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ToolExecution(Base):
    __tablename__='tool_executions'; id: Mapped[int]=mapped_column(primary_key=True); session_id: Mapped[int]=mapped_column(ForeignKey('sessions.id')); run_id: Mapped[str]=mapped_column(String(100)); tool_name: Mapped[str]=mapped_column(String(100)); arguments: Mapped[dict]=mapped_column(JSON); status: Mapped[str]=mapped_column(String(30)); result: Mapped[str|None]=mapped_column(Text,nullable=True); error: Mapped[str|None]=mapped_column(Text,nullable=True); approved: Mapped[bool]=mapped_column(default=False); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); finished_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class Memory(Base):
    __tablename__='memories'; id: Mapped[int]=mapped_column(primary_key=True); key: Mapped[str]=mapped_column(String(200),unique=True); value: Mapped[str]=mapped_column(Text); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
class Approval(Base):
    __tablename__='approvals'; id: Mapped[int]=mapped_column(primary_key=True); run_id: Mapped[str]=mapped_column(String(100)); tool_execution_id: Mapped[int]=mapped_column(ForeignKey('tool_executions.id')); status: Mapped[str]=mapped_column(String(30),default='pending'); reason: Mapped[str]=mapped_column(Text); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); resolved_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
