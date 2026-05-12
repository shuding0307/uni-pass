from sqlalchemy import Column, String, Integer, SmallInteger, Boolean, ForeignKey, JSON, Numeric, DateTime, Text, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class Student(Base):
    __tablename__ = "students"
    student_id = Column(String(12), primary_key=True)
    name = Column(String(50), nullable=False)
    major = Column(String(100), nullable=False)
    sub_major = Column(String(100))
    admission_year = Column(SmallInteger, nullable=False)
    is_transfer = Column(Boolean, default=False, nullable=False)
    is_eng_cert = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Course(Base):
    __tablename__ = "courses"
    course_code = Column(String(20), primary_key=True)
    name = Column(String(200), nullable=False)
    credits = Column(SmallInteger, nullable=False)
    area_type = Column(String(50), nullable=False)
    sub_area = Column(String(100))
    building_name = Column(String(100))
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class GraduationRequirementDB(Base):
    __tablename__ = "graduation_requirements"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    major = Column(String(100), nullable=False)
    admission_year = Column(SmallInteger, nullable=False)
    is_eng_cert = Column(Boolean, default=False, nullable=False)
    basic_ge = Column(SmallInteger, default=0, nullable=False)
    balanced_ge = Column(SmallInteger, default=0, nullable=False)
    specialized_ge = Column(SmallInteger, default=0, nullable=False)
    univ_core_ge = Column(SmallInteger, default=0, nullable=False)
    major_required = Column(SmallInteger, default=0, nullable=False)
    major_elective = Column(SmallInteger, default=0, nullable=False)
    advanced_major = Column(SmallInteger, default=0, nullable=False)
    general_elective = Column(SmallInteger, default=0, nullable=False)
    total_credits = Column(SmallInteger, default=130, nullable=False)
    min_ge_areas = Column(SmallInteger, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class CompletedCourse(Base):
    __tablename__ = "completed_courses"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(String(12), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)
    course_code = Column(String(20), ForeignKey("courses.course_code"), nullable=False)
    area_type = Column(String(50), nullable=False)
    credits = Column(SmallInteger, nullable=False)
    grade = Column(String(5), nullable=False)
    semester_taken = Column(String(10), nullable=False)
    is_substituted = Column(Boolean, default=False, nullable=False)
    substituted_by = Column(UUID(as_uuid=True), ForeignKey("completed_courses.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(String(12), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)
    requirement_id = Column(UUID(as_uuid=True), ForeignKey("graduation_requirements.id"), nullable=False)
    result_json = Column(JSONB, nullable=False)
    deficiency_map = Column(JSONB, default={}, nullable=False)
    overflow_map = Column(JSONB, default={}, nullable=False)
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())

class CourseOffering(Base):
    __tablename__ = "course_offerings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_code = Column(String(20), ForeignKey("courses.course_code"), nullable=False)
    semester = Column(String(10), nullable=False)
    section = Column(String(20), nullable=False)
    professor = Column(String(100))
    schedule = Column(String(200))
    building_name = Column(String(100))
    room_number = Column(String(20))
    raw_classroom = Column(Text)
    offering_college = Column(String(100))
    offering_department = Column(String(100))
    offering_major = Column(String(100))
    target_departments = Column(Text)
    is_remote = Column(Boolean, default=False, nullable=False)
    language_type = Column(String(100))
    course_note = Column(Text)
    is_cancelled = Column(Boolean, default=False, nullable=False)
    current_enrollment = Column(SmallInteger, default=0, nullable=False)
    max_enrollment = Column(SmallInteger, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Regulation(Base):
    __tablename__ = "regulations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    major = Column(String(100))
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    source_tag = Column(String(100))
    # content_vector(tsvector) and embedding(vector) are usually handled via raw SQL or specific extensions
    effective_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TranscriptUpload(Base):
    __tablename__ = "transcript_uploads"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(String(12), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(255), nullable=False)
    storage_path = Column(Text, nullable=False)
    parse_status = Column(String(20), default="pending", nullable=False)
    parse_error = Column(Text)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    parsed_at = Column(DateTime(timezone=True))
