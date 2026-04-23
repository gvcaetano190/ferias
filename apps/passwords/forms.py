from django import forms

from apps.shared.repositories.people import ColaboradorRepository


class PasswordShareForm(forms.Form):
    senha = forms.CharField(
        label="Senha",
        widget=forms.TextInput(attrs={"class": "mt-2 w-full rounded-xl border-slate-300"}),
    )
    nome_pessoa = forms.CharField(
        label="Pessoa",
        widget=forms.TextInput(
            attrs={
                "class": "mt-2 w-full rounded-xl border-slate-300",
                "autocomplete": "off",
                "placeholder": "Comece a digitar para buscar no banco",
            }
        ),
    )
    colaborador_id = forms.IntegerField(widget=forms.HiddenInput())
    descricao = forms.CharField(
        label="Descrição",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "mt-2 w-full rounded-xl border-slate-300"}),
    )
    ttl_seconds = forms.ChoiceField(
        label="Expiração",
        initial="604800",
        choices=[
            ("1800", "30 minutos"),
            ("3600", "1 hora"),
            ("14400", "4 horas"),
            ("86400", "24 horas"),
            ("604800", "7 dias"),
        ],
        widget=forms.Select(attrs={"class": "mt-2 w-full rounded-xl border-slate-300"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        colaborador_id = cleaned_data.get("colaborador_id")
        nome_pessoa = (cleaned_data.get("nome_pessoa") or "").strip()
        repository = ColaboradorRepository()

        if not colaborador_id:
            raise forms.ValidationError("Selecione uma pessoa da base antes de gerar o link.")

        colaborador = repository.get_by_id(colaborador_id)
        if not colaborador:
            raise forms.ValidationError("A pessoa selecionada não foi encontrada no banco.")

        cleaned_data["colaborador"] = colaborador
        cleaned_data["nome_pessoa"] = colaborador.nome
        cleaned_data["gestor_pessoa"] = colaborador.gestor or ""

        if nome_pessoa and colaborador.nome.lower() != nome_pessoa.lower():
            cleaned_data["nome_pessoa"] = colaborador.nome

        return cleaned_data


class PasswordStatusForm(forms.Form):
    confirm = forms.BooleanField(required=False, widget=forms.HiddenInput, initial=True)
