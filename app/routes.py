from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime



from .supabase_client import get_session
from .models import User, ConsultantProfile, Company, JobPost, UserRole, Skill

import os
from werkzeug.utils import secure_filename

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "gif"}

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
                user = User(username=username, role=UserRole(role))
                db.add(user)
                db.flush()

                if role == "consultant":
                    prof = ConsultantProfile(
                        user_id=user.id,
                        display_name_masked=username,
                        availability=True,
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

            # SESSIE SETTEN
            session["user_id"] = user.id
            session["role"] = user.role.value

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
        profile = None
        company = None

        if user:
            if user.role == UserRole.consultant:
                profile = db.query(ConsultantProfile).filter_by(user_id=user.id).first()
            elif user.role == UserRole.company:
                company = db.query(Company).filter_by(user_id=user.id).first()

        return render_template(
    "dashboard.html",
    user=user,
    profile=profile,
    company=company,
    UserRole=UserRole
)


@main.route("/dashboard/company/industry", methods=["POST"])
def update_company_industry():
    with get_session() as db:
        user = get_current_user(db)
        if not user or user.role != UserRole.company:
            flash("Alleen companies kunnen industry aanpassen")
            return redirect(url_for("main.login"))

        company = db.query(Company).filter_by(user_id=user.id).first()
        if not company:
            flash("Company profiel niet gevonden")
            return redirect(url_for("main.dashboard"))

        industry = request.form.get("industry")

        if industry == "" or industry is None:
            company.industry = None
        else:
            company.industry = industry

        db.commit()
        flash("Industry opgeslagen!")
        return redirect(url_for("main.dashboard"))

# ------------------ CONSULTANTS ------------------
@main.route("/consultant/edit", methods=["GET", "POST"])
def edit_consultant_profile():
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.consultant:
            flash("Alleen consultants kunnen hun profiel aanpassen")
            return redirect(url_for("main.dashboard"))

        profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user.id
        ).first()

        if request.method == "POST":
            profile.display_name = request.form.get("display_name")
            profile.location_city = request.form.get("location_city")
            profile.country = request.form.get("country")
            profile.headline = request.form.get("headline")

            # ----------------------
            #   PROFIELFOTO
            # ----------------------
            file = request.files.get("profile_image")

            if file and file.filename != "":
                # Maak een map /static/uploads als die nog niet bestaat
                upload_folder = os.path.join(current_app.root_path, "static", "uploads")
                os.makedirs(upload_folder, exist_ok=True)

                # Unieke bestandsnaam
                filename = f"user_{user.id}.jpg"
                save_path = os.path.join(upload_folder, filename)

                file.save(save_path)

                # Pad opslaan in database (wat je gebruikt in je template)
                profile.profile_image = f"/static/uploads/{filename}"

            db.commit()

            flash("Profiel bijgewerkt")
            return redirect(url_for("main.dashboard"))

        return render_template("edit_consultant_profile.html", profile=profile)
    
@main.route("/consultants", methods=["GET"])
def consultants_list():
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.company:
            flash("Alleen companies kunnen consultants bekijken")
            return redirect(url_for("main.dashboard"))

        profiles = db.query(ConsultantProfile).all()
        return render_template("consultant_list.html", profiles=profiles)


# ------------------ JOB POSTS ------------------
@main.route("/jobs", methods=["GET"])
def jobs_list():
    with get_session() as db:
        user = get_current_user(db)

        # Consultants zien ALLE jobs
        if user and user.role == UserRole.consultant:
            jobs = db.query(JobPost).all()
            return render_template("job_list.html", jobs=jobs)

        # Companies zien alleen hun eigen jobs
        if user and user.role == UserRole.company:
            company = db.query(Company).filter(Company.user_id == user.id).first()
            jobs = db.query(JobPost).filter(JobPost.company_id == company.id).all()
            return render_template("job_list.html", jobs=jobs)

        flash("Log in om jobs te zien")
        return redirect(url_for("main.login"))


@main.route("/jobs/<int:job_id>", methods=["GET"])
def job_detail(job_id):
    with get_session() as db:
        user = get_current_user(db)

        job = db.query(JobPost).filter(JobPost.id == job_id).first()
        if not job:
            flash("Job niet gevonden")
            return redirect(url_for("main.jobs_list"))

        company = None
        if user and user.role == UserRole.company:
            company = db.query(Company).filter(Company.user_id == user.id).first()

        return render_template(
            "job_detail.html",
            job=job,
            user=user,
            company=company,
            UserRole=UserRole
        )



@main.route("/jobs/new", methods=["GET", "POST"])
def job_new():
    with get_session() as db:
        user = get_current_user(db)
        if not user or user.role != UserRole.company:
            flash("Alleen companies mogen jobs toevoegen")
            return redirect(url_for("main.login"))

        company = db.query(Company).filter(Company.user_id == user.id).first()
        all_skills = db.query(Skill).order_by(Skill.name).all()

        if request.method == "POST":
            title = request.form.get("title")
            description = request.form.get("description")
            city = request.form.get("location_city")
            country = request.form.get("country")
            contract_type = request.form.get("contract_type")

            selected_skill_ids = [int(x) for x in request.form.getlist("skills")]


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

            # koppel skills aan job (vult job_skills automatisch)
            if selected_skill_ids:
                selected_skills = db.query(Skill).filter(Skill.id.in_(selected_skill_ids)).all()
                job.skills = selected_skills

            db.add(job)
            db.commit()

            return redirect(url_for("main.job_detail", job_id=job.id))

        return render_template("job_new.html", company=company, skills=all_skills)

@main.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def job_edit(job_id):
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.company:
            flash("Alleen companies mogen jobs wijzigen")
            return redirect(url_for("main.login"))

        company = db.query(Company).filter_by(user_id=user.id).first()
        job = db.query(JobPost).filter_by(id=job_id, company_id=company.id).first()

        if not job:
            flash("Job niet gevonden of je bent niet de eigenaar")
            return redirect(url_for("main.jobs_list"))

        all_skills = db.query(Skill).order_by(Skill.name).all()

        if request.method == "POST":
            job.title = request.form.get("title")
            job.description = request.form.get("description")
            job.location_city = request.form.get("location_city")
            job.country = request.form.get("country")
            job.contract_type = request.form.get("contract_type")

            selected_skill_ids = [int(x) for x in request.form.getlist("skills")]
            job.skills = db.query(Skill).filter(Skill.id.in_(selected_skill_ids)).all()

            db.commit()
            flash("Job bijgewerkt!")
            return redirect(url_for("main.job_detail", job_id=job.id))

        return render_template("job_edit.html", job=job, skills=all_skills)

@main.route("/jobs/<int:job_id>/delete", methods=["POST"])
def job_delete(job_id):
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.company:
            flash("Alleen companies mogen jobs verwijderen")
            return redirect(url_for("main.login"))

        company = db.query(Company).filter_by(user_id=user.id).first()
        job = db.query(JobPost).filter_by(id=job_id, company_id=company.id).first()

        if not job:
            flash("Job niet gevonden of je bent niet de eigenaar")
            return redirect(url_for("main.jobs_list"))

        db.delete(job)
        db.commit()
        flash("Job verwijderd")
        return redirect(url_for("main.jobs_list"))
