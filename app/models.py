from sqlalchemy import (
    Column, Integer, String, Text, DECIMAL, Boolean,
    ForeignKey, Enum, TIMESTAMP, Index, func, Float
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


# ---- ENUM TYPES ----
class UserRole(enum.Enum):
    consultant = "consultant"
    company = "company"
    admin = "admin"


class IndustryEnum(enum.Enum):
    Technology = "Technology"
    Finance = "Finance"
    Healthcare = "Healthcare"
    Logistics = "Logistics"
    Manufacturing = "Manufacturing"
    Consulting = "Consulting"


class UnlockTarget(enum.Enum):
    consultant = "consultant"
    job = "job"


class CollaborationStatus(enum.Enum):
    active = "active"
    ended = "ended"


# ---- TABLES ----
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    consultant_profile = relationship(
        "ConsultantProfile",
        back_populates="user",
        uselist=False
    )
    company = relationship(
        "Company",
        back_populates="user",
        uselist=False
    )

    # ✅ NEW: user.unlocks
    unlocks = relationship(
        "Unlock",
        back_populates="user"
    )


class ConsultantProfile(Base):
    __tablename__ = "consultant_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    display_name_masked = Column(String(120), nullable=False)
    headline = Column(String(160))
    location_city = Column(String(120))
    country = Column(String(120))
    availability = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    years_experience = Column(Integer, nullable=True)

    profile_image = Column(String(300), nullable=True)
    cv_document = Column(String(300), nullable=True)
    contact_email = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)

    # link met current company (kan NULL zijn)
    current_company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True
    )

    # 🌍 coördinaten voor locatie-matching
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # relaties
    user = relationship("User", back_populates="consultant_profile")
    skills = relationship(
        "Skill",
        secondary="profile_skills",
        back_populates="profiles"
    )
    collaborations = relationship(
        "Collaboration",
        back_populates="consultant"
    )

    # ✅ NEW: profile.current_company + company.current_consultants
    current_company = relationship(
        "Company",
        foreign_keys=[current_company_id],
        backref="current_consultants"
    )

    @property
    def initials(self):
        """Genereert initialen van de display_name_masked."""
        if self.display_name_masked:
            names = self.display_name_masked.split()
            initials = "".join(name[0].upper() for name in names if name)
            return initials if initials else "C"
        return "C"


Index("idx_consultant_profiles_user_id", ConsultantProfile.user_id)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    company_name_masked = Column(String(160), nullable=False)
    industries = Column(Enum(IndustryEnum), nullable=True)
    location_city = Column(String(120))
    country = Column(String(120))
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    contact_email = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)

    # relaties
    user = relationship("User", back_populates="company")
    jobs = relationship("JobPost", back_populates="company")
    collaborations = relationship("Collaboration", back_populates="company")

    @property
    def initials(self):
        if self.company_name_masked:
            names = self.company_name_masked.split()
            initials = "".join(name[0].upper() for name in names if name)
            return initials if initials else "B"
        return "B"


Index("idx_companies_user_id", Company.user_id)


class JobPost(Base):
    __tablename__ = "job_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False
    )

    title = Column(String(200), nullable=False)
    description = Column(Text)
    location_city = Column(String(120))
    country = Column(String(120))
    contract_type = Column(String(80))
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    # ✅ actieve/inactieve status
    is_active = Column(Boolean, nullable=False, server_default="1")
    hired_consultant_id = Column(
        Integer,
        ForeignKey("consultant_profiles.id", ondelete="SET NULL"),
        nullable=True
    )

    # 🌍 coördinaten van de job-locatie (voor distance filter)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # relaties
    company = relationship("Company", back_populates="jobs")
    skills = relationship(
        "Skill",
        secondary="job_skills",
        back_populates="jobs"
    )

    # ✅ UPDATED: backref zodat consultant.hired_jobs bestaat
    hired_consultant = relationship(
        "ConsultantProfile",
        foreign_keys=[hired_consultant_id],
        backref="hired_jobs"
    )

    collaborations = relationship("Collaboration", back_populates="job_post")


Index("idx_job_posts_company_id", JobPost.company_id)


class Unlock(Base):
    __tablename__ = "unlocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    target_type = Column(Enum(UnlockTarget), nullable=False)
    target_id = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    # ✅ NEW: unlock.user + user.unlocks
    user = relationship("User", back_populates="unlocks")


Index("idx_unlocks_user_id", Unlock.user_id)


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), unique=True, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    profiles = relationship(
        "ConsultantProfile",
        secondary="profile_skills",
        back_populates="skills"
    )
    jobs = relationship(
        "JobPost",
        secondary="job_skills",
        back_populates="skills"
    )


class ProfileSkill(Base):
    __tablename__ = "profile_skills"

    profile_id = Column(
        Integer,
        ForeignKey("consultant_profiles.id", ondelete="CASCADE"),
        primary_key=True
    )
    skill_id = Column(
        Integer,
        ForeignKey("skills.id", ondelete="RESTRICT"),
        primary_key=True
    )
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


Index("idx_profile_skills_profile_id", ProfileSkill.profile_id)
Index("idx_profile_skills_skill_id", ProfileSkill.skill_id)


class JobSkill(Base):
    __tablename__ = "job_skills"

    job_id = Column(
        Integer,
        ForeignKey("job_posts.id", ondelete="CASCADE"),
        primary_key=True
    )
    skill_id = Column(
        Integer,
        ForeignKey("skills.id", ondelete="RESTRICT"),
        primary_key=True
    )
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


Index("idx_job_skills_job_id", JobSkill.job_id)
Index("idx_job_skills_skill_id", JobSkill.skill_id)


class Collaboration(Base):
    __tablename__ = "collaborations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False
    )
    consultant_id = Column(
        Integer,
        ForeignKey("consultant_profiles.id", ondelete="CASCADE"),
        nullable=False
    )
    job_post_id = Column(
        Integer,
        ForeignKey("job_posts.id", ondelete="SET NULL"),
        nullable=True
    )

    status = Column(
        Enum(CollaborationStatus, name="collaboration_status"),
        nullable=False,
        server_default="active"
    )
    started_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    ended_at = Column(TIMESTAMP, nullable=True)

    company = relationship("Company", back_populates="collaborations")
    consultant = relationship("ConsultantProfile", back_populates="collaborations")
    job_post = relationship("JobPost", back_populates="collaborations")
