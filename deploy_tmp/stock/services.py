import os
import json
from django.conf import settings
from .models import StockMaster, MyTrackedStock, StockAnalysisLatest, SignalCode

class StockDataService:
    @staticmethod
    def get_stock_json_data(user_name):
        master_file = os.path.join(settings.BASE_DIR, f'stocks_{user_name}.json')
        if os.path.exists(master_file):
            with open(master_file, 'r', encoding='utf-8') as f:
                return f.read(), json.load(f)
        return "", {}

    @staticmethod
    def save_stock_json_data(user_name, data):
        master_file = os.path.join(settings.BASE_DIR, f'stocks_{user_name}.json')
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def get_analysis_results(user_name):
        result_file = os.path.join(settings.BASE_DIR, f'result_{user_name}.json')
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    @staticmethod
    def save_analysis_results(user_name, results):
        result_file = os.path.join(settings.BASE_DIR, f'result_{user_name}.json')
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)

    @staticmethod
    def get_dashboard_data():
        signal_map = {sc.code: {'name': sc.name, 'desc': sc.description} for sc in SignalCode.objects.all()}
        my_stocks = MyTrackedStock.objects.select_related('stock', 'stock__latest_analysis').all()
        
        categorized_stocks = {'KR': [], 'US': [], 'COIN': []}
        for item in my_stocks:
            stock = item.stock
            analysis = getattr(stock, 'latest_analysis', None)
            code = analysis.signal_code if analysis and analysis.signal_code else 'd01'
            
            stock_data = {
                'id': stock.id,
                'name_kr': stock.name_kr,
                'ticker': stock.ticker,
                'ticker_clean': stock.ticker.split('.')[0],
                't_signal': analysis.t_signal if analysis else 'gray',
                'n_signal': analysis.n_signal if analysis else 'gray',
                'c_signal': analysis.c_signal if analysis else 'gray',
                'p_name': analysis.p_name if analysis else '대기중',
                'up_days': analysis.up_days if analysis else 0,
                'signal_code': code,
                'signal_name': signal_map.get(code, {}).get('name', 'Hold (관망)'),
                'signal_desc': signal_map.get(code, {}).get('desc', '분석 대기중입니다.'),
                'trend_url': stock.tv_url,
                'naver_url': stock.naver_url
            }
            if stock.market in categorized_stocks:
                categorized_stocks[stock.market].append(stock_data)
        
        for mkt in categorized_stocks:
            categorized_stocks[mkt].sort(key=lambda x: x['signal_code'])
            
        return categorized_stocks
