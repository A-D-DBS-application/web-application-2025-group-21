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
        
        if not user:
            flash(_("Please log in to view your dashboard."))
            return redirect(url_for("main.login"))
        
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
            profile.contact_email = request.form.get("contact_email")
            profile.phone_number = request.form.get("phone_number")

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



# In app/routes.py (Vervang uw bestaande consultants_list functie)

@main.route("/consultants", methods=["GET"])
def consultants_list():
    from datetime import datetime, timezone
    with get_session() as db:
        user = get_current_user(db)

        # 1. Beveiligingscontrole (Moet een Company zijn)
        if not user or user.role != UserRole.company:
            flash(_("Only companies can browse consultant profiles."))
            # Dit is de reden voor de redirect: een consultant mag dit niet zien.
            return redirect(url_for("main.dashboard")) 

        # 2. Parameters Ophalen
        sort_by = request.args.get("sort_by", "relevance") 
        
        # Handmatige filters ophalen
        query_skills = request.args.getlist("skills")
        if query_skills:
            query_skills = list(map(int, query_skills))

        city = request.args.get("city")
        country = request.args.get("country")
        text_query = request.args.get("q", None)
        
        # 3. Company Behoeften Ophalen (voor Relevantieberekening)
        company_profile = db.query(Company).filter_by(user_id=user.id).first()
        
        required_job = None
        required_skill_ids = set()
        
        if company_profile:
            # Zoek de meest recente JobPost gelinkt aan dit Company ID
            required_job = db.query(JobPost).filter(
                JobPost.company_id == company_profile.id
            ).order_by(JobPost.created_at.desc()).first()
            
            if required_job:
                required_skill_ids = set(s.id for s in required_job.skills)
        
        if not required_job and sort_by == "relevance":
            flash(_("Maak eerst een Job Post aan om het IConsult relevantiefilter op basis van uw behoeften in te schakelen."))


        # 4. Basisquery en Filters Toepassen
        query = db.query(ConsultantProfile)
        
        # Filters gelden ALLEEN in de 'Handmatige Filter' modus
        if sort_by != "relevance":
            if city:
                query = query.filter(ConsultantProfile.location_city.ilike(f"%{city}%"))
            if country:
                query = query.filter(ConsultantProfile.country.ilike(f"%{country}%"))
            
            # Handmatige skill-filter (AND logica)
            if query_skills:
                for skill_id in query_skills:
                    query = query.filter(ConsultantProfile.skills.any(Skill.id == skill_id))

        consultants = query.all()

        # 5. Sortering & Relevantie Berekening
        if sort_by == "relevance":
            now = datetime.now(timezone.utc)
            
            def compute_score(profile):
                # Zorgt ervoor dat de score-berekening niet crasht als er geen job is.
                if not required_job:
                    return {'total': 0.0, 'skill': 0.0, 'text': 0.0, 'recency': 0.0, 'skill_factor': 0.0, 'text_factor': 0.0, 'recency_factor': 0.0}

                # A. Skill Similarity (Gewicht 0.5)
                consultant_skill_ids = set(s.id for s in profile.skills)
                matched = len(consultant_skill_ids & required_skill_ids)
                max_skills = max(len(required_skill_ids), 1)
                skill_similarity = (matched / max_skills) # 0 tot 1
                skill_weighted_score = skill_similarity * 0.5 
                
                # B. Text Match (Gewicht 0.3)
                text_match = 0
                if text_query:
                    # Gebruikt display_name_masked en andere velden voor tekstmatch
                    text_fields = " ".join(filter(None, [profile.display_name_masked, profile.short_bio, profile.specialization]))
                    if text_query.lower() in text_fields.lower():
                        text_match = 1
                text_weighted_score = text_match * 0.3
                
                # C. Recency of Profile Update (Gewicht 0.2)
                days_old = (now - profile.created_at).days
                recency_factor = max(0, 1 - days_old / 30) # 1 voor < 30 dagen, daalt naar 0
                recency_weighted_score = recency_factor * 0.2
                
                final_score = skill_weighted_score + text_weighted_score + recency_weighted_score
                
                return {
                    'total': final_score,
                    'skill': skill_weighted_score, 
                    'text': text_weighted_score, 
                    'recency': recency_weighted_score,
                    'skill_factor': skill_similarity,
                    'text_factor': text_match,
                    'recency_factor': recency_factor
                }

            scored_consultants = [] 
            for consultant in consultants:
                score_data = compute_score(consultant)
                consultant.score = score_data['total']
                consultant.score_breakdown = score_data
                scored_consultants.append(consultant)

            # Sorteer de consultants op de berekende score
            consultants = sorted(scored_consultants, key=lambda c: c.score, reverse=True)
            
        elif sort_by == "title":
            # Alfabetische sortering (op display_name)
            # FIX: Gebruikt 'display_name_masked' in plaats van 'display_name' om de AttributeError te voorkomen
            consultants = sorted(consultants, 
                                 key=lambda c: c.display_name_masked if c.display_name_masked else c.user.username)


        # 6. Template Renderen
        all_skills = db.query(Skill).order_by(Skill.name).all()

        return render_template(
            "consultant_list.html", 
            consultants=consultants, 
            skills=all_skills, 
            user=user,
            sort_by=sort_by,
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
# In app/routes.py (of waar je routes zijn gedefinieerd)

# In app/routes.py (of waar je routes zijn gedefinieerd)
# Zorg ervoor dat je alle benodigde imports hebt:
from datetime import datetime, timezone
# from flask import Blueprint, render_template, request, redirect, url_for, flash
# from .models import JobPost, Skill, ConsultantProfile, UserRole
# from .utils import get_session, get_current_user
# from flask_babel import _ # Indien je gebruik maakt van i18n

@main.route("/jobs", methods=["GET"])
def jobs_list():
    with get_session() as db:
        user = get_current_user(db)

        # 1. Beveiligingscontrole (US-JOB-01)
        # Zorg ervoor dat je UserRole.consultant correct importeert.
        if not user or user.role != UserRole.consultant:
            flash(_("Only consultants can browse job posts."))
            return redirect(url_for("main.dashboard")) 

        # 2. Parameters Ophalen
        # Standaard is 'relevance' (IConsult Filter)
        sort_by = request.args.get("sort_by", "relevance") 
        
        # Handmatige filters ophalen
        query_skills = request.args.getlist("skills")
        if query_skills:
            query_skills = list(map(int, query_skills))

        city = request.args.get("city")
        country = request.args.get("country")
        contract_type = request.args.get("contract_type")
        text_query = request.args.get("q", None)
        
        # 3. Consultant Skills Ophalen (voor Relevantieberekening)
        current_consultant_profile = db.query(ConsultantProfile).filter_by(user_id=user.id).first()
        consultant_skill_ids = set(s.id for s in current_consultant_profile.skills) if current_consultant_profile else set()

        # 4. Basisquery en Filters Toepassen
        query = db.query(JobPost)

        # LET OP: Filters worden ALLEEN toegepast in de 'Handmatige Filter' modus
        if sort_by != "relevance":
            if city:
                query = query.filter(JobPost.location_city.ilike(f"%{city}%"))
            if country:
                query = query.filter(JobPost.country.ilike(f"%{country}%"))
            if contract_type:
                query = query.filter(JobPost.contract_type.ilike(f"%{contract_type}%"))
            
            # Handmatige skill-filter
            if query_skills:
                # Belangrijk: De join zorgt ervoor dat alleen jobs met ALLE geselecteerde skills getoond worden
                # Als je OR wilt, moet je de query anders formuleren. Hier gaan we uit van een AND-achtige join:
                for skill_id in query_skills:
                    query = query.filter(JobPost.skills.any(Skill.id == skill_id))

        # Haal alle jobs op die voldoen aan de (eventuele) filters
        jobs = query.all()

        # 5. Sortering & Relevantie Berekening (US-SRCH-01)
        if sort_by == "relevance":
            # Dit is de complexe IConsult Filter
            now = datetime.now(timezone.utc)

            def compute_score(job):
                # A. Skill Similarity (Gewicht 0.5)
                job_required_skill_ids = set(s.id for s in job.skills)
                matched = len(job_required_skill_ids & consultant_skill_ids)
                max_skills = max(len(job_required_skill_ids), 1)
                skill_similarity = (matched / max_skills) # 0 tot 1
                skill_weighted_score = skill_similarity * 0.5 
                
                # B. Text Match (Gewicht 0.3)
                text_match = 0
                if text_query:
                    # Zoek naar de term in titel, omschrijving, stad of land
                    text_fields = " ".join(filter(None, [job.title, job.description, job.location_city, job.country]))
                    if text_query.lower() in text_fields.lower():
                        text_match = 1 # 0 of 1
                text_weighted_score = text_match * 0.3
                
                # C. Recency (Gewicht 0.2)
                # Max 0.2 score voor de meest recente jobs (daling over 30 dagen)
                days_old = (now - job.created_at).days
                recency_factor = max(0, 1 - days_old / 30) # 1 voor < 30 dagen, daalt naar 0
                recency_weighted_score = recency_factor * 0.2
                
                final_score = skill_weighted_score + text_weighted_score + recency_weighted_score
                
                return {
                    'total': final_score,
                    'skill': skill_weighted_score, 
                    'text': text_weighted_score,  
                    'recency': recency_weighted_score,
                    # De ongewogen factoren (voor weergave in de uitsplitsing)
                    'skill_factor': skill_similarity,
                    'text_factor': text_match,
                    'recency_factor': recency_factor
                }

            scored_jobs = [] 
            for job in jobs:
                score_data = compute_score(job)
                # Voeg de totale score en de uitsplitsing toe aan het job-object
                job.score = score_data['total']
                job.score_breakdown = score_data
                scored_jobs.append(job)

            # Sorteer de jobs op de berekende score
            jobs = sorted(scored_jobs, key=lambda j: j.score, reverse=True)
            
        elif sort_by == "title":
            # Alfabetische sortering (Handmatige Modus)
            jobs = sorted(jobs, key=lambda job: job.title)

        # 6. Template Renderen
        all_skills = db.query(Skill).order_by(Skill.name).all()

        return render_template(
            "job_list.html", 
            jobs=jobs, 
            skills=all_skills, 
            user=user,
            sort_by=sort_by
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
