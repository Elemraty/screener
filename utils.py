import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Any, Dict, Optional
import pandas as pd
import numpy as np
from config import LOG_CONFIG, RETRY_CONFIG

# 로깅 설정
logging.basicConfig(
    level=LOG_CONFIG["level"],
    format=LOG_CONFIG["format"],
    filename=LOG_CONFIG["filename"]
)
logger = logging.getLogger(__name__)

def create_retry_session() -> requests.Session:
    """재시도 로직이 포함된 requests 세션을 생성합니다."""
    session = requests.Session()
    retry = Retry(
        total=RETRY_CONFIG["max_retries"],
        backoff_factor=RETRY_CONFIG["backoff_factor"],
        status_forcelist=RETRY_CONFIG["status_forcelist"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """딕셔너리에서 안전하게 값을 가져옵니다."""
    try:
        return data.get(key, default)
    except (AttributeError, TypeError):
        return default

def parse_amount(amount_str: str) -> float:
    """금액 문자열을 숫자로 변환합니다."""
    try:
        # 쉼표 제거
        amount_str = amount_str.replace(",", "")
        return float(amount_str)
    except (ValueError, AttributeError):
        return 0.0

def calculate_growth_rate(current: float, previous: float) -> float:
    """성장률을 계산합니다."""
    try:
        if previous == 0:
            return 0.0
        return ((current - previous) / abs(previous)) * 100
    except Exception:
        return 0.0

def normalize_data(data: pd.Series) -> pd.Series:
    """데이터를 0-1 범위로 정규화합니다."""
    try:
        if data.empty:
            return pd.Series()
        min_val = data.min()
        max_val = data.max()
        if min_val == max_val:
            return pd.Series([0.5] * len(data))
        return (data - min_val) / (max_val - min_val)
    except Exception:
        return pd.Series([0.0] * len(data))

def percentile_rank(series: pd.Series, value: float) -> float:
    """
    주어진 값의 백분위 순위를 계산합니다.
    
    Args:
        series: 비교 기준이 되는 데이터 Series
        value: 백분위 순위를 계산할 값
        
    Returns:
        0-100 사이의 백분위 값
    """
    try:
        if series.empty:
            return 50.0  # 기본값
        
        # NaN 값 제거
        clean_series = series.dropna()
        if clean_series.empty:
            return 50.0
            
        # 백분위 계산
        n_smaller = (clean_series < value).sum()
        n_equal = (clean_series == value).sum()
        n = len(clean_series)
        
        # 백분위 공식: (n_smaller + 0.5 * n_equal) / n * 100
        percentile = (n_smaller + 0.5 * n_equal) / n * 100
        return percentile
    except Exception as e:
        logger.error(f"백분위 계산 실패: {str(e)}")
        return 50.0  # 기본값

def calculate_rolling_mean(data: pd.Series, window: int) -> pd.Series:
    """이동평균을 계산합니다."""
    return data.rolling(window=window, min_periods=1).mean()

def calculate_rolling_std(data: pd.Series, window: int) -> pd.Series:
    """이동 표준편차를 계산합니다."""
    return data.rolling(window=window, min_periods=1).std()

def detect_volume_spike(volume: pd.Series, threshold: float = 2.0) -> pd.Series:
    """거래량 급증을 감지합니다."""
    mean_volume = volume.rolling(window=20, min_periods=1).mean()
    return volume > (mean_volume * threshold) 