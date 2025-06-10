import os
from app import app, db

# Manuelles Setzen der Umgebungsvariablen für die Datenbank-URL,
# falls die app.py sie nicht sofort aus os.environ.get() liest
# (Dies ist eine Sicherheitsmaßnahme, falls Render sie nicht früh genug bereitstellt)
if "DATABASE_URL" in os.environ and not app.config.get("SQLALCHEMY_DATABASE_URI"):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]

# Sicherstellen, dass Flask den Anwendungskontext erkennt
with app.app_context():
    print("Attempting to create database tables if they don't exist...")
    db.create_all()
    print("Database table creation process completed.")

print("DB initialization script finished.")