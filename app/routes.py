from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from datetime import datetime, timezone
from functools import wraps
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload
from flask_babel import gettext as _
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
    Skill,
    Unlock,
    UnlockTarget,
    Collaboration,
    CollaborationStatus,
)
from werkzeug.utils import secure_filename
import requests
from math import radians, sin, cos, sqrt, atan2

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")
main = Blueprint("main", __name__)

# ------------------ GENERIC HELPERS ------------------

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "gif"}

def haversine_km(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
    except (TypeError, ValueError):
        return None
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def geocode_with_mapbox(city, country):
    if not MAPBOX_TOKEN or (not city and not country):
        return None, None
    query = ", ".join(filter(None, [city, country]))
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
    params = {"access_token": MAPBOX_TOKEN, "limit": 1}
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
    except Exception:
        return None, None
    data = resp.json()
    if not data.get("features"):
        return None, None
    lon, lat = data["features"][0]["center"]
    return lat, lon

def upload_file_to_bucket(file_obj, bucket_name, folder="uploads"):
    try:
        filename = f"{int(time.time())}_{file_obj.filename.replace(' ', '_')}"
        file_path = f"{folder}/{filename}"
        content_type = mimetypes.guess_type(file_obj.filename)[0] or "application/octet-stream"
        file_data = file_obj.read()
        supabase.storage.from_(bucket_name).upload(file_path, file_data, {"content-type": content_type})
        public_url_response = supabase.storage.from_(bucket_name).get_public_url(file_path)
        return public_url_response
    except Exception as e:
        print(f"Upload error: {e}")
        return None

def get_current_user(db):
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_id") is None:
            flash(_("Gelieve in te loggen om deze actie uit te voeren."))
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("main.login"))
        if session.get("role") != UserRole.admin.value:
            flash(_("You do not have access to this page."))
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated

def is_unlocked(db, unlocking_user_id, target_type, target_id):
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

def query_unlocked_ids(db, user_id, target_type):
    rows = (
        db.query(Unlock.target_id)
        .filter(Unlock.user_id == user_id, Unlock.target_type == target_type)
        .all()
    )
    return {row[0] for row in rows}

def ensure_geocoded(entity, city_attr="location_city", country_attr="country", lat_attr="latitude", lon_attr="longitude"):
    lat = getattr(entity, lat_attr, None)
    lon = getattr(entity, lon_attr, None)
    if lat is None or lon is None:
        city = getattr(entity, city_attr, None)
        country = getattr(entity, country_attr, None)
        lat, lon = geocode_with_mapbox(city, country)
        setattr(entity, lat_attr, lat)
        setattr(entity, lon_attr, lon)
    return getattr(entity, lat_attr), getattr(entity, lon_attr)

def within_distance(origin_lat, origin_lon, target_lat, target_lon, max_km):
    if max_km is None or origin_lat is None or origin_lon is None:
        return True
    if target_lat is None or target_lon is None:
        return False
    distance = haversine_km(origin_lat, origin_lon, target_lat, target_lon)
    return distance is not None and distance <= max_km

def recency_factor(now, created_at, window_days=30):
    days_old = (now - created_at).days
    return max(0.0, 1 - days_old / window_days)

def compute_weighted_score(skill_similarity, text_match, recency, popularity):
    return (
        skill_similarity * 0.50 +
        text_match * 0.20 +
        recency * 0.20 +
        popularity * 0.10
    )

def fetch_unlock_counts(db, target_type, ids):
    if not ids:
        return {}
    rows = (
        db.query(Unlock.target_id, func.count(Unlock.id))
        .filter(Unlock.target_type == target_type, Unlock.target_id.in_(ids))
        .group_by(Unlock.target_id)
        .all()
    )
    return {target_id: count for target_id, count in rows}

def apply_common_filters(items, *, same_country=None, max_km=None, origin=None):
    if not items:
        return []
    out = []
    for item in items:
        if same_country:
            country_val = (getattr(item, "country", "") or "").strip().lower()
            if country_val and country_val != same_country:
                continue
        if max_km is not None and origin:
            lat = getattr(item, "latitude", None)
            lon = getattr(item, "longitude", None)
            if not within_distance(origin[0], origin[1], lat, lon, max_km):
                continue
        out.append(item)
    return out

def compute_relevance(item, required_skills, text_query, created_at, unlock_counts, now, text_fields):
    if not required_skills:
        skill_similarity = 0.0
    else:
        item_skill_ids = {s.id for s in getattr(item, "skills", [])}
        matched = len(item_skill_ids & required_skills)
        skill_similarity = matched / max(len(required_skills), 1)

    text_match = 0
    if text_query:
        all_text = " ".join(filter(None, text_fields(item)))
        if text_query.lower() in all_text.lower():
            text_match = 1

    rec = recency_factor(now, created_at)
    unlock_count = unlock_counts.get(item.id, 0)
    popularity = min(unlock_count / 50, 1.0)
    total = compute_weighted_score(skill_similarity, text_match, rec, popularity)

    breakdown = {
        "total": total,
        "skill": skill_similarity * 0.50,
        "text": text_match * 0.20,
        "recency": rec * 0.20,
        "popularity": popularity * 0.10,
        "skill_factor": skill_similarity,
        "text_factor": text_match,
        "recency_factor": rec,
        "popularity_factor": popularity,
        "unlock_count": unlock_count,
    }
    return total, breakdown

def check_profile_completion(user, profile, company):
    missing_fields = []
    edit_target = "profile"

    if user.role == UserRole.consultant:
        if not profile:
            return
        if not (profile.headline or "").strip():
            missing_fields.append("Headline")
        if profile.years_experience is None:
            missing_fields.append("Years of experience")
        if not (profile.location_city or "").strip():
            missing_fields.append("City")
        if not (profile.country or "").strip():
            missing_fields.append("Country")
        if not profile.skills:
            missing_fields.append("Skills")
            edit_target = "skills"
        if not profile.profile_image:
            missing_fields.append("Profile Picture")
        if not profile.cv_document:
            missing_fields.append("CV Document")
        if not (profile.display_name_masked or "").strip():
            missing_fields.append("Full Name")
        if missing_fields:
            fields_str = ", ".join(missing_fields)
            flash(
                f"Your profile is incomplete! Please update the following details for better matching: {fields_str}.",
                f"warning-link-{edit_target}",
            )

    elif user.role == UserRole.company:
        if not company:
            return
        if not (company.company_name_masked or "").strip():
            missing_fields.append("Company Name")
        if not (company.location_city or "").strip():
            missing_fields.append("City")
        if not (company.country or "").strip():
            missing_fields.append("Country")
        if missing_fields:
            fields_str = ", ".join(missing_fields)
            flash(
                f"Your company profile is incomplete! Please update the following details: {fields_str}.",
                "warning-link-profile",
            )

def save_job_from_form(job, form, db):
    job.title = form.get("title")
    job.description = form.get("description")
    job.location_city = form.get("location_city")
    job.country = form.get("country")
    job.contract_type = form.get("contract_type")
    job.latitude, job.longitude = geocode_with_mapbox(job.location_city, job.country)
    skill_ids = [int(x) for x in form.getlist("skills")]
    job.skills = db.query(Skill).filter(Skill.id.in_(skill_ids)).all() if skill_ids else []

def start_collab(db, consultant, company, job=None):
    collab = Collaboration(
        company_id=company.id,
        consultant_id=consultant.id,
        job_post_id=job.id if job else None,
        status=CollaborationStatus.active,
    )
    db.add(collab)
    consultant.availability = False
    consultant.current_company_id = company.id
    if job:
        job.is_active = False
        job.hired_consultant_id = consultant.id

# ------------------ HOME / AUTH ------------------

@main.route("/company/jobs", methods=["GET"])
def company_jobs_list():
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
                or_(JobPost.title.ilike(f"%{q}%"), JobPost.description.ilike(f"%{q}%"))
            )
        jobs = query.order_by(JobPost.created_at.desc()).all()
        return render_template(
            "job_list.html",
            jobs=jobs,
            user=user,
            skills=[],
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
        if requested_role == UserRole.admin and admin_code_input != os.getenv("ADMIN_CODE"):
            flash(_("Invalid admin code."))
            return redirect(url_for("main.login"))
        with get_session() as db:
            user = db.query(User).filter(User.username == username).first()
            if user:
                if user.role == requested_role:
                    session["user_id"] = user.id
                    session["role"] = user.role.value
                    flash(_(f"Welcome back, {username}."))
                    return redirect(url_for("main.dashboard"))
                flash(_("This username already exists and is linked to another role."))
                return redirect(url_for("main.login"))
            user = User(username=username, role=requested_role)
            db.add(user)
            db.flush()
            if requested_role == UserRole.consultant:
                db.add(
                    ConsultantProfile(
                        user_id=user.id,
                        display_name_masked=username,
                        availability=True,
                        created_at=datetime.utcnow(),
                    )
                )
            elif requested_role == UserRole.company:
                db.add(
                    Company(
                        user_id=user.id,
                        company_name_masked=username,
                        created_at=datetime.utcnow(),
                    )
                )
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
        profile = company = None
        company_jobs = []
        company_active_collaborations = []
        consultant_active_collaborations = []
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

# ------------------ CONSULTANT PROFILE & SKILLS ------------------

@main.route("/consultant/edit", methods=["GET", "POST"])
def edit_consultant_profile():
    with get_session() as db:
        user = get_current_user(db)
        if not user or user.role != UserRole.consultant:
            flash("Only consultants can edit their profile")
            return redirect(url_for("main.dashboard"))
        profile = db.query(ConsultantProfile).filter(ConsultantProfile.user_id == user.id).first()
        if request.method == "POST":
            profile.display_name_masked = request.form.get("display_name")
            profile.location_city = request.form.get("location_city")
            profile.country = request.form.get("country")
            profile.headline = request.form.get("headline")
            profile.contact_email = request.form.get("contact_email")
            profile.phone_number = request.form.get("phone_number")
            years_experience_raw = (request.form.get("years_experience") or "").strip()
            try:
                profile.years_experience = int(years_experience_raw) if years_experience_raw else None
            except ValueError:
                profile.years_experience = None
            availability_value = request.form.get("availability_status", "available")
            was_available_before = profile.availability
            profile.availability = availability_value == "available"
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
            lat, lon = geocode_with_mapbox(profile.location_city, profile.country)
            profile.latitude = lat
            profile.longitude = lon
            bucket_name = os.getenv("SUPABASE_BUCKET_NAME", "iconsult-assets")
            file = request.files.get("profile_image")
            if file and file.filename:
                public_url = upload_file_to_bucket(file, bucket_name, folder="profile_images")
                if public_url:
                    profile.profile_image = public_url
                else:
                    flash(_("Failed to upload profile image."), "error")
            cv_file = request.files.get("cv_document")
            if cv_file and cv_file.filename:
                public_url = upload_file_to_bucket(cv_file, bucket_name, folder="cv_documents")
                if public_url:
                    profile.cv_document = public_url
                else:
                    flash(_("Failed to upload CV."), "error")
            db.commit()
            flash("Profile updated successfully")
            return redirect(url_for("main.dashboard"))
        return render_template("edit_consultant_profile.html", profile=profile, UserRole=UserRole)

@main.route("/consultant/skills/edit", methods=["GET", "POST"])
def edit_consultant_skills():
    with get_session() as db:
        user = get_current_user(db)
        if not user or user.role != UserRole.consultant:
            flash(_("Only consultants can update their skills"))
            return redirect(url_for("main.dashboard"))
        profile = db.query(ConsultantProfile).filter(ConsultantProfile.user_id == user.id).first()
        if request.method == "POST":
            selected_ids = list(map(int, request.form.getlist("skills")))
            profile.skills = db.query(Skill).filter(Skill.id.in_(selected_ids)).all() if selected_ids else []
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
        profile = db.query(ConsultantProfile).filter(ConsultantProfile.id == profile_id).first()
        if not profile:
            flash(_("Consultant not found"))
            return redirect(url_for("main.consultants_list"))
        user = get_current_user(db)
        is_owner = user and user.id == profile.user_id
        is_unlocked_status = False
        if user:
            is_unlocked_status = is_unlocked(db, user.id, UnlockTarget.consultant, profile_id)
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

# ------------------ CONSULTANTS LIST (COMPANY) ------------------

@main.route("/consultants", methods=["GET"])
def consultants_list():
    with get_session() as db:
        user = get_current_user(db)
        if not user or user.role != UserRole.company:
            flash(_("Only companies can browse consultant profiles."))
            return redirect(url_for("main.dashboard"))

        sort_by = request.args.get("sort_by", "relevance")
        query_skills = list(map(int, request.args.getlist("skills") or []))
        city = request.args.get("city")
        country = request.args.get("country")
        text_query = request.args.get("q", None)
        min_experience_raw = (request.args.get("min_experience") or "").strip()
        min_experience = int(min_experience_raw) if min_experience_raw.isdigit() else None
        max_distance_raw = (request.args.get("max_distance_km", "") or "").strip()
        max_distance_km = float(max_distance_raw) if max_distance_raw.replace(".", "", 1).isdigit() else None
        same_country_only = request.args.get("same_country_only") == "1"
        selected_job_id = request.args.get("job_id", type=int)

        company_profile = db.query(Company).filter_by(user_id=user.id).first()
        required_job = None
        required_skill_ids = set()
        company_jobs = []

        if company_profile:
            company_jobs = (
                db.query(JobPost)
                .filter(JobPost.company_id == company_profile.id)
                .order_by(JobPost.created_at.desc())
                .all()
            )
            if selected_job_id:
                required_job = next((job for job in company_jobs if job.id == selected_job_id), None)
            if not required_job and company_jobs:
                required_job = company_jobs[0]
            if required_job:
                required_skill_ids = {s.id for s in required_job.skills}

        if not required_job and sort_by == "relevance":
            flash(
                _(
                    "First, create a Job Post (or select one) to enable the IConsult relevance filter based on your needs."
                )
            )

        company_country = (
            (company_profile.country or "").strip().lower()
            if company_profile and company_profile.country
            else None
        )

        origin_lat = origin_lon = None
        if max_distance_km is not None and required_job:
            origin_lat, origin_lon = required_job.latitude, required_job.longitude
            if (origin_lat is None or origin_lon is None) and required_job.location_city and required_job.country:
                origin_lat, origin_lon = ensure_geocoded(required_job)

        query = (
            db.query(ConsultantProfile)
            .options(joinedload(ConsultantProfile.user))
            .filter(ConsultantProfile.availability == True)
        )

        if min_experience is not None:
            query = query.filter(ConsultantProfile.years_experience >= min_experience)

        if sort_by != "relevance":
            if city:
                query = query.filter(ConsultantProfile.location_city.ilike(f"%{city}%"))
            if country:
                query = query.filter(ConsultantProfile.country.ilike(f"%{country}%"))
            for skill_id in query_skills:
                query = query.filter(ConsultantProfile.skills.any(Skill.id == skill_id))

        consultants = query.all()

        # apply common filters: same country + distance
        same_country = company_country if same_country_only else None
        origin = (origin_lat, origin_lon) if origin_lat is not None and origin_lon is not None else None
        consultants = apply_common_filters(consultants, same_country=same_country, max_km=max_distance_km, origin=origin)

        unlocked_profile_ids = set()
        if user and user.role == UserRole.company:
            unlocked_profile_ids = query_unlocked_ids(db, user.id, UnlockTarget.consultant)
        for consultant in consultants:
            consultant.is_unlocked_for_me = consultant.id in unlocked_profile_ids

        if sort_by == "relevance" and required_job:
            now = datetime.now(timezone.utc)
            consultant_ids = [c.id for c in consultants]
            unlock_counts = fetch_unlock_counts(db, UnlockTarget.consultant, consultant_ids)

            def text_fields(profile):
                return [
                    profile.display_name_masked,
                    profile.headline,
                    profile.location_city,
                    profile.country,
                ]

            for consultant in consultants:
                total, breakdown = compute_relevance(
                    consultant,
                    required_skill_ids,
                    text_query,
                    consultant.created_at,
                    unlock_counts,
                    now,
                    text_fields,
                )
                consultant.score = total
                consultant.score_breakdown = breakdown

            consultants = sorted(consultants, key=lambda c: c.score, reverse=True)

        elif sort_by == "title":
            consultants = sorted(
                consultants,
                key=lambda c: c.display_name_masked or c.user.username,
            )

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
            company.industries = ", ".join(request.form.getlist("industries"))
            db.add(company)
            db.commit()
            flash(_("Company profile updated"))
            return redirect(url_for("main.dashboard"))
        return render_template("edit_company_profile.html", company=company)

# ------------------ UNLOCK ROUTES ------------------

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
        else:
            db.add(Unlock(user_id=user.id, target_type=UnlockTarget.consultant, target_id=profile_id))
            db.commit()
            flash(_("Contact details successfully released!"), "success")
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
        else:
            db.add(Unlock(user_id=user.id, target_type=UnlockTarget.job, target_id=job_id))
            db.commit()
            flash(_("Contact details successfully released!"), "success")
        return redirect(url_for("main.job_detail", job_id=job_id))

# ------------------ COLLABORATIONS ------------------

@main.route("/consultant/<int:profile_id>/collaborate", methods=["POST"])
@login_required
def collaborate_with_consultant(profile_id):
    with get_session() as db:
        user = get_current_user(db)
        if not user or user.role != UserRole.company:
            flash(_("Only companies can start a collaboration with a consultant."), "error")
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
        if not is_unlocked(db, user.id, UnlockTarget.consultant, profile_id):
            flash(_("First unlock this consultant before starting a collaboration."), "error")
            return redirect(url_for("main.consultant_detail", profile_id=profile_id))
        start_collab(db, profile, company, job=None)
        db.commit()
        flash(
            _(
                "You are now collaborating with this consultant. They have been marked as unavailable."
            ),
            "success",
        )
        return redirect(url_for("main.consultant_detail", profile_id=profile_id))

@main.route("/jobs/<int:job_id>/collaborate", methods=["POST"])
@login_required
def collaborate_on_job(job_id):
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
        if not is_unlocked(db, user.id, UnlockTarget.job, job_id):
            flash(_("First unlock this job before starting a collaboration."), "error")
            return redirect(url_for("main.job_detail", job_id=job_id))
        start_collab(db, profile, job.company, job=job)
        company_user_id = job.company.user_id if job.company else None
        if company_user_id and not is_unlocked(db, company_user_id, UnlockTarget.consultant, profile.id):
            db.add(
                Unlock(
                    user_id=company_user_id,
                    target_type=UnlockTarget.consultant,
                    target_id=profile.id,
                )
            )
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
        if not user or user.role != UserRole.consultant:
            flash(_("Only consultants can browse job posts."))
            return redirect(url_for("main.dashboard"))

        sort_by = request.args.get("sort_by", "relevance")
        query_skills = list(map(int, request.args.getlist("skills") or []))
        city = request.args.get("city")
        country = request.args.get("country")
        contract_type = request.args.get("contract_type")
        text_query = request.args.get("q", None)

        max_distance_raw = (request.args.get("max_distance_km", "") or "").strip()
        max_distance_km = float(max_distance_raw) if max_distance_raw.replace(".", "", 1).isdigit() else None
        ignore_distance = request.args.get("ignore_distance") == "1"
        same_country_only = request.args.get("same_country_only") == "1"

        consultant_profile = (
            db.query(ConsultantProfile)
            .filter(ConsultantProfile.user_id == user.id)
            .first()
        )

        consultant_skill_ids = {s.id for s in (consultant_profile.skills if consultant_profile else [])}
        consultant_lat = getattr(consultant_profile, "latitude", None) if consultant_profile else None
        consultant_lon = getattr(consultant_profile, "longitude", None) if consultant_profile else None
        consultant_country = (
            (consultant_profile.country or "").strip().lower()
            if consultant_profile and consultant_profile.country
            else None
        )

        query = (
            db.query(JobPost)
            .options(joinedload(JobPost.company))
            .filter(JobPost.is_active == True)
        )

        if contract_type:
            query = query.filter(JobPost.contract_type == contract_type)

        if sort_by != "relevance":
            if city:
                query = query.filter(JobPost.location_city.ilike(f"%{city}%"))
            if country:
                query = query.filter(JobPost.country.ilike(f"%{country}%"))
            for skill_id in query_skills:
                query = query.filter(JobPost.skills.any(Skill.id == skill_id))

        jobs = query.all()

        # apply common filters: same country + distance
        same_country = consultant_country if same_country_only else None
        origin = None
        if not ignore_distance and consultant_lat is not None and consultant_lon is not None:
            origin = (consultant_lat, consultant_lon)
        jobs = apply_common_filters(jobs, same_country=same_country, max_km=max_distance_km if not ignore_distance else None, origin=origin)

        job_ids_unlocked_by_user = set()
        if user and user.role == UserRole.consultant:
            job_ids_unlocked_by_user = query_unlocked_ids(db, user.id, UnlockTarget.job)
        for job in jobs:
            job.is_unlocked_for_me = job.id in job_ids_unlocked_by_user

        if sort_by == "relevance":
            now = datetime.now(timezone.utc)
            job_ids = [j.id for j in jobs]
            unlock_counts = fetch_unlock_counts(db, UnlockTarget.job, job_ids)

            def text_fields(job):
                return [
                    job.title,
                    job.description,
                    job.location_city,
                    job.country,
                    job.contract_type,
                ]

            for job in jobs:
                total, breakdown = compute_relevance(
                    job,
                    consultant_skill_ids,
                    text_query,
                    job.created_at,
                    unlock_counts,
                    now,
                    text_fields,
                )
                job.score = total
                job.score_breakdown = breakdown

            jobs = sorted(jobs, key=lambda j: j.score, reverse=True)

        elif sort_by == "title":
            jobs = sorted(jobs, key=lambda j: j.title or "")

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
            if not request.form.get("title"):
                flash(_("Title is required"))
                return redirect(url_for("main.job_new"))
            job = JobPost(company_id=company.id)
            save_job_from_form(job, request.form, db)
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
        possible_contract_types = [
            ("Freelance", _("Freelance")),
            ("Full-time", _("Full-time")),
            ("Part-time", _("Part-time")),
            ("Project-based", _("Project-based")),
        ]
        if request.method == "POST":
            save_job_from_form(job, request.form, db)
            db.commit()
            flash(_("Job updated!"))
            return redirect(url_for("main.job_detail", job_id=job.id))
        return render_template(
            "job_edit.html",
            job=job,
            skills=all_skills,
            possible_contract_types=possible_contract_types,
        )

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

# ------------------ ADMIN ------------------

@main.route("/admin/consultants")
@login_required
@admin_required
def admin_consultants():
    q = request.args.get("q", "").lower()
    with get_session() as db:
        consultants = db.query(ConsultantProfile).all()
    if q:
        consultants = [
            c for c in consultants
            if (c.display_name_masked or "").lower().find(q) != -1
        ]
    return render_template("admin_consultants.html", consultants=consultants)

@main.route("/admin/companies")
@login_required
@admin_required
def admin_companies():
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
            if (c.company_name_masked or "").lower().find(q) != -1
        ]
    return render_template(
        "admin_companies.html",
        companies=companies,
        jobs_by_company=jobs_by_company,
    )

@main.route("/admin/collaborations")
@login_required
@admin_required
def admin_collaborations():
    q = request.args.get("q", "").lower()
    with get_session() as db:
        query = db.query(Collaboration).order_by(Collaboration.started_at.desc())
        if q:
            query = (
                query.join(Collaboration.consultant)
                .join(Collaboration.company)
                .outerjoin(Collaboration.job_post)
                .filter(
                    or_(
                        func.lower(ConsultantProfile.display_name_masked).like(f"%{q}%"),
                        func.lower(Company.company_name_masked).like(f"%{q}%"),
                        func.lower(JobPost.title).like(f"%{q}%"),
                    )
                )
            )
        collaborations = query.all()
        return render_template(
            "admin_collaborations.html",
            collaborations=collaborations,
            q=q,
        )

@main.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")
