from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Integer, String, Text, Numeric, ForeignKey, TIMESTAMP, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int]                             = mapped_column(Integer, primary_key=True)
    name: Mapped[str]                           = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]]                = mapped_column(String(255), unique=True)
    portal_username: Mapped[Optional[str]]      = mapped_column(String(255))
    # portal_password_encrypted intentionally excluded from ORM —
    # structurally prevents it from ever appearing in API responses.
    created_at: Mapped[datetime]                = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    students: Mapped[list["Student"]] = relationship(
        "Student", back_populates="teacher", lazy="select"
    )


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int]                                 = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[Optional[int]]               = mapped_column(
        Integer, ForeignKey("teachers.id", ondelete="CASCADE")
    )
    name: Mapped[Optional[str]]                     = mapped_column(String(255))
    usn: Mapped[Optional[str]]                      = mapped_column(String(50), index=True)
    semester: Mapped[Optional[str]]                 = mapped_column(String(20))
    registration_status: Mapped[Optional[str]]      = mapped_column(String(255))
    backlogs_status: Mapped[Optional[str]]           = mapped_column(String(255))
    student_email: Mapped[Optional[str]]             = mapped_column(Text)
    created_at: Mapped[datetime]                    = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    teacher: Mapped[Optional["Teacher"]]                = relationship("Teacher", back_populates="students")
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        "AttendanceRecord", back_populates="student", lazy="select"
    )


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int]                                     = mapped_column(Integer, primary_key=True)
    student_id: Mapped[Optional[int]]                   = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE")
    )
    subject_name: Mapped[Optional[str]]                 = mapped_column(String(255))
    course_type: Mapped[Optional[str]]                  = mapped_column(String(100))
    attendance_percentage: Mapped[Optional[Decimal]]    = mapped_column(Numeric(5, 2))
    total_classes: Mapped[Optional[int]]                = mapped_column(Integer)
    attended_classes: Mapped[Optional[int]]             = mapped_column(Integer)
    cie_max_marks: Mapped[Optional[int]]                = mapped_column(Integer)
    cie_obtained_marks: Mapped[Optional[int]]           = mapped_column(Integer)
    scraped_at: Mapped[datetime]                        = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    student: Mapped[Optional["Student"]] = relationship("Student", back_populates="attendance_records")
