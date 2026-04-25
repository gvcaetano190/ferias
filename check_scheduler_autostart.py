import os


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
    try:
        import django

        django.setup()
        from apps.core.models import OperationalSettings

        settings = OperationalSettings.get_solo()
        print("1" if settings and settings.auto_start_scheduler_with_server else "0")
        return 0
    except Exception:
        print("0")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
