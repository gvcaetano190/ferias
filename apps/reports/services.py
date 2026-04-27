from django.db.models import Count, Q
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone
from apps.people.models import Ferias, Colaborador
from datetime import date, timedelta

class ReportService:

    def _build_period_query(self, month, year):
        """
        Retorna a query correta dependendo se o mês é passado ou atual/futuro.

        REGRA DE NEGÓCIO:
        - Mês PASSADO: conta apenas quem INICIOU as férias naquele mês (data_saida no mês).
          Ex: Março mostra só os 3 que saíram em Março, não quem veio de Fevereiro.
        - Mês ATUAL ou FUTURO: usa interseção, capturando também resíduos
          de meses anteriores que ainda estão de férias.
          Ex: Abril mostra quem saiu em Abril + os 3 de Março que ainda estão fora.
        """
        import calendar
        today = timezone.now().date()
        _, last_day = calendar.monthrange(year, month)
        start_month = date(year, month, 1)
        end_month = date(year, month, last_day)

        # Mês passado (já encerrado completamente)
        if end_month < today.replace(day=1):
            # Estrito: só quem COMEÇOU neste mês
            return Q(data_saida__year=year, data_saida__month=month)
        else:
            # Atual ou futuro: interseção (pega resíduos de meses anteriores)
            return Q(data_saida__lte=end_month) & Q(data_retorno__gte=start_month)

    def get_vacation_pico_data(self, month=None, year=None):
        """
        Retorna a contagem de pessoas em férias por semana.
        """
        today = timezone.now().date()
        query = Q()

        if month and year:
            query &= self._build_period_query(month, year)
        else:
            six_months_later = today + timedelta(days=180)
            query &= Q(data_saida__lte=six_months_later) & Q(data_retorno__gte=today)

        vacations = Ferias.objects.filter(query)
        data = (
            vacations.annotate(week=TruncWeek('data_saida'))
            .values('week')
            .annotate(count=Count('id'))
            .order_by('week')
        )
        result = list(data)
        labels = [d['week'].strftime('%d/%m/%y') for d in result]
        values = [d['count'] for d in result]

        # Semana com o maior número de saídas
        peak_index = values.index(max(values)) if values else 0
        peak_label = labels[peak_index] if labels else None
        peak_value = values[peak_index] if values else 0

        return {
            "labels": labels,
            "values": values,
            "peak_label": peak_label,
            "peak_value": peak_value,
        }

    def get_department_impact_data(self, month=None, year=None):
        """
        Retorna a distribuição de férias por departamento no período,
        incluindo a lista de nomes de cada colaborador.
        """
        query = Q()
        if month and year:
            query &= self._build_period_query(month, year)
        else:
            today = timezone.now().date()
            query &= Q(data_saida__lte=today, data_retorno__gte=today)

        active_vacations = Ferias.objects.filter(query).select_related('colaborador')

        # Agrupa nomes por departamento
        dept_people: dict = {}
        for ferias in active_vacations:
            dept = ferias.colaborador.departamento or "Não Definido"
            nome = ferias.colaborador.nome or "Desconhecido"
            if dept not in dept_people:
                dept_people[dept] = []
            dept_people[dept].append(nome)

        # Ordena por quantidade (maior primeiro)
        sorted_depts = sorted(dept_people.items(), key=lambda x: len(x[1]), reverse=True)

        return {
            "labels": [d[0] for d in sorted_depts],
            "values": [len(d[1]) for d in sorted_depts],
            "people": [d[1] for d in sorted_depts],  # lista de listas de nomes
        }

    def get_available_periods(self):
        """
        Retorna lista de meses/anos que possuem registros de férias.
        """
        data = (
            Ferias.objects.annotate(month=TruncMonth('data_saida'))
            .values('month')
            .distinct()
            .order_by('-month')
        )
        return [
            {"month": d['month'].month, "year": d['month'].year, "label": d['month'].strftime('%B %Y')}
            for d in data if d['month']
        ]

    def get_period_summary(self, month=None, year=None):
        """
        Retorna um resumo do mês filtrado com 3 números:
        - total_saiu: quantas pessoas INICIARAM férias naquele mês (data_saida no mês)
        - ja_voltou: desses, quantos já retornaram (data_retorno < hoje)
        - ainda_fora: desses, quantos ainda estão de férias (data_retorno >= hoje)
        """
        today = timezone.now().date()

        if month and year:
            base_query = Q(data_saida__year=year, data_saida__month=month)
        else:
            base_query = Q(data_saida__year=today.year, data_saida__month=today.month)

        base_qs = Ferias.objects.filter(base_query)

        total_saiu = base_qs.count()
        ja_voltou = base_qs.filter(data_retorno__lt=today).count()
        ainda_fora = base_qs.filter(data_retorno__gte=today).count()

        return {
            "total_saiu": total_saiu,
            "ja_voltou": ja_voltou,
            "ainda_fora": ainda_fora,
        }
