from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from flask import current_app
from functools import wraps
from sqlalchemy import or_


from flask_babel import gettext as _

from .supabase_client import get_session
from .models import User, ConsultantProfile, Company, JobPost, UserRole, Skill, Unlock, UnlockTarget

import os
from werkzeug.utils import secure_filename
from sqlalchemy import func  # <-- NIEUW: voor count() over Unlocks


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "gif"}

main = Blueprint("main", __name__)

# Helper om User uit session te halen
def get_current_user(db):
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()

def login_required(f): # <--- ESSENTIEEL: Vangt de 'login_required not defined' fout op
    """Controleert of de gebruiker is ingelogd via de sessie."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            flash(_("Gelieve in te loggen om deze actie uit te voeren."))
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)
    return decorated_function

# helper voor unlock
def is_unlocked(db, unlocking_user_id, target_type, target_id):
    """Controleert of een gebruiker al de contactgegevens van een target heeft unlocked."""
    return db.query(Unlock).filter(
        Unlock.user_id == unlocking_user_id,
        Unlock.target_type == target_type,
        Unlock.target_id == target_id
    ).first() is not None


# ------------------ HOME ------------------
# NIEUW: Toont alle Job Posts die door het ingelogde bedrijf zijn aangemaakt
@main.route("/company/jobs", methods=["GET"])
def company_jobs_list():
    with get_session() as db:
        user = get_current_user(db)

        # 1. Beveiligingscontrole
        if not user or user.role != UserRole.company:
            flash(_("Only companies can view their own job posts."))
            return redirect(url_for("main.dashboard")) 
        
        # Zoek het Company profiel
        company = db.query(Company).filter_by(user_id=user.id).first()
        
        if not company:
            flash(_("Company profile not found."))
            return redirect(url_for("main.dashboard"))

        # Simpele zoekterm (optioneel)
        q = request.args.get("q", "").strip()

        query = db.query(JobPost).filter(JobPost.company_id == company.id)

        if q:
            query = query.filter(
                or_(
                    JobPost.title.ilike(f"%{q}%"),
                    JobPost.description.ilike(f"%{q}%")
                )
            )

        # Sorteer op meest recent aangemaakt
        jobs = query.order_by(JobPost.created_at.desc()).all()
        
        # skills wordt niet echt gebruikt hier, maar template verwacht 'skills'
        all_skills = []

        return render_template(
            "job_list.html", 
            jobs=jobs, 
            user=user,
            skills=all_skills,

            # Belangrijk: sort_by is GEEN 'relevance' hier
            sort_by='none',

            # Titel speciaal voor deze pagina
            page_title=_("Mijn Vacatures"),

            # Nieuwe flags voor template:
            show_mode_selector=False,  # geen IConsult/Handmatige modus-balk
            simple_search=True         # toon enkel simpele zoekbalk
        )


#dit gebeurt vanzelf dus geen registreer nodig
@main.route("/", methods=["GET"])
def index():
    return render_template("index.html")



# ------------------ LOGIN ------------------
# In app/routes.py (Vervang de bestaande login functie)
# In app/routes.py (Vervang de bestaande login functie)
@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        role_str = request.form.get("role", "consultant")
        requested_role = UserRole(role_str)
        
        if not username:
            flash(_("Username is required."))
            return redirect(url_for("main.login"))

        with get_session() as db:
            user = db.query(User).filter(User.username == username).first()
            
            if user:
                # --- LOGICA VOOR BESTAANDE GEBRUIKER ---
                # Check of de gevraagde rol overeenkomt met de bestaande rol
                if user.role == requested_role:
                    # ROL KOMT OVEREEN: Inloggen
                    session["user_id"] = user.id
                    session["role"] = user.role.value
                    flash(_(f"Welcome back, {username}."))
                    return redirect(url_for("main.dashboard"))
                else:
                    # ROL CONFLICT: Geen login, geef een generieke foutmelding
                    # Dit voorkomt het onthullen van de bestaande rol (veiligheid)
                    flash(_("This username already exists and is linked to another role. Please choose a different username or log in with the correct role."))
                    return redirect(url_for("main.login"))
                
            else:
                # --- LOGICA VOOR NIEUWE GEBRUIKER ---
                user = User(username=username, role=requested_role)
                db.add(user)
                db.flush()

                if requested_role == UserRole.consultant:
                    prof = ConsultantProfile(
                        user_id=user.id,
                        display_name_masked=username,
                        availability=True,
                        created_at=datetime.utcnow()
                    )
                    db.add(prof)
                else: # UserRole.company
                    comp = Company(
                        user_id=user.id,
                        company_name_masked=f"{username} BV",
                        created_at=datetime.utcnow()
                    )
                    db.add(comp)

                db.commit()
                flash(_(f"Welcome, {username}. You are registered and logged in as {role_str}."))

                # SESSIE SETTEN voor de nieuwe gebruiker
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
            
            # ----------------------
            #   CV / DOCUMENT
            # ----------------------
            cv_file = request.files.get("cv_document")

            if cv_file and cv_file.filename != "":
                upload_folder = os.path.join(current_app.root_path, "static", "uploads")
                os.makedirs(upload_folder, exist_ok=True)

                # extensie behouden
                _, ext = os.path.splitext(cv_file.filename)
                ext = ext.lower()

                # Enkel toegelaten types
                allowed_exts = {".pdf", ".doc", ".docx"}
                if ext not in allowed_exts:
                    flash("Invalid file type. Only upload pdf/doc/docx.")
                    return redirect(url_for("main.edit_consultant_profile"))

                # Unieke bestandsnaam voor CV
                cv_filename = f"cv_user_{user.id}{ext}"
                cv_save_path = os.path.join(upload_folder, cv_filename)

                cv_file.save(cv_save_path)

                # Pad opslaan in database
                profile.cv_document = f"/static/uploads/{cv_filename}"
            


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
# in app/routes.py (Vervang de bestaande consultant_detail functie)

@main.route("/consultant/<int:profile_id>")
def consultant_detail(profile_id):
    with get_session() as db:
        profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.id == profile_id
        ).first()

        if not profile:
            flash(_("Consultant not found"))
            return redirect(url_for("main.consultants_list"))

        user = get_current_user(db)
        is_owner = user and user.id == profile.user_id
        is_unlocked_status = False

        if user:
            is_unlocked_status = is_unlocked(db, user.id, UnlockTarget.consultant, profile_id)

        return render_template(
            "consultant_detail.html", 
            profile=profile,
            user=user,               # <-- FIX: user doorgeven
            UserRole=UserRole,       # <-- FIX: UserRole doorgeven
            is_owner=is_owner,
            is_unlocked=is_unlocked_status
        )


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
            flash(_("First, create a Job Post to enable the IConsult relevance filter based on your needs."))


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

            # 🔹 Haal in één keer op hoe vaak elke consultant is ge-unlocked
            consultant_ids = [c.id for c in consultants]
            unlock_counts = {}
            if consultant_ids:
                unlock_rows = (
                    db.query(Unlock.target_id, func.count(Unlock.id))
                    .filter(
                        Unlock.target_type == UnlockTarget.consultant,
                        Unlock.target_id.in_(consultant_ids),
                    )
                    .group_by(Unlock.target_id)
                    .all()
                )
                unlock_counts = {target_id: count for target_id, count in unlock_rows}
            
            def compute_score(profile):
                # Zorgt ervoor dat de score-berekening niet crasht als er geen job is.
                if not required_job:
                    return {
                        'total': 0.0,
                        'skill': 0.0,
                        'text': 0.0,
                        'recency': 0.0,
                        'skill_factor': 0.0,
                        'text_factor': 0.0,
                        'recency_factor': 0.0,
                        'popularity': 0.0,
                        'popularity_factor': 0.0,
                        'unlock_count': 0,
                    }

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

                # D. Populariteit op basis van unlocks (Gewicht 0.15)
                unlock_count = unlock_counts.get(profile.id, 0)
                max_unlocks = 50   # vanaf 50 unlocks is popularity_factor = 1
                popularity_factor = min(unlock_count / max_unlocks, 1.0)
                popularity_weighted_score = popularity_factor * 0.15
                
                final_score = (
                    skill_weighted_score
                    + text_weighted_score
                    + recency_weighted_score
                    + popularity_weighted_score
                )
                
                return {
                    'total': final_score,
                    'skill': skill_weighted_score, 
                    'text': text_weighted_score, 
                    'recency': recency_weighted_score,
                    'skill_factor': skill_similarity,
                    'text_factor': text_match,
                    'recency_factor': recency_factor,
                    'popularity': popularity_weighted_score,
                    'popularity_factor': popularity_factor,
                    'unlock_count': unlock_count,
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

# ------------------ UNLOCK LOGICA ------------------

# Unlock Consultant (Bedrijf -> Consultant)
@main.route("/unlock/consultant/<int:profile_id>")
@login_required
def unlock_consultant(profile_id):
    with get_session() as db:
        user = get_current_user(db)
        
        if user.role != UserRole.company:
            flash(_("Only companies can reveal consultants contact details."), "error")
            return redirect(url_for("main.consultant_detail", profile_id=profile_id))
        # Gebruik filter_by voor betere compatibiliteit met Pylance
        consultant_profile = db.query(ConsultantProfile).filter_by(id=profile_id).first()
        if not consultant_profile:
            flash(_("Consultant profile not found."), "error")
            return redirect(url_for("main.dashboard"))

        if is_unlocked(db, user.id, UnlockTarget.consultant, profile_id):
            flash(_("Contact details have already been released."), "info")
            return redirect(url_for("main.consultant_detail", profile_id=profile_id))

        new_unlock = Unlock(
            user_id=user.id,
            target_type=UnlockTarget.consultant,
            target_id=profile_id
        )
        db.add(new_unlock)
        db.commit()
        
        flash(_("Contact details successfully released!"), "success")
        return redirect(url_for("main.consultant_detail", profile_id=profile_id))

# Unlock Job/Company (Consultant -> Company)
@main.route("/unlock/job/<int:job_id>")
@login_required
def unlock_job(job_id):
    with get_session() as db:
        user = get_current_user(db)
        
        if user.role != UserRole.consultant:
            flash(_("Only consultants can reveal companies' contact details."), "error")
            return redirect(url_for("main.job_detail", job_id=job_id))
        job_post = db.query(JobPost).filter_by(id=job_id).first()
        if not job_post:
            flash(_("Job post not found."), "error")
            return redirect(url_for("main.dashboard"))

        if is_unlocked(db, user.id, UnlockTarget.job, job_id):
            flash(_("Contact details have already been released."), "info")
            return redirect(url_for("main.job_detail", job_id=job_id))

        new_unlock = Unlock(
            user_id=user.id,
            target_type=UnlockTarget.job,
            target_id=job_id
        )
        db.add(new_unlock)
        db.commit()

        flash(_("Contact details successfully released!"), "success")
        return redirect(url_for("main.job_detail", job_id=job_id))

# ------------------ JOB POSTS ------------------
# In app/routes.py (of waar je routes zijn gedefinieerd)

# In app/routes.py (of waar je routes zijn gedefinieerd)
# Zorg ervoor dat je alle benodigde imports hebt:
from datetime import datetime, timezone
# from flask import Blueprint, render_template, request, redirect, url_for, flash
# from .models import JobPost, Skill, ConsultantProfile, UserRole
# from .utils import get_session, get_current_user
# from flask_babel import _ # Indien je gebruik maakt van i18n

# In app/routes.py, de functie jobs_list
@main.route("/jobs", methods=["GET"])
def jobs_list():
    from datetime import datetime, timezone
    from sqlalchemy import func  # zorg dat dit bovenaan je file geïmporteerd is

    with get_session() as db:
        user = get_current_user(db)

        # 1. Beveiligingscontrole (Moet een Consultant zijn)
        if not user or user.role != UserRole.consultant:
            flash(_("Only consultants can browse job posts."))
            return redirect(url_for("main.dashboard"))

        # 2. Parameters Ophalen
        sort_by = request.args.get("sort_by", "relevance")

        query_skills = request.args.getlist("skills")
        if query_skills:
            query_skills = list(map(int, query_skills))

        city = request.args.get("city")
        country = request.args.get("country")
        contract_type = request.args.get("contract_type")
        text_query = request.args.get("q", None)

        # 3. Consultant profiel & skills ophalen (voor relevantie-berekening)
        consultant_profile = (
            db.query(ConsultantProfile)
            .filter(ConsultantProfile.user_id == user.id)
            .first()
        )
        consultant_skill_ids = set()
        if consultant_profile:
            consultant_skill_ids = {s.id for s in consultant_profile.skills}

        # 4. Basisquery en filters (alleen actief bij niet-relevance)
        query = db.query(JobPost)

        if sort_by != "relevance":
            if city:
                query = query.filter(JobPost.location_city.ilike(f"%{city}%"))
            if country:
                query = query.filter(JobPost.country.ilike(f"%{country}%"))
            if contract_type:
                query = query.filter(JobPost.contract_type == contract_type)

            if query_skills:
                # AND–logica: job moet alle gekozen skills hebben
                for skill_id in query_skills:
                    query = query.filter(JobPost.skills.any(Skill.id == skill_id))

        jobs = query.all()

        # 5. Sortering & Relevantie Berekening (zoals bij consultants, met unlocks)
        if sort_by == "relevance":
            now = datetime.now(timezone.utc)

            # 🔹 Haal in één keer op hoe vaak elke job is ge-unlocked
            job_ids = [j.id for j in jobs]
            unlock_counts = {}
            if job_ids:
                unlock_rows = (
                    db.query(Unlock.target_id, func.count(Unlock.id))
                    .filter(
                        Unlock.target_type == UnlockTarget.job,
                        Unlock.target_id.in_(job_ids),
                    )
                    .group_by(Unlock.target_id)
                    .all()
                )
                unlock_counts = {target_id: count for target_id, count in unlock_rows}

            MAX_UNLOCKS = 50  # vanaf 50 unlocks is populariteit max

            def compute_score(job):
                # fallback als consultant geen profiel heeft
                if not consultant_profile:
                    return {
                        "total": 0.0,
                        "skill": 0.0,
                        "text": 0.0,
                        "recency": 0.0,
                        "popularity": 0.0,
                        "skill_factor": 0.0,
                        "text_factor": 0.0,
                        "recency_factor": 0.0,
                        "popularity_factor": 0.0,
                        "unlock_count": 0,
                    }

                # A. Skill Similarity (Gewicht 0.5)
                job_skill_ids = {s.id for s in job.skills}
                matched = len(job_skill_ids & consultant_skill_ids)
                max_skills = max(len(consultant_skill_ids), 1)
                skill_similarity = matched / max_skills  # 0..1
                skill_weighted_score = skill_similarity * 0.5

                # B. Text Match (Gewicht 0.3)
                text_match = 0
                if text_query:
                    text_fields = " ".join(
                        filter(
                            None,
                            [
                                job.title,
                                job.description,
                                job.location_city,
                                job.country,
                                job.contract_type,
                            ],
                        )
                    )
                    if text_query.lower() in text_fields.lower():
                        text_match = 1
                text_weighted_score = text_match * 0.3

                # C. Recency (Gewicht 0.2)
                days_old = (now - job.created_at).days
                recency_factor = max(0, 1 - days_old / 30)  # 0..1
                recency_weighted_score = recency_factor * 0.2

                # D. Populariteit (Gewicht 0.15) – op basis van unlocks
                unlock_count = unlock_counts.get(job.id, 0)
                popularity_factor = min(unlock_count / MAX_UNLOCKS, 1.0)
                popularity_weighted_score = popularity_factor * 0.15

                total = (
                    skill_weighted_score
                    + text_weighted_score
                    + recency_weighted_score
                    + popularity_weighted_score
                )

                return {
                    "total": total,
                    "skill": skill_weighted_score,
                    "text": text_weighted_score,
                    "recency": recency_weighted_score,
                    "popularity": popularity_weighted_score,
                    "skill_factor": skill_similarity,
                    "text_factor": text_match,
                    "recency_factor": recency_factor,
                    "popularity_factor": popularity_factor,
                    "unlock_count": unlock_count,
                }

            scored_jobs = []
            for job in jobs:
                score_data = compute_score(job)
                job.score = score_data["total"]
                job.score_breakdown = score_data
                scored_jobs.append(job)

            # Sorteer jobs op score (hoog naar laag)
            jobs = sorted(scored_jobs, key=lambda j: j.score, reverse=True)

        elif sort_by == "title":
            jobs = sorted(jobs, key=lambda j: j.title or "")

        # 6. Template Renderen
        all_skills = db.query(Skill).order_by(Skill.name).all()

        possible_contract_types = [
            ("Freelance", _("Freelance")),
            ("Full-time", _("Full-time")),
            ("Part-time", _("Part-time")),
            ("Project-based", _("Project-based")),
        ]

        return render_template(
            "job_list.html",
            jobs=jobs,
            skills=all_skills,
            user=user,
            sort_by=sort_by,
            possible_contract_types=possible_contract_types,
            current_contract_type=contract_type,
        )




@main.route("/jobs/<int:job_id>", methods=["GET"])
def job_detail(job_id):
    with get_session() as db:
        user = get_current_user(db)

        job = db.query(JobPost).filter(JobPost.id == job_id).first()
        if not job:
            flash(_("Job not found"))
            return redirect(url_for("main.jobs_list"))
        
        company_posting = job.company # Haalt het Company object op

        is_owner = user and company_posting and user.id == company_posting.user_id
        is_unlocked_status = False
        
        if user:
            is_unlocked_status = is_unlocked(db, user.id, UnlockTarget.job, job_id)

        return render_template(
            "job_detail.html",
            job=job,
            user=user,             # <-- FIX: user doorgeven
            company=company_posting,
            UserRole=UserRole,      # <-- FIX: UserRole doorgeven
            is_owner=is_owner,
            is_unlocked=is_unlocked_status
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
