from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, Text, Float, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id:                     Mapped[int]              = mapped_column(Integer, primary_key=True)
    teacher_email:          Mapped[Optional[str]]    = mapped_column(Text)
    student_name:           Mapped[Optional[str]]    = mapped_column(Text)
    usn:                    Mapped[Optional[str]]    = mapped_column(Text)
    subject_name:           Mapped[Optional[str]]    = mapped_column(Text)
    attendance_percentage:  Mapped[Optional[float]]  = mapped_column(Float)
    status:                 Mapped[Optional[str]]    = mapped_column(Text)   # 'success' | 'failed'
    error_message:          Mapped[Optional[str]]    = mapped_column(Text)
    recipient_type:         Mapped[Optional[str]]    = mapped_column(Text)   # 'teacher' | 'student'
    created_at:             Mapped[datetime]         = mapped_column(
        TIMESTAMP, server_default=func.now()
    )
