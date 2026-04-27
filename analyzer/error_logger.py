import logging
import traceback
import pandas as pd
from functools import wraps

def setup_detailed_logger(log_file="coin_analysis_error.log"):
    """파일과 콘솔에 동시에 상세 로그를 남기는 로거 설정"""
    logger = logging.getLogger("CoinAnalysisLogger")
    
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')

        # 콘솔 출력 핸들러
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # 파일 출력 핸들러
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.ERROR)  # 파일에는 ERROR 이상만 기록
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

logger = setup_detailed_logger()

def trace_exceptions(func):
    """함수 실행 중 에러 발생 시 상세 스택 트레이스와 입력값을 기록하는 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_msg = f"\n{'='*50}\n"
            err_msg += f"🚨 [에러 발생 함수]: {func.__name__}\n"
            err_msg += f"📝 [에러 메시지]: {str(e)}\n"
            err_msg += f"📦 [입력 인자]: args={args}, kwargs={kwargs}\n"
            err_msg += f"🔍 [상세 호출 스택]:\n{traceback.format_exc()}"
            err_msg += f"{'='*50}\n"
            logger.error(err_msg)
            return None # 파이프라인 중단을 막기 위해 None 반환
    return wrapper

def inspect_df_nans(df: pd.DataFrame, context_msg: str = ""):
    """DataFrame 내의 NaN 분포와 발생 위치의 실제 데이터를 출력"""
    if df.empty:
        logger.warning(f"[{context_msg}] DataFrame이 비어 있습니다.")
        return

    nan_counts = df.isna().sum()
    has_nan = nan_counts[nan_counts > 0]
    
    if not has_nan.empty:
        logger.error(f"[{context_msg}] ❌ DataFrame 컬럼별 NaN 개수:\n{has_nan}")
        # NaN이 포함된 행만 필터링하여 최근 5개 출력
        nan_rows = df[df.isna().any(axis=1)]
        logger.error(f"[{context_msg}] 🔍 NaN 포함 최신 행 데이터 (최대 5건):\n{nan_rows.tail(5)}")
    else:
        logger.debug(f"[{context_msg}] ✅ DataFrame 결측치 없음 확인 완료.")