import os

from django.core.wsgi import get_wsgi_application
from waitress import serve


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

application = get_wsgi_application()


if __name__ == "__main__":
    serve(application, host="127.0.0.1", port=8000, threads=8)
