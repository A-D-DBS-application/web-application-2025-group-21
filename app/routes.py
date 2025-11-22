from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime



from .supabase_client import get_session
from .models import User, ConsultantProfile, Company, JobPost, UserRole, Skill


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
        profile = None
        company = None

        if user:
            if user.role == UserRole.consultant:
                profile = db.query(ConsultantProfile).filter_by(user_id=user.id).first()
            elif user.role == UserRole.company:
                company = db.query(Company).filter_by(user_id=user.id).first()

        return render_template("dashboard.html", user=user, profile=profile, company=company)

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
@main.route("/consultants", methods=["GET"])
def consultants_list():
    with get_session() as db:
        profiles = db.query(ConsultantProfile).all()
        return render_template("consultant_list.html", profiles=profiles)

@main.route("/consultants/<int:profile_id>", methods=["GET"])
def consultant_detail(profile_id):
    with get_session() as db:
        profile = db.query(ConsultantProfile).filter(ConsultantProfile.id == profile_id).first()
        if not profile:
            flash("Consultant niet gevonden")
            return redirect(url_for("main.consultants_list"))
        return render_template("consultant_detail.html", profile=profile)

@main.route("/dashboard/skills", methods=["GET", "POST"])
def edit_consultant_skills():
    with get_session() as db:
        user = get_current_user(db)
        if not user or user.role != UserRole.consultant:
            flash("Alleen consultants kunnen skills aanpassen")
            return redirect(url_for("main.login"))

        profile = db.query(ConsultantProfile).filter_by(user_id=user.id).first()
        all_skills = db.query(Skill).order_by(Skill.name).all()

        if request.method == "POST":
            selected_skill_ids = [int(x) for x in request.form.getlist("skills")]


            selected_skills = []
            if selected_skill_ids:
                selected_skills = db.query(Skill).filter(Skill.id.in_(selected_skill_ids)).all()

            profile.skills = selected_skills
            db.commit()

            flash("Skills opgeslagen!")
            return redirect(url_for("main.dashboard"))

        return render_template(
            "consultant_skills_edit.html",
            profile=profile,
            skills=all_skills
        )


# ------------------ JOB POSTS ------------------
@main.route("/jobs", methods=["GET"])
def jobs_list():
    with get_session() as db:
        jobs = db.query(JobPost).all()
        return render_template("job_list.html", jobs=jobs)

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

