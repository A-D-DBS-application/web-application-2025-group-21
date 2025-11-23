from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from flask import current_app



from flask_babel import gettext as _


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

#taalwissel-route:
@main.route("/set_language", methods=["POST"])
def set_language():
    lang = request.form.get("language", "en")
    if lang not in ["en", "nl", "fr"]:
        lang = "en"
    session["language"] = lang
    return redirect(request.referrer or url_for("main.index"))


# ------------------ LOGIN ------------------
@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        role = request.form.get("role", "consultant")

        if not username:
            flash(_("Username is required"))
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
        
        # NIEUWE CONTROLE: Als er geen gebruiker is, stuur naar login.
        if not user:
            flash(_("Please log in to view your dashboard."))
            return redirect(url_for("main.login"))
        # EINDE NIEUWE CONTROLE
        
        profile = None
        company = None

        # Dit blok wordt nu alleen uitgevoerd als 'user' NIET None is.
        # De 'if user:' die hier eerder stond, is nu overbodig geworden 
        # door de 'if not user:' check erboven.
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

# ------------------ CONSULTANTS ------------------
@main.route("/consultant/edit", methods=["GET", "POST"])
def edit_consultant_profile():
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.consultant:
            flash(_("Only consultants can edit their profile"))
            return redirect(url_for("main.dashboard"))

        profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user.id
        ).first()

        if request.method == "POST":
            profile.display_name = request.form.get("display_name")
            profile.location_city = request.form.get("location_city")
            profile.country = request.form.get("country")
            profile.headline = request.form.get("headline")
            # --- NIEUW: Contactvelden opslaan ---
            profile.contact_email = request.form.get("contact_email")
            profile.phone_number = request.form.get("phone_number")
            # ------------------------------------

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

            flash("Profile updated")
            return redirect(url_for("main.dashboard"))

        return render_template("edit_consultant_profile.html", profile=profile)
@main.route("/consultant/skills/edit", methods=["GET", "POST"])
def edit_consultant_skills():
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.consultant:
            flash(_("Only consultants can update their skills"))
            return redirect(url_for("main.dashboard"))

        profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user.id
        ).first()

        if request.method == "POST":
            selected_ids = list(map(int, request.form.getlist("skills")))
            profile.skills = db.query(Skill).filter(Skill.id.in_(selected_ids)).all()
            db.commit()

            flash(_("Profile updated"))
            return redirect(url_for("main.dashboard"))

        all_skills = db.query(Skill).all()
        return render_template(
            "edit_consultant_skills.html",
            profile=profile,
            skills=all_skills
        )

@main.route("/consultant/<int:profile_id>")
def consultant_detail(profile_id):
    with get_session() as db:
        profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.id == profile_id
        ).first()

        if not profile:
            flash(_("Consultant not found"))
            return redirect(url_for("main.consultants_list"))

        return render_template("consultant_detail.html", profile=profile)



@main.route("/consultants", methods=["GET"])
def consultants_list():
    from datetime import datetime, timezone
    with get_session() as db:
        user = get_current_user(db)

        # ---------------------------------
        # NIEUWE SECURITY CHECK
        # ---------------------------------
        if not user or user.role != UserRole.company:
            flash(_("Only companies can view consultants."))
            return redirect(url_for("main.dashboard"))
        # ---------------------------------

        # --- Filters ophalen uit query params ---
        
        # --- AANGEPASTE SKILL FILTER ---
        # Gebruik .getlist() om alle 'skills' parameters te krijgen (bv: ['1', '3'])
        query_skills = request.args.getlist("skills")
        if query_skills:
            # Converteer de lijst van strings naar een lijst van integers
            query_skills = list(map(int, query_skills))
        # --- EINDE AANPASSING ---
            
        city = request.args.get("city")
        country = request.args.get("country")
        text_query = request.args.get("q", None)

        # --- Basisquery ---
        query = db.query(ConsultantProfile)

        # Filter op locatie
        if city:
            query = query.filter(ConsultantProfile.location_city.ilike(f"%{city}%"))
        if country:
            query = query.filter(ConsultantProfile.country.ilike(f"%{country}%"))

        # Filter op skills
        if query_skills:
            # Deze join-logica was al correct
            query = query.join(ConsultantProfile.skills).filter(Skill.id.in_(query_skills))

        profiles = query.all()

        # --- Bereken relevance score ---
        now = datetime.now(timezone.utc)

        def compute_score(profile):
            score = 0.0
            # skills
            if query_skills:
                matched = len(set(s.id for s in profile.skills) & set(query_skills))
                score += (matched / max(len(query_skills), 1)) * 0.5
            # text match
            if text_query:
                text_fields = " ".join(filter(None, [profile.display_name_masked, profile.headline, profile.location_city, profile.country]))
                if text_query.lower() in text_fields.lower():
                    score += 0.3
            # recency
            days_old = (now - profile.created_at).days
            score += max(0, 0.2 - days_old * 0.01)
            return score

        profiles = sorted(profiles, key=compute_score, reverse=True)
        
        # Zorg dat je all_skills meegeeft aan de template (net als bij jobs)
        all_skills = db.query(Skill).order_by(Skill.name).all()

        return render_template(
            "consultant_list.html", 
            profiles=profiles, 
            skills=all_skills # VOEG DEZE TOE
        )

# ------------------ COMPANY ------------------
@main.route("/company/edit", methods=["GET", "POST"])
def edit_company_profile():
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.company:
            flash(_("Only companies can edit their profile"))
            return redirect(url_for("main.dashboard"))

        company = db.query(Company).filter(
            Company.user_id == user.id
        ).first()

        if request.method == "POST":
            company.company_name_masked = request.form.get("company_name")
            company.location_city = request.form.get("location_city")
            company.country = request.form.get("country")
            # NIEUW: Contactvelden opslaan
            company.contact_email = request.form.get("contact_email")
            company.phone_number = request.form.get("phone_number")

            db.commit()

            flash(_("Company profile updated"))
            return redirect(url_for("main.dashboard"))

        return render_template("edit_company_profile.html", company=company)


# ------------------ JOB POSTS ------------------
@main.route("/jobs", methods=["GET"])
def jobs_list():
    from datetime import datetime, timezone
    with get_session() as db:
        user = get_current_user(db)

        # ---------------------------------
        # NIEUWE SECURITY CHECK
        # ---------------------------------
        if not user or user.role != UserRole.consultant:
            flash(_("Only consultants can view job posts."))
            return redirect(url_for("main.dashboard"))
        # ---------------------------------

        # --- Filters ophalen uit query params ---

        # --- AANGEPASTE SKILL FILTER ---
        # Gebruik .getlist() om alle 'skills' parameters te krijgen (bv: ['1', '3'])
        query_skills = request.args.getlist("skills")
        if query_skills:
            # Converteer de lijst van strings naar een lijst van integers
            query_skills = list(map(int, query_skills))
        # --- EINDE AANPASSING ---

        city = request.args.get("city")
        country = request.args.get("country")
        contract_type = request.args.get("contract_type")
        text_query = request.args.get("q", None)

        # Basisquery (haalt ALLE jobs op)
        query = db.query(JobPost)

        # OUDE CODEBLOK VOOR COMPANIES IS VERWIJDERD
        # (De check hierboven vangt dit al af)

        # Filters (worden nu op alle jobs toegepast)
        if city:
            query = query.filter(JobPost.location_city.ilike(f"%{city}%"))
        if country:
            query = query.filter(JobPost.country.ilike(f"%{country}%"))
        if contract_type:
            query = query.filter(JobPost.contract_type.ilike(f"%{contract_type}%"))
        if query_skills:
            # Deze join-logica was al correct
            query = query.join(JobPost.skills).filter(Skill.id.in_(query_skills))

        jobs = query.all()

        # --- Relevance scoring ---
        now = datetime.now(timezone.utc)

        def compute_score(job):
            score = 0.0
            # skills
            if query_skills:
                matched = len(set(s.id for s in job.skills) & set(query_skills))
                score += (matched / max(len(query_skills), 1)) * 0.5
            # text match
            if text_query:
                text_fields = " ".join(filter(None, [job.title, job.description, job.location_city, job.country]))
                if text_query.lower() in text_fields.lower():
                    score += 0.3
            # recency
            days_old = (now - job.created_at).days
            score += max(0, 0.2 - days_old * 0.01)
            return score

        jobs = sorted(jobs, key=compute_score, reverse=True)

        # --- Hier haal je alle skills op voor het filterformulier ---
        all_skills = db.query(Skill).order_by(Skill.name).all()

        return render_template(
            "job_list.html", 
            jobs=jobs, 
            skills=all_skills, 
            user=user # Geef user ook mee
        )




@main.route("/jobs/<int:job_id>", methods=["GET"])
def job_detail(job_id):
    with get_session() as db:
        user = get_current_user(db)

        job = db.query(JobPost).filter(JobPost.id == job_id).first()
        if not job:
            flash(_("Job not found"))
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
            flash(_("Only companies can create job posts"))
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
                flash(_("Title is required"))
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
            flash(_("Only companies can edit job posts"))
            return redirect(url_for("main.login"))

        company = db.query(Company).filter_by(user_id=user.id).first()
        job = db.query(JobPost).filter_by(id=job_id, company_id=company.id).first()

        if not job:
            flash(_("Job not found or you are not the owner"))
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
            flash(_("Job updated!"))
            return redirect(url_for("main.job_detail", job_id=job.id))

        return render_template("job_edit.html", job=job, skills=all_skills)

@main.route("/jobs/<int:job_id>/delete", methods=["POST"])
def job_delete(job_id):
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.company:
            flash(_("Only companies can delete job posts"))
            return redirect(url_for("main.login"))

        company = db.query(Company).filter_by(user_id=user.id).first()
        job = db.query(JobPost).filter_by(id=job_id, company_id=company.id).first()

        if not job:
            flash(_("Job not found or you are not the owner"))
            return redirect(url_for("main.jobs_list"))

        db.delete(job)
        db.commit()
        flash(_("Job deleted"))
        return redirect(url_for("main.jobs_list"))
