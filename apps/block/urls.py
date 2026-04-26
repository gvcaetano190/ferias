from django.urls import path

from apps.block.views import executar, executar_operacional, index, preview, testar_bloqueio, testar_desbloqueio, verification_modal


urlpatterns = [
    path("", index, name="index"),
    path("executar/", executar, name="executar"),
    path("executar-operacional/", executar_operacional, name="executar_operacional"),
    path("preview/", preview, name="preview"),
    path("verification-modal/", verification_modal, name="verification_modal"),
    path("teste/bloqueio/", testar_bloqueio, name="testar_bloqueio"),
    path("teste/desbloqueio/", testar_desbloqueio, name="testar_desbloqueio"),
]
