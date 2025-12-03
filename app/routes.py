from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from datetime import datetime, timezone
from functools import wraps
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload
from flask_babel import gettext as _
from .supabase_client import get_session
from .models import (
    User,
    ConsultantProfile,
    Company,
    JobPost,
    UserRole,
    Skill,
    Unlock,
    UnlockTarget,
    Collaboration,
    CollaborationStatus,
)
import os
from werkzeug.utils import secure_filename

import requests
from math import radians, sin, cos, sqrt, atan2


# ------------------ MAPBOX CONFIG & HELPERS ------------------

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "gif"}


def haversine_km(lat1, lon1, lat2, lon2):
    """Bereken afstand in km tussen twee (lat, lon) punten."""
    try:
        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)
    except (TypeError, ValueError):
        return None

    R = 6371.0  # straal aarde in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c  # km


def geocode_with_mapbox(city, country):
    """Geocode 'stad, land' naar (lat, lon) met Mapbox."""
    if not MAPBOX_TOKEN:
        return None, None

    if not city and not country:
        return None, None

    query = ", ".join(filter(None, [city, country]))
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"

    params = {
        "access_token": MAPBOX_TOKEN,
        "limit": 1,
    }

    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
    except Exception:
        return None, None

    data = resp.json()
    if not data.get("features"):
        return None, None

    # Mapbox center: [lon, lat]
    lon, lat = data["features"][0]["center"]
    return lat, lon


# ------------------ BLUEPRINT & HELPERS ------------------

main = Blueprint("main", __name__)


def get_current_user(db):
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def login_required(f):
    """Controleert of de gebruiker is ingelogd via de sessie."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            flash(_("Gelieve in te loggen om deze actie uit te voeren."))
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)

    return decorated_function


def is_unlocked(db, unlocking_user_id, target_type, target_id):
    """Controleert of een gebruiker al de contactgegevens van een target heeft unlocked."""
    return (
        db.query(Unlock)
        .filter(
            Unlock.user_id == unlocking_user_id,
            Unlock.target_type == target_type,
            Unlock.target_id == target_id,
        )
        .first()
        is not None
    )

# ------------------ NIEUWE GECORRIGEERDE HELPERFUNCTIE ------------------
def check_profile_completion(user, profile, company):
    """
    Controleert of essentiële velden zijn ingevuld en stuurt een Engelse melding, 
    inclusief een hint naar de benodigde edit-URL.
    """
    missing_fields = []
    edit_target = 'profile' # Default target: Edit Profile

    if user.role == UserRole.consultant:
        if not profile:
            return 
        
        # 1. Essentiële Matching Velden
        if not profile.headline or profile.headline == "":
            missing_fields.append("Headline")
        if profile.years_experience is None:
            missing_fields.append("Years of experience")
        if not profile.location_city or profile.location_city == "":
            missing_fields.append("City")
        if not profile.country or profile.country == "":
            missing_fields.append("Country")
        
        # 2. Skills (vereist aparte edit pagina)
        if not profile.skills:
             missing_fields.append("Skills")
             edit_target = 'skills' # Als skills ontbreken, stuur naar de skills editor

        # 3. Profielkwaliteit (niet strikt essentieel voor matching, maar wel voor unlock)
        if not profile.profile_image:
             missing_fields.append("Profile Picture")
        if not profile.cv_document:
             missing_fields.append("CV Document")
        
        # Controleer of de display_name de default username is
        if profile.display_name_masked == user.username:
             missing_fields.append("Full Name")


        if missing_fields:
            fields_str = ", ".join(missing_fields)
            
            # De flash melding krijgt nu de edit_target mee in de categorie, 
            # zodat base.html weet naar welke pagina te linken.
            flash(
                (f"Your profile is incomplete! Please update the following details for better matching: {fields_str}."),
                f"warning-link-{edit_target}"
            )

    elif user.role == UserRole.company:
        if not company:
            return 
        
        # Velden die we als essentieel beschouwen voor bedrijven
        if company.company_name_masked == user.username:
            missing_fields.append("Company Name")
        if not company.location_city or company.location_city == "":
            missing_fields.append("City")
        if not company.country or company.country == "":
            missing_fields.append("Country")

        if missing_fields:
            fields_str = ", ".join(missing_fields)
            # Bedrijven linken altijd naar de algemene edit_company_profile
            flash(
                f"Your company profile is incomplete! Please update the following details: {fields_str}.",
                "warning-link-profile" 
            )

# EINDE GECORRIGEERDE HELPERFUNCTIE
# ------------------ HOME ------------------

@main.route("/company/jobs", methods=["GET"])
def company_jobs_list():
    """
    Toont alle Job Posts die door het ingelogde bedrijf zijn aangemaakt.
    Gebruik dezelfde job_list template maar met:
    - sort_by='none'
    - show_mode_selector=False
    - simple_search=True
    """
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.company:
            flash(_("Only companies can view their own job posts."))
            return redirect(url_for("main.dashboard"))

        company = db.query(Company).filter_by(user_id=user.id).first()

        if not company:
            flash(_("Company profile not found."))
            return redirect(url_for("main.dashboard"))

        q = request.args.get("q", "").strip()

        query = db.query(JobPost).filter(JobPost.company_id == company.id)

        if q:
            query = query.filter(
                or_(
                    JobPost.title.ilike(f"%{q}%"),
                    JobPost.description.ilike(f"%{q}%"),
                )
            )

        jobs = query.order_by(JobPost.created_at.desc()).all()

        all_skills = []  # template verwacht 'skills'

        return render_template(
            "job_list.html",
            jobs=jobs,
            user=user,
            skills=all_skills,
            sort_by="none",
            page_title=_("My job posts"),
            show_mode_selector=False,
            simple_search=True,
            possible_contract_types=[],
            current_contract_type=None,
            UserRole=UserRole,
        )


@main.route("/", methods=["GET"])
def index():
    with get_session() as db:
        # aantal consultants die beschikbaar staan
        open_consultants_count = (
            db.query(func.count(ConsultantProfile.id))
            .filter(ConsultantProfile.availability == True)
            .scalar()
        )

        # aantal actieve jobs
        active_jobs_count = (
            db.query(func.count(JobPost.id))
            .filter(JobPost.is_active == True)
            .scalar()
        )

        return render_template(
            "index.html",
            open_consultants_count=open_consultants_count,
            active_jobs_count=active_jobs_count,
        )


# ------------------ LOGIN / LOGOUT ------------------

@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        role_str = request.form.get("role", "consultant")
        requested_role = UserRole(role_str)

        admin_code_input = request.form.get("admin_code")

        if not username:
            flash(_("Username is required."))
            return redirect(url_for("main.login"))

        # ADMIN BEVEILIGING
        if requested_role == UserRole.admin:
            if admin_code_input != os.getenv("ADMIN_CODE"):
                flash(_("Invalid admin code."))
                return redirect(url_for("main.login"))

        with get_session() as db:
            user = db.query(User).filter(User.username == username).first()

            if user:
                # Bestaande gebruiker
                if user.role == requested_role:
                    session["user_id"] = user.id
                    session["role"] = user.role.value
                    flash(_(f"Welcome back, {username}."))
                    return redirect(url_for("main.dashboard"))
                else:
                    flash(_("This username already exists and is linked to another role."))
                    return redirect(url_for("main.login"))
            else:
                # Nieuwe gebruiker
                user = User(username=username, role=requested_role)
                db.add(user)
                db.flush()

                if requested_role == UserRole.consultant:
                    prof = ConsultantProfile(
                        user_id=user.id,
                        display_name_masked=username,
                        availability=True,
                        created_at=datetime.utcnow(),
                    )
                    db.add(prof)

                elif requested_role == UserRole.company:
                    comp = Company(
                        user_id=user.id,
                        company_name_masked=username,
                        created_at=datetime.utcnow(),
                    )
                    db.add(comp)

                # admin heeft geen extra profiel nodig

                db.commit()
                flash(
                    _(
                        f"Welcome, {username}. You are registered and logged in as {role_str}."
                    )
                )

                session["user_id"] = user.id
                session["role"] = user.role.value
                return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@main.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("main.index"))


# ------------------ DASHBOARD ------------------

@main.route("/dashboard", methods=["GET"])
def dashboard():
    with get_session() as db:
        user = get_current_user(db)

        if not user:
            flash(_("Please log in to view your dashboard."))
            return redirect(url_for("main.login"))

        profile = None
        company = None
        company_jobs = []
        company_active_collaborations = []
        consultant_active_collaborations = []

        if user.role == UserRole.consultant:
            profile = db.query(ConsultantProfile).filter_by(user_id=user.id).first()

            if profile:
                # 🔹 Actieve samenwerkingen voor deze consultant
                consultant_active_collaborations = (
                    db.query(Collaboration)
                    .options(
                        joinedload(Collaboration.company),
                        joinedload(Collaboration.job_post),
                    )
                    .filter(
                        Collaboration.consultant_id == profile.id,
                        Collaboration.status == CollaborationStatus.active,
                    )
                    .order_by(Collaboration.started_at.desc())
                    .all()
                )

        elif user.role == UserRole.company:
            company = db.query(Company).filter_by(user_id=user.id).first()

            if company:
                # 🔹 Alle jobposts van dit bedrijf (zowel active als closed)
                company_jobs = (
                    db.query(JobPost)
                    .options(joinedload(JobPost.hired_consultant))
                    .filter(JobPost.company_id == company.id)
                    .order_by(JobPost.created_at.desc())
                    .all()
                )

                # 🔹 Actieve samenwerkingen voor deze company
                company_active_collaborations = (
                    db.query(Collaboration)
                    .options(
                        joinedload(Collaboration.consultant),
                        joinedload(Collaboration.job_post),
                    )
                    .filter(
                        Collaboration.company_id == company.id,
                        Collaboration.status == CollaborationStatus.active,
                    )
                    .order_by(Collaboration.started_at.desc())
                    .all()
                )

        # 🟢 NIEUW: Roep de check functie aan
        check_profile_completion(user, profile, company)

        return render_template(
            "dashboard.html",
            user=user,
            profile=profile,
            company=company,
            UserRole=UserRole,
            company_jobs=company_jobs,
            company_active_collaborations=company_active_collaborations,
            consultant_active_collaborations=consultant_active_collaborations,
        )
        


# ------------------ CONSULTANTS ------------------

@main.route("/consultant/edit", methods=["GET", "POST"])
def edit_consultant_profile():
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.consultant:
            flash("Only consultants can edit their profile")
            return redirect(url_for("main.dashboard"))

        profile = (
            db.query(ConsultantProfile)
            .filter(ConsultantProfile.user_id == user.id)
            .first()
        )

        if request.method == "POST":
            profile.display_name_masked = request.form.get("display_name")
            profile.location_city = request.form.get("location_city")
            profile.country = request.form.get("country")
            profile.headline = request.form.get("headline")
            profile.contact_email = request.form.get("contact_email")
            profile.phone_number = request.form.get("phone_number")

            # 🔹 Years of experience
            years_experience_raw = (request.form.get("years_experience") or "").strip()
            try:
                profile.years_experience = (
                    int(years_experience_raw) if years_experience_raw else None
                )
            except ValueError:
                profile.years_experience = None

            # Availability uit dropdown lezen
            availability_value = request.form.get("availability_status", "available")
            was_available_before = profile.availability
            profile.availability = availability_value == "available"

            # Als je jezelf weer 'available' maakt, actieve samenwerkingen afsluiten
            if (not was_available_before) and profile.availability:
                now = datetime.now(timezone.utc)
                active_collabs = (
                    db.query(Collaboration)
                    .filter(
                        Collaboration.consultant_id == profile.id,
                        Collaboration.status == CollaborationStatus.active,
                    )
                    .all()
                )
                for c in active_collabs:
                    c.status = CollaborationStatus.ended
                    c.ended_at = now

                # consultant loskoppelen van current_company
                profile.current_company_id = None

            # Geocode locatie
            lat, lon = geocode_with_mapbox(profile.location_city, profile.country)
            profile.latitude = lat
            profile.longitude = lon

            # Profielfoto
            file = request.files.get("profile_image")
            if file and file.filename != "":
                upload_folder = os.path.join(
                    current_app.root_path, "static", "uploads"
                )
                os.makedirs(upload_folder, exist_ok=True)

                orig_name = secure_filename(file.filename)
                _, ext = os.path.splitext(orig_name)
                ext = ext.lower()
                if ext not in {".png", ".jpg", ".jpeg", ".gif"}:
                    flash(
                        _("Invalid image type. Allowed: png/jpg/jpeg/gif."), "error"
                    )
                    return redirect(url_for("main.edit_consultant_profile"))

                filename = f"user_{user.id}{ext}"
                save_path = os.path.join(upload_folder, filename)
                file.save(save_path)
                profile.profile_image = f"/static/uploads/{filename}"

            # CV
            cv_file = request.files.get("cv_document")
            if cv_file and cv_file.filename != "":
                upload_folder = os.path.join(
                    current_app.root_path, "static", "uploads"
                )
                os.makedirs(upload_folder, exist_ok=True)

                orig_name = secure_filename(cv_file.filename)
                _, ext = os.path.splitext(orig_name)
                ext = ext.lower()

                allowed_exts = {".pdf", ".doc", ".docx"}
                if ext not in allowed_exts:
                    flash(_("Invalid file type. Only upload pdf/doc/docx."))
                    return redirect(url_for("main.edit_consultant_profile"))

                cv_filename = f"cv_user_{user.id}{ext}"
                cv_save_path = os.path.join(upload_folder, cv_filename)
                cv_file.save(cv_save_path)
                profile.cv_document = f"/static/uploads/{cv_filename}"

            db.commit()
            flash("Profile updated successfully")
            return redirect(url_for("main.dashboard"))

        return render_template(
            "edit_consultant_profile.html",
            profile=profile,
            UserRole=UserRole,
        )


@main.route("/consultant/skills/edit", methods=["GET", "POST"])
def edit_consultant_skills():
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.consultant:
            flash(_("Only consultants can update their skills"))
            return redirect(url_for("main.dashboard"))

        profile = (
            db.query(ConsultantProfile)
            .filter(ConsultantProfile.user_id == user.id)
            .first()
        )

        if request.method == "POST":
            selected_ids = list(map(int, request.form.getlist("skills")))
            profile.skills = (
                db.query(Skill).filter(Skill.id.in_(selected_ids)).all()
                if selected_ids
                else []
            )
            db.commit()

            flash(_("Profile updated"))
            return redirect(url_for("main.dashboard"))

        all_skills = db.query(Skill).all()
        return render_template(
            "edit_consultant_skills.html",
            profile=profile,
            skills=all_skills,
        )


@main.route("/consultant/<int:profile_id>")
def consultant_detail(profile_id):
    with get_session() as db:
        profile = (
            db.query(ConsultantProfile)
            .filter(ConsultantProfile.id == profile_id)
            .first()
        )

        if not profile:
            flash(_("Consultant not found"))
            return redirect(url_for("main.consultants_list"))

        user = get_current_user(db)
        is_owner = user and user.id == profile.user_id
        is_unlocked_status = False

        if user:
            is_unlocked_status = is_unlocked(
                db, user.id, UnlockTarget.consultant, profile_id
            )

        return render_template(
            "consultant_detail.html",
            profile=profile,
            user=user,
            UserRole=UserRole,
            is_owner=is_owner,
            is_unlocked=is_unlocked_status,
        )


@main.route("/consultants", methods=["GET"])
def consultants_list():
    with get_session() as db:
        user = get_current_user(db)

        # 1. Beveiligingscontrole (Moet een Company zijn)
        if not user or user.role != UserRole.company:
            flash(_("Only companies can browse consultant profiles."))
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

        # 🔹 Min. jaren ervaring
        min_experience_raw = (request.args.get("min_experience") or "").strip()
        min_experience = None
        if min_experience_raw:
            try:
                min_experience = int(min_experience_raw)
            except ValueError:
                min_experience = None

        # 🔹 Locatie-filters uit de query
        max_distance_raw = (request.args.get("max_distance_km", "") or "").strip()
        max_distance_km = None
        if max_distance_raw != "":
            try:
                val = float(max_distance_raw)
                if val > 0:
                    max_distance_km = val
            except ValueError:
                max_distance_km = None

        ignore_distance = request.args.get("ignore_distance") == "1"
        same_country_only = request.args.get("same_country_only") == "1"

        # 🔹 Nieuwe: expliciet gekozen job voor matching
        selected_job_id = request.args.get("job_id", type=int)

        # 3. Company-profiel (voor locatie & jobs)
        company_profile = db.query(Company).filter_by(user_id=user.id).first()

        required_job = None
        required_skill_ids = set()
        company_jobs = []

        if company_profile:
            # alle jobs van dit bedrijf (nieuwste eerst)
            company_jobs = (
                db.query(JobPost)
                .filter(JobPost.company_id == company_profile.id)
                .order_by(JobPost.created_at.desc())
                .all()
            )

            # eerst proberen: job_id uit query
            if selected_job_id:
                required_job = next(
                    (job for job in company_jobs if job.id == selected_job_id),
                    None,
                )

            # geen geldige gekozen job → fallback: nieuwste job
            if not required_job and company_jobs:
                required_job = company_jobs[0]

            if required_job:
                required_skill_ids = {s.id for s in required_job.skills}

        # Als we in relevance-modus zitten maar geen job hebben
        if not required_job and sort_by == "relevance":
            flash(
                _(
                    "First, create a Job Post (or select one) to enable the IConsult relevance filter based on your needs."
                )
            )

        company_lat = getattr(company_profile, "latitude", None) if company_profile else None
        company_lon = getattr(company_profile, "longitude", None) if company_profile else None
        company_country = (
            (company_profile.country or "").strip().lower()
            if company_profile and company_profile.country
            else None
        )

        # 4. Basisquery en Filters Toepassen (zonder afstand)
        query = (
            db.query(ConsultantProfile)
            .options(joinedload(ConsultantProfile.user))
            .filter(ConsultantProfile.availability == True)
        )

        if min_experience is not None:
            query = query.filter(ConsultantProfile.years_experience >= min_experience)

        # Filters gelden ALLEEN in de 'Handmatige Filter' modus
        if sort_by != "relevance":
            if city:
                query = query.filter(ConsultantProfile.location_city.ilike(f"%{city}%"))
            if country:
                query = query.filter(ConsultantProfile.country.ilike(f"%{country}%"))

            # Handmatige skill-filter (AND logica)
            if query_skills:
                for skill_id in query_skills:
                    query = query.filter(
                        ConsultantProfile.skills.any(Skill.id == skill_id)
                    )

        consultants = query.all()

        # 🔹 LOCATIE-FILTER toepassen (afstand + zelfde land)
        filtered_consultants = []
        for profile in consultants:
            # Zelfde land (indien aangevinkt én company country gekend)
            if same_country_only and company_country:
                prof_country = (profile.country or "").strip().lower()
                if prof_country and prof_country != company_country:
                    continue  # ander land → skip

            # Afstand
            if (
                not ignore_distance
                and max_distance_km is not None
                and company_lat is not None
                and company_lon is not None
            ):
                prof_lat = getattr(profile, "latitude", None)
                prof_lon = getattr(profile, "longitude", None)

                if prof_lat is None or prof_lon is None:
                    continue

                distance = haversine_km(company_lat, company_lon, prof_lat, prof_lon)
                if distance is None or distance > max_distance_km:
                    continue

            filtered_consultants.append(profile)

        consultants = filtered_consultants

        # 5. UNLOCK STATUS OPHALEN
        unlocked_profile_ids = set()
        if user and user.role == UserRole.company:
            unlocked_profiles_rows = (
                db.query(Unlock.target_id)
                .filter(
                    Unlock.user_id == user.id,
                    Unlock.target_type == UnlockTarget.consultant,
                )
                .all()
            )
            unlocked_profile_ids = {row[0] for row in unlocked_profiles_rows}

        for consultant in consultants:
            consultant.is_unlocked_for_me = consultant.id in unlocked_profile_ids

        # 6. Sortering & Relevantie Berekening (LOCATIE NIET MEER IN SCORE)
        if sort_by == "relevance":
            now = datetime.now(timezone.utc)

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

            SKILL_WEIGHT = 0.50
            TEXT_WEIGHT = 0.20
            RECENCY_WEIGHT = 0.20
            POPULARITY_WEIGHT = 0.10

            def compute_score(profile):
                if not required_job:
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

                # A. Skills
                consultant_skill_ids = {s.id for s in profile.skills}
                matched = len(consultant_skill_ids & required_skill_ids)
                max_skills = max(len(required_skill_ids), 1)
                skill_similarity = matched / max_skills
                skill_weighted_score = skill_similarity * SKILL_WEIGHT

                # B. Text
                text_match = 0
                if text_query:
                    text_fields = " ".join(
                        filter(
                            None,
                            [
                                profile.display_name_masked,
                                profile.headline,
                                profile.location_city,
                                profile.country,
                            ],
                        )
                    )
                    if text_query.lower() in text_fields.lower():
                        text_match = 1
                text_weighted_score = text_match * TEXT_WEIGHT

                # C. Recency
                days_old = (now - profile.created_at).days
                recency_factor = max(0, 1 - days_old / 30)
                recency_weighted_score = recency_factor * RECENCY_WEIGHT

                # D. Populariteit
                unlock_count = unlock_counts.get(profile.id, 0)
                max_unlocks = 50
                popularity_factor = min(unlock_count / max_unlocks, 1.0)
                popularity_weighted_score = popularity_factor * POPULARITY_WEIGHT

                final_score = (
                    skill_weighted_score
                    + text_weighted_score
                    + recency_weighted_score
                    + popularity_weighted_score
                )

                return {
                    "total": final_score,
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

            scored_consultants = []
            for consultant in consultants:
                score_data = compute_score(consultant)
                consultant.score = score_data["total"]
                consultant.score_breakdown = score_data
                scored_consultants.append(consultant)

            consultants = sorted(scored_consultants, key=lambda c: c.score, reverse=True)

        elif sort_by == "title":
            consultants = sorted(
                consultants,
                key=lambda c: c.display_name_masked
                if c.display_name_masked
                else c.user.username,
            )

        # 7. Template Renderen  ✅ altijd een return
        all_skills = db.query(Skill).order_by(Skill.name).all()

        return render_template(
            "consultant_list.html",
            consultants=consultants,
            skills=all_skills,
            user=user,
            sort_by=sort_by,
            company_jobs=company_jobs,
            selected_job_id=selected_job_id,
            UserRole=UserRole,
        )



# ------------------ COMPANY PROFILE ------------------

@main.route("/company/edit", methods=["GET", "POST"])
def edit_company_profile():
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.company:
            flash(_("Only companies can edit their profile"))
            return redirect(url_for("main.dashboard"))

        company = db.query(Company).filter(Company.user_id == user.id).first()

        if request.method == "POST":
            company.company_name_masked = request.form.get("company_name")
            company.location_city = request.form.get("location_city")
            company.country = request.form.get("country")
            company.contact_email = request.form.get("contact_email")
            company.phone_number = request.form.get("phone_number")

            # Geocode locatie
            lat, lon = geocode_with_mapbox(company.location_city, company.country)
            company.latitude = lat
            company.longitude = lon

            db.commit()

            flash(_("Company profile updated"))
            return redirect(url_for("main.dashboard"))

        return render_template("edit_company_profile.html", company=company)


# ------------------ UNLOCK LOGICA ------------------

@main.route("/unlock/consultant/<int:profile_id>")
@login_required
def unlock_consultant(profile_id):
    with get_session() as db:
        user = get_current_user(db)

        if user.role != UserRole.company:
            flash(_("Only companies can reveal consultants contact details."), "error")
            return redirect(url_for("main.consultant_detail", profile_id=profile_id))

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
            target_id=profile_id,
        )
        db.add(new_unlock)
        db.commit()

        flash(_("Contact details successfully released!"), "success")
        return redirect(url_for("main.consultant_detail", profile_id=profile_id))


@main.route("/consultant/<int:profile_id>/collaborate", methods=["POST"])
@login_required
def collaborate_with_consultant(profile_id):
    """
    Company klikt op 'Samenwerken' bij een consultant.
    """
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.company:
            flash(
                _("Only companies can start a collaboration with a consultant."), "error"
            )
            return redirect(url_for("main.consultant_detail", profile_id=profile_id))

        company = db.query(Company).filter_by(user_id=user.id).first()
        if not company:
            flash(_("Company profile not found."), "error")
            return redirect(url_for("main.dashboard"))

        profile = db.query(ConsultantProfile).filter_by(id=profile_id).first()
        if not profile:
            flash(_("Consultant profile not found."), "error")
            return redirect(url_for("main.consultants_list"))

        if not profile.availability:
            flash(_("This consultant is currently not available."), "error")
            return redirect(url_for("main.consultant_detail", profile_id=profile_id))

        # eerst unlock checken
        if not is_unlocked(db, user.id, UnlockTarget.consultant, profile_id):
            flash(
                _("First unlock this consultant before starting a collaboration."),
                "error",
            )
            return redirect(url_for("main.consultant_detail", profile_id=profile_id))

        # Collaboration aanmaken zonder specifieke job
        collab = Collaboration(
            company_id=company.id,
            consultant_id=profile.id,
            job_post_id=None,
            status=CollaborationStatus.active,
        )
        db.add(collab)

        # Consultant unavailable + link naar current company
        profile.availability = False
        profile.current_company_id = company.id

        db.commit()

        flash(
            _(
                "You are now collaborating with this consultant. They have been marked as unavailable."
            ),
            "success",
        )
        return redirect(url_for("main.consultant_detail", profile_id=profile_id))


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
            target_id=job_id,
        )
        db.add(new_unlock)
        db.commit()

        flash(_("Contact details successfully released!"), "success")
        return redirect(url_for("main.job_detail", job_id=job_id))


@main.route("/jobs/<int:job_id>/collaborate", methods=["POST"])
@login_required
def collaborate_on_job(job_id):
    """
    Consultant klikt op 'Ik wil samenwerken' bij een job.
    """
    with get_session() as db:
        user = get_current_user(db)

        if not user or user.role != UserRole.consultant:
            flash(_("Only consultants can start a collaboration for a job."), "error")
            return redirect(url_for("main.job_detail", job_id=job_id))

        job = db.query(JobPost).filter_by(id=job_id).first()
        if not job:
            flash(_("Job post not found."), "error")
            return redirect(url_for("main.jobs_list"))

        if not job.is_active:
            flash(_("This job is no longer available."), "error")
            return redirect(url_for("main.job_detail", job_id=job_id))

        profile = db.query(ConsultantProfile).filter_by(user_id=user.id).first()
        if not profile:
            flash(_("Consultant profile not found."), "error")
            return redirect(url_for("main.dashboard"))

        if not profile.availability:
            flash(_("You are currently marked as unavailable."), "error")
            return redirect(url_for("main.job_detail", job_id=job_id))

        # job moet eerst unlocked zijn
        if not is_unlocked(db, user.id, UnlockTarget.job, job_id):
            flash(_("First unlock this job before starting a collaboration."), "error")
            return redirect(url_for("main.job_detail", job_id=job_id))

        # Collaboration aanmaken (archief)
        collab = Collaboration(
            company_id=job.company_id,
            consultant_id=profile.id,
            job_post_id=job.id,
            status=CollaborationStatus.active,
        )
        db.add(collab)

        # Job sluiten + consultant unavailable maken
        job.is_active = False
        job.hired_consultant_id = profile.id

        profile.availability = False
        profile.current_company_id = job.company_id

        db.commit()

        flash(
            _(
                "You are now collaborating with this company. The job is closed and you are set to unavailable."
            ),
            "success",
        )
        return redirect(url_for("main.dashboard"))


# ------------------ JOB POSTS ------------------

@main.route("/jobs", methods=["GET"])
def jobs_list():
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

        # Locatie-filters
        max_distance_raw = (request.args.get("max_distance_km", "") or "").strip()
        max_distance_km = None
        if max_distance_raw != "":
            try:
                val = float(max_distance_raw)
                if val > 0:
                    max_distance_km = val
            except ValueError:
                max_distance_km = None

        ignore_distance = request.args.get("ignore_distance") == "1"
        same_country_only = request.args.get("same_country_only") == "1"

        # 3. Consultant profiel & skills / locatie
        consultant_profile = (
            db.query(ConsultantProfile)
            .filter(ConsultantProfile.user_id == user.id)
            .first()
        )
        consultant_skill_ids = set()
        if consultant_profile:
            consultant_skill_ids = {s.id for s in consultant_profile.skills}

        consultant_lat = (
            getattr(consultant_profile, "latitude", None) if consultant_profile else None
        )
        consultant_lon = (
            getattr(consultant_profile, "longitude", None)
            if consultant_profile
            else None
        )
        consultant_country = (
            (consultant_profile.country or "").strip().lower()
            if consultant_profile and consultant_profile.country
            else None
        )

        # 4. Basisquery en filters (nog zonder afstandsfilter)
        query = (
            db.query(JobPost)
            .options(joinedload(JobPost.company))
            .filter(JobPost.is_active == True)
        )

        # 🔹 Contract type moet ALTIJD filteren (ook in relevance-modus)
        if contract_type:
            query = query.filter(JobPost.contract_type == contract_type)

        # 🔹 Overige manual filters alleen in 'title'/manual mode
        if sort_by != "relevance":
            if city:
                query = query.filter(JobPost.location_city.ilike(f"%{city}%"))
            if country:
                query = query.filter(JobPost.country.ilike(f"%{country}%"))
            if query_skills:
                for skill_id in query_skills:
                    query = query.filter(JobPost.skills.any(Skill.id == skill_id))

        jobs = query.all()

        # Locatie-filter (afstand + zelfde land)
        filtered_jobs = []
        for job in jobs:
            company = job.company

            # Zelfde land
            if same_country_only and consultant_country:
                job_country = (
                    job.country
                    or (company.country if company else "")
                    or ""
                ).strip().lower()
                if job_country and job_country != consultant_country:
                    continue

            # Afstand
            if (
                not ignore_distance
                and max_distance_km is not None
                and consultant_lat is not None
                and consultant_lon is not None
            ):
                comp_lat = getattr(company, "latitude", None) if company else None
                comp_lon = getattr(company, "longitude", None) if company else None

                if comp_lat is None or comp_lon is None:
                    continue

                distance = haversine_km(
                    consultant_lat, consultant_lon, comp_lat, comp_lon
                )
                if distance is None or distance > max_distance_km:
                    continue

            filtered_jobs.append(job)

        jobs = filtered_jobs

        # 5. UNLOCK STATUS OPHALEN
        job_ids_unlocked_by_user = set()
        if user and user.role == UserRole.consultant:
            unlocked_jobs = (
                db.query(Unlock.target_id)
                .filter(
                    Unlock.user_id == user.id,
                    Unlock.target_type == UnlockTarget.job,
                )
                .all()
            )
            job_ids_unlocked_by_user = {row[0] for row in unlocked_jobs}

        for job in jobs:
            job.is_unlocked_for_me = job.id in job_ids_unlocked_by_user

        # 6. Sortering & Relevantie Berekening
        if sort_by == "relevance":
            now = datetime.now(timezone.utc)
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

            MAX_UNLOCKS = 50

            SKILL_WEIGHT = 0.50
            TEXT_WEIGHT = 0.20
            RECENCY_WEIGHT = 0.20
            POPULARITY_WEIGHT = 0.10

            def compute_score(job):
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

                # A. Skills
                job_skill_ids = {s.id for s in job.skills}
                matched = len(job_skill_ids & consultant_skill_ids)
                max_skills = max(len(consultant_skill_ids), 1)
                skill_similarity = matched / max_skills
                skill_weighted_score = skill_similarity * SKILL_WEIGHT

                # B. Text Match
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
                text_weighted_score = text_match * TEXT_WEIGHT

                # C. Recency
                days_old = (now - job.created_at).days
                recency_factor = max(0, 1 - days_old / 30)
                recency_weighted_score = recency_factor * RECENCY_WEIGHT

                # D. Populariteit (unlocks)
                unlock_count = unlock_counts.get(job.id, 0)
                popularity_factor = min(unlock_count / MAX_UNLOCKS, 1.0)
                popularity_weighted_score = popularity_factor * POPULARITY_WEIGHT

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

            jobs = sorted(scored_jobs, key=lambda j: j.score, reverse=True)

        elif sort_by == "title":
            jobs = sorted(jobs, key=lambda j: j.title or "")

        # 7. Template Renderen
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
            simple_search=False,
            show_mode_selector=True,
            UserRole=UserRole,
        )



@main.route("/jobs/<int:job_id>", methods=["GET"])
def job_detail(job_id):
    with get_session() as db:
        user = get_current_user(db)

        job = db.query(JobPost).filter(JobPost.id == job_id).first()
        if not job:
            flash(_("Job not found"))
            return redirect(url_for("main.jobs_list"))

        company_posting = job.company

        is_owner = user and company_posting and user.id == company_posting.user_id

        # Als job ingevuld/inactief is: alleen eigenaar mag de detailpagina nog zien
        if not job.is_active and not is_owner:
            flash(_("This job is no longer available."))
            return redirect(url_for("main.jobs_list"))

        is_unlocked_status = False

        if user:
            is_unlocked_status = is_unlocked(db, user.id, UnlockTarget.job, job_id)

        return render_template(
            "job_detail.html",
            job=job,
            user=user,
            company=company_posting,
            UserRole=UserRole,
            is_owner=is_owner,
            is_unlocked=is_unlocked_status,
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

            if selected_skill_ids:
                selected_skills = (
                    db.query(Skill)
                    .filter(Skill.id.in_(selected_skill_ids))
                    .all()
                )
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
            job.skills = (
                db.query(Skill).filter(Skill.id.in_(selected_skill_ids)).all()
                if selected_skill_ids
                else []
            )

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


# ------------------ ADMIN DECORATOR ------------------

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("main.login"))

        if session.get("role") != UserRole.admin.value:
            flash(_("You do not have access to this page."))
            return redirect(url_for("main.dashboard"))

        return f(*args, **kwargs)

    return decorated_function


# ------------------ ADMIN CONSULTANTS ------------------

@main.route("/admin/consultants")
@login_required
@admin_required
def admin_consultants():
    q = request.args.get("q", "").lower()

    with get_session() as db:
        consultants = db.query(ConsultantProfile).all()

    # zoekfilter
    if q:
        consultants = [
            c for c in consultants
            if q in c.display_name_masked.lower()
        ]

    return render_template("admin_consultants.html", consultants=consultants)

    

#------------------- ADMIN JOBPOSTS ---------------------

@main.route("/admin/companies")
@login_required
@admin_required
def admin_companies():
    q = request.args.get("q", "").lower()

    with get_session() as db:
        companies = db.query(Company).all()
        jobs = db.query(JobPost).all()

    # groepeer jobs per company
    jobs_by_company = {}
    for job in jobs:
        jobs_by_company.setdefault(job.company_id, []).append(job)

    # zoekfilter
    if q:
        companies = [
            c for c in companies
            if q in c.company_name_masked.lower()
        ]

    return render_template(
        "admin_companies.html",
        companies=companies,
        jobs_by_company=jobs_by_company
    )


# ------------------ ADMIN COLLABORATIONS ------------------

@main.route("/admin/collaborations")
@login_required
@admin_required
def admin_collaborations():
    q = request.args.get("q", "").lower()

    with get_session() as db:
        # BASISQUERY
        query = (
            db.query(Collaboration)
            .order_by(Collaboration.started_at.desc())
        )

        # ALS ER EEN ZOEKTERM IS — FILTEREN
        if q:
            # JOIN MET CONSULTANT, COMPANY EN JOBPOST
            query = (
                query.join(Collaboration.consultant)
                     .join(Collaboration.company)
                     .outerjoin(Collaboration.job_post)
                     .filter(
                        or_(
                            func.lower(ConsultantProfile.display_name_masked).like(f"%{q}%"),
                            func.lower(Company.company_name_masked).like(f"%{q}%"),
                            func.lower(JobPost.title).like(f"%{q}%")
                        )
                     )
            )

        collaborations = query.all()

        return render_template(
            "admin_collaborations.html",
            collaborations=collaborations,
            q=q
        )




# ------------------ ADMIN DASHBOARD ------------------

@main.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")

