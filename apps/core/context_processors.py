from apps.core.models import OperationalSettings


def global_settings(request):
    return {"operational_settings": OperationalSettings.get_solo()}
