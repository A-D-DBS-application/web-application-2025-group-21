from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timezone
from functools import wraps
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload
import os
import mimetypes
import time
from .supabase_client import get_session, supabase
from .models import (
    User,
    ConsultantProfile,
    Company,
    JobPost,
    UserRole,
    IndustryEnum,
    Skill,
    Unlock,
    UnlockTarget,
    Collaboration,
    CollaborationStatus,
)
import requests
from math import radians, sin, cos, sqrt, atan2

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

CONSULTANT_SKILL_WEIGHT = 0.50
CONSULTANT_TEXT_WEIGHT = 0.20
CONSULTANT_RECENCY_WEIGHT = 0.20
CONSULTANT_POPULARITY_WEIGHT = 0.10
CONSULTANT_MAX_UNLOCKS = 50  # voor normalisatie van popularity

JOB_SKILL_WEIGHT = 0.50
JOB_TEXT_WEIGHT = 0.20
JOB_RECENCY_WEIGHT = 0.20
JOB_POPULARITY_WEIGHT = 0.10
JOB_MAX_UNLOCKS = 50  # voor normalisatie van popularity

POSSIBLE_CONTRACT_TYPES = [
    ("Freelance", ("Freelance")),
    ("Full-time", ("Full-time")),
    ("Part-time", ("Part-time")),
    ("Project-based", ("Project-based")),
]


# ------------------ MAPBOX HELPERS ------------------

def haversine_km(lat1, lon1, lat2, lon2):
    """
    Bereken afstand in km tussen twee (lat, lon) punten met de Haversine-formule.

    Wordt gebruikt om consultants en jobs binnen een bepaalde radius te filteren.
    """
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
    """
    Geocode 'stad, land' naar (lat, lon) met Mapbox.

    - Geeft (None, None) terug als geocoding faalt.
    - Resultaat wordt opgeslagen in de database (latitude / longitude kolommen)
      zodat we later afstandsberekeningen kunnen doen.
    """
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


# ------------------ SUPABASE STORAGE HELPER ------------------

def upload_file_to_bucket(file_obj, bucket_name, folder="uploads"):
    """
    Uploads een file naar Supabase Storage en geeft de public URL terug.
    - Leest de file uit request.files
    - Bepaalt het content-type
    - Gebruikt een unieke bestandsnaam met timestamp

    Retourneert:
        - public URL (string) als upload slaagt
        - None bij fouten
    """
    try:
        # Unieke filename: timestamp_original_filename
        filename = f"{int(time.time())}_{file_obj.filename.replace(' ', '_')}"
        file_path = f"{folder}/{filename}"

        # Bepaal content type (image/jpeg, application/pdf, ...)
        content_type = mimetypes.guess_type(file_obj.filename)[0] or "application/octet-stream"

        # File bytes lezen
        file_data = file_obj.read()

        # Upload naar Supabase
        supabase.storage.from_(bucket_name).upload(
            file_path,
            file_data,
            {"content-type": content_type}
        )

        # Public URL ophalen
        public_url_response = supabase.storage.from_(bucket_name).get_public_url(file_path)

        return public_url_response

    except Exception as e:
        print(f"Upload error: {e}")
        return None


# ------------------ BLUEPRINT & GENERIC HELPERS ------------------

main = Blueprint("main", __name__)


def get_current_user(db):
    """
    Haal de ingelogde gebruiker op uit de database m.b.v. de session['user_id'].

    Retourneert:
        - User instance of None als niemand ingelogd is.
    """
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def login_required(f):
    """
    Decorator die checkt of er een gebruiker is ingelogd.
    - Als niemand ingelogd is: redirect naar login pagina.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            flash(("Gelieve in te loggen om deze actie uit te voeren."))
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)

    return decorated_function


def require_role(
    user,
    role,
    message,
    redirect_endpoint="main.dashboard",
    category=None,
    redirect_kwargs=None,
):
    """
    Guard helper:
    - Als user niet ingelogd is of niet de juiste role heeft:
      -> flash + redirect
    - Anders: return None (dus je route kan verder)

    Gebruik:
        guard = require_role(user, UserRole.company, "Only companies ...")
        if guard: return guard
    """
    if not user or user.role != role:
        if category:
            flash((message), category)
        else:
            flash((message))
        redirect_kwargs = redirect_kwargs or {}
        return redirect(url_for(redirect_endpoint, **redirect_kwargs))
    return None
# dit is een helperfunctie die zo duplicatie vermijdt


def get_or_redirect(obj, message, redirect_endpoint, category=None, redirect_kwargs=None):
    """
    Kleine helper voor 'not found' patronen:
    - Als obj falsy is -> flash + redirect
    - Anders -> (obj, None)
    """
    if obj:
        return obj, None
    if category:
        flash((message), category)
    else:
        flash((message))
    redirect_kwargs = redirect_kwargs or {}
    return None, redirect(url_for(redirect_endpoint, **redirect_kwargs))


def require_company(db, user, not_found_message, redirect_endpoint="main.dashboard", category=None, redirect_kwargs=None):
    """
    Haal company-profiel op voor een user.
    - Als niet gevonden -> flash + redirect
    """
    company = db.query(Company).filter_by(user_id=user.id).first()
    company, guard = get_or_redirect(
        company,
        not_found_message,
        redirect_endpoint,
        category=category,
        redirect_kwargs=redirect_kwargs,
    )
    return company, guard


def require_consultant_profile(db, user, not_found_message, redirect_endpoint="main.dashboard", category=None, redirect_kwargs=None):
    """
    Haal consultant-profiel op voor een user.
    - Als niet gevonden -> flash + redirect
    """
    profile = db.query(ConsultantProfile).filter_by(user_id=user.id).first()
    profile, guard = get_or_redirect(
        profile,
        not_found_message,
        redirect_endpoint,
        category=category,
        redirect_kwargs=redirect_kwargs,
    )
    return profile, guard


def get_all_skills(db, ordered=True):
    """
    Centraliseer skills-ophaal duplicatie.
    """
    q = db.query(Skill)
    if ordered:
        q = q.order_by(Skill.name)
    return q.all()


def get_unlock_counts(db, target_type, target_ids):
    """
    Centraliseer unlock-count aggregatie (popularity) voor relevance.
    Geeft dict terug: {target_id: count}
    """
    if not target_ids:
        return {}

    unlock_rows = (
        db.query(Unlock.target_id, func.count(Unlock.id))
        .filter(
            Unlock.target_type == target_type,
            Unlock.target_id.in_(target_ids),
        )
        .group_by(Unlock.target_id)
        .all()
    )
    return {target_id: count for target_id, count in unlock_rows}


def apply_relevance_scoring(items, scoring_fn):
    """
    Centraliseer: score berekenen + score velden zetten + sorteren.
    scoring_fn(item) moet score_data dict returnen met key 'total'.
    """
    scored_items = []
    for item in items:
        score_data = scoring_fn(item)
        item.score = score_data["total"]
        item.score_breakdown = score_data
        scored_items.append(item)

    return sorted(scored_items, key=lambda x: x.score, reverse=True)


def is_unlocked(db, unlocking_user_id, target_type, target_id):
    """
    Check of een user de contactgegevens van een bepaald target al heeft 'unlocked'.

    target_type:
        - UnlockTarget.consultant
        - UnlockTarget.job
    """
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


def check_profile_completion(user, profile, company):
    """
    Toont waarschuwingen (flash) als een profiel onvolledig is.

    - Voor consultants: headline, years_experience, locatie, skills, foto, CV, naam.
    - Voor companies: company name, locatie.
    """
    missing_fields = []
    edit_target = 'profile'  # Default target: Edit Profile

    if user.role == UserRole.consultant:
        if not profile:
            return

        # 1. Essentiële Matching Velden
        if not profile.headline or profile.headline.strip() == "":
            missing_fields.append("Headline")
        if profile.years_experience is None:
            missing_fields.append("Years of experience")
        if not profile.location_city or profile.location_city.strip() == "":
            missing_fields.append("City")
        if not profile.country or profile.country.strip() == "":
            missing_fields.append("Country")

        # 2. Skills
        if not profile.skills:
            missing_fields.append("Skills")
            edit_target = 'skills'

        # 3. Profielkwaliteit
        if not profile.profile_image:
            missing_fields.append("Profile Picture")
        if not profile.cv_document:
            missing_fields.append("CV Document")

        # 4. Volledige naam
        if not profile.display_name_masked or profile.display_name_masked.strip() == "":
            missing_fields.append("Full Name")

        if missing_fields:
            fields_str = ", ".join(missing_fields)
            flash(
                f"Your profile is incomplete! Please update the following details for better matching: {fields_str}.",
                f"warning-link-{edit_target}"
            )

    elif user.role == UserRole.company:
        if not company:
            return

        if not company.company_name_masked or company.company_name_masked.strip() == "":
            missing_fields.append("Company Name")
        if not company.location_city or company.location_city.strip() == "":
            missing_fields.append("City")
        if not company.country or company.country.strip() == "":
            missing_fields.append("Country")

        if missing_fields:
            fields_str = ", ".join(missing_fields)
            flash(
                f"Your company profile is incomplete! Please update the following details: {fields_str}.",
                "warning-link-profile"
            )


# ------------------ RELEVANCE SCORE HELPERS ------------------
# Deze helpers maken de matching beter uitbreidbaar/scalable:
# als je later de scoring wilt aanpassen, kan dat centraal hier.

def compute_consultant_relevance(
    profile,
    required_job,
    required_skill_ids,
    text_query,
    unlock_counts,
    now,
):
    """
    Bereken relevance-score voor een consultant vanuit een geselecteerde JobPost.

    Let op: deze functie verandert NIETS aan het gedrag t.o.v. de oude inline code,
    alleen gestructureerd in een helper voor schaalbaarheid.
    """
    if not required_job:
        # Geen job → geen relevance mogelijk
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
    skill_weighted_score = skill_similarity * CONSULTANT_SKILL_WEIGHT

    # B. Text match (eenvoudig: substring zoekterm in combinatie van velden)
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
    text_weighted_score = text_match * CONSULTANT_TEXT_WEIGHT

    # C. Recency (nieuwere profielen scoren hoger)
    days_old = (now - profile.created_at).days
    recency_factor = max(0, 1 - days_old / 30)  # binnen 30 dagen → tot 1.0
    recency_weighted_score = recency_factor * CONSULTANT_RECENCY_WEIGHT

    # D. Populariteit (aantal unlocks, genormaliseerd met CONSULTANT_MAX_UNLOCKS)
    unlock_count = unlock_counts.get(profile.id, 0)
    popularity_factor = min(unlock_count / CONSULTANT_MAX_UNLOCKS, 1.0)
    popularity_weighted_score = popularity_factor * CONSULTANT_POPULARITY_WEIGHT

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


def compute_job_relevance(
    job,
    consultant_profile,
    consultant_skill_ids,
    text_query,
    unlock_counts,
    now,
):
    """
    Bereken relevance-score voor een JobPost vanuit een consultant-profiel.

    Houdt rekening met:
    - Skill overlap
    - Tekst-match
    - Recency
    - Populariteit (unlocks)
    """
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
    skill_weighted_score = skill_similarity * JOB_SKILL_WEIGHT

    # B. Text match
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
    text_weighted_score = text_match * JOB_TEXT_WEIGHT

    # C. Recency
    days_old = (now - job.created_at).days
    recency_factor = max(0, 1 - days_old / 30)
    recency_weighted_score = recency_factor * JOB_RECENCY_WEIGHT

    # D. Populariteit (unlocks)
    unlock_count = unlock_counts.get(job.id, 0)
    popularity_factor = min(unlock_count / JOB_MAX_UNLOCKS, 1.0)
    popularity_weighted_score = popularity_factor * JOB_POPULARITY_WEIGHT

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


# ------------------ HOME ------------------

@main.route("/company/jobs", methods=["GET"])
def company_jobs_list():
    """
    Toon alle JobPosts die door het ingelogde bedrijf aangemaakt zijn.
    Gebruikt dezelfde template als de algemene jobslijst, maar:
    - sort_by='none'
    - show_mode_selector=False
    - simple_search=True
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.company,
            "Only companies can view their own job posts.",
        )
        if guard:
            return guard

        company, guard = require_company(
            db,
            user,
            ("Company profile not found."),
            redirect_endpoint="main.dashboard",
        )
        if guard:
            return guard

        q = request.args.get("q", "").strip()

        query = db.query(JobPost).filter(JobPost.company_id == company.id)

        # Eenvoudige text search op title/description
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
            page_title=("My job posts"),
            show_mode_selector=False,
            simple_search=True,
            possible_contract_types=[],
            current_contract_type=None,
            UserRole=UserRole,
        )


@main.route("/", methods=["GET"])
def index():
    """
    Landingpagina:
    - Laat tellers zien: aantal open consultants en actieve jobs.
    """
    with get_session() as db:
        open_consultants_count = (
            db.query(func.count(ConsultantProfile.id))
            .filter(ConsultantProfile.availability == True)
            .scalar()
        )

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
    """
    Eenvoudige login op basis van username + role.
    - Als username nog niet bestaat → nieuwe user + profiel (consultant/company).
    - Admin-login vereist ADMIN_CODE uit env.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        role_str = request.form.get("role", "consultant")
        requested_role = UserRole(role_str)

        admin_code_input = request.form.get("admin_code")

        if not username:
            flash(("Username is required."))
            return redirect(url_for("main.login"))

        # Admin beveiliging
        if requested_role == UserRole.admin:
            if admin_code_input != os.getenv("ADMIN_CODE"):
                flash(("Invalid admin code."))
                return redirect(url_for("main.login"))

        with get_session() as db:
            user = db.query(User).filter(User.username == username).first()

            if user:
                # Bestaande gebruiker: role moet matchen
                if user.role == requested_role:
                    session["user_id"] = user.id
                    session["role"] = user.role.value
                    flash((f"Welcome back, {username}."))
                    return redirect(url_for("main.dashboard"))
                else:
                    flash(("This username already exists and is linked to another role."))
                    return redirect(url_for("main.login"))
            else:
                # Nieuwe gebruiker + bijhorende profieltype
                user = User(username=username, role=requested_role)
                db.add(user)
                db.flush()  # zodat user.id beschikbaar is

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
                    (
                        f"Welcome, {username}. You are registered and logged in as {role_str}."
                    )
                )

                session["user_id"] = user.id
                session["role"] = user.role.value
                return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@main.route("/logout", methods=["POST"])
def logout():
    """Log de gebruiker uit door de session te clearen."""
    session.clear()
    return redirect(url_for("main.index"))


# ------------------ DASHBOARD ------------------

@main.route("/dashboard", methods=["GET"])
def dashboard():
    """
    Toon dashboard afhankelijk van role:
    - Consultant: eigen profiel + actieve collaborations
    - Company: eigen company + jobposts + actieve collaborations
    """
    with get_session() as db:
        user = get_current_user(db)

        if not user:
            flash(("Please log in to view your dashboard."))
            return redirect(url_for("main.login"))

        profile = None
        company = None
        company_jobs = []
        company_active_collaborations = []
        consultant_active_collaborations = []
        collabs_by_job_id = {}  # 🔹 standaard lege mapping

        if user.role == UserRole.consultant:
            profile = db.query(ConsultantProfile).filter_by(user_id=user.id).first()

            if profile:
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
                company_jobs = (
                    db.query(JobPost)
                    .options(joinedload(JobPost.hired_consultant))
                    .filter(JobPost.company_id == company.id)
                    .order_by(JobPost.created_at.desc())
                    .all()
                )

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

        # Check of profiel voldoende is ingevuld
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
    """
    Consultant kan zijn eigen profiel bewerken:
    - Basisinfo
    - Availability (en bij terug naar available: collaborations sluiten)
    - Locatie (Mapbox geocoding)
    - Profielfoto + CV (Supabase upload)
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.consultant,
            "Only consultants can edit their profile"
        )
        if guard:
            return guard

        profile, guard = require_consultant_profile(
            db,
            user,
            ("Consultant profile not found."),
            redirect_endpoint="main.dashboard",
            category="error",
        )
        if guard:
            return guard

        if request.method == "POST":
            profile.display_name_masked = request.form.get("display_name")
            profile.location_city = request.form.get("location_city")
            profile.country = request.form.get("country")
            profile.headline = request.form.get("headline")
            profile.contact_email = request.form.get("contact_email")
            profile.phone_number = request.form.get("phone_number")

            # Years of experience
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

            # Wanneer je jezelf weer 'available' maakt:
            # - lopende collaborations worden beëindigd
            # - current_company wordt losgekoppeld
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

                profile.current_company_id = None

            # Locatie laten geocoden voor afstandsfilters
            lat, lon = geocode_with_mapbox(profile.location_city, profile.country)
            profile.latitude = lat
            profile.longitude = lon

            bucket_name = os.getenv("SUPABASE_BUCKET_NAME", "iconsult-assets")

            # -- Profielfoto upload (Supabase) --
            file = request.files.get("profile_image")
            if file and file.filename != "":
                public_url = upload_file_to_bucket(file, bucket_name, folder="profile_images")
                if public_url:
                    profile.profile_image = public_url
                else:
                    flash(("Failed to upload profile image."), "error")

            # -- CV upload (Supabase) --
            cv_file = request.files.get("cv_document")
            if cv_file and cv_file.filename != "":
                public_url = upload_file_to_bucket(cv_file, bucket_name, folder="cv_documents")
                if public_url:
                    profile.cv_document = public_url
                else:
                    flash(("Failed to upload CV."), "error")

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
    """
    Pagina waar een consultant zijn skills kan beheren (many-to-many relatie).
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.consultant,
            "Only consultants can update their skills"
        )
        if guard:
            return guard

        profile, guard = require_consultant_profile(
            db,
            user,
            ("Consultant profile not found."),
            redirect_endpoint="main.dashboard",
            category="error",
        )
        if guard:
            return guard

        if request.method == "POST":
            selected_ids = list(map(int, request.form.getlist("skills")))
            profile.skills = (
                db.query(Skill).filter(Skill.id.in_(selected_ids)).all()
                if selected_ids
                else []
            )
            db.commit()

            flash(("Profile updated"))
            return redirect(url_for("main.dashboard"))

        all_skills = get_all_skills(db, ordered=False)
        return render_template(
            "edit_consultant_skills.html",
            profile=profile,
            skills=all_skills,
        )


@main.route("/consultant/<int:profile_id>")
def consultant_detail(profile_id):
    """
    Detailpagina van een consultant:
    - Bedrijven zien beperkte info tenzij ze 'unlocked' hebben.
    - Als er ooit een collaboration was tussen company & consultant,
      wordt automatisch een Unlock aangemaakt (permanent toegang).
    """
    with get_session() as db:
        profile = (
            db.query(ConsultantProfile)
            .filter(ConsultantProfile.id == profile_id)
            .first()
        )

        profile, guard = get_or_redirect(
            profile,
            ("Consultant not found"),
            "main.consultants_list",
        )
        if guard:
            return guard

        user = get_current_user(db)
        is_owner = user and user.id == profile.user_id
        is_unlocked_status = False

        if user:
            # Normale unlock-check
            is_unlocked_status = is_unlocked(
                db, user.id, UnlockTarget.consultant, profile_id
            )

            # Als company ooit met deze consultant samenwerkte → altijd unlocked
            if not is_unlocked_status and user.role == UserRole.company:
                company = db.query(Company).filter_by(user_id=user.id).first()

                if company:
                    collab_exists = (
                        db.query(Collaboration)
                        .filter(
                            Collaboration.company_id == company.id,
                            Collaboration.consultant_id == profile.id,
                        )
                        .first()
                        is not None
                    )

                    if collab_exists:
                        is_unlocked_status = True

                        # Optioneel: direct een Unlock-record creëren
                        new_unlock = Unlock(
                            user_id=user.id,
                            target_type=UnlockTarget.consultant,
                            target_id=profile.id,
                        )
                        db.add(new_unlock)
                        db.commit()

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
    """
    Overzicht van consultants voor bedrijven.

    Functionaliteit:
    - Alleen toegankelijk voor role=company.
    - Handmatige filters (skills, city, country, min_experience).
    - Locatiefilter (max_distance_km, same_country_only) o.b.v. job-locatie.
    - Relevance-sorting o.b.v. geselecteerde job (skills, tekst, recency, popularity).
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.company,
            "Only companies can browse consultant profiles."
        )
        if guard:
            return guard

        sort_by = request.args.get("sort_by", "relevance")

        # Skills-filter (IDs uit query string)
        query_skills = request.args.getlist("skills")
        if query_skills:
            query_skills = list(map(int, query_skills))

        city = request.args.get("city")
        country = request.args.get("country")
        text_query = request.args.get("q", None)

        # Min. jaren ervaring
        min_experience_raw = (request.args.get("min_experience") or "").strip()
        min_experience = None
        if min_experience_raw:
            try:
                min_experience = int(min_experience_raw)
            except ValueError:
                min_experience = None

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

        same_country_only = request.args.get("same_country_only") == "1"

        # Expliciet gekozen job voor relevance matching
        selected_job_id = request.args.get("job_id", type=int)

        # Company-profiel ophalen (o.a. voor jobs & land)
        company_profile = db.query(Company).filter_by(user_id=user.id).first()

        required_job = None
        required_skill_ids = set()
        company_jobs = []

        if company_profile:
            # 🔹 Alleen ACTIEVE jobs tonen in dropdown & gebruiken voor matching
            company_jobs = (
                db.query(JobPost)
                .filter(
                    JobPost.company_id == company_profile.id,
                    JobPost.is_active == True      # <--- hier zit de truc
                )
                .order_by(JobPost.created_at.desc())
                .all()
            )

            # Probeer eerst job_id uit query
            if selected_job_id:
                required_job = next(
                    (job for job in company_jobs if job.id == selected_job_id),
                    None,
                )

            # Geen geldige gekozen job → fallback naar nieuwste job (ook actief)
            if not required_job and company_jobs:
                required_job = company_jobs[0]

            if required_job:
                required_skill_ids = {s.id for s in required_job.skills}

        # In relevance-modus moet er een (actieve) job zijn
        if not required_job and sort_by == "relevance":
            flash(
                (
                    "First, create an active Job Post (or select one) "
                    "to enable the IConsult relevance filter based on your needs."
                )
            )

        # same_country_only moet op basis van de job-locatie werken (zelfde referentie als distance)
        country_source = None
        if required_job and required_job.country:
            country_source = required_job.country
        elif company_profile and company_profile.country:
            country_source = company_profile.country

        company_country = (country_source or "").strip().lower() if country_source else None

        # Origin-coördinaten voor afstandsfilter: job-locatie
        origin_lat = None
        origin_lon = None

        if max_distance_km is not None and required_job:
            origin_lat = required_job.latitude
            origin_lon = required_job.longitude

            # Als job nog geen coords heeft → nu geocoden en opslaan
            if (origin_lat is None or origin_lon is None) and required_job.location_city and required_job.country:
                lat, lon = geocode_with_mapbox(required_job.location_city, required_job.country)
                origin_lat, origin_lon = lat, lon
                required_job.latitude = lat
                required_job.longitude = lon
                db.commit()

        # Basisquery: alleen beschikbare consultants
        query = (
            db.query(ConsultantProfile)
            .options(joinedload(ConsultantProfile.user))
            .filter(ConsultantProfile.availability == True)
        )

        if min_experience is not None:
            query = query.filter(ConsultantProfile.years_experience >= min_experience)

        # Handmatige filters gelden alleen als niet 'relevance'
        if sort_by != "relevance":
            if city:
                query = query.filter(ConsultantProfile.location_city.ilike(f"%{city}%"))
            if country:
                query = query.filter(ConsultantProfile.country.ilike(f"%{country}%"))
            if query_skills:
                for skill_id in query_skills:
                    query = query.filter(
                        ConsultantProfile.skills.any(Skill.id == skill_id)
                    )

        consultants = query.all()

        # Locatie-filter (zelfde land + afstand tot job)
        filtered_consultants = []
        for profile in consultants:
            if same_country_only and company_country:
                prof_country = (profile.country or "").strip().lower()
                if prof_country and prof_country != company_country:
                    continue

            if (
                max_distance_km is not None
                and origin_lat is not None
                and origin_lon is not None
            ):
                prof_lat = getattr(profile, "latitude", None)
                prof_lon = getattr(profile, "longitude", None)

                if prof_lat is None or prof_lon is None:
                    continue

                distance = haversine_km(origin_lat, origin_lon, prof_lat, prof_lon)
                profile.distance_km = distance

                if distance is None or distance > max_distance_km:
                    continue

            filtered_consultants.append(profile)

        consultants = filtered_consultants

        # Unlock-status voor huidige company
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

        # Relevance sorting
        if sort_by == "relevance":
            now = datetime.now(timezone.utc)

            consultant_ids = [c.id for c in consultants]
            unlock_counts = get_unlock_counts(db, UnlockTarget.consultant, consultant_ids)

            consultants = apply_relevance_scoring(
                consultants,
                lambda consultant: compute_consultant_relevance(
                    profile=consultant,
                    required_job=required_job,
                    required_skill_ids=required_skill_ids,
                    text_query=text_query,
                    unlock_counts=unlock_counts,
                    now=now,
                )
            )

        elif sort_by == "title":
            consultants = sorted(
                consultants,
                key=lambda c: c.display_name_masked
                if c.display_name_masked
                else c.user.username,
            )

        all_skills = get_all_skills(db, ordered=True)

        return render_template(
            "consultant_list.html",
            consultants=consultants,
            skills=all_skills,
            user=user,
            sort_by=sort_by,
            company_jobs=company_jobs,      # ← hier gaan nog steeds je jobs naar de template
            selected_job_id=selected_job_id,
            UserRole=UserRole,
        )

# ------------------ COMPANY PROFILE ------------------
@main.route("/company/edit", methods=["GET", "POST"])
def edit_company_profile():
    """
    Company kan zijn eigen profiel aanpassen:
    - Naam, locatie, contactgegevens
    - Industry (Enum)
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.company,
            "Only companies can edit their profile"
        )
        if guard:
            return guard

        company, guard = require_company(
            db,
            user,
            ("Company profile not found."),
            redirect_endpoint="main.dashboard",
        )
        if guard:
            return guard

        if request.method == "POST":
            company.company_name_masked = request.form.get("company_name")
            company.location_city = request.form.get("location_city")
            company.country = request.form.get("country")
            company.contact_email = request.form.get("contact_email")
            company.phone_number = request.form.get("phone_number")

            # Industry opslaan als Enum (1 value)
            selected = request.form.get("industries")  # 1 value
            company.industries = selected or None

            db.add(company)
            db.commit()

            flash(("Company profile updated"))
            return redirect(url_for("main.dashboard"))

        return render_template("edit_company_profile.html", company=company)



# ------------------ UNLOCK LOGICA ------------------

@main.route("/unlock/consultant/<int:profile_id>")
@login_required
def unlock_consultant(profile_id):
    """
    Company 'unlocked' de contactgegevens van een consultant.
    - Alleen companies kunnen dit
    - Als al unlocked → info message
    - Bewaart optionele job_id in de redirect zodat we weten
      voor welke job er later wordt gecollaboreerd.
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.company,
            ("Only companies can reveal consultants contact details."),
            redirect_endpoint="main.consultant_detail",
            redirect_kwargs={"profile_id": profile_id},
            category="error",
        )
        if guard:
            return guard

        consultant_profile = db.query(ConsultantProfile).filter_by(id=profile_id).first()
        consultant_profile, guard = get_or_redirect(
            consultant_profile,
            ("Consultant profile not found."),
            "main.dashboard",
            category="error",
        )
        if guard:
            return guard

        # job_id uit querystring (kan None zijn)
        job_id = request.args.get("job_id", type=int)

        # ✅ next uit querystring (kan None zijn)
        next_url = request.args.get("next")

        if is_unlocked(db, user.id, UnlockTarget.consultant, profile_id):
            flash(("Contact details have already been released."), "info")
            if job_id:
                return redirect(
                    url_for(
                        "main.consultant_detail",
                        profile_id=profile_id,
                        job_id=job_id,
                        next=next_url,
                    )
                )
            return redirect(
                url_for("main.consultant_detail", profile_id=profile_id, next=next_url)
            )

        new_unlock = Unlock(
            user_id=user.id,
            target_type=UnlockTarget.consultant,
            target_id=profile_id,
        )
        db.add(new_unlock)
        db.commit()

        flash(("Contact details successfully released!"), "success")

        if job_id:
            return redirect(
                url_for(
                    "main.consultant_detail",
                    profile_id=profile_id,
                    job_id=job_id,
                    next=next_url,
                )
            )
        return redirect(
            url_for("main.consultant_detail", profile_id=profile_id, next=next_url)
        )

@main.route("/consultant/<int:profile_id>/collaborate", methods=["POST"])
@login_required
def collaborate_with_consultant(profile_id):
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.company,
            ("Only companies can start a collaboration with a consultant."),
            redirect_endpoint="main.consultant_detail",
            redirect_kwargs={"profile_id": profile_id},
            category="error",
        )
        if guard:
            return guard

        company, guard = require_company(
            db,
            user,
            ("Company profile not found."),
            redirect_endpoint="main.dashboard",
            category="error",
        )
        if guard:
            return guard

        profile = db.query(ConsultantProfile).filter_by(id=profile_id).first()
        profile, guard = get_or_redirect(
            profile,
            ("Consultant profile not found."),
            "main.consultants_list",
            category="error",
        )
        if guard:
            return guard

        if not profile.availability:
            flash(("This consultant is currently not available."), "error")
            return redirect(url_for("main.consultant_detail", profile_id=profile_id))

        # job_id uit form of querystring
        job_id = request.form.get("job_id", type=int) or request.args.get("job_id", type=int)

        # Eerst unlock checken
        if not is_unlocked(db, user.id, UnlockTarget.consultant, profile_id):
            flash(
                ("First unlock this consultant before starting a collaboration."),
                "error",
            )
            # 🔹 job_id meegeven zodat detailpagina het behoudt
            if job_id:
                return redirect(
                    url_for("main.consultant_detail", profile_id=profile_id, job_id=job_id)
                )
            return redirect(url_for("main.consultant_detail", profile_id=profile_id))

        # Optioneel koppelen aan job
        job = None
        if job_id:
            job = (
                db.query(JobPost)
                .filter(
                    JobPost.id == job_id,
                    JobPost.company_id == company.id,
                )
                .first()
            )
            if not job:
                flash(("Selected job not found or not owned by your company."), "error")
                return redirect(url_for("main.consultant_detail", profile_id=profile_id))

        collab = Collaboration(
            company_id=company.id,
            consultant_id=profile.id,
            job_post_id=job.id if job else None,
            status=CollaborationStatus.active,
        )
        db.add(collab)

        # Consultant blokkeren
        profile.availability = False
        profile.current_company_id = company.id

        # 🔹 Hier wordt ENKEL de gekozen job gesloten
        if job:
            job.is_active = False
            job.hired_consultant_id = profile.id

        db.commit()

        if job:
            flash(
                (
                    "You are now collaborating with this consultant on the selected job. "
                    "The job has been closed and the consultant is unavailable."
                ),
                "success",
            )
        else:
            flash(
                (
                    "You are now collaborating with this consultant. "
                    "They have been marked as unavailable."
                ),
                "success",
            )

        # Terug naar detail, mét job_id voor duidelijkheid
        if job:
            return redirect(
                url_for("main.consultant_detail", profile_id=profile.id, job_id=job.id)
            )
        return redirect(url_for("main.consultant_detail", profile_id=profile.id))



@main.route("/unlock/job/<int:job_id>")
@login_required
def unlock_job(job_id):
    """
    Consultant 'unlocked' de contactgegevens van een job/company.
    - Alleen consultants kunnen dit.
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.consultant,
            ("Only consultants can reveal companies' contact details."),
            redirect_endpoint="main.job_detail",
            redirect_kwargs={"job_id": job_id},
            category="error",
        )
        if guard:
            return guard

        job_post = db.query(JobPost).filter_by(id=job_id).first()
        job_post, guard = get_or_redirect(
            job_post,
            ("Job post not found."),
            "main.dashboard",
            category="error",
        )
        if guard:
            return guard

        if is_unlocked(db, user.id, UnlockTarget.job, job_id):
            flash(("Contact details have already been released."), "info")
            return redirect(url_for("main.job_detail", job_id=job_id))

        new_unlock = Unlock(
            user_id=user.id,
            target_type=UnlockTarget.job,
            target_id=job_id,
        )
        db.add(new_unlock)
        db.commit()

        flash(("Contact details successfully released!"), "success")
        return redirect(url_for("main.job_detail", job_id=job_id))


@main.route("/jobs/<int:job_id>/collaborate", methods=["POST"])
@login_required
def collaborate_on_job(job_id):
    """
    Consultant klikt op 'Ik wil samenwerken' bij een job:
    - Vereist unlock voor job.
    - Maakt Collaboration aan met job_post_id.
    - Sluit job (is_active=False) en markeert consultant als unavailable.
    - Company krijgt automatisch een Unlock naar deze consultant.
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.consultant,
            ("Only consultants can start a collaboration for a job."),
            redirect_endpoint="main.job_detail",
            redirect_kwargs={"job_id": job_id},
            category="error",
        )
        if guard:
            return guard

        job = db.query(JobPost).filter_by(id=job_id).first()
        job, guard = get_or_redirect(
            job,
            ("Job post not found."),
            "main.jobs_list",
            category="error",
        )
        if guard:
            return guard

        if not job.is_active:
            flash(("This job is no longer available."), "error")
            return redirect(url_for("main.job_detail", job_id=job_id))

        profile, guard = require_consultant_profile(
            db,
            user,
            ("Consultant profile not found."),
            redirect_endpoint="main.dashboard",
            category="error",
        )
        if guard:
            return guard

        if not profile.availability:
            flash(("You are currently marked as unavailable."), "error")
            return redirect(url_for("main.job_detail", job_id=job_id))

        # Job moet eerst unlocked zijn
        if not is_unlocked(db, user.id, UnlockTarget.job, job_id):
            flash(("First unlock this job before starting a collaboration."), "error")
            return redirect(url_for("main.job_detail", job_id=job_id))

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

        # Company krijgt automatische unlock op deze consultant
        company_user_id = job.company.user_id if job.company else None
        if company_user_id:
            already_unlocked = is_unlocked(
                db,
                company_user_id,
                UnlockTarget.consultant,
                profile.id,
            )
            if not already_unlocked:
                auto_unlock = Unlock(
                    user_id=company_user_id,
                    target_type=UnlockTarget.consultant,
                    target_id=profile.id,
                )
                db.add(auto_unlock)

        db.commit()

        flash(
            (
                "You are now collaborating with this company. The job is closed and you are set to unavailable."
            ),
            "success",
        )
        return redirect(url_for("main.dashboard"))


# ------------------ JOB POSTS ------------------

@main.route("/jobs", methods=["GET"])
def jobs_list():
    """
    Overzicht van jobs voor consultants.

    Functionaliteit:
    - Alleen toegankelijk voor role=consultant.
    - Filters: skills, locatie, contract_type, tekst.
    - Locatie-filters o.b.v. consultant-locatie.
    - Relevance-sorting via compute_job_relevance.
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.consultant,
            "Only consultants can browse job posts."
        )
        if guard:
            return guard

        sort_by = request.args.get("sort_by", "relevance")

        query_skills = request.args.getlist("skills")
        if query_skills:
            query_skills = list(map(int, query_skills))

        city = request.args.get("city")
        country = request.args.get("country")
        contract_type = request.args.get("contract_type")
        text_query = request.args.get("q", None)

        # Locatie-filters (afstand, zelfde land)
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

        # Consultant-profiel voor skills + locatie
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

        # Basisquery: alleen actieve jobs
        query = (
            db.query(JobPost)
            .options(joinedload(JobPost.company))
            .filter(JobPost.is_active == True)
        )

        # Contracttype filter ALTIJD toepassen
        if contract_type:
            query = query.filter(JobPost.contract_type == contract_type)

        # Overige manual filters niet in relevance-modus
        if sort_by != "relevance":
            if city:
                query = query.filter(JobPost.location_city.ilike(f"%{city}%"))
            if country:
                query = query.filter(JobPost.country.ilike(f"%{country}%"))
            if query_skills:
                for skill_id in query_skills:
                    query = query.filter(JobPost.skills.any(Skill.id == skill_id))

        jobs = query.all()

        # Locatie-filter: zelfde land + afstand tot consultant
        filtered_jobs = []
        for job in jobs:
            company = job.company

            if same_country_only and consultant_country:
                job_country = (
                    job.country
                    or (company.country if company else "")
                    or ""
                ).strip().lower()
                if job_country and job_country != consultant_country:
                    continue

            # Afstand via job-coördinaten
            if (
                not ignore_distance
                and max_distance_km is not None
                and consultant_lat is not None
                and consultant_lon is not None
            ):
                job_lat = getattr(job, "latitude", None)
                job_lon = getattr(job, "longitude", None)

                if job_lat is None or job_lon is None:
                    continue

                distance = haversine_km(
                    consultant_lat, consultant_lon, job_lat, job_lon
                )
                if distance is None or distance > max_distance_km:
                    continue

            filtered_jobs.append(job)

        jobs = filtered_jobs

        # Unlock status ophalen (welke jobs heeft deze consultant al unlocked?)
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

        # Relevance sorting (via helper)
        if sort_by == "relevance":
            now = datetime.now(timezone.utc)
            job_ids = [j.id for j in jobs]

            unlock_counts = get_unlock_counts(db, UnlockTarget.job, job_ids)

            jobs = apply_relevance_scoring(
                jobs,
                lambda job: compute_job_relevance(
                    job=job,
                    consultant_profile=consultant_profile,
                    consultant_skill_ids=consultant_skill_ids,
                    text_query=text_query,
                    unlock_counts=unlock_counts,
                    now=now,
                )
            )

        elif sort_by == "title":
            jobs = sorted(jobs, key=lambda j: j.title or "")

        all_skills = get_all_skills(db, ordered=True)

        possible_contract_types = POSSIBLE_CONTRACT_TYPES

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
    """
    Detailpagina van één job:
    - Als job inactief is mag alleen de eigenaar (company) de pagina nog zien.
    - 'Unlocked' toont meer company-contactdetails aan consultant.
    """
    with get_session() as db:
        user = get_current_user(db)

        job = db.query(JobPost).filter(JobPost.id == job_id).first()
        job, guard = get_or_redirect(
            job,
            ("Job not found"),
            "main.jobs_list",
        )
        if guard:
            return guard

        company_posting = job.company

        is_owner = user and company_posting and user.id == company_posting.user_id

        # Inactieve job → alleen eigenaar mag het detail nog zien
        if not job.is_active and not is_owner:
            flash(("This job is no longer available."))
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
    """
    Company kan een nieuwe job aanmaken:
    - Titel, beschrijving, locatie, contract_type, skills.
    - Locatie wordt gegeocodeerd voor lat/lon (afstandsmatching).
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.company,
            "Only companies can create job posts",
            redirect_endpoint="main.login"
        )
        if guard:
            return guard

        company, guard = require_company(
            db,
            user,
            ("Company profile not found."),
            redirect_endpoint="main.dashboard",
        )
        if guard:
            return guard

        all_skills = get_all_skills(db, ordered=True)

        if request.method == "POST":
            title = request.form.get("title")
            description = request.form.get("description")
            city = request.form.get("location_city")
            country = request.form.get("country")
            contract_type = request.form.get("contract_type")

            selected_skill_ids = [int(x) for x in request.form.getlist("skills")]

            if not title:
                flash(("Title is required"))
                return redirect(url_for("main.job_new"))

            # Geocode job-locatie
            lat, lon = geocode_with_mapbox(city, country)

            job = JobPost(
                company_id=company.id,
                title=title,
                description=description,
                location_city=city,
                country=country,
                contract_type=contract_type,
                latitude=lat,
                longitude=lon,
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
    """
    Company kan een bestaande job aanpassen.
    - Zelfde velden als job_new.
    - Zelfde geocoding-logica.
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.company,
            "Only companies can edit job posts",
            redirect_endpoint="main.login"
        )
        if guard:
            return guard

        company, guard = require_company(
            db,
            user,
            ("Company profile not found."),
            redirect_endpoint="main.dashboard",
        )
        if guard:
            return guard

        job = db.query(JobPost).filter_by(id=job_id, company_id=company.id).first()
        job, guard = get_or_redirect(
            job,
            ("Job not found or you are not the owner"),
            "main.jobs_list",
        )
        if guard:
            return guard

        all_skills = get_all_skills(db, ordered=True)

        possible_contract_types = POSSIBLE_CONTRACT_TYPES

        if request.method == "POST":
            job.title = request.form.get("title")
            job.description = request.form.get("description")
            city = request.form.get("location_city")
            country = request.form.get("country")
            job.location_city = city
            job.country = country
            job.contract_type = request.form.get("contract_type")

            # Geocode job-locatie
            lat, lon = geocode_with_mapbox(city, country)
            job.latitude = lat
            job.longitude = lon

            selected_skill_ids = [int(x) for x in request.form.getlist("skills")]
            job.skills = (
                db.query(Skill).filter(Skill.id.in_(selected_skill_ids)).all()
                if selected_skill_ids
                else []
            )

            db.commit()
            flash(("Job updated!"))
            return redirect(url_for("main.job_detail", job_id=job.id))

        return render_template(
            "job_edit.html",
            job=job,
            skills=all_skills,
            possible_contract_types=possible_contract_types,
        )


@main.route("/jobs/<int:job_id>/delete", methods=["POST"])
def job_delete(job_id):
    """
    Company kan een job verwijderen (harde delete).
    """
    with get_session() as db:
        user = get_current_user(db)

        guard = require_role(
            user,
            UserRole.company,
            "Only companies can delete job posts",
            redirect_endpoint="main.login"
        )
        if guard:
            return guard

        company, guard = require_company(
            db,
            user,
            ("Company profile not found."),
            redirect_endpoint="main.dashboard",
        )
        if guard:
            return guard

        job = db.query(JobPost).filter_by(id=job_id, company_id=company.id).first()
        job, guard = get_or_redirect(
            job,
            ("Job not found or you are not the owner"),
            "main.company_jobs_list",
        )
        if guard:
            return guard

        db.delete(job)
        db.commit()
        flash(("Job deleted"))
        return redirect(url_for("main.company_jobs_list"))



# ------------------ ADMIN DECORATOR ------------------

def admin_required(f):
    """
    Decorator voor admin-only routes.

    - Checkt of user ingelogd is én role=admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("main.login"))

        if session.get("role") != UserRole.admin.value:
            flash(("You do not have access to this page."))
            return redirect(url_for("main.dashboard"))

        return f(*args, **kwargs)

    return decorated_function


# ------------------ ADMIN CONSULTANTS ------------------

@main.route("/admin/consultants")
@login_required
@admin_required
def admin_consultants():
    """
    Admin-overzicht van alle consultants.
    - Simpele text search op display_name_masked.
    """
    q = request.args.get("q", "").lower()

    with get_session() as db:
        consultants = db.query(ConsultantProfile).all()

    if q:
        consultants = [
            c for c in consultants
            if q in (c.display_name_masked or "").lower()
        ]

    return render_template("admin_consultants.html", consultants=consultants)


#------------------- ADMIN COMPANIES + JOBS ---------------------

@main.route("/admin/companies")
@login_required
@admin_required
def admin_companies():
    """
    Admin-overzicht van companies + hun jobs.
    - Jobs worden gegroepeerd per company_id.
    - Simpele text search op company_name_masked.
    """
    q = request.args.get("q", "").lower()

    with get_session() as db:
        companies = db.query(Company).all()
        jobs = db.query(JobPost).all()

    jobs_by_company = {}
    for job in jobs:
        jobs_by_company.setdefault(job.company_id, []).append(job)

    if q:
        companies = [
            c for c in companies
            if q in (c.company_name_masked or "").lower()
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
    """
    Admin-overzicht van alle Collaborations.
    - Optionele zoekterm q op consultantnaam, companynaam of jobtitel.
    """
    q = request.args.get("q", "").lower()

    with get_session() as db:
        query = (
            db.query(Collaboration)
            .order_by(Collaboration.started_at.desc())
        )

        if q:
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
    """Startpagina voor admin-sectie."""
    return render_template("admin_dashboard.html")


@main.route("/vision")
def vision_page():
    """Statische pagina voor 'Vision'."""
    return render_template("vision.html")
