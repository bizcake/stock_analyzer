from django.contrib import admin
from django.db.models import Case, When, Value, IntegerField
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.utils.timezone import localtime

from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
# from import_export.admin import ImportExportModelAdmin
from .models import StockMaster, MyTrackedStock, SignalCode, StockAnalysisHistory, StockAnalysisLatest

class HorizontalFilterMixin:
    """
    관리자 페이지의 세로 필터를 가로 바 형태로 변경해주는 믹스인
    """
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['custom_css'] = mark_safe("""
            <style>
                #changelist.filtered { margin-right: 0 !important; }
                #changelist-filter {
                    position: static !important; width: 100% !important;
                    float: none !important; display: flex !important;
                    flex-wrap: wrap !important; background: #f8f9fa !important;
                    border: 1px solid #eee !important; margin-bottom: 15px !important;
                    padding: 10px !important; border-radius: 8px;
                }
                #changelist-filter h2 { display: none; }
                #changelist-filter h3 { 
                    margin: 0 15px 0 0 !important; font-size: 13px !important;
                    display: flex; align-items: center; color: #666;
                }
                #changelist-filter ul { 
                    display: flex !important; flex-wrap: wrap !important; 
                    margin: 0 30px 5px 0 !important; padding: 0 !important;
                    list-style: none !important; gap: 5px;
                }
                #changelist-filter li { margin: 0 !important; padding: 0 !important; }
                #changelist-filter li a {
                    padding: 3px 10px !important; border: 1px solid #ddd !important;
                    border-radius: 15px !important; background: #fff !important;
                    font-size: 12px !important; white-space: nowrap; display: block;
                }
                #changelist-filter li.selected a {
                    background: #79aec8 !important; color: white !important;
                    border-color: #79aec8 !important; font-weight: bold;
                }
                #changelist-filter li a:hover { background: #eee !important; }
                /* 🚀 --- 하단 페이징(Paginator) 깨짐 복구 CSS 추가 --- 🚀 */
                .paginator { padding-top: 10px !important; display: flex !important; align-items: center; }
                .paginator ul { 
                    display: flex !important; flex-wrap: wrap !important; gap: 4px !important; 
                    list-style: none !important; margin: 0 !important; padding: 0 !important; 
                }
                .paginator ul li { list-style: none !important; margin: 0 !important; padding: 0 !important; }
                .paginator ul li::before { content: none !important; } /* 네모 불릿 점 제거 */
            </style>
        """)
        return super().changelist_view(request, extra_context=extra_context)
    
# --- 기존 StockMaster 설정 --- (유지)
class StockMasterResource(resources.ModelResource):
    class Meta:
        model = StockMaster
        import_id_fields = ('ticker',)
        fields = ('ticker', 'name_kr', 'name_en', 'market')

@admin.register(StockMaster)
class StockMasterAdmin(HorizontalFilterMixin, admin.ModelAdmin):
    resource_class = StockMasterResource
    # 1. 목록에 표시할 컬럼 지정 (exchange 추가)
    list_display = ('ticker', 'name_kr', 'market', 'exchange')
    # 2. 목록 화면에서 셀렉트 박스로 바로 수정할 컬럼 지정
    list_editable = ('market', 'exchange') 
    # 3. 우측 필터 조건 (exchange 추가)
    list_filter = ('market', 'exchange')
    # 4. 검색 조건
    search_fields = ('ticker', 'name_kr')

# --- 1. MyTrackedStock용 리소스 정의 ---
class MyTrackedStockResource(resources.ModelResource):
    
    # 엑셀의 'ticker' 열을 읽어서 StockMaster의 ticker 필드와 매칭
    stock = fields.Field(
        column_name='ticker',
        attribute='stock',
        widget=ForeignKeyWidget(StockMaster, 'ticker')
    )

    class Meta:
        model = MyTrackedStock
        import_id_fields = ('stock',) # 티커를 기준으로 중복 체크
        fields = ('stock', 'created_at')


# --- 2. MyTrackedStock용 어드민 설정 ---
@admin.register(MyTrackedStock)
class MyTrackedStockAdmin(HorizontalFilterMixin, admin.ModelAdmin):
    
    # 관련 모델을 한 번에 가져오도록 설정 (JOIN 수행)
    list_select_related = ('stock',)

    # 목록에서 보여줄 항목
    list_display = ('get_ticker', 'get_name_kr', 'get_market', 'created_at')
    
    # 🚀 핵심 기능: 수천 개 종목 중 검색해서 선택할 수 있게 함
    autocomplete_fields = ['stock'] 
    
    # 필터 및 검색
    list_filter = ('stock__market', 'created_at')
    search_fields = ('stock__ticker', 'stock__name_kr')

    # 목록 화면에서 종목 정보를 예쁘게 보여주기 위한 메서드들
    @admin.display(ordering='stock__ticker', description='티커')
    def get_ticker(self, obj):
        return obj.stock.ticker

    @admin.display(ordering='stock__name_kr', description='종목명')
    def get_name_kr(self, obj):
        return obj.stock.name_kr

    @admin.display(ordering='stock__market', description='마켓')
    def get_market(self, obj):
        return obj.stock.market

@admin.register(SignalCode)
class SignalCodeAdmin(HorizontalFilterMixin, admin.ModelAdmin):
    # 1. 목록에 표시할 필드 (코드, 이름, 설명)
    list_display = ('code', 'name', 'description')
    
    # 2. 목록에서 바로 수정 가능하게 설정 (이름과 설명)
    list_editable = ('name', 'description')
    
    # 3. 검색 기능 (코드와 이름으로 검색 가능)
    search_fields = ('code', 'name')
    
    # 4. 한 페이지에 표시할 개수
    list_per_page = 20

    # 텍스트 영역(description)이 너무 길게 보이지 않도록 관리자 화면 최적화
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'description' in form.base_fields:
            form.base_fields['description'].widget.attrs['rows'] = 3
            form.base_fields['description'].widget.attrs['style'] = 'width: 100%;'
        return form
    
@admin.register(StockAnalysisHistory)
class StockAnalysisHistoryAdmin(HorizontalFilterMixin, admin.ModelAdmin):
    
    # 관련 모델을 한 번에 가져오도록 설정 (JOIN 수행)
    list_select_related = ('stock',)

    # 목록에서 보여줄 필드 (종목, 시그널, 분석일시 등)
    list_display = ('get_ticker', 'get_name', 'signal_code', 'date')
    
    # 우측 필터 (시그널 코드나 날짜별로 보기 편함)
    list_filter = ('signal_code', 'date', 'stock__market')
    
    # 검색 (티커나 종목명으로 이력 찾기)
    search_fields = ('stock__ticker', 'stock__name_kr')
    
    # 최신 데이터가 위로 오도록 정렬
    ordering = ('-date',)

    # 관계형 모델(StockMaster)의 필드를 가져오기 위한 메서드
    @admin.display(description='티커')
    def get_ticker(self, obj):
        return obj.stock.ticker

    @admin.display(description='종목명')
    def get_name(self, obj):
        return obj.stock.name_kr

# 1. 코드명으로 필터링하기 위한 커스텀 필터 클래스
class SignalNameFilter(admin.SimpleListFilter):
    title = '시그널 코드명'
    parameter_name = 'signal_code'

    def lookups(self, request, model_admin):
        # 🚀 .order_by('code')를 추가하여 d01, d02... 순서로 정렬
        codes = SignalCode.objects.all().order_by('code').values_list('code', 'name')
        return [(code, name) for code, name in codes]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(signal_code=self.value())
        return queryset

@admin.register(StockAnalysisLatest)
class StockAnalysisLatestAdmin(HorizontalFilterMixin, admin.ModelAdmin):
    # 관련 모델을 한 번에 가져오도록 설정 (JOIN 수행)
    list_select_related = ('stock',)
    list_display = ('get_name', 'get_signal_name','p_name', 'go_chart', 'get_updated_at')
    ordering = ('signal_code', 'p_code', '-updated_at')
    # 🚀 액션 드롭다운 및 좌측 체크박스 비활성화
    actions = None
    
    list_filter = (
        SignalNameFilter,
        'stock__market',
    )

    # 3. 티커나 종목명으로 검색 가능 (관계형 검색)
    search_fields = ('^stock__ticker', '^stock__name_kr')    
    show_full_result_count = False
    list_per_page = 50

    # 4. 🚀 핵심: 종목 선택 시 9,000개 리스트를 다 불러오지 않고 검색해서 선택
    autocomplete_fields = ['stock']
    readonly_fields = ('updated_at',)
    
    # 2. 날짜 포맷 변환 메서드 추가
    @admin.display(ordering='updated_at', description='업데이트 일시')
    def get_updated_at(self, obj):
        if obj.updated_at:
            # 로컬 타임(한국 시간)으로 변환 후 yyyy-mm-dd hh:mm 형식으로 출력
            return localtime(obj.updated_at).strftime('%Y-%m-%d %H:%M')
        return '-'
    
    # --- 코드명을 가져오기 위한 메서드 ---
    @admin.display(description='시그널 코드명')
    def get_signal_name(self, obj):
        # 해당 요청(request) 동안 한 번만 DB에서 모든 코드를 긁어와 메모리에 저장
        if not hasattr(self, '_signal_map'):
            self._signal_map = {sc.code: sc.name for sc in SignalCode.objects.all()}
        
        return self._signal_map.get(obj.signal_code, obj.signal_code)
        
    # 5. 자동 업데이트되는 시간은 읽기 전용으로 설정
    readonly_fields = ('updated_at',)

    # 관계형 모델(StockMaster)의 데이터를 가져오기 위한 헬퍼 메서드
    # @admin.display(ordering='stock__ticker', description='티커')
    # def get_ticker(self, obj):
    #     return obj.stock.ticker

    @admin.display(ordering='stock__name_kr', description='종목명')
    def get_name(self, obj):
        return obj.stock.name_kr
    
    @admin.display(description='차트 링크')
    def go_chart(self, obj):
        # StockMasterAdmin이면 obj 자체가 stock이고, 
        # StockAnalysisLatestAdmin이면 obj.stock을 참조해야 하므로 분기 처리
        stock = obj if hasattr(obj, 'market') else obj.stock
        
        market = stock.market
        actual_exchange = stock.exchange.upper() if stock.exchange else ''
        tv_base = "https://www.tradingview.com/chart/aFDVPmY7/"

        # 1. 코인 처리
        if market == 'COIN':
            clean_ticker = stock.ticker.replace("-USD", "").replace("KRW-", "")
            tv_url = f"{tv_base}?symbol=BINANCE:{clean_ticker}USDT"
            naver_url = f"https://m.stock.naver.com/fchart/crypto/UPBIT/{clean_ticker}"
            
        # 2. 한국 주식 처리
        elif market in ['KR', 'KOSPI', 'KOSDAQ']: 
            code = stock.ticker.split('.')[0]
            tv_url = f"{tv_base}?symbol=KRX:{code}"
            naver_url = f"https://m.stock.naver.com/fchart/domestic/stock/{code}"
            
        # 3. 미국 주식 처리
        else: 
            if actual_exchange == 'NASDAQ':
                tv_url = f"{tv_base}?symbol=NASDAQ:{stock.ticker}"
                naver_url = f"https://m.stock.naver.com/fchart/foreign/stock/{stock.ticker}.O"
            elif actual_exchange == 'AMEX':
                tv_url = f"{tv_base}?symbol=AMEX:{stock.ticker}"
                naver_url = f"https://m.stock.naver.com/fchart/foreign/stock/{stock.ticker}"
            else:
                tv_url = f"{tv_base}?symbol=NYSE:{stock.ticker}"
                naver_url = f"https://m.stock.naver.com/fchart/foreign/stock/{stock.ticker}"

        # HTML 버튼 렌더링
        return format_html(
            '<a href="{}" target="_blank" style="display:inline-block; padding:2px 6px; background:#2196F3; color:white; border-radius:4px; font-size:11px; text-decoration:none; margin-right:4px;"> T </a>'
            '<a href="{}" target="_blank" style="display:inline-block; padding:2px 6px; background:#00C73C; color:white; border-radius:4px; font-size:11px; text-decoration:none;"> N </a>',
            tv_url, naver_url
        )