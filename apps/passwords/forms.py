from django import forms

from apps.shared.repositories.people import ColaboradorRepository


class PasswordShareForm(forms.Form):
    share_mode = forms.ChoiceField(
        initial="password",
        choices=[
            ("password", "Senha"),
            ("secret", "Segredo livre"),
        ],
        widget=forms.HiddenInput(),
    )
    senha = forms.CharField(
        label="Senha",
        required=False,
        widget=forms.TextInput(attrs={"class": "mt-2 w-full rounded-xl border-slate-300"}),
    )
    secret_message = forms.CharField(
        label="Segredo",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "class": "mt-2 w-full rounded-xl border-slate-300",
                "placeholder": "Digite uma ou mais senhas, tokens, observações ou qualquer conteúdo sensível.",
            }
        ),
    )
    nome_pessoa = forms.CharField(
        label="Pessoa",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "mt-2 w-full rounded-xl border-slate-300",
                "autocomplete": "off",
                "placeholder": "Comece a digitar para buscar no banco",
            }
        ),
    )
    colaborador_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
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
        share_mode = cleaned_data.get("share_mode") or "password"
        colaborador_id = cleaned_data.get("colaborador_id")
        nome_pessoa = (cleaned_data.get("nome_pessoa") or "").strip()
        senha = (cleaned_data.get("senha") or "").strip()
        secret_message = (cleaned_data.get("secret_message") or "").strip()
        repository = ColaboradorRepository()

        if share_mode == "password":
            if not senha:
                self.add_error("senha", "Informe a senha para gerar o link.")
            if not colaborador_id:
                raise forms.ValidationError("Selecione uma pessoa da base antes de gerar o link.")

            colaborador = repository.get_by_id(colaborador_id)
            if not colaborador:
                raise forms.ValidationError("A pessoa selecionada não foi encontrada no banco.")

            cleaned_data["colaborador"] = colaborador
            cleaned_data["nome_pessoa"] = colaborador.nome
            cleaned_data["gestor_pessoa"] = colaborador.gestor or ""
            cleaned_data["secret_payload"] = senha
            cleaned_data["finalidade"] = "Acesso Temporário"

            if nome_pessoa and colaborador.nome.lower() != nome_pessoa.lower():
                cleaned_data["nome_pessoa"] = colaborador.nome
        else:
            if not secret_message:
                self.add_error("secret_message", "Digite o conteúdo do segredo para gerar o link.")
            cleaned_data["colaborador"] = repository.get_by_id(colaborador_id) if colaborador_id else None
            cleaned_data["gestor_pessoa"] = cleaned_data["colaborador"].gestor if cleaned_data["colaborador"] else ""
            cleaned_data["secret_payload"] = secret_message
            cleaned_data["finalidade"] = "Segredo Livre"
            if cleaned_data["colaborador"]:
                cleaned_data["nome_pessoa"] = cleaned_data["colaborador"].nome
            elif not nome_pessoa:
                cleaned_data["nome_pessoa"] = "Segredo livre"

        return cleaned_data


class PasswordStatusForm(forms.Form):
    confirm = forms.BooleanField(required=False, widget=forms.HiddenInput, initial=True)
