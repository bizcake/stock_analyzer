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
        """네이버 금융 차트 링크 반환"""
        actual_exchange = self.exchange.upper() if self.exchange else ''
        
        if self.market == 'COIN':
            clean_ticker = self.ticker.replace("-USD", "").replace("KRW-", "")
            return f"https://m.stock.naver.com/fchart/crypto/UPBIT/{clean_ticker}"
        elif self.market in ['KR', 'KOSPI', 'KOSDAQ']:
            code = self.ticker.split('.')[0]
            return f"https://m.stock.naver.com/fchart/domestic/stock/{code}"
        else:
            if actual_exchange == 'NASDAQ':
                return f"https://m.stock.naver.com/fchart/foreign/stock/{self.ticker}.O"
            else:
                return f"https://m.stock.naver.com/fchart/foreign/stock/{self.ticker}"
    
# 2. 내가 대시보드에 등록한 관심 종목
class MyTrackedStock(models.Model):
    stock = models.ForeignKey(StockMaster, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.stock.name_kr

# 3. 매일 분석된 결과 저장 (버튼 누를 때마다 수집 방지)
class StockAnalysisLatest(models.Model):
    # OneToOneField: 종목당 무조건 1개의 레코드만 존재
    stock = models.OneToOneField('StockMaster', on_delete=models.CASCADE, related_name='latest_analysis')
    
    t_signal = models.CharField(max_length=10, default='gray')
    n_signal = models.CharField(max_length=10, default='gray')
    c_signal = models.CharField(max_length=10, default='gray')
    p_code = models.CharField(max_length=10, default='p04', verbose_name="패턴 코드")
    p_name = models.CharField(max_length=50, default='대기중')
    up_days = models.IntegerField(default=0)
    signal_code = models.CharField(max_length=10, default='d01', verbose_name="공통 코드") 

    updated_at = models.DateTimeField(auto_now=True) # 업데이트 시간

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
        # 한 종목당 같은 날짜의 데이터는 1개만 존재하도록 강제 (중복 방지)
        unique_together = ('stock', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"[히스토리] {self.stock.ticker} ({self.date})"
    
class SignalCode(models.Model):
    code = models.CharField(max_length=10, primary_key=True, verbose_name="시그널 코드")
    name = models.CharField(max_length=50, verbose_name="시그널 명칭")
    description = models.CharField(max_length=200, verbose_name="의미 및 설명")

    def __str__(self):
        return f"[{self.code}] {self.name}"