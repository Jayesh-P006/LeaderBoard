"""
WSGI entry point.

    flask run                       # development
    gunicorn "app:create_app()" -w 4 -b 0.0.0.0:5000  # production
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
