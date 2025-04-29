import pandas as pd
from typing import Dict
from utils import normalize_data, logger
from sepa_metrics import SEPAMetrics
from pattern_detector import PatternDetector

class ScoringEngine:
    def __init__(self, stock_data: Dict):
        """
        stock_data: {
            "price": pd.DataFrame,          # Date, Open, High, Low, Close, Volume
            "financial": {"annual": pd.DataFrame, ...}
        }
        """
        self.stock_data = stock_data
        self.sepa_metrics = SEPAMetrics(stock_data["financial"])
        self.pattern_detector = PatternDetector(stock_data["price"])
        
    def calculate_trend_score(self) -> float:
        """1단계: 기술적 추세 점수 (0.0–1.0)"""
        try:
            df = self.stock_data["price"]
            if df.empty:
                logger.warning("주가 데이터가 없어 추세 점수를 계산할 수 없습니다.")
                return 0.0

            # 최신 종가
            latest = df["Close"].iloc[-1]
            # 이동평균선
            ma50  = df["Close"].rolling(50).mean().iloc[-1]
            ma150 = df["Close"].rolling(150).mean().iloc[-1]
            ma200 = df["Close"].rolling(200).mean().iloc[-1]
            # 기울기 (5/10/20일 전 비교)
            ma50_prev  = df["Close"].rolling(50).mean().iloc[-6]
            ma150_prev = df["Close"].rolling(150).mean().iloc[-11]
            ma200_prev = df["Close"].rolling(200).mean().iloc[-21]
            # 52주 고/저가
            high52 = df["High"].tail(250).max()
            low52  = df["Low"].tail(250).min()

            conds = {
                "price_above_ma": latest > ma50 and latest > ma150 and latest > ma200,
                "ma_alignment":  ma50 > ma150 > ma200,
                "ma_slope":      (ma50 > ma50_prev and ma150 > ma150_prev and ma200 > ma200_prev),
                "price_vs_52w":  (latest >= low52 * 1.3 and latest >= high52 * 0.75)
            }
            # 각 조건 0.25점
            score = sum(0.25 for ok in conds.values() if ok)
            logger.info(f"추세 점수: {score:.2f}")
            return score
        except Exception as e:
            logger.error(f"추세 점수 계산 실패: {e}")
            return 0.0

    def calculate_fundamental_score(self) -> float:
        """2단계: 펀더멘털 점수 (0.0–1.0)"""
        try:
            df_ann = self.stock_data["financial"]["annual"]
            if df_ann.empty:
                logger.warning("재무제표 데이터가 없어 펀더멘털 점수를 계산할 수 없습니다.")
                return 0.0

            metas = self.sepa_metrics.get_all_metrics()
            if all(v == 0.0 for v in metas.values()):
                logger.warning("모든 펀더멘털 지표가 0입니다.")
                return 0.0

            norm = {}
            for k, v in metas.items():
                norm[k] = 0.0 if v == 0 else normalize_data(pd.Series([v]))[0]
            # 부채비율 역변환
            norm["debt_ratio"] = 1 - norm["debt_ratio"]

            w = {
                "sales_growth":            0.3,
                "operating_income_growth": 0.3,
                "roe":                     0.2,
                "debt_ratio":              0.2
            }
            score = sum(norm[k] * w[k] for k in w)
            score = max(0.0, min(1.0, score))
            logger.info(f"펀더멘털 점수: {score:.2f}")
            return score
        except Exception as e:
            logger.error(f"펀더멘털 점수 계산 실패: {e}")
            return 0.0

    def calculate_rs_score(self) -> float:
        """3단계: 상대적 강도 점수 (0.0–1.0)"""
        try:
            df = self.stock_data["price"]
            if df.empty:
                logger.warning("주가 데이터가 없어 RS 점수를 계산할 수 없습니다.")
                return 0.0

            # 13주(약 65 거래일)와 26주(약 130 거래일) 수익률 계산
            current_price = df["Close"].iloc[-1]
            price_13w_ago = df["Close"].iloc[-65] if len(df) >= 65 else df["Close"].iloc[0]
            price_26w_ago = df["Close"].iloc[-130] if len(df) >= 130 else df["Close"].iloc[0]
            
            returns_13w = ((current_price / price_13w_ago) - 1) * 100
            returns_26w = ((current_price / price_26w_ago) - 1) * 100
            
            # 13주와 26주 수익률에 가중치 적용 (13주에 더 큰 가중치)
            rs_score_13w = min(max(returns_13w / 20, 0), 1)  # 20% 이상 상승 시 만점
            rs_score_26w = min(max(returns_26w / 30, 0), 1)  # 30% 이상 상승 시 만점
            
            # 가중치 적용
            score = rs_score_13w * 0.6 + rs_score_26w * 0.4
            score = max(0.0, min(1.0, score))
            
            logger.info(f"RS 점수: 13주 수익률={returns_13w:.2f}%, 26주 수익률={returns_26w:.2f}%, 점수={score:.2f}")
            return score
            
        except Exception as e:
            logger.error(f"RS 점수 계산 실패: {e}")
            return 0.0

    def calculate_pattern_score(self) -> float:
        """4단계: 패턴 점수 (0.0–1.0)"""
        try:
            df = self.stock_data["price"]
            if df.empty:
                logger.warning("주가 데이터가 없어 패턴 점수를 계산할 수 없습니다.")
                return 0.0

            pats = self.pattern_detector.get_all_patterns()
            weights = {"vcp":0.4, "pocket_pivot":0.3, "breakout":0.3}

            recent = {}
            for t, lst in pats.items():
                # 최근 30일, 최대 2개
                rp = [p for p in lst if (pd.Timestamp.now() - p["date"]).days <= 30]
                recent[t] = sorted(rp, key=lambda x:x["date"], reverse=True)[:2]

            pat_score = 0.0
            for t, w in weights.items():
                lst = recent[t]
                if not lst:
                    continue
                # 첫 패턴 100%, 두 번째 50%
                pat_score += w * (1.0 if len(lst)>=1 else 0.0)
                if len(lst)>=2:
                    pat_score += w * 0.5

            # 정규화 (최대 1.0)
            score = min(pat_score, 1.0)
            logger.info(f"패턴 점수: {score:.2f}")
            return score
        except Exception as e:
            logger.error(f"패턴 점수 계산 실패: {e}")
            return 0.0

    def calculate_total_score(self) -> Dict[str, float]:
        """4단계 가중 합산한 최종 점수 반환"""
        try:
            t = self.calculate_trend_score()
            f = self.calculate_fundamental_score()
            r = self.calculate_rs_score()
            p = self.calculate_pattern_score()
            if all(x==0.0 for x in (t,f,r,p)):
                logger.warning("모든 점수가 0입니다.")
                return {"total":0.0, "trend":t, "fundamental":f, "rs":r, "pattern":p}

            w = {"trend":0.25, "fundamental":0.30, "rs":0.20, "pattern":0.25}
            total = t*w["trend"] + f*w["fundamental"] + r*w["rs"] + p*w["pattern"]
            total = max(0.0, min(1.0, total))
            return {"total":total, "trend":t, "fundamental":f, "rs":r, "pattern":p}
        except Exception as e:
            logger.error(f"종합 점수 계산 실패: {e}")
            return {"total":0.0, "trend":0.0, "fundamental":0.0, "rs":0.0, "pattern":0.0}

    def check_trend_filter(self) -> bool:
        """1단계 필터 (모두 True여야 통과)"""
        try:
            df = self.stock_data["price"]
            if df.empty:
                return False
            latest = df["Close"].iloc[-1]
            ma50  = df["Close"].rolling(50).mean().iloc[-1]
            ma150 = df["Close"].rolling(150).mean().iloc[-1]
            ma200 = df["Close"].rolling(200).mean().iloc[-1]
            ma50_p  = df["Close"].rolling(50).mean().iloc[-6]
            ma150_p = df["Close"].rolling(150).mean().iloc[-11]
            ma200_p = df["Close"].rolling(200).mean().iloc[-21]
            high52 = df["High"].tail(250).max()
            low52  = df["Low"].tail(250).min()

            return (
                latest>ma50 and latest>ma150 and latest>ma200 and
                ma50>ma150>ma200 and
                ma50>ma50_p and ma150>ma150_p and ma200>ma200_p and
                latest>=low52*1.3 and latest>=high52*0.75
            )
        except Exception as e:
            logger.error(f"추세 필터 확인 실패: {e}")
            return False

    def check_fundamental_filter(self) -> bool:
        """2단계 필터: 최소 3개 지표 통과"""
        try:
            st = self.sepa_metrics.check_sepa_criteria()
            return sum(1 for v in st.values() if v) >= 3
        except Exception as e:
            logger.error(f"기본 필터 확인 실패: {e}")
            return False

    def check_rs_filter(self) -> bool:
        """3단계 필터: RS ≥ 0.7"""
        try:
            return self.calculate_rs_score() >= 0.7
        except Exception as e:
            logger.error(f"RS 필터 확인 실패: {e}")
            return False

    def get_recommendation(self) -> str:
        """최종 투자 추천 생성"""
        scores = self.calculate_total_score()
        tot = scores["total"]
        trend_ok = self.check_trend_filter()
        fund_ok  = self.check_fundamental_filter()
        rs_ok    = self.check_rs_filter()

        if tot >= 0.8 and trend_ok and fund_ok and rs_ok:
            return "강력 매수"
        if tot >= 0.6 and trend_ok and fund_ok and rs_ok:
            return "매수"
        if tot >= 0.4:
            return "관망"
        return "매도"
        
    def get_sepa_status(self) -> Dict[str, bool]:
        """SEPA 기준 충족 여부를 확인합니다."""
        try:
            if self.stock_data["financial"]["annual"].empty:
                logger.warning("재무제표 데이터가 없어 SEPA 기준을 확인할 수 없습니다.")
                return {
                    "sales_growth": False,
                    "operating_income_growth": False,
                    "roe": False,
                    "debt_ratio": False
                }
            return self.sepa_metrics.check_sepa_criteria()
        except Exception as e:
            logger.error(f"SEPA 기준 확인 실패: {str(e)}")
            return {
                "sales_growth": False,
                "operating_income_growth": False,
                "roe": False,
                "debt_ratio": False
            }