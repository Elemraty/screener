import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from config import VCP_WINDOW, POCKET_PIVOT_VOL, BOLLINGER_BANDS
from utils import calculate_rolling_mean, calculate_rolling_std, detect_volume_spike, logger

class PatternDetector:
    def __init__(self, price_data: pd.DataFrame):
        self.price_data = price_data
        self._calculate_indicators()
        
    def _calculate_indicators(self):
        """기술적 지표를 계산합니다."""
        try:
            # 볼린저 밴드
            self.bb_middle = calculate_rolling_mean(
                self.price_data["Close"], 
                BOLLINGER_BANDS["window"]
            )
            self.bb_std = calculate_rolling_std(
                self.price_data["Close"], 
                BOLLINGER_BANDS["window"]
            )
            self.bb_upper = self.bb_middle + (self.bb_std * BOLLINGER_BANDS["std_dev"])
            self.bb_lower = self.bb_middle - (self.bb_std * BOLLINGER_BANDS["std_dev"])
            
            # 이동평균선
            self.ma20 = calculate_rolling_mean(self.price_data["Close"], 20)
            self.ma50 = calculate_rolling_mean(self.price_data["Close"], 50)
            self.ma200 = calculate_rolling_mean(self.price_data["Close"], 200)
            
        except Exception as e:
            logger.error(f"기술적 지표 계산 실패: {str(e)}")
            
    def detect_vcp(self) -> List[Dict]:
        """Volume Cup with Handle 패턴을 감지합니다."""
        try:
            vcp_patterns = []
            window = VCP_WINDOW
            
            for i in range(window, len(self.price_data)):
                # 최근 window 기간의 데이터
                recent_data = self.price_data.iloc[i-window:i]
                
                # 가격 하락 후 반등 확인
                price_decline = recent_data["Close"].iloc[0] > recent_data["Close"].iloc[-1]
                price_rebound = recent_data["Close"].iloc[-1] > recent_data["Close"].iloc[-2]
                
                # 거래량 감소 후 증가 확인
                volume_decline = recent_data["Volume"].iloc[0] > recent_data["Volume"].iloc[-2]
                volume_increase = recent_data["Volume"].iloc[-1] > recent_data["Volume"].iloc[-2]
                
                if price_decline and price_rebound and volume_decline and volume_increase:
                    # 패턴 강도 계산 (거래량 증가 비율과 가격 반등 비율의 조합)
                    volume_increase_ratio = recent_data["Volume"].iloc[-1] / recent_data["Volume"].iloc[-2] if recent_data["Volume"].iloc[-2] > 0 else 1.0
                    price_rebound_ratio = recent_data["Close"].iloc[-1] / recent_data["Close"].iloc[-2] if recent_data["Close"].iloc[-2] > 0 else 1.0
                    
                    # 강도는 0-1 범위로 정규화
                    strength = min(1.0, (volume_increase_ratio * 0.5 + price_rebound_ratio * 0.5 - 1.0))
                    strength = max(0.1, strength)  # 최소값 0.1 보장
                    
                    vcp_patterns.append({
                        "date": recent_data.index[-1],
                        "price": recent_data["Close"].iloc[-1],
                        "volume": recent_data["Volume"].iloc[-1],
                        "strength": strength
                    })
                    
            return vcp_patterns
        except Exception as e:
            logger.error(f"VCP 패턴 감지 실패: {str(e)}")
            return []
            
    def detect_pocket_pivot(self) -> List[Dict]:
        """Pocket Pivot 패턴을 감지합니다."""
        try:
            pivot_patterns = []
            
            for i in range(1, len(self.price_data)):
                # 전일 대비 상승 확인
                price_increase = self.price_data["Close"].iloc[i] > self.price_data["Close"].iloc[i-1]
                
                # 거래량 급증 확인
                volume_spike = detect_volume_spike(
                    self.price_data["Volume"], 
                    POCKET_PIVOT_VOL
                ).iloc[i]
                
                # 이동평균선 위에서 거래 확인
                above_ma = self.price_data["Close"].iloc[i] > self.ma50.iloc[i]
                
                if price_increase and volume_spike and above_ma:
                    # 패턴 강도 계산 (거래량 증가 비율과 가격 상승 비율의 조합)
                    volume_ratio = self.price_data["Volume"].iloc[i] / self.price_data["Volume"].iloc[i-20:i].mean() if self.price_data["Volume"].iloc[i-20:i].mean() > 0 else 1.0
                    price_increase_ratio = self.price_data["Close"].iloc[i] / self.price_data["Close"].iloc[i-1] if self.price_data["Close"].iloc[i-1] > 0 else 1.0
                    
                    # 강도는 0-1 범위로 정규화
                    strength = min(1.0, (volume_ratio * 0.6 + price_increase_ratio * 0.4 - 1.0) / 3.0)
                    strength = max(0.1, strength)  # 최소값 0.1 보장
                    
                    pivot_patterns.append({
                        "date": self.price_data.index[i],
                        "price": self.price_data["Close"].iloc[i],
                        "volume": self.price_data["Volume"].iloc[i],
                        "strength": strength
                    })
                    
            return pivot_patterns
        except Exception as e:
            logger.error(f"Pocket Pivot 패턴 감지 실패: {str(e)}")
            return []
            
    def detect_breakout(self) -> List[Dict]:
        """볼린저 밴드 돌파를 감지합니다."""
        try:
            breakouts = []
            
            for i in range(1, len(self.price_data)):
                # 상단 돌파 확인
                upper_breakout = (
                    self.price_data["Close"].iloc[i] > self.bb_upper.iloc[i] and
                    self.price_data["Close"].iloc[i-1] <= self.bb_upper.iloc[i-1]
                )
                
                # 하단 돌파 확인
                lower_breakout = (
                    self.price_data["Close"].iloc[i] < self.bb_lower.iloc[i] and
                    self.price_data["Close"].iloc[i-1] >= self.bb_lower.iloc[i-1]
                )
                
                if upper_breakout or lower_breakout:
                    # 패턴 강도 계산 (돌파 정도와 거래량 증가의 조합)
                    if upper_breakout:
                        # 상단 돌파는 상단밴드와의 차이 기준
                        breakout_degree = (self.price_data["Close"].iloc[i] - self.bb_upper.iloc[i]) / self.bb_upper.iloc[i]
                        is_upper = True
                    else:
                        # 하단 돌파는 하단밴드와의 차이 기준
                        breakout_degree = (self.bb_lower.iloc[i] - self.price_data["Close"].iloc[i]) / self.bb_lower.iloc[i]
                        is_upper = False
                    
                    # 거래량 비율 계산
                    volume_ratio = self.price_data["Volume"].iloc[i] / self.price_data["Volume"].iloc[i-10:i].mean() if self.price_data["Volume"].iloc[i-10:i].mean() > 0 else 1.0
                    
                    # 강도는 0-1 범위로 정규화
                    strength = min(1.0, (breakout_degree * 5.0 + volume_ratio * 0.2))
                    strength = max(0.1, strength)  # 최소값 0.1 보장
                    
                    breakouts.append({
                        "date": self.price_data.index[i],
                        "price": self.price_data["Close"].iloc[i],
                        "type": "upper" if is_upper else "lower",
                        "strength": strength
                    })
                    
            return breakouts
        except Exception as e:
            logger.error(f"돌파 패턴 감지 실패: {str(e)}")
            return []
            
    def get_all_patterns(self) -> Dict[str, List[Dict]]:
        """모든 패턴을 감지합니다."""
        return {
            "vcp": self.detect_vcp(),
            "pocket_pivot": self.detect_pocket_pivot(),
            "breakout": self.detect_breakout()
        } 