from django.urls import path

from apps.block.views import executar, index, preview, testar_bloqueio, testar_desbloqueio


urlpatterns = [
    path("", index, name="index"),
    path("executar/", executar, name="executar"),
    path("preview/", preview, name="preview"),
    path("teste/bloqueio/", testar_bloqueio, name="testar_bloqueio"),
    path("teste/desbloqueio/", testar_desbloqueio, name="testar_desbloqueio"),
]
