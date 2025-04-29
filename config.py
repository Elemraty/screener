import datetime

DART_API_KEY = "1c0d58c20bca902c71666c62da81bd5991c14ec1"  # 이 키는 예시입니다. 실제 사용시 새로운 API 키로 교체하세요.

# ───────── 종목 리스트 ─────────
SEMICONDUCTOR_STOCKS = [
    "005930",  # 삼성전자            (메모리·파운드리)
    "000660",  # SK하이닉스          (메모리)
    "000990",  # DB하이텍            (파운드리)
    "042700",  # 한미반도체          (패키징·테스트 장비)
    "336370",  # 테스나              (반도체 검사·테스트 장비)
    "357780",  # 솔브레인            (웨이퍼 세정·표면처리)
    "240810",  # 원익IPS             (웨이퍼 가공·장비)
    "104830",  # 원익머트리얼즈      (식각·증착 가스)
    "069730",  # 피에스케이(PSK)     (PCB/반도체 부품 소재)
    "033640",  # 네패스              (조립·검사 부품)
    "086390",  # 유니테스트          (반도체 테스트 장비)
    "322310",  # 오로스테크놀로지    (웨이퍼 세정·표면처리)
    "403870",  # HPSP
    "036930",  # 주성엔지니어링
    "166090",  # 하나머터리얼
    "058470",  # 리노공업
    "005290",  # 동진쌔미켐
    "140860",  # 파크시스템스
]

# ───────── SEPA 임계치 ─────────
SEPA_THRESHOLDS = {
    "sales_growth":           5.0,   # % ≥ 5
    "operating_income_growth":10.0,  # % ≥ 10
    "roe":                    8.0,   # % ≥ 8
    "debt_ratio":            150.0   # % ≤ 150
}

# ───────── 차트 & 패턴 ─────────
VCP_WINDOW       = 20    # 일
POCKET_PIVOT_VOL = 1.5   # 거래량 배수

# ───────── 가격 이력 ─────────
PRICE_HISTORY = {
    "start_date": "2020-01-01",
    "end_date": datetime.datetime.now().strftime("%Y-%m-%d")
}

# ───────── 볼린저 밴드 설정 ─────────
BOLLINGER_BANDS = {
    "window": 20,
    "std_dev": 2
}

# ───────── 로깅 설정 ─────────
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "filename": "sepa_screener.log"
}

# ───────── 재시도 설정 ─────────
RETRY_CONFIG = {
    "max_retries": 3,
    "backoff_factor": 0.5,
    "status_forcelist": [500, 502, 503, 504]
} 