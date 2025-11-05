#companies, jobs, profiles, skills, unlocks, users

#testroute
from flask import Blueprint, jsonify, request
from .supabase_client import supabase

main = Blueprint("main", __name__)

@main.route("/")
def index():
    return "Welkom bij de Flask + Supabase app!"

@main.route("/users", methods=["GET"])
def get_users():
    users = supabase.table("users").select("*").execute()
    return jsonify(users.data)

@main.route("/users", methods=["POST"])
def create_user():
    data = request.json
    response = supabase.table("users").insert([{
        "username": data["username"],
        "role": data["role"]
    }]).execute()
    return jsonify(response.data)