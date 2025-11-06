from flask import Blueprint, request, jsonify
from app.config import db
from app.models import User, UserRole

users_bp = Blueprint("users", __name__)

@users_bp.route("/", methods=["POST"])
def create_user():
    data = request.json
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username exists"}), 400

    user = User(
        username=data["username"],
        role=UserRole(data["role"])
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"id": user.id, "username": user.username}), 201

@users_bp.route("/", methods=["GET"])
def list_users():
    users = User.query.all()
    return jsonify([
        {"id": u.id, "username": u.username, "role": u.role.value}
        for u in users
    ])
