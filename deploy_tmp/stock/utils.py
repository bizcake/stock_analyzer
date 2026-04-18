import os
import ssl
import logging
from .constants import SIGNAL_MAP

# --- [1. 시스템 및 보안 설정] ---
logger = logging.getLogger(__name__)

def setup_ssl():
    """SSL 검증 무력화 (야후 및 AI API 통신용)"""
    os.environ['CURL_CA_BUNDLE'] = ""
    os.environ['REQUESTS_CA_BUNDLE'] = ""
    os.environ['PYTHONHTTPSVERIFY'] = '0'
    os.environ['SSL_CERT_FILE'] = ""

    try:
        ssl._create_default_https_context = ssl._create_unverified_context
    except AttributeError:
        pass

    # curl_cffi 패치
    try:
        from curl_cffi import requests as core_requests
        original_session_request = core_requests.Session.request
        def patched_request(self, method, url, *args, **kwargs):
            kwargs['verify'] = False
            return original_session_request(self, method, url, *args, **kwargs)
        core_requests.Session.request = patched_request
    except ImportError:
        pass

# 실행 시 SSL 설정 적용
setup_ssl()

def get_signal_code(final_signal):
    """신호 명칭으로 공통 코드 반환"""
    return SIGNAL_MAP.get(final_signal, "d01")
