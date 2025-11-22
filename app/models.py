from sqlalchemy import (
    Column, Integer, String, Text, DECIMAL, Boolean,
    ForeignKey, Enum, TIMESTAMP, Index, func
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


# ---- ENUM TYPES ----
class UserRole(enum.Enum):
    consultant = "consultant"
    company = "company"
    admin = "admin"


class UnlockTarget(enum.Enum):
    consultant = "consultant"
    job = "job"


# ---- TABLES ----
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    consultant_profile = relationship("ConsultantProfile", back_populates="user", uselist=False)
    company = relationship("Company", back_populates="user", uselist=False)


class ConsultantProfile(Base):
    __tablename__ = "consultant_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    display_name_masked = Column(String(120), nullable=False)
    headline = Column(String(160))
    location_city = Column(String(120))
    country = Column(String(120))
    availability = Column(String(120))
    rate_value = Column(DECIMAL(10, 2))
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="consultant_profile")
    skills = relationship("Skill", secondary="profile_skills", back_populates="profiles")


Index("idx_consultant_profiles_user_id", ConsultantProfile.user_id)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    company_name_masked = Column(String(160), nullable=False)
    industry = Column(String(160))
    location_city = Column(String(120))
    country = Column(String(120))
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="company")
    jobs = relationship("JobPost", back_populates="company")


Index("idx_companies_user_id", Company.user_id)


class JobPost(Base):
    __tablename__ = "job_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)

    title = Column(String(200), nullable=False)
    description = Column(Text)
    location_city = Column(String(120))
    country = Column(String(120))
    contract_type = Column(String(80))
    anonymize = Column(Boolean, nullable=False, server_default="1")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    company = relationship("Company", back_populates="jobs")
    skills = relationship("Skill", secondary="job_skills", back_populates="jobs")


Index("idx_job_posts_company_id", JobPost.company_id)


class Unlock(Base):
    __tablename__ = "unlocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    target_type = Column(Enum(UnlockTarget), nullable=False)
    target_id = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


Index("idx_unlocks_user_id", Unlock.user_id)


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), unique=True, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    profiles = relationship("ConsultantProfile", secondary="profile_skills", back_populates="skills")
    jobs = relationship("JobPost", secondary="job_skills", back_populates="skills")


class ProfileSkill(Base):
    __tablename__ = "profile_skills"

    profile_id = Column(Integer, ForeignKey("consultant_profiles.id", ondelete="CASCADE"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="RESTRICT"), primary_key=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


Index("idx_profile_skills_profile_id", ProfileSkill.profile_id)
Index("idx_profile_skills_skill_id", ProfileSkill.skill_id)


class JobSkill(Base):
    __tablename__ = "job_skills"

    job_id = Column(Integer, ForeignKey("job_posts.id", ondelete="CASCADE"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="RESTRICT"), primary_key=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


Index("idx_job_skills_job_id", JobSkill.job_id)
Index("idx_job_skills_skill_id", JobSkill.skill_id)

