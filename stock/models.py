from django.db import models
from django.utils import timezone

# 1. 전체 종목 마스터 테이블 (검색용)
class StockMaster(models.Model):
    
    INDEX_CHOICES = [
        ('K200', '코스피 200'),
        ('Q150', '코스닥 150'),
        ('N100', '나스닥 100'),
    ]
    # 1. 지수 코드 정의 (DB 저장값, 화면 표시값)
    MARKET_CHOICES = [
        ('KR', '한국 (KR)'),
        ('US', '미국 (US)'),
        ('COIN', '암호화폐 (COIN)'),
    ]
    
    EXCHANGE_CHOICES = [
        ('KOSPI', '코스피 (KOSPI)'),
        ('KOSDAQ', '코스닥 (KOSDAQ)'),
        ('NASDAQ', '나스닥 (NASDAQ)'),
        ('NYSE', '뉴욕증권거래소 (NYSE)'),
        ('AMEX', '아멕스 (AMEX)'),
        ('COIN', '암호화폐 (COIN)'),
    ]

    ticker = models.CharField(max_length=20, unique=True)
    name_kr = models.CharField(max_length=500)
    market = models.CharField(max_length=50, choices=MARKET_CHOICES)
    exchange = models.CharField(max_length=50, choices=EXCHANGE_CHOICES, null=True, blank=True)
    # 데이터가 수정될 때마다 현재 시간으로 자동 업데이트 (선택 사항)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정 일시")
    
    # 🚀 단일 컬럼으로 지수 관리 (예: 'K200', 'Q150', 'N100' 등 코드 입력)
    # index_type = models.CharField(max_length=50, blank=True, null=True, db_index=True)
# 2. choices 적용
    index_type = models.CharField(
        max_length=10, 
        choices=INDEX_CHOICES, # 미리 정의된 코드만 허용
        blank=True, 
        null=True, 
        db_index=True,
        help_text="편입된 주요 지수를 선택하세요."
    )
    class Meta:
        # ticker와 market의 조합이 유일하도록 설정
        constraints = [
            models.UniqueConstraint(
                fields=['ticker', 'market'], 
                name='unique_stock_ticker_market'
            )
        ]
    def __str__(self):
        return f"{self.ticker} ({self.name_kr})"

    @property
    def tv_url(self):
        """트레이딩뷰 차트 링크 반환"""
        tv_base = "https://www.tradingview.com/chart/aFDVPmY7/"
        actual_exchange = self.exchange.upper() if self.exchange else ''
        
        if self.market == 'COIN':
            clean_ticker = self.ticker.replace("-USD", "").replace("KRW-", "")
            return f"{tv_base}?symbol=BINANCE:{clean_ticker}USDT"
        elif self.market in ['KR', 'KOSPI', 'KOSDAQ']:
            code = self.ticker.split('.')[0]
            return f"{tv_base}?symbol=KRX:{code}"
        else:
            if actual_exchange == 'NASDAQ':
                return f"{tv_base}?symbol=NASDAQ:{self.ticker}"
            elif actual_exchange == 'AMEX':
                return f"{tv_base}?symbol=AMEX:{self.ticker}"
            else:
                return f"{tv_base}?symbol=NYSE:{self.ticker}"

    @property
    def naver_url(self):
        """네이버 금융 상세 페이지 링크 반환"""
        actual_exchange = self.exchange.upper() if self.exchange else ''
        
        if self.market == 'COIN':
            clean_ticker = self.ticker.replace("-USD", "").replace("KRW-", "")
            # 암호화폐 상세 페이지
            
            return f"https://m.stock.naver.com/crypto/UPBIT/{clean_ticker}/total"
            # return f"https://m.stock.naver.com/crypto/item/{clean_ticker}"
        elif self.market in ['KR', 'KOSPI', 'KOSDAQ']:
            code = self.ticker.split('.')[0]
            # 국내 주식 상세 페이지
            return f"https://m.stock.naver.com/domestic/stock/{code}/total"
        else:
            # 해외 주식 상세 페이지 (foreign -> worldstock)
            if actual_exchange == 'NASDAQ':
                return f"https://m.stock.naver.com/worldstock/stock/{self.ticker}.O/total"
            else:
                return f"https://m.stock.naver.com/worldstock/stock/{self.ticker}/total"
    # @property
    # def naver_url(self):
    #     """네이버 금융 차트 링크 반환"""
    #     actual_exchange = self.exchange.upper() if self.exchange else ''
        
    #     if self.market == 'COIN':
    #         clean_ticker = self.ticker.replace("-USD", "").replace("KRW-", "")
    #         return f"https://m.stock.naver.com/fchart/crypto/UPBIT/{clean_ticker}"
    #     elif self.market in ['KR', 'KOSPI', 'KOSDAQ']:
    #         code = self.ticker.split('.')[0]
    #         return f"https://m.stock.naver.com/fchart/domestic/stock/{code}"
    #     else:
    #         if actual_exchange == 'NASDAQ':
    #             return f"https://m.stock.naver.com/fchart/foreign/stock/{self.ticker}.O"
    #         else:
    #             return f"https://m.stock.naver.com/fchart/foreign/stock/{self.ticker}"

class StockDailyChart(models.Model):
    # StockMaster와의 외래키 관계 (종목 삭제 시 관련 차트 데이터도 삭제)
    stock = models.ForeignKey(
        'StockMaster', 
        on_delete=models.CASCADE, 
        related_name='daily_charts',
        to_field='ticker'  # ticker를 기준으로 관계 형성
    )
    
    date = models.DateField(verbose_name="거래 일자")
    
    # 가격 데이터 (소수점 4자리까지 허용하여 정밀도 확보)
    open_price = models.DecimalField(max_digits=20, decimal_places=4, verbose_name="시가")
    high_price = models.DecimalField(max_digits=20, decimal_places=4, verbose_name="고가")
    low_price = models.DecimalField(max_digits=20, decimal_places=4, verbose_name="저가")
    close_price = models.DecimalField(max_digits=20, decimal_places=4, verbose_name="종가")
    
    # 수정 종가 (배당, 분할 반영 - 분석 로직의 핵심 데이터)
    adj_close = models.DecimalField(max_digits=20, decimal_places=4, verbose_name="수정 종가")
    
    # 거래량 (매우 클 수 있으므로 BigInteger 사용)
    volume = models.BigIntegerField(verbose_name="거래량")

    class Meta:
        verbose_name = "일별 차트 데이터"
        verbose_name_plural = "일별 차트 데이터 목록" 
        
        constraints = [
            models.UniqueConstraint(
                fields=['stock', 'date'],
                name='unique_stock_date'
            )
        ]
        
        indexes = [
            models.Index(fields=['stock', '-date']),
            models.Index(fields=['-date']),
        ]

    def __str__(self):
        return f"{self.stock.ticker} - {self.date}"
    
# 2. 내가 대시보드에 등록한 관심 종목
class MyTrackedStock(models.Model):
    stock = models.ForeignKey(StockMaster, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.stock.name_kr

# 3. 매일 분석된 결과 저장 (버튼 누를 때마다 수집 방지)
class StockAnalysisLatest(models.Model):
    # OneToOneField: 종목당 무조건 1개의 레코드만 존재
    stock = models.OneToOneField('StockMaster', on_delete=models.CASCADE, related_name='latest_analysis2')
    
    t_signal = models.CharField(max_length=10, default='gray')
    n_signal = models.CharField(max_length=10, default='gray')
    c_signal = models.CharField(max_length=10, default='gray')
    p_code = models.CharField(max_length=10, default='p04', verbose_name="패턴 코드")
    p_name = models.CharField(max_length=50, default='대기중')
    up_days = models.IntegerField(default=0)
    signal_code = models.CharField(max_length=10, default='d01', verbose_name="공통 코드") 

    updated_at = models.DateTimeField(auto_now=True) # 업데이트 시간

    class Meta:
        verbose_name = "종목 최신 분석"
        
    def __str__(self):
        return f"[최신] {self.stock.ticker}"

class StockAnalysisLatest2(models.Model):
    # OneToOneField: 종목당 무조건 1개의 레코드만 존재
    stock = models.OneToOneField('StockMaster', on_delete=models.CASCADE, to_field='ticker' , related_name='latest_analysis')
    
    # 기준 정보
    analyzed_date = models.DateField(null=True, blank=True, verbose_name="분석 기준일")
    close_price   = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True, verbose_name="종가")
    volume        = models.BigIntegerField(null=True, blank=True, verbose_name="거래량")
    vol_ratio     = models.FloatField(null=True, blank=True, verbose_name="거래량 배수")
    change_rate   = models.FloatField(null=True, blank=True, verbose_name="등락률(%)")

    t_signal = models.CharField(max_length=10, default='gray')
    n_signal = models.CharField(max_length=10, default='gray')
    c_signal = models.CharField(max_length=10, default='gray')
    p_code = models.CharField(max_length=10, default='p04', verbose_name="패턴 코드")
    p_name = models.CharField(max_length=50, default='대기중')
    up_days = models.IntegerField(default=0)

    # 시그널
    signal_code = models.ForeignKey(
        'SignalCode2', on_delete=models.SET_DEFAULT,
        default='d01', db_column='signal_code',
        verbose_name="시그널 코드"
    )

    signal   = models.CharField(max_length=100, default='대기중', verbose_name="시그널 텍스트")
    priority = models.IntegerField(default=0, verbose_name="우선순위")
    action   = models.TextField(null=True, blank=True, verbose_name="행동 지침")

    # Supertrend
    supertrend_direction = models.IntegerField(null=True, blank=True, verbose_name="방향(1/-1)")
    supertrend_value     = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    # WaveTrend
    wt1           = models.FloatField(null=True, blank=True)
    wt2           = models.FloatField(null=True, blank=True)
    wt_cross_up   = models.BooleanField(default=False)
    wt_cross_down = models.BooleanField(default=False)
    wt_oversold   = models.BooleanField(default=False)
    wt_overbought = models.BooleanField(default=False)
    wt_momentum   = models.FloatField(null=True, blank=True)

    # 응축
    is_squeeze       = models.BooleanField(default=False)
    squeeze_released = models.BooleanField(default=False)

    # OBV
    obv_confirmed = models.BooleanField(default=False)

    # 보조지표
    rsi         = models.FloatField(null=True, blank=True)
    macd        = models.FloatField(null=True, blank=True)
    macd_signal = models.FloatField(null=True, blank=True)
    macd_hist   = models.FloatField(null=True, blank=True)
    adx         = models.FloatField(null=True, blank=True)
    mfi         = models.FloatField(null=True, blank=True)

    # 이동평균
    sma5      = models.FloatField(null=True, blank=True)
    sma20     = models.FloatField(null=True, blank=True)
    sma120    = models.FloatField(null=True, blank=True)
    deviation = models.FloatField(null=True, blank=True, verbose_name="20일선 이격도(%)")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "종목 최신 분석_v2"
        indexes = [
            models.Index(fields=['priority', 'signal_code']),
            models.Index(fields=['signal_code']),
            models.Index(fields=['is_squeeze', 'squeeze_released']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return f"[최신] {self.stock.ticker}"

# 2. 통계 및 차트용 (일별 기록)
class StockAnalysisHistory(models.Model):
    # ForeignKey: 종목당 여러 날짜의 레코드가 존재
    stock = models.ForeignKey('StockMaster', on_delete=models.CASCADE, related_name='analysis_history')
    
    date = models.DateField(db_index=True) # 기준 일자
    t_signal = models.CharField(max_length=10, default='gray')
    n_signal = models.CharField(max_length=10, default='gray')
    c_signal = models.CharField(max_length=10, default='gray')
    p_code = models.CharField(max_length=10, default='p90', verbose_name="패턴 코드")
    p_name = models.CharField(max_length=50, default='대기중')
    up_days = models.IntegerField(default=0)
    signal_code = models.CharField(max_length=10, default='d01', verbose_name="공통 코드") 

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['stock', 'date'], 
                name='unique_stock_analysis_history'
            )
        ]
        ordering = ['-date']

    def __str__(self):
        return f"[히스토리] {self.stock.ticker} ({self.date})"
    
class SignalCode(models.Model):
    code = models.CharField(max_length=10, primary_key=True, verbose_name="시그널 코드")
    name = models.CharField(max_length=50, verbose_name="시그널 명칭")
    description = models.CharField(max_length=200, verbose_name="의미 및 설명")

    def __str__(self):
        return f"[{self.code}] {self.name}"

class SignalCode2(models.Model):
    code = models.CharField(max_length=10, primary_key=True, verbose_name="시그널 코드")
    name = models.CharField(max_length=50, verbose_name="시그널 명칭")
    description = models.CharField(max_length=200, verbose_name="의미 및 설명")

    def __str__(self):
        return f"[{self.code}] {self.name}"