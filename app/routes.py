from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime

from .supabase_client import get_session
from .models import User, ConsultantProfile, Company, JobPost, UserRole


main = Blueprint("main", __name__)

# Helper om User uit session te halen
def get_current_user(db):
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()

# ------------------ HOME ------------------
#dit gebeurt vanzelf dus geen registreer nodig
@main.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# ------------------ LOGIN ------------------
@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        role = request.form.get("role", "consultant")

        if not username:
            flash("Username is verplicht")
            return redirect(url_for("main.login"))

        with get_session() as db:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                # Nieuwe user + profiel/bedrijf
                user = User(username=username, role=UserRole(role))
                db.add(user)
                db.flush()

                if role == "consultant":
                    prof = ConsultantProfile(
                        user_id=user.id,
                        display_name_masked=username,
                        created_at=datetime.utcnow()
                    )
                    db.add(prof)
                else:
                    comp = Company(
                        user_id=user.id,
                        company_name_masked=f"{username} BV",
                        created_at=datetime.utcnow()
                    )
                    db.add(comp)

                db.commit()

            session["user_id"] = user.id
        return redirect(url_for("main.dashboard"))

    return render_template("login.html")


# LOGOUT ----------------------
@main.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("main.index"))

# ------------------ DASHBOARD ------------------
#is je persoonlijk profiel
@main.route("/dashboard", methods=["GET"])
def dashboard():
    with get_session() as db:
        user = get_current_user(db)
        return render_template("dashboard.html", user=user)

# ------------------ CONSULTANTS ------------------
@main.route("/consultants", methods=["GET"])
def consultants_list():
    with get_session() as db:
        profiles = db.query(ConsultantProfile).all()
        return render_template("consultants_list.html", profiles=profiles)

@main.route("/consultants/<int:profile_id>", methods=["GET"])
def consultant_detail(profile_id):
    with get_session() as db:
        profile = db.query(ConsultantProfile).filter(ConsultantProfile.id == profile_id).first()
        if not profile:
            flash("Consultant niet gevonden")
            return redirect(url_for("main.consultants_list"))
        return render_template("consultant_detail.html", profile=profile)

# ------------------ JOB POSTS ------------------
@main.route("/jobs", methods=["GET"])
def jobs_list():
    with get_session() as db:
        jobs = db.query(JobPost).all()
        return render_template("jobs_list.html", jobs=jobs)

@main.route("/jobs/<int:job_id>", methods=["GET"])
def job_detail(job_id):
    with get_session() as db:
        job = db.query(JobPost).filter(JobPost.id == job_id).first()
        if not job:
            flash("Job niet gevonden")
            return redirect(url_for("main.jobs_list"))
        return render_template("job_detail.html", job=job)

@main.route("/jobs/new", methods=["GET", "POST"])
def job_new():
    with get_session() as db:
        user = get_current_user(db)
        if not user or user.role != UserRole.company:
            flash("Alleen companies mogen jobs toevoegen")
            return redirect(url_for("main.login"))

        company = db.query(Company).filter(Company.user_id == user.id).first()

        if request.method == "POST":
            title = request.form.get("title")
            description = request.form.get("description")
            city = request.form.get("location_city")
            country = request.form.get("country")
            contract_type = request.form.get("contract_type")

            if not title:
                flash("Titel is verplicht")
                return redirect(url_for("main.job_new"))

            job = JobPost(
                company_id=company.id,
                title=title,
                description=description,
                location_city=city,
                country=country,
                contract_type=contract_type,
            )
            db.add(job)
            db.commit()

            return redirect(url_for("main.job_detail", job_id=job.id))

        return render_template("job_new.html", company=company)
