import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from data_fetcher import DataFetcher
from scoring import ScoringEngine
from config import SEMICONDUCTOR_STOCKS, SEPA_THRESHOLDS
import logging
from utils import logger

# 페이지 설정
st.set_page_config(
    page_title="SEPA 반도체 스크리너",
    page_icon="📈",
    layout="wide"
)

# 제목
st.title("SEPA 반도체 스크리너")
st.markdown("---")

# 데이터 로딩
@st.cache_data(ttl=3600)  # 1시간 캐시
def load_data():
    fetcher = DataFetcher()
    return fetcher.get_all_stock_data()

# 데이터 로드
with st.spinner("데이터를 불러오는 중..."):
    stock_data = load_data()

# 데이터 로드 결과 확인
if not stock_data:
    st.error("데이터를 불러올 수 없습니다. API 연결 상태를 확인하거나 나중에 다시 시도해주세요.")
    st.stop()

# SEPA 지표 한글 명칭 매핑
sepa_criteria_names = {
    "sales_growth": "매출액 성장률",
    "operating_income_growth": "영업이익 성장률",
    "roe": "자기자본이익률(ROE)",
    "debt_ratio": "부채비율"
}

# SEPA 임계값 텍스트 표시 설정
sepa_criteria_threshold_texts = {
    "sales_growth": f"{SEPA_THRESHOLDS['sales_growth']}% 이상",
    "operating_income_growth": f"{SEPA_THRESHOLDS['operating_income_growth']}% 이상",
    "roe": f"{SEPA_THRESHOLDS['roe']}% 이상",
    "debt_ratio": f"{SEPA_THRESHOLDS['debt_ratio']}% 이하"
}

# 모든 종목 점수 계산
@st.cache_data(ttl=3600)  # 1시간 캐시
def calculate_all_scores():
    results = []
    for code in SEMICONDUCTOR_STOCKS:
        if code not in stock_data:
            continue
        
        # 기업 정보 가져오기
        company_name = stock_data[code]["info"].get("name", f"기업 {code}")
        
        # 스코어링 엔진 초기화
        scoring_engine = ScoringEngine(stock_data[code])
        
        # 점수 계산
        scores = scoring_engine.calculate_total_score()
        recommendation = scoring_engine.get_recommendation()
        
        # 필터 충족 여부
        trend_filter_passed = scoring_engine.check_trend_filter()
        fundamental_filter_passed = scoring_engine.check_fundamental_filter()
        rs_filter_passed = scoring_engine.check_rs_filter()
        all_filters_passed = trend_filter_passed and fundamental_filter_passed and rs_filter_passed
        
        # 결과 추가
        results.append({
            "code": code,
            "name": company_name,
            "total_score": scores["total"],
            "trend_score": scores["trend"],
            "fundamental_score": scores["fundamental"],
            "rs_score": scores["rs"],
            "pattern_score": scores["pattern"],
            "recommendation": recommendation,
            "all_filters_passed": all_filters_passed
        })
    
    # 종합 점수 기준으로 정렬
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values("total_score", ascending=False).reset_index(drop=True)
    return results_df

# 모든 종목 점수 계산
all_scores = calculate_all_scores()

# 메인 대시보드 - 모든 종목 점수 테이블 표시
st.subheader("종목별 SEPA 점수")

if not all_scores.empty:
    # 표시할 데이터 포맷팅
    display_data = all_scores.copy()
    display_data["total_score"] = display_data["total_score"].apply(lambda x: f"{x:.2%}")
    display_data["trend_score"] = display_data["trend_score"].apply(lambda x: f"{x:.2%}")
    display_data["fundamental_score"] = display_data["fundamental_score"].apply(lambda x: f"{x:.2%}")
    display_data["rs_score"] = display_data["rs_score"].apply(lambda x: f"{x:.2%}")
    display_data["pattern_score"] = display_data["pattern_score"].apply(lambda x: f"{x:.2%}")
    display_data["필터 충족"] = display_data["all_filters_passed"].apply(lambda x: "✅" if x else "❌")
    
    # 표시할 컬럼 선택 및 컬럼명 변경
    display_data = display_data[["code", "name", "total_score", "trend_score", "fundamental_score", "rs_score", "pattern_score", "recommendation", "필터 충족"]]
    display_data.columns = ["종목코드", "기업명", "종합 점수", "기술적 추세", "기본적 성장성", "상대적 강도", "패턴 점수", "투자 추천", "필터 충족"]
    
    # 데이터프레임을 표시하고 선택 가능하게 함
    st.dataframe(display_data, use_container_width=True, hide_index=True)
    
    # 선택 가능한 종목 리스트 생성
    selected_stock = st.selectbox(
        "상세 분석할 종목 선택",
        options=all_scores["code"].tolist(),
        format_func=lambda x: f"{x} - {all_scores[all_scores['code'] == x]['name'].values[0]}"
    )
else:
    st.warning("분석할 수 있는 종목이 없습니다.")
    st.stop()

# 선택한 종목 상세 분석
if selected_stock:
    st.markdown("---")
    st.subheader(f"종목 상세 분석: {selected_stock} - {all_scores[all_scores['code'] == selected_stock]['name'].values[0]}")
    
    code = selected_stock
    
    if code not in stock_data:
        st.warning(f"종목 {code}의 데이터를 찾을 수 없습니다. API 연결 상태를 확인하거나 나중에 다시 시도해주세요.")
    else:
        # 스코어링 엔진 초기화
        scoring_engine = ScoringEngine(stock_data[code])
        
        # 점수 계산
        scores = scoring_engine.calculate_total_score()
        sepa_status = scoring_engine.get_sepa_status()
        recommendation = scoring_engine.get_recommendation()
        
        # 필터 확인
        trend_filter_passed = scoring_engine.check_trend_filter()
        fundamental_filter_passed = scoring_engine.check_fundamental_filter()
        rs_filter_passed = scoring_engine.check_rs_filter()
        
        # 펀더멘털 점수 상세 내역
        metrics = scoring_engine.sepa_metrics.get_all_metrics()
        
        # 표시할 컬럼 구성
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("종합 점수 평가")
            st.metric("종합 점수", f"{scores['total']:.2%}")
            st.metric("기술적 추세 점수", f"{scores['trend']:.2%}")
            st.metric("기본적 성장성 점수", f"{scores['fundamental']:.2%}")
            st.metric("상대적 강도 점수", f"{scores['rs']:.2%}")
            st.metric("패턴 점수", f"{scores['pattern']:.2%}")
            st.metric("투자 추천", recommendation)
            
            # 가중치 정보 설명 추가
            st.info("""
            **SEPA 점수 산출 방식**:
            - 기술적 추세 점수 (가중치: 25%)
            - 기본적 성장성 점수 (가중치: 30%)
            - 상대적 강도 점수 (가중치: 20%)
            - 패턴 점수 (가중치: 25%)
            """)
            
        with col2:
            st.subheader("SEPA 필터 충족 여부")
            
            # 각 필터 충족 여부 표시
            st.metric(
                "1단계: 기술적 추세 필터", 
                "통과" if trend_filter_passed else "미통과",
                delta_color="normal" if trend_filter_passed else "inverse"
            )
            
            st.metric(
                "2단계: 기본적 성장성 필터", 
                "통과" if fundamental_filter_passed else "미통과",
                delta_color="normal" if fundamental_filter_passed else "inverse"
            )
            
            st.metric(
                "3단계: 상대적 강도 필터", 
                "통과" if rs_filter_passed else "미통과",
                delta_color="normal" if rs_filter_passed else "inverse"
            )
            
            # 모든 필터 통과 여부
            all_filters_passed = trend_filter_passed and fundamental_filter_passed and rs_filter_passed
            st.metric(
                "모든 필터 충족", 
                "충족" if all_filters_passed else "미충족",
                delta="매수 추천 가능" if all_filters_passed else "매수 추천 불가",
                delta_color="normal" if all_filters_passed else "inverse"
            )
            
            # SEPA 지표 상세 표시
            st.subheader("SEPA 기본적 성장성 지표")
            for criterion, status in sepa_status.items():
                kr_name = sepa_criteria_names.get(criterion, criterion)
                threshold_text = sepa_criteria_threshold_texts.get(criterion, "")
                current_value = metrics[criterion]
                
                # 부채비율은 낮을수록 좋음, 나머지는 높을수록 좋음
                if criterion == "debt_ratio":
                    is_good = current_value <= SEPA_THRESHOLDS[criterion]
                    delta_value = f"{SEPA_THRESHOLDS[criterion] - current_value:.2f}%p 여유" if is_good else f"{current_value - SEPA_THRESHOLDS[criterion]:.2f}%p 초과"
                else:
                    is_good = current_value >= SEPA_THRESHOLDS[criterion]
                    delta_value = f"{current_value - SEPA_THRESHOLDS[criterion]:.2f}%p 초과" if is_good else f"{SEPA_THRESHOLDS[criterion] - current_value:.2f}%p 부족"
                
                # 현재 값, 기준, 델타값 표시
                st.metric(
                    f"{kr_name} (기준: {threshold_text})", 
                    f"{current_value:.2f}%",
                    delta=delta_value,
                    delta_color="normal" if is_good else "inverse"
                )
                
        # 점수 산출 근거 상세 표시
        st.subheader("💡 상세 분석")
        
        # 기술적 추세 점수 상세
        with st.expander("기술적 추세 점수 상세 (가중치: 25%)"):
            price_data = stock_data[code]["price"]
            
            if not price_data.empty:
                # 최근 종가
                latest_close = price_data["Close"].iloc[-1]
                
                # 이동평균선 계산
                ma50 = price_data["Close"].rolling(window=50).mean().iloc[-1]
                ma150 = price_data["Close"].rolling(window=150).mean().iloc[-1]
                ma200 = price_data["Close"].rolling(window=200).mean().iloc[-1]
                
                # 이동평균선 기울기 확인
                ma50_prev = price_data["Close"].rolling(window=50).mean().iloc[-6]  # 5일 전
                ma150_prev = price_data["Close"].rolling(window=150).mean().iloc[-11]  # 10일 전
                ma200_prev = price_data["Close"].rolling(window=200).mean().iloc[-21]  # 20일 전
                
                # 52주(약 250 거래일) 고가/저가
                high_52w = price_data["High"].tail(250).max()
                low_52w = price_data["Low"].tail(250).min()
                
                # 조건 체크 결과
                conditions = {
                    "주가 > 이동평균선(50,150,200일)": latest_close > ma50 and latest_close > ma150 and latest_close > ma200,
                    "이동평균선 정렬(50 > 150 > 200)": ma50 > ma150 > ma200,
                    "이동평균선 상승 추세": ma50 > ma50_prev and ma150 > ma150_prev and ma200 > ma200_prev,
                    "52주 고저점 위치 기준 충족": (latest_close >= low_52w * 1.3) and (latest_close >= high_52w * 0.75)
                }
                
                # 각 조건의 결과를 표로 표시
                condition_data = []
                for condition_name, condition_result in conditions.items():
                    condition_data.append({
                        "항목": condition_name,
                        "결과": "충족" if condition_result else "미충족",
                        "점수": "0.25" if condition_result else "0"
                    })
                
                st.table(pd.DataFrame(condition_data))
                
                st.markdown("""
                **산출 방식**:
                1. 각 조건마다 0.25점씩 부여
                2. 모든 조건을 충족해야 기술적 추세 필터를 통과
                3. 최종 점수는 0~100% 범위로 표시
                """)
            else:
                st.warning("주가 데이터가 없어 기술적 추세 점수를 계산할 수 없습니다.")
        
        # 상대적 강도 점수 상세
        with st.expander("상대적 강도 점수 상세 (가중치: 20%)"):
            price_data = stock_data[code]["price"]
            
            if not price_data.empty:
                # 13주(약 65 거래일)와 26주(약 130 거래일) 수익률 계산
                current_price = price_data["Close"].iloc[-1]
                price_13w_ago = price_data["Close"].iloc[-65] if len(price_data) >= 65 else price_data["Close"].iloc[0]
                price_26w_ago = price_data["Close"].iloc[-130] if len(price_data) >= 130 else price_data["Close"].iloc[0]
                
                returns_13w = ((current_price / price_13w_ago) - 1) * 100
                returns_26w = ((current_price / price_26w_ago) - 1) * 100
                
                # 데이터 표시
                rs_data = [
                    {"기간": "13주 수익률", "값": f"{returns_13w:.2f}%", "가중치": "60%"},
                    {"기간": "26주 수익률", "값": f"{returns_26w:.2f}%", "가중치": "40%"}
                ]
                
                st.table(pd.DataFrame(rs_data))
                
                st.markdown(f"""
                **RS 점수**: {scores['rs']:.2%}
                
                **산출 방식**:
                1. 13주 수익률: {returns_13w:.2f}% (20% 이상이면 만점)
                2. 26주 수익률: {returns_26w:.2f}% (30% 이상이면 만점)
                3. 가중치 적용: 13주(60%), 26주(40%)
                4. RS 점수 70% 이상이면 RS 필터 통과
                """)
            else:
                st.warning("주가 데이터가 없어 상대적 강도 점수를 계산할 수 없습니다.")
                
        # 패턴 점수 상세
        with st.expander("패턴 점수 상세 (가중치: 25%)"):
            patterns = scoring_engine.pattern_detector.get_all_patterns()
            
            # 최신 2개로 제한된 패턴 데이터 준비
            filtered_patterns = {}
            for pattern_type, pattern_list in patterns.items():
                # 날짜 기준 정렬
                sorted_patterns = sorted(
                    [p for p in pattern_list if (pd.Timestamp.now() - p["date"]).days <= 30],
                    key=lambda x: x["date"],
                    reverse=True  # 최신 패턴이 먼저 오도록
                )
                # 각 패턴 타입별로 최대 2개만 사용
                filtered_patterns[pattern_type] = sorted_patterns[:2]
            
            # 패턴 데이터를 테이블로 표시
            if all(len(p) == 0 for p in filtered_patterns.values()):
                st.write("감지된 패턴이 없습니다.")
            else:
                for pattern_type, pattern_list in filtered_patterns.items():
                    if pattern_list:
                        if pattern_type == "vcp":
                            pattern_kr = "볼륨 수축 패턴 (VCP)"
                            weight = "40%"
                        elif pattern_type == "pocket_pivot":
                            pattern_kr = "포켓 피봇 (Pocket Pivot)"
                            weight = "30%"
                        elif pattern_type == "breakout":
                            pattern_kr = "돌파 (Breakout)"
                            weight = "30%"
                        else:
                            pattern_kr = pattern_type
                            weight = "N/A"
                        
                        st.write(f"**{pattern_kr}** (가중치: {weight})")
                        
                        # 패턴 정보 표시
                        pattern_data = []
                        for p in pattern_list:
                            pattern_data.append({
                                "날짜": p["date"].strftime("%Y-%m-%d"),
                                "강도": f"{p.get('strength', 0):.2f}" if "strength" in p else "N/A"
                            })
                        
                        if pattern_data:
                            st.table(pd.DataFrame(pattern_data))
            
            st.markdown("""
            **산출 방식**:
            1. 최근 30일 이내 패턴 발생 횟수에 가중치 적용 (각 패턴 타입별 최대 2개)
            2. 볼륨 수축 패턴(40%), 포켓 피봇(30%), 돌파(30%)
            3. 첫 번째 패턴은 가중치의 100%, 두 번째는 50% 적용
            4. 최종 점수는 0~100% 범위로 표시
            """)
            
        # 차트
        price_data = stock_data[code]["price"]
        
        if not price_data.empty:
            # 인덱스가 DatetimeIndex인지 확인하고 변환
            if not isinstance(price_data.index, pd.DatetimeIndex):
                try:
                    price_data.index = pd.to_datetime(price_data.index)
                except Exception as e:
                    logger.error(f"날짜 변환 오류: {str(e)}")
                    st.warning("가격 데이터의 날짜 형식이 올바르지 않아 차트를 표시할 수 없습니다.")
            
            try:
                fig = go.Figure()
                
                # 캔들스틱
                fig.add_trace(go.Candlestick(
                    x=price_data.index,
                    open=price_data["Open"],
                    high=price_data["High"],
                    low=price_data["Low"],
                    close=price_data["Close"],
                    name="가격"
                ))
                
                # 이동평균선
                fig.add_trace(go.Scatter(
                    x=price_data.index,
                    y=price_data["Close"].rolling(window=20).mean(),
                    name="20일 이동평균",
                    line=dict(color="blue", width=1)
                ))
                
                fig.add_trace(go.Scatter(
                    x=price_data.index,
                    y=price_data["Close"].rolling(window=50).mean(),
                    name="50일 이동평균",
                    line=dict(color="orange", width=1)
                ))
                
                fig.add_trace(go.Scatter(
                    x=price_data.index,
                    y=price_data["Close"].rolling(window=200).mean(),
                    name="200일 이동평균",
                    line=dict(color="red", width=1)
                ))
                
                # 패턴 정보 가져오기
                all_patterns = scoring_engine.pattern_detector.get_all_patterns()
                
                # VCP 패턴 표시
                vcp_patterns = all_patterns.get("vcp", [])
                if vcp_patterns:
                    vcp_dates = [p["date"] for p in vcp_patterns]
                    vcp_prices = [p["price"] for p in vcp_patterns]
                    vcp_strengths = [p.get("strength", 0.5) for p in vcp_patterns]
                    
                    # 크기를 강도 기반으로 스케일링 (10-16 사이의 값)
                    marker_sizes = [10 + s * 12 for s in vcp_strengths]
                    
                    # VCP 패턴 표시
                    fig.add_trace(go.Scatter(
                        x=vcp_dates,
                        y=vcp_prices,
                        mode='markers',
                        marker=dict(
                            symbol='triangle-up',
                            size=marker_sizes,
                            color='green',
                            line=dict(width=1, color='darkgreen')
                        ),
                        name='VCP 패턴'
                    ))
                
                # Breakout 패턴 표시
                breakout_patterns = all_patterns.get("breakout", [])
                if breakout_patterns:
                    # 상단 돌파와 하단 돌파 분리
                    upper_breakouts = [p for p in breakout_patterns if p.get("type") == "upper"]
                    lower_breakouts = [p for p in breakout_patterns if p.get("type") == "lower"]
                    
                    # 상단 돌파 표시
                    if upper_breakouts:
                        upper_dates = [p["date"] for p in upper_breakouts]
                        upper_prices = [p["price"] for p in upper_breakouts]
                        upper_strengths = [p.get("strength", 0.5) for p in upper_breakouts]
                        
                        # 크기를 강도 기반으로 스케일링
                        marker_sizes = [10 + s * 12 for s in upper_strengths]
                        
                        fig.add_trace(go.Scatter(
                            x=upper_dates,
                            y=upper_prices,
                            mode='markers',
                            marker=dict(
                                symbol='triangle-up',
                                size=marker_sizes,
                                color='red',
                                line=dict(width=1, color='darkred')
                            ),
                            name='상단 돌파'
                        ))
                    
                    # 하단 돌파 표시
                    if lower_breakouts:
                        lower_dates = [p["date"] for p in lower_breakouts]
                        lower_prices = [p["price"] for p in lower_breakouts]
                        lower_strengths = [p.get("strength", 0.5) for p in lower_breakouts]
                        
                        # 크기를 강도 기반으로 스케일링
                        marker_sizes = [10 + s * 12 for s in lower_strengths]
                        
                        fig.add_trace(go.Scatter(
                            x=lower_dates,
                            y=lower_prices,
                            mode='markers',
                            marker=dict(
                                symbol='triangle-down',
                                size=marker_sizes,
                                color='blue',
                                line=dict(width=1, color='darkblue')
                            ),
                            name='하단 돌파'
                        ))
                
                # 레이아웃 설정
                fig.update_layout(
                    title="가격 차트와 패턴 표시",
                    yaxis_title="가격",
                    xaxis_title="날짜",
                    height=500,
                    xaxis_rangeslider_visible=False,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    )
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # 패턴 범례 설명
                st.info("""
                **차트 패턴 설명**:
                - 🟢 **초록색 삼각형**: VCP 패턴 - 거래량 감소 후 가격과 거래량이 동시에 반등하는 패턴
                - 🔴 **빨간색 삼각형**: 상단 돌파 - 가격이 볼린저 밴드 상단을 상향 돌파
                - 🔵 **파란색 삼각형**: 하단 돌파 - 가격이 볼린저 밴드 하단을 하향 돌파
                - 삼각형 크기는 패턴의 강도를 나타냅니다.
                """)
                
            except Exception as e:
                logger.error(f"차트 생성 오류: {str(e)}")
                st.warning(f"차트를 생성하는 중 오류가 발생했습니다: {str(e)}")
        else:
            st.warning("주가 데이터가 없어 차트를 표시할 수 없습니다.")
            
        # 상세 정보
        with st.expander("상세 정보 보기"):
            # 재무제표
            st.subheader("재무제표")
            financial_data = stock_data[code]["financial"]
            
            if "annual" in financial_data and not financial_data["annual"].empty:
                st.dataframe(financial_data["annual"])
            else:
                st.warning("재무제표 데이터가 없습니다. API 연결 상태를 확인하거나 나중에 다시 시도해주세요.")
                
            # 회사 정보
            st.subheader("회사 정보")
            company_info = stock_data[code]["info"]
            
            if company_info:
                st.json(company_info)
            else:
                st.warning("회사 정보가 없습니다. API 연결 상태를 확인하거나 나중에 다시 시도해주세요.")
                
        st.markdown("---")
    
# 푸터
st.markdown("---")
st.markdown("SEPA 반도체 스크리너 v2.0")
st.markdown("© 2024 All Rights Reserved.") 