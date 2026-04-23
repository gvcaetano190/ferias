import os

from django.core.wsgi import get_wsgi_application
from waitress import serve


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

application = get_wsgi_application()


if __name__ == "__main__":
    host = os.environ.get("DJANGO_HOST", "127.0.0.1")
    port = int(os.environ.get("DJANGO_PORT", "8000"))
    threads = int(os.environ.get("DJANGO_THREADS", "8"))
    serve(application, host=host, port=port, threads=threads)
