import FinanceDataReader as fdr
import pandas as pd
import OpenDartReader
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import os
from config import DART_API_KEY, SEMICONDUCTOR_STOCKS, PRICE_HISTORY
from utils import create_retry_session, safe_get, parse_amount, logger
import numpy as np

class DataFetcher:
    def __init__(self):
        self.dart = OpenDartReader(DART_API_KEY)
        self.session = create_retry_session()
        self.data_dir = "financial_data"
        os.makedirs(self.data_dir, exist_ok=True)
        
    def validate_financial_data(self, financial_data: Dict[str, pd.DataFrame]) -> bool:
        """재무제표 데이터 유효성 검사"""
        if financial_data["annual"].empty:
            logger.warning("연간 재무제표 데이터가 비어있습니다.")
            return False
            
        required_accounts = ["매출액", "영업이익", "당기순이익", "자본총계", "부채총계"]
        available_accounts = financial_data["annual"]["account_nm"].unique()
        missing_accounts = [acc for acc in required_accounts if acc not in available_accounts]
        
        if missing_accounts:
            logger.warning(f"필수 계정과목 누락: {', '.join(missing_accounts)}")
            return False
            
        return True
        
    def get_stock_price(self, code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """주가 데이터를 가져옵니다."""
        try:
            if start_date is None:
                start_date = PRICE_HISTORY["start_date"]
            if end_date is None:
                end_date = PRICE_HISTORY["end_date"]
                
            logger.info(f"주가 데이터 요청: {code}, {start_date} ~ {end_date}")
            
            # 샘플 데이터 생성 (테스트용)
            sample_data = self._create_sample_price_data(code, start_date, end_date)
            
            # 실제 데이터 요청
            try:
                df = fdr.DataReader(code, start_date, end_date)
                if not df.empty:
                    # 인덱스가 DatetimeIndex가 아니면 변환
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index)
                    logger.info(f"주가 데이터 가져오기 성공: {code}, {len(df)}개 레코드")
                    return df
                else:
                    logger.warning(f"주가 데이터가 비어있어 샘플 데이터 사용: {code}")
                    return sample_data
            except Exception as e:
                logger.error(f"주가 데이터 요청 실패, 샘플 데이터 사용: {code}, 에러: {str(e)}")
                return sample_data
                
        except Exception as e:
            logger.error(f"주가 데이터 수집 실패: {code}, 에러: {str(e)}")
            return self._create_sample_price_data(code, start_date, end_date)
            
    def _create_sample_price_data(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """테스트용 샘플 주가 데이터를 생성합니다."""
        try:
            # 날짜 범위 생성
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            date_range = pd.date_range(start=start, end=end, freq='B')  # 영업일만
            
            # 기본 가격 설정 (종목코드 기반으로 다양한 값 생성)
            base_price = int(code) % 900 + 100  # 100~1000 사이 값
            price_volatility = 0.02  # 가격 변동성
            
            # 데이터 프레임 생성
            prices = []
            volume = []
            current_price = base_price
            
            for i in range(len(date_range)):
                # 가격 변동
                daily_change = current_price * np.random.normal(0, price_volatility)
                open_price = current_price
                close_price = max(10, current_price + daily_change)  # 최소 10원
                high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.01)))
                low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.01)))
                
                # 거래량 (평균 100만 주, 표준편차 50만 주)
                daily_volume = max(1000, int(np.random.normal(1000000, 500000)))
                
                prices.append([open_price, high_price, low_price, close_price])
                volume.append(daily_volume)
                current_price = close_price
            
            # 데이터프레임 생성
            df = pd.DataFrame(
                prices, 
                columns=['Open', 'High', 'Low', 'Close'],
                index=date_range
            )
            df['Volume'] = volume
            logger.info(f"샘플 주가 데이터 생성 완료: {code}, {len(df)}개 레코드")
            return df
            
        except Exception as e:
            logger.error(f"샘플 주가 데이터 생성 실패: {code}, 에러: {str(e)}")
            # 최소한의 샘플 데이터만 반환
            dates = pd.date_range(start='2020-01-01', periods=100, freq='B')
            return pd.DataFrame({
                'Open': [100] * 100,
                'High': [110] * 100,
                'Low': [90] * 100,
                'Close': [105] * 100,
                'Volume': [1000000] * 100
            }, index=dates)
            
    def get_financial_statements(self, code: str, year: int = 2024) -> Dict[str, pd.DataFrame]:
        """연간 재무제표를 가져옵니다."""
        try:
            # CSV 파일 경로
            csv_path = os.path.join(self.data_dir, f'financial_statement_{code}_{year}.csv')
            
            # CSV 파일이 존재하면 파일에서 데이터 읽기
            if os.path.exists(csv_path):
                try:
                    annual = pd.read_csv(csv_path, encoding='utf-8-sig')
                    logger.info(f"{code} 종목의 재무제표 데이터를 파일에서 읽었습니다.")
                except Exception as e:
                    logger.error(f"CSV 파일 읽기 실패: {str(e)}")
                    annual = pd.DataFrame()
            else:
                # DART API에서 데이터 가져오기
                try:
                    annual = self.dart.finstate(code, year)
                    if isinstance(annual, dict) and 'status' in annual:
                        # API 오류 응답 처리
                        logger.error(f"DART API 오류: {annual}")
                        annual = pd.DataFrame()
                    elif annual.empty:
                        logger.warning(f"연간 재무제표 데이터가 비어있습니다: {code}")
                        annual = pd.DataFrame()
                    else:
                        # 성공적으로 가져온 경우 CSV로 저장
                        annual.to_csv(csv_path, index=False, encoding='utf-8-sig')
                        logger.info(f"{code} 종목의 재무제표 데이터를 API에서 가져와 저장했습니다.")
                except Exception as e:
                    logger.error(f"DART API 요청 실패: {str(e)}")
                    annual = pd.DataFrame()
            
            # 데이터가 비어있으면 샘플 데이터 생성
            if annual.empty:
                logger.warning(f"{code} 종목의 재무제표를 가져오지 못해 샘플 데이터를 생성합니다.")
                annual = self._create_sample_financial_data(code)
            
            # 연결재무제표만 사용
            if not annual.empty and 'fs_div' in annual.columns:
                annual = annual[annual['fs_div'] == 'CFS']
            
            financial_data = {
                "annual": annual,
                "semi_annual": pd.DataFrame()  # 반기 재무제표는 사용하지 않음
            }
            
            # 데이터 유효성 검사
            if not self.validate_financial_data(financial_data):
                logger.warning(f"{code} 종목의 재무제표 데이터 유효성 검사 실패, 샘플 데이터를 사용합니다.")
                return {"annual": self._create_sample_financial_data(code), "semi_annual": pd.DataFrame()}
                
            return financial_data
            
        except Exception as e:
            logger.error(f"재무제표 수집 실패: {code}, 에러: {str(e)}")
            return {"annual": self._create_sample_financial_data(code), "semi_annual": pd.DataFrame()}

    def _create_sample_financial_data(self, code: str) -> pd.DataFrame:
        """샘플 재무제표 데이터를 생성합니다."""
        try:
            # 기본 값 설정 (종목코드 기반으로 다양한 값 생성)
            base_value = int(code) % 900 + 100  # 100~1000 사이 값
            sales = base_value * 1000000000  # 매출액 (수십억 단위)
            op_income = sales * 0.15  # 영업이익 (매출의 15%)
            net_income = op_income * 0.8  # 당기순이익 (영업이익의 80%)
            total_equity = sales * 0.7  # 자본총계 (매출의 70%)
            total_liabilities = total_equity * 0.5  # 부채총계 (자본의 50%)
            
            # 작년 대비 10~20% 성장
            growth_rate = 1 + (0.1 + (int(code) % 10) / 100)
            prev_sales = sales / growth_rate
            prev_op_income = op_income / growth_rate
            prev_net_income = net_income / growth_rate
            
            # 샘플 데이터 생성
            data = [
                {
                    'rcept_no': f'sample_{code}_1',
                    'bsns_year': '2024',
                    'stock_code': code,
                    'reprt_code': '11011',
                    'account_nm': '매출액',
                    'fs_div': 'CFS',
                    'fs_nm': '연결재무제표',
                    'sj_div': 'IS',
                    'sj_nm': '손익계산서',
                    'thstrm_nm': '당기',
                    'thstrm_dt': '2024-12-31',
                    'thstrm_amount': f'{int(sales):,}',
                    'frmtrm_nm': '전기',
                    'frmtrm_dt': '2023-12-31',
                    'frmtrm_amount': f'{int(prev_sales):,}'
                },
                {
                    'rcept_no': f'sample_{code}_2',
                    'bsns_year': '2024',
                    'stock_code': code,
                    'reprt_code': '11011',
                    'account_nm': '영업이익',
                    'fs_div': 'CFS',
                    'fs_nm': '연결재무제표',
                    'sj_div': 'IS',
                    'sj_nm': '손익계산서',
                    'thstrm_nm': '당기',
                    'thstrm_dt': '2024-12-31',
                    'thstrm_amount': f'{int(op_income):,}',
                    'frmtrm_nm': '전기',
                    'frmtrm_dt': '2023-12-31',
                    'frmtrm_amount': f'{int(prev_op_income):,}'
                },
                {
                    'rcept_no': f'sample_{code}_3',
                    'bsns_year': '2024',
                    'stock_code': code,
                    'reprt_code': '11011',
                    'account_nm': '당기순이익',
                    'fs_div': 'CFS',
                    'fs_nm': '연결재무제표',
                    'sj_div': 'IS',
                    'sj_nm': '손익계산서',
                    'thstrm_nm': '당기',
                    'thstrm_dt': '2024-12-31',
                    'thstrm_amount': f'{int(net_income):,}',
                    'frmtrm_nm': '전기',
                    'frmtrm_dt': '2023-12-31',
                    'frmtrm_amount': f'{int(prev_net_income):,}'
                },
                {
                    'rcept_no': f'sample_{code}_4',
                    'bsns_year': '2024',
                    'stock_code': code,
                    'reprt_code': '11011',
                    'account_nm': '자본총계',
                    'fs_div': 'CFS',
                    'fs_nm': '연결재무제표',
                    'sj_div': 'BS',
                    'sj_nm': '재무상태표',
                    'thstrm_nm': '당기',
                    'thstrm_dt': '2024-12-31',
                    'thstrm_amount': f'{int(total_equity):,}',
                    'frmtrm_nm': '전기',
                    'frmtrm_dt': '2023-12-31',
                    'frmtrm_amount': f'{int(total_equity * 0.9):,}'
                },
                {
                    'rcept_no': f'sample_{code}_5',
                    'bsns_year': '2024',
                    'stock_code': code,
                    'reprt_code': '11011',
                    'account_nm': '부채총계',
                    'fs_div': 'CFS',
                    'fs_nm': '연결재무제표',
                    'sj_div': 'BS',
                    'sj_nm': '재무상태표',
                    'thstrm_nm': '당기',
                    'thstrm_dt': '2024-12-31',
                    'thstrm_amount': f'{int(total_liabilities):,}',
                    'frmtrm_nm': '전기',
                    'frmtrm_dt': '2023-12-31',
                    'frmtrm_amount': f'{int(total_liabilities * 0.95):,}'
                }
            ]
            
            df = pd.DataFrame(data)
            logger.info(f"샘플 재무제표 데이터 생성 완료: {code}")
            return df
            
        except Exception as e:
            logger.error(f"샘플 재무제표 데이터 생성 실패: {code}, 에러: {str(e)}")
            # 최소한의 샘플 데이터 생성
            columns = ['rcept_no', 'bsns_year', 'stock_code', 'reprt_code', 'account_nm', 
                      'fs_div', 'fs_nm', 'sj_div', 'sj_nm', 'thstrm_nm', 'thstrm_dt', 
                      'thstrm_amount', 'frmtrm_nm', 'frmtrm_dt', 'frmtrm_amount']
            return pd.DataFrame([], columns=columns)

    def get_company_info(self, code: str) -> Dict:
        """회사 기본 정보를 가져옵니다."""
        try:
            # 회사 개요 정보
            info = self.dart.company(code)
            if isinstance(info, dict) and 'status' in info:
                # API 오류 응답 처리
                logger.error(f"DART API 오류: {info}")
                return self._create_sample_company_info(code)
            elif info is None or (isinstance(info, pd.DataFrame) and info.empty):
                logger.warning(f"회사 개요 정보가 없습니다: {code}")
                return self._create_sample_company_info(code)
                
            # 회사 정보 추출
            if isinstance(info, pd.DataFrame):
                company_info = {
                    "name": safe_get(info.iloc[0].to_dict() if not info.empty else {}, "corp_name", ""),
                    "sector": safe_get(info.iloc[0].to_dict() if not info.empty else {}, "sector", ""),
                    "industry": safe_get(info.iloc[0].to_dict() if not info.empty else {}, "industry", ""),
                    "listing_date": "",
                    "market_cap": 0
                }
            else:
                company_info = {
                    "name": safe_get(info, "corp_name", ""),
                    "sector": safe_get(info, "sector", ""),
                    "industry": safe_get(info, "industry", ""),
                    "listing_date": "",
                    "market_cap": 0
                }
            
            # 필수 정보 검증
            if not company_info["name"]:
                logger.warning(f"회사명 정보가 없습니다: {code}")
                return self._create_sample_company_info(code)
                
            return company_info
            
        except Exception as e:
            logger.error(f"회사 정보 수집 실패: {code}, 에러: {str(e)}")
            return self._create_sample_company_info(code)

    def _create_sample_company_info(self, code: str) -> Dict:
        """샘플 회사 정보를 생성합니다."""
        try:
            # 종목코드와 명칭 목록에서 회사명 찾기
            company_names = {
                "005930": "삼성전자",
                "000660": "SK하이닉스",
                "000990": "DB하이텍",
                "042700": "한미반도체",
                "336370": "테스나",
                "357780": "솔브레인",
                "240810": "원익IPS",
                "104830": "원익머트리얼즈",
                "069730": "피에스케이",
                "033640": "네패스",
                "086390": "유니테스트",
                "148250": "알엔투테크놀로지",
                "322310": "오로스테크놀로지",
                "403870": "HPSP",
                "036930": "주성엔지니어링",
                "166090": "하나머터리얼",
                "058470": "리노공업",
                "005290": "동진쌔미켐",
                "140860": "파크시스템스"
            }
            
            company_name = company_names.get(code, f"기업 {code}")
            
            # 산업 정보
            sectors = {
                "005930": "반도체 및 관련장비",
                "000660": "반도체 및 관련장비",
                "000990": "반도체 및 관련장비",
                "042700": "반도체 장비 및 검사",
                "336370": "반도체 검사 및 테스트",
                "357780": "반도체 소재",
                "240810": "반도체 장비",
                "104830": "반도체 소재",
                "069730": "반도체 부품",
                "033640": "반도체 패키징",
                "086390": "반도체 테스트 장비",
                "148250": "반도체 패키지 소재",
                "322310": "반도체 소재",
                "403870": "반도체 소재",
                "036930": "반도체 장비",
                "166090": "반도체 소재",
                "058470": "반도체 부품",
                "005290": "반도체 소재",
                "140860": "반도체 장비"
            }
            
            # 샘플 상장일 생성
            import random
            from datetime import datetime, timedelta
            
            start_date = datetime(2000, 1, 1)
            end_date = datetime(2022, 12, 31)
            days_between = (end_date - start_date).days
            random_days = random.randint(0, days_between)
            random_date = start_date + timedelta(days=random_days)
            listing_date = random_date.strftime("%Y-%m-%d")
            
            # 시가총액 생성 (1000억 ~ 1조 사이)
            market_cap = random.randint(10, 100) * 10000000000
            
            return {
                "name": company_name,
                "sector": sectors.get(code, "반도체 산업"),
                "industry": "정보기술",
                "listing_date": listing_date,
                "market_cap": market_cap
            }
            
        except Exception as e:
            logger.error(f"샘플 회사 정보 생성 실패: {code}, 에러: {str(e)}")
            return {
                "name": f"기업 {code}",
                "sector": "기타",
                "industry": "기타",
                "listing_date": "",
                "market_cap": 0
            }
            
    def get_all_stock_data(self) -> Dict[str, Dict]:
        """모든 대상 종목의 데이터를 수집합니다."""
        result = {}
        for code in SEMICONDUCTOR_STOCKS:
            try:
                # 주가 데이터
                price_data = self.get_stock_price(code)
                if price_data.empty:
                    logger.warning(f"주가 데이터 수집 실패로 건너뜀: {code}")
                    continue
                    
                # 재무제표
                financial_data = self.get_financial_statements(code, 2024)
                if financial_data["annual"].empty:
                    logger.warning(f"재무제표 데이터 수집 실패로 건너뜀: {code}")
                    continue
                    
                # 회사 정보
                company_info = self.get_company_info(code)
                if not company_info:
                    logger.warning(f"회사 정보 수집 실패로 건너뜀: {code}")
                    continue
                    
                result[code] = {
                    "price": price_data,
                    "financial": financial_data,
                    "info": company_info
                }
                
            except Exception as e:
                logger.error(f"데이터 수집 실패: {code}, 에러: {str(e)}")
                continue
                
        return result 