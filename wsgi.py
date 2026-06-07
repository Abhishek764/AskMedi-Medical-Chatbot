"""Gunicorn / WSGI entrypoint."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Local dev only; production uses gunicorn (see Procfile / render.yaml).
    app.run(host="0.0.0.0", port=8080, debug=True)
