from django.contrib import admin
from django.db.models import Case, When, Value, IntegerField
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.utils.timezone import localtime

from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
# from import_export.admin import ImportExportModelAdmin
from .models import StockMaster, MyTrackedStock, SignalCode, StockAnalysisHistory, StockAnalysisLatest, StockDailyChart
from .models import StockAnalysisLatest2


# --- 기존 StockMaster 설정 --- (유지)
class StockMasterResource(resources.ModelResource):
    class Meta:
        model = StockMaster
        import_id_fields = ('ticker',)
        fields = ('ticker', 'name_kr', 'name_en', 'market')

@admin.register(StockMaster)
class StockMasterAdmin(admin.ModelAdmin):
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
class MyTrackedStockAdmin(admin.ModelAdmin):
    
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
class SignalCodeAdmin(admin.ModelAdmin):
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
class StockAnalysisHistoryAdmin(admin.ModelAdmin):
    
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

    # 🚀 필터를 드롭다운으로 변경
    list_filter_dropdown = True

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
        # 🚀 .order_by('code')로 정렬하고, 'p'로 시작하는 봉 시그널은 필터에서 제외
        codes = SignalCode.objects.exclude(code__startswith='p').order_by('code').values_list('code', 'name')
        return [(code, name) for code, name in codes]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(signal_code=self.value())
        return queryset

# 1. 보유 여부로 필터링하기 위한 커스텀 필터 클래스
class TrackedFilter(admin.SimpleListFilter):
    title = '보유 여부'
    parameter_name = 'is_tracked'

    def lookups(self, request, model_admin):
        return [
            ('yes', '내 보유 종목'),
            ('no', '그 외 종목'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(stock__mytrackedstock__isnull=False).distinct()
        if self.value() == 'no':
            return queryset.filter(stock__mytrackedstock__isnull=True)
        return queryset

@admin.register(StockAnalysisLatest)
class StockAnalysisLatestAdmin(admin.ModelAdmin):
    change_list_template = 'admin/change_list2.html'
    # 관련 모델을 한 번에 가져오도록 설정 (JOIN 수행)
    list_select_related = ('stock',)
    list_display = ('get_name', 'get_signal_name','p_name', 'go_chart')
    # , 'get_updated_at'
    ordering = ('signal_code', 'p_code', 'p_name', '-updated_at')
    # 🚀 액션 드롭다운 및 좌측 체크박스 비활성화
    actions = None

    list_filter = (
        TrackedFilter, # 🚀 여기에 커스텀 보유 필터 추가
        'stock__market',
    )

    # 🚀 Jazzmin 기능으로 필터를 드롭다운으로 변경
    # (기존 HorizontalFilterMixin의 자바스크립트 기능을 대체합니다)
    list_filter_dropdown = True

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

    @admin.display(ordering='stock__name_kr', description='종목명')
    def get_name(self, obj):
        return obj.stock.name_kr
    
    @admin.display(description='차트 링크')
    def go_chart(self, obj):
        # StockMasterAdmin이면 obj 자체가 stock이고, 
        # StockAnalysisLatestAdmin이면 obj.stock을 참조해야 하므로 분기 처리
        stock = obj if hasattr(obj, 'market') else obj.stock

        # HTML 버튼 렌더링
        return format_html(
            '<a href="{}" target="_blank" style="display:inline-block; padding:2px 6px; background:#2196F3; color:white; border-radius:4px; font-size:11px; text-decoration:none; margin-right:4px;"> T </a>'
            '<a href="{}" target="_blank" style="display:inline-block; padding:2px 6px; background:#00C73C; color:white; border-radius:4px; font-size:11px; text-decoration:none;"> N </a>',
            stock.tv_url, stock.naver_url
        )
    
@admin.register(StockAnalysisLatest2)
class StockAnalysisLatest2Admin(admin.ModelAdmin):
    change_list_template = 'admin/change_list2.html'

    list_select_related = ('stock', 'signal_code')

    actions             = None
    list_filter_dropdown = True
    show_full_result_count = False
    list_per_page       = 50

    list_display = (
        'get_name_kr',
        'signal_display',
        'change_rate_display',
        'vol_ratio',
        'go_chart',
    )

    list_filter = (
        'signal_code',       # ✅ SignalCode2 FK 그대로 사용
        'stock__market',
    )
    search_fields = ('stock__ticker', 'stock__name_kr', 'signal')
    ordering      = ('signal_code', '-analyzed_date')

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('stock', 'signal_code')
        )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return [f.name for f in self.model._meta.fields]
        return ['updated_at']

    fieldsets = (
        ('기본 정보', {
            'fields': (
                'stock', 'analyzed_date', 'updated_at',
                'close_price', 'change_rate', 'volume', 'vol_ratio',
            )
        }),
        ('분석 시그널', {
            'fields': (
                'priority', 'signal_code', 'signal',
                'action', 'p_code', 'p_name', 'up_days',
                't_signal', 'n_signal', 'c_signal',
            )
        }),
        ('Supertrend / WaveTrend', {
            'classes': ('collapse',),
            'fields': (
                ('supertrend_direction', 'supertrend_value'),
                ('wt1', 'wt2', 'wt_momentum'),
                ('wt_cross_up', 'wt_cross_down', 'wt_oversold', 'wt_overbought'),
            )
        }),
        ('보조 지표', {
            'classes': ('collapse',),
            'fields': (
                ('rsi', 'mfi', 'adx'),
                ('macd', 'macd_signal', 'macd_hist'),
                ('sma5', 'sma20', 'sma120', 'deviation'),
                ('is_squeeze', 'squeeze_released', 'obv_confirmed'),
            )
        }),
    )

    @admin.display(description='종목명', ordering='stock__name_kr')
    def get_name_kr(self, obj):
        # 종목명을 이미지처럼 청록색 텍스트로 강조
        return format_html(
            '<span style="color: #00A88F; font-weight: bold;">{}</span>',
            obj.stock.name_kr
        )

    @admin.display(description='시그널 코드명', ordering='signal')
    def signal_display(self, obj):
        # 시그널 텍스트에 따라 아이콘 분기 처리
        signal_text = obj.signal if obj.signal else "대기중"
        if "매수" in signal_text:
            icon = ""
        elif "매도" in signal_text:
            icon = ""
        else:
            icon = ""
        
        return format_html('{} {}', icon, signal_text)

    # 관계형 모델 필드 및 커스텀 표시 메서드
    @admin.display(description='티커', ordering='stock__ticker')
    def get_ticker(self, obj):
        return obj.stock.ticker

    @admin.display(description='등락률', ordering='change_rate')
    def change_rate_display(self, obj):
        if obj.change_rate is None: return "-"
        color = "red" if obj.change_rate > 0 else "blue" if obj.change_rate < 0 else "black"
        return admin.utils.format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, obj.change_rate
        )
    
    @admin.display(description='차트 링크')
    def go_chart(self, obj):
        # StockMasterAdmin이면 obj 자체가 stock이고, 
        # StockAnalysisLatestAdmin이면 obj.stock을 참조해야 하므로 분기 처리
        stock = obj if hasattr(obj, 'market') else obj.stock

        # HTML 버튼 렌더링
        return format_html(
            '<a href="{}" target="_blank" style="display:inline-block; padding:2px 6px; background:#2196F3; color:white; border-radius:4px; font-size:11px; text-decoration:none; margin-right:4px;"> T </a>'
            '<a href="{}" target="_blank" style="display:inline-block; padding:2px 6px; background:#00C73C; color:white; border-radius:4px; font-size:11px; text-decoration:none;"> N </a>',
            stock.tv_url, stock.naver_url
        )

@admin.register(StockDailyChart)
class StockDailyChartAdmin(admin.ModelAdmin):
    # 1. 성능 최적화: StockMaster를 JOIN하여 가져옴
    list_select_related = ('stock',)

    # 2. 목록 뷰 구성: 일자, 종목명, 수정종가, 거래량, 차트 링크 순
    list_display = (
        'date', 
        'get_ticker',
        'get_name_kr', 
        'adj_close', 
        'get_volume',
        'go_chart'
    )

    # 3. 검색 및 필터: 대량 데이터 처리를 위해 필수
    search_fields = ('stock__ticker', 'stock__name_kr')
    list_filter = ('stock__market', 'date')
    
    # 4. 정렬: 최신 날짜가 항상 위로
    ordering = ('-date', 'stock__ticker')

    # --- 커스텀 컬럼 정의 ---

    @admin.display(description='티커', ordering='stock__ticker')
    def get_ticker(self, obj):
        return obj.stock.ticker

    @admin.display(description='종목명', ordering='stock__name_kr')
    def get_name_kr(self, obj):
        return format_html(
            '<span style="color: #00A88F; font-weight: bold;">{}</span>',
            obj.stock.name_kr
        )
    
    @admin.display(description='거래량', ordering='volume')
    def get_volume(self, obj):
        if obj.volume is None:
            return "-"
        # 1. f-string을 사용하는 방법 (가장 깔끔)
        return f"{obj.volume:,}"

    @admin.display(description='차트 링크')
    def go_chart(self, obj):
        # StockDailyChart에서 stock 객체 추출
        stock = obj.stock
        
        # 이전 UI와 동일한 버튼 스타일 적용
        return format_html(
            '<a href="{}" target="_blank" style="display:inline-block; padding:2px 6px; background:#2196F3; color:white; border-radius:4px; font-size:11px; text-decoration:none; margin-right:4px;"> T </a>'
            '<a href="{}" target="_blank" style="display:inline-block; padding:2px 6px; background:#00C73C; color:white; border-radius:4px; font-size:11px; text-decoration:none;"> N </a>',
            stock.tv_url, stock.naver_url
        )

    # 상세 페이지 읽기 전용 설정 (차트 데이터는 보통 수동 수정을 막음)
    readonly_fields = ('updated_at',) if hasattr(StockDailyChart, 'updated_at') else []