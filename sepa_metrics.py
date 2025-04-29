import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from config import SEPA_THRESHOLDS
from utils import calculate_growth_rate, logger

class SEPAMetrics:
    def __init__(self, financial_data: Dict[str, pd.DataFrame]):
        self.financial_data = financial_data
        
    def _get_account_value(self, account_name: str) -> float:
        """특정 계정과목의 값을 가져옵니다."""
        try:
            annual = self.financial_data["annual"]
            if annual.empty:
                return 0.0
                
            # 연결재무제표(CFS)만 필터링
            annual_cfs = annual[annual["fs_div"] == "CFS"]
            if annual_cfs.empty:
                logger.warning(f"연결재무제표(CFS) 데이터가 없습니다.")
                return 0.0
                
            # 계정과목 필터링
            account_data = annual_cfs[annual_cfs["account_nm"] == account_name]
            if account_data.empty:
                logger.warning(f"계정과목 '{account_name}'을 찾을 수 없습니다.")
                return 0.0
                
            # 최신 데이터 사용
            amount_str = account_data.iloc[0]["thstrm_amount"].replace(",", "")
            logger.info(f"계정과목 '{account_name}' 값: {amount_str}")
            return float(amount_str)
        except Exception as e:
            logger.error(f"계정과목 '{account_name}' 값 추출 실패: {str(e)}")
            return 0.0
            
    def calculate_sales_growth(self) -> float:
        """매출액 성장률을 계산합니다."""
        try:
            annual = self.financial_data["annual"]
            if annual.empty:
                logger.warning("재무제표 데이터가 비어있습니다.")
                return 0.0
                
            # 연결재무제표(CFS)만 필터링
            annual_cfs = annual[annual["fs_div"] == "CFS"]
            if annual_cfs.empty:
                logger.warning("연결재무제표(CFS) 데이터가 없습니다.")
                return 0.0
                
            # 매출액 데이터 필터링
            sales = annual_cfs[annual_cfs["account_nm"] == "매출액"]
            if sales.empty:
                logger.warning("매출액 데이터를 찾을 수 없습니다.")
                return 0.0
                
            if len(sales) < 1:
                logger.warning("매출액 데이터가 부족합니다.")
                return 0.0
                
            current_str = sales.iloc[0]["thstrm_amount"]
            previous_str = sales.iloc[0]["frmtrm_amount"]
            
            logger.info(f"매출액 현재값: {current_str}, 이전값: {previous_str}")
            
            current = float(current_str.replace(",", ""))
            previous = float(previous_str.replace(",", ""))
            
            growth_rate = calculate_growth_rate(current, previous)
            logger.info(f"매출액 성장률 계산 결과: {growth_rate:.2f}%")
            
            return growth_rate
        except Exception as e:
            logger.error(f"매출액 성장률 계산 실패: {str(e)}")
            return 0.0
            
    def calculate_operating_income_growth(self) -> float:
        """영업이익 성장률을 계산합니다."""
        try:
            annual = self.financial_data["annual"]
            if annual.empty:
                logger.warning("재무제표 데이터가 비어있습니다.")
                return 0.0
                
            # 연결재무제표(CFS)만 필터링
            annual_cfs = annual[annual["fs_div"] == "CFS"]
            if annual_cfs.empty:
                logger.warning("연결재무제표(CFS) 데이터가 없습니다.")
                return 0.0
                
            # 영업이익 데이터 필터링
            operating_income = annual_cfs[annual_cfs["account_nm"] == "영업이익"]
            if operating_income.empty:
                logger.warning("영업이익 데이터를 찾을 수 없습니다.")
                return 0.0
                
            if len(operating_income) < 1:
                logger.warning("영업이익 데이터가 부족합니다.")
                return 0.0
                
            current_str = operating_income.iloc[0]["thstrm_amount"]
            previous_str = operating_income.iloc[0]["frmtrm_amount"]
            
            logger.info(f"영업이익 현재값: {current_str}, 이전값: {previous_str}")
            
            current = float(current_str.replace(",", ""))
            previous = float(previous_str.replace(",", ""))
            
            growth_rate = calculate_growth_rate(current, previous)
            logger.info(f"영업이익 성장률 계산 결과: {growth_rate:.2f}%")
            
            return growth_rate
        except Exception as e:
            logger.error(f"영업이익 성장률 계산 실패: {str(e)}")
            return 0.0
            
    def calculate_roe(self) -> float:
        """ROE를 계산합니다."""
        try:
            # 당기순이익과 자본총계
            net_income = self._get_account_value("당기순이익")
            capital = self._get_account_value("자본총계")
            
            if capital == 0:
                logger.warning("자본총계가 0이어서 ROE를 계산할 수 없습니다.")
                return 0.0
                
            roe = (net_income / capital) * 100
            logger.info(f"ROE 계산 결과: {roe:.2f}%")
            
            return roe
        except Exception as e:
            logger.error(f"ROE 계산 실패: {str(e)}")
            return 0.0
            
    def calculate_debt_ratio(self) -> float:
        """부채비율을 계산합니다."""
        try:
            # 부채총계와 자본총계
            debt = self._get_account_value("부채총계")
            capital = self._get_account_value("자본총계")
            
            if capital == 0:
                logger.warning("자본총계가 0이어서 부채비율을 계산할 수 없습니다.")
                return 0.0
                
            debt_ratio = (debt / capital) * 100
            logger.info(f"부채비율 계산 결과: {debt_ratio:.2f}%")
            
            return debt_ratio
        except Exception as e:
            logger.error(f"부채비율 계산 실패: {str(e)}")
            return 0.0
            
    def get_all_metrics(self) -> Dict[str, float]:
        """모든 SEPA 지표를 계산합니다."""
        return {
            "sales_growth": self.calculate_sales_growth(),
            "operating_income_growth": self.calculate_operating_income_growth(),
            "roe": self.calculate_roe(),
            "debt_ratio": self.calculate_debt_ratio()
        }
        
    def check_sepa_criteria(self) -> Dict[str, bool]:
        """SEPA 기준 충족 여부를 확인합니다."""
        metrics = self.get_all_metrics()
        return {
            "sales_growth": metrics["sales_growth"] >= SEPA_THRESHOLDS["sales_growth"],
            "operating_income_growth": metrics["operating_income_growth"] >= SEPA_THRESHOLDS["operating_income_growth"],
            "roe": metrics["roe"] >= SEPA_THRESHOLDS["roe"],
            "debt_ratio": metrics["debt_ratio"] <= SEPA_THRESHOLDS["debt_ratio"]
        } 