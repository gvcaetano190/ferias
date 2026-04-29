from __future__ import annotations

import uuid

from django import forms

from apps.totvs.credentials import TotvsCredentialStore
from apps.totvs.models import TotvsIntegrationConfig


class TotvsIntegrationConfigAdminForm(forms.ModelForm):
    credential_username = forms.CharField(
        label="Usuario tecnico TOTVS",
        required=False,
        help_text="Nao sera salvo em texto puro no banco.",
    )
    credential_password = forms.CharField(
        label="Senha tecnica TOTVS",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Nao sera salvo em texto puro no banco.",
    )

    class Meta:
        model = TotvsIntegrationConfig
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.credential_store = TotvsCredentialStore()

    def clean(self):
        cleaned_data = super().clean()
        username = (cleaned_data.get("credential_username") or "").strip()
        password = cleaned_data.get("credential_password") or ""
        has_existing = bool(self.instance.pk and self.instance.credential_key)

        if username and not password:
            self.add_error("credential_password", "Informe a senha junto com o usuario.")
        if password and not username:
            self.add_error("credential_username", "Informe o usuario junto com a senha.")
        if not has_existing and (not username or not password):
            raise forms.ValidationError(
                "Cadastre usuario e senha tecnicos na primeira configuracao TOTVS."
            )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        username = (self.cleaned_data.get("credential_username") or "").strip()
        password = self.cleaned_data.get("credential_password") or ""

        if not instance.credential_key:
            instance.credential_key = f"totvs-{uuid.uuid4().hex}"

        if commit:
            instance.save()

        if username and password:
            self.credential_store.save(
                credential_key=instance.credential_key,
                username=username,
                password=password,
            )
        return instance
