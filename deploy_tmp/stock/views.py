import json
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Q
from .models import StockMaster
from .constants import SIGNAL_PRIORITY
from .services import StockDataService

def stock_analysis_view(request):
    user_name = request.POST.get("user_name", "현욱").strip() if request.method == "POST" else request.GET.get("user_name", "현욱").strip()
    target_category = request.POST.get("target_category")
    
    master_json_str, stocks_to_analyze = StockDataService.get_stock_json_data(user_name)
    results = {}

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "save_json":
            new_json_data = request.POST.get("json_data")
            try:
                parsed_data = json.loads(new_json_data)
                StockDataService.save_stock_json_data(user_name, parsed_data)
                return JsonResponse({"status": "success", "message": "✅ 저장되었습니다."})
            except json.JSONDecodeError:
                return JsonResponse({"status": "error", "message": "❌ 형식이 잘못되었습니다."}, status=400)

        elif action == "analyze":
            # NOTE: Actual analysis logic is now triggered via analyzer_service or management commands.
            # This view's 'analyze' action seems to be a placeholder or uses pre-analyzed results.
            results = StockDataService.get_analysis_results(user_name)
            
            for category in results:
                if target_category and category != target_category:
                    continue
                if isinstance(results[category], list):
                    results[category].sort(key=lambda x: SIGNAL_PRIORITY.get(x.get('signal'), 99))
            
            StockDataService.save_analysis_results(user_name, results)

    else: # GET 요청
        results = StockDataService.get_analysis_results(user_name)
        for cat in results:
            if isinstance(results[cat], list):
                results[cat].sort(key=lambda x: SIGNAL_PRIORITY.get(x.get('signal'), 99))

    return render(request, 'stock/stock_analysis.html', {
        'results': results,
        'user_name': user_name,
        'master_json_str': master_json_str,
        'target_category': target_category
    })

def search_stock_api(request):
    """종목 검색 API (Ajax 용)"""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    stocks = StockMaster.objects.filter(
        Q(ticker__icontains=query) |
        Q(name_kr__icontains=query) |
        Q(name_en__icontains=query)
    )[:20]

    results = [
        {'id': s.id, 'ticker': s.ticker, 'name': s.name_kr or s.name_en, 'market': s.market}
        for s in stocks
    ]
    return JsonResponse({'results': results})

def dashboard_view(request):
    """DB에 저장된 최신 분석 결과를 바로 조회하여 전달"""
    categorized_stocks = StockDataService.get_dashboard_data()
    return render(request, 'stock/dashboard.html', {'categorized_stocks': categorized_stocks})
