from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .services import ReportService

@login_required
def dashboard(request):
    service = ReportService()
    
    # Extrai filtro do request
    period = request.GET.get("period")
    month, year = None, None
    if period and "_" in period:
        month, year = map(int, period.split("_"))
    
    dept_data = service.get_department_impact_data(month=month, year=year)
    pico_data = service.get_vacation_pico_data(month=month, year=year)
    
    summary = service.get_period_summary(month=month, year=year)

    context = {
        "pico_data": pico_data,
        "dept_data": dept_data,
        "total_saiu": summary["total_saiu"],
        "ja_voltou": summary["ja_voltou"],
        "ainda_fora": summary["ainda_fora"],
        "periods": service.get_available_periods(),
        "selected_period": period,
    }
    
    if request.headers.get("HX-Request"):
        return render(request, "reports/partials/dashboard_content.html", context)
        
    return render(request, "reports/dashboard.html", context)
