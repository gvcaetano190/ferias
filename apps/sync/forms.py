from django import forms


class ManualSyncForm(forms.Form):
    force = forms.BooleanField(required=False, label="Forçar novo download")
