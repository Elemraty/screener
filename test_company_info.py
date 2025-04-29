from data_fetcher import DataFetcher

def test_company_info():
    df = DataFetcher()
    print('== 회사 정보 테스트 ==')
    
    test_codes = [
        '005930',  # 삼성전자
        '000660',  # SK하이닉스
        '000990',  # DB하이텍
        '322310',  # 오로스테크놀로지
        '403870',  # HPSP
        '036930',  # 주성엔지니어링
        '166090',  # 하나머터리얼
        '058470',  # 리노공업
        '005290',  # 동진쌔미켐
        '140860',  # 파크시스템스
    ]
    
    for code in test_codes:
        info = df.get_company_info(code)
        print(f'{code}: {info.get("name", "이름 없음")}')

if __name__ == "__main__":
    test_company_info() 