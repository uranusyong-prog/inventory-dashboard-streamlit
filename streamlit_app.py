"""
26년 부진·부동 재고 소진 대시보드 (Streamlit Cloud)
Google Sheets 라이브 연동 + 시안(STANDALONE) 스타일 재현
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

# ============================================================
# 0. 페이지 설정
# ============================================================
KST = timezone(timedelta(hours=9))
def kst_today_key():
    return datetime.now(KST).strftime("%Y-%m-%d")

st.set_page_config(
    page_title="26년 부진·부동 재고 소진 대시보드",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 1. 전역 CSS — 시안 톤 (배경색 KPI · 인사이트 박스 · 산식 바)
# ============================================================
st.markdown("""
<style>
  /* 기본 폰트 */
  html, body, [class*="css"] { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; }

  /* STANDALONE 뱃지 */
  .standalone-badge {
    display: inline-block; background: #2563EB; color: #fff;
    font-size: 12px; font-weight: 700; padding: 4px 10px;
    border-radius: 6px; vertical-align: middle; margin-left: 8px;
  }

  /* KPI 카드 컨테이너 */
  .kpi-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin: 16px 0 12px; }
  .kpi {
    border-radius: 10px; padding: 18px 16px; text-align: center;
    border: 1px solid rgba(0,0,0,0.05);
  }
  .kpi .label { font-size: 13px; color: #555; font-weight: 600; margin-bottom: 6px; }
  .kpi .value { font-size: 28px; font-weight: 800; color: #111; }
  .kpi.total    { background: #F4F4F5; }
  .kpi.emergency{ background: #FEECEC; }
  .kpi.emergency .value { color: #DC2626; }
  .kpi.warning  { background: #FEF6E0; }
  .kpi.warning  .value { color: #B45309; }
  .kpi.caution  { background: #F4F4F5; }
  .kpi.amount   { background: #F4F4F5; }
  .kpi.sellrate { background: #E8F5E9; }
  .kpi.sellrate .value { color: #1E7F36; }

  /* 위험 점수 산식 바 */
  .formula-bar {
    background: #F4F4F5; border-radius: 8px; padding: 10px 14px;
    font-size: 13px; color: #333; margin: 10px 0 18px;
    display: flex; flex-wrap: wrap; gap: 14px; align-items: center;
  }
  .formula-bar .lbl { font-weight: 700; color: #555; background: #fff;
                      padding: 3px 8px; border-radius: 4px; border: 1px solid #ddd; }
  .formula-bar .sep { color: #bbb; }
  .formula-bar .em-red    { color: #DC2626; font-weight: 700; }
  .formula-bar .em-orange { color: #D97706; font-weight: 700; }
  .formula-bar .em-blue   { color: #2563EB; font-weight: 700; }

  /* 인사이트 박스 4종 */
  .insight-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 16px 0; }
  .insight {
    border-radius: 10px; padding: 14px 16px; font-size: 13.5px; line-height: 1.55;
    border-left: 4px solid #ccc;
  }
  .insight .title { font-weight: 700; margin-bottom: 6px; font-size: 14px; }
  .insight.blue   { background: #EFF6FF; border-color: #3B82F6; }
  .insight.blue   .title { color: #1D4ED8; }
  .insight.red    { background: #FEF2F2; border-color: #EF4444; }
  .insight.red    .title { color: #B91C1C; }
  .insight.green  { background: #ECFDF5; border-color: #10B981; }
  .insight.green  .title { color: #047857; }
  .insight.yellow { background: #FFFBEB; border-color: #F59E0B; }
  .insight.yellow .title { color: #B45309; }

  /* 인사이트 섹션 헤더 */
  .insight-section-title {
    font-weight: 800; font-size: 16px; margin: 8px 0 4px;
  }
  .insight-section-title .auto-tag {
    float: right; font-size: 11px; color: #888; font-weight: 500;
  }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 2. 시트 설정 — 게시된(published) CSV URL
# ============================================================
PUBLISHED_ID = "2PACX-1vRT7vP8ND1zE_SQEAr_Ox6F5MgfNxldetfTJ9x8IOCjYlTE9a-mot83vUV6SJ4OkvDdpM15saxIMU3Y"
SHEET_ID = "1agL_qDqdc6NicnaBI50J12tebDxe-TspjJRkzh4K6WA"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/e/{PUBLISHED_ID}/pub?output=csv&gid=0"

@st.cache_data(ttl=86400, show_spinner="시트에서 데이터를 읽는 중…")
def load_sheet(day_key: str):
    df = pd.read_csv(EXPORT_URL, header=None, dtype=str, keep_default_na=False)
    return df

# ============================================================
# 3. 유틸
# ============================================================
def to_num(v):
    if v is None or v == "":
        return 0
    s = re.sub(r"[^\d.-]", "", str(v).replace(",", ""))
    try:
        return float(s)
    except Exception:
        return 0

def to_pct(v):
    if v is None or v == "":
        return 0
    s = str(v)
    has = "%" in s
    n = to_num(s)
    return n / 100 if (has or n > 1.5) else n

def fmt_won(v):
    if v is None or v == 0:
        return "-"
    v = float(v)
    if abs(v) >= 1e8:
        return f"{v/1e8:.2f}억원"
    if abs(v) >= 1e7:
        return f"{round(v/1e7)}천만원"
    if abs(v) >= 1e6:
        return f"{round(v/1e6)}백만원"
    if abs(v) >= 1e4:
        return f"{round(v/1e4):,}만원"
    return f"{round(v):,}원"

# ============================================================
# 4. 시트 파싱
# ============================================================
CHANNEL_NAMES = ("중국", "글로벌", "글로벌EC", "오프라인", "온라인", "일본", "미주")

def parse_sheet(df):
    rows = df.values.tolist()

    # --- 4-1. 채널 요약: 행 길이에 관계없이 첫 25행에서 채널명 매칭 ---
    channels = {}
    for row in rows[:25]:
        if not row:
            continue
        name = str(row[0]).strip() if len(row) > 0 else ""
        if name in CHANNEL_NAMES:
            # 컬럼 위치 안전 접근
            sku = int(to_num(row[1])) if len(row) > 1 else 0
            assigned = to_num(row[2]) if len(row) > 2 else 0
            remain   = to_num(row[3]) if len(row) > 3 else 0
            consumed = to_num(row[4]) if len(row) > 4 else 0
            channels[name] = {"sku": sku, "assigned": assigned, "remain": remain, "consumed": consumed}

    # --- 4-2. 메인 헤더 탐색 (40컬럼 부진 SKU 영역) ---
    main_h_idx = -1
    main_hdr = None
    for i, row in enumerate(rows):
        joined = "|".join(str(c).replace("\n", " ").strip() for c in row)
        if "상품 코드" in joined and "가용재고" in joined and "등급" in joined:
            main_h_idx = i
            main_hdr = [re.sub(r"\s+", " ", str(c)).strip() for c in row]
            break

    if main_h_idx == -1:
        return {"channels": channels, "items": [], "dormant_items": [], "error": "메인 헤더를 찾지 못함"}

    iDept, iCode, iName = 1, 2, 3
    iBase, iAvail, iRate, iAmount, iGrade = 4, 5, 8, 9, 10
    w_idx = [i for i, h in enumerate(main_hdr) if re.fullmatch(r"\d+W", h.strip())]

    dormant_items = []
    dormant_codes = set()
    for r_idx in range(main_h_idx + 1, len(rows)):
        row = rows[r_idx]
        if len(row) != len(main_hdr):
            continue
        code = str(row[iCode]).strip()
        if not code or not re.match(r"^B\w+", code):
            continue
        base = to_num(row[iBase])
        avail = to_num(row[iAvail])
        amount = to_num(row[iAmount])
        rate = to_pct(row[iRate])
        grade_raw = str(row[iGrade]).strip()
        grade = re.sub(r"^\d+\.", "", grade_raw).strip()
        shipped = max(0, base - avail)
        w4 = [to_num(row[i]) for i in w_idx[16:20]] if len(w_idx) >= 20 else []
        w4_prev = [to_num(row[i]) for i in w_idx[12:16]] if len(w_idx) >= 16 else []
        dormant_codes.add(code)
        dormant_items.append({
            "level": grade if grade in ("비상", "경고", "주의") else None,
            "dept": str(row[iDept]).strip(),
            "code": code,
            "name": str(row[iName]).strip(),
            "base": base, "avail": int(round(avail)),
            "shipped": int(round(shipped)),
            "rate": rate, "amount": amount,
            "ship4w": int(round(sum(w4))),
            "ship4w_prev": int(round(sum(w4_prev))),
            "is_dormant": True,
        })

    # --- 4-3. 8컬럼 부서별 영역 ---
    sku_8col = {}
    for i, row in enumerate(rows):
        if len(row) < 8 or i < 200 or i > 450:
            continue
        code = str(row[2]).strip()
        if not re.match(r"^B\w+", code):
            continue
        dept = str(row[1]).strip()
        if dept not in CHANNEL_NAMES:
            continue
        base = to_num(row[6])
        current = to_num(row[7])
        if code not in sku_8col:
            sku_8col[code] = {"dept": dept, "name": str(row[3]).strip(), "base": 0, "current": 0}
        sku_8col[code]["base"] += base
        sku_8col[code]["current"] += current

    # --- 4-4. 18컬럼 위험점수·유통기한 ---
    score_by_code = {}
    expiry_by_code = defaultdict(list)
    near_expiry_by_code = defaultdict(int)
    total_near_6m = 0
    for row in rows:
        if len(row) != 18:
            continue
        code = str(row[0]).strip()
        if not re.match(r"^B\w+", code):
            continue
        avail = int(to_num(row[3]))
        exp_date = str(row[4]).strip()
        remaining = to_num(row[5])
        total_score = to_num(row[10])
        if exp_date and avail > 0:
            m = exp_date[:7] if re.match(r"^\d{4}-\d{2}", exp_date) else exp_date
            expiry_by_code[code].append((m, avail))
            if remaining and remaining <= 6:
                near_expiry_by_code[code] += avail
                total_near_6m += avail
        if total_score > 0:
            # 같은 코드가 여러 라인으로 나오면 최댓값을 점수로 채택
            score_by_code[code] = max(score_by_code.get(code, 0), int(total_score))

    expiry_clean = {}
    for code, lst in expiry_by_code.items():
        by_month = defaultdict(int)
        for m, q in lst:
            by_month[m] += q
        expiry_clean[code] = sorted(by_month.items())

    # --- 4-5. 부진 외 SKU 가상행 ---
    non_dormant_items = []
    for code, info in sku_8col.items():
        if code in dormant_codes:
            continue
        base = info["base"]
        avail = info["current"]
        shipped = max(0, base - avail)
        rate = shipped / base if base > 0 else 0
        d_avail_dept = sum(i["avail"] for i in dormant_items if i["dept"] == info["dept"])
        d_amount_dept = sum(i["amount"] for i in dormant_items if i["dept"] == info["dept"])
        unit_price = d_amount_dept / d_avail_dept if d_avail_dept > 0 else 5000
        amount = avail * unit_price
        non_dormant_items.append({
            "level": None, "dept": info["dept"], "code": code, "name": info["name"],
            "base": base, "avail": int(round(avail)), "shipped": int(round(shipped)),
            "rate": rate, "amount": amount, "ship4w": 0, "ship4w_prev": 0,
            "is_dormant": False,
        })

    # --- 4-6. 등급 분류 ---
    # 점수 기반 분류만 신뢰 (시트 grade는 무시) → 점수 없으면 amount 환산 점수로 보조 산정
    def classify(it):
        score = score_by_code.get(it["code"])
        if score is None:
            # 점수가 없으면 금액(원)을 10만 단위 환산해서 보조 점수로 사용
            score = round(it["amount"] / 100000)
        if score > 100:
            return "비상", score
        elif score >= 50:
            return "경고", score
        else:
            return "주의", score

    all_items = dormant_items + non_dormant_items
    for it in all_items:
        lv, sc = classify(it)
        it["level"] = lv
        it["score"] = sc
        it["expiry"] = expiry_clean.get(it["code"], [])
        it["near_expiry"] = int(near_expiry_by_code.get(it["code"], 0))

    return {
        "channels": channels,
        "items": all_items,
        "dormant_items": dormant_items,
        "total_near_6m": total_near_6m,
    }

# ============================================================
# 5. 헤더
# ============================================================
st.markdown(
    f'<h1 style="margin-bottom:4px;">📦 26년 부진·부동 재고 소진 대시보드'
    f'<span class="standalone-badge">LIVE</span></h1>'
    f'<div style="color:#666; font-size:13px; margin-bottom:14px;">'
    f'Google Sheets 연동 · 매일 자정(KST) 자동 갱신 · 수량: EA · 금액: 원 · 데이터 기준일: {kst_today_key()}'
    f'</div>',
    unsafe_allow_html=True,
)

# ============================================================
# 6. 데이터 로드
# ============================================================
try:
    df = load_sheet(kst_today_key())
    data = parse_sheet(df)
except Exception as e:
    st.error(f"시트 로딩 실패: {e}")
    st.info("시트가 '웹에 게시'되어 있는지 확인하세요. (파일 → 공유 → 웹에 게시)")
    st.stop()

if not data["items"]:
    st.error(f"메인 데이터를 찾지 못했습니다. ({data.get('error','')})")
    st.stop()

channels = data["channels"]
all_items = data["items"]
dormant_items = data["dormant_items"]
total_near_6m = data.get("total_near_6m", 0)

shown = [i for i in all_items if i["rate"] < 0.9]
excluded_count = len(all_items) - len(shown)

# ============================================================
# 7. 사이드바
# ============================================================
with st.sidebar:
    st.header("필터")
    depts = ["전체"] + sorted(set(i["dept"] for i in shown))
    sel_dept = st.selectbox("부서", depts)
    grades = ["전체", "비상", "경고", "주의"]
    sel_grade = st.selectbox("위험도", grades)
    st.markdown("---")
    st.markdown(f"**전체 SKU**: {len(all_items)}건")
    st.markdown(f"**90% 이상 제외**: {excluded_count}건")
    st.markdown(f"**표시**: {len(shown)}건")
    if st.button("🔄 시트 새로고침"):
        st.cache_data.clear()
        st.rerun()

# ============================================================
# 8. KPI 계산 — 채널 합계 + 부진 SKU 백업 경로
# ============================================================
emergency = sum(1 for i in all_items if i["level"] == "비상")
warning   = sum(1 for i in all_items if i["level"] == "경고")
caution   = sum(1 for i in all_items if i["level"] == "주의")
cleanup_amount = sum(i["amount"] for i in dormant_items)

# 채널 요약 우선, 실패시 부진 SKU base/shipped 합으로 백업
total_assigned = sum(c["assigned"] for c in channels.values())
total_consumed = sum(c["consumed"] for c in channels.values())
if total_assigned <= 0:
    total_assigned = sum(i["base"] for i in dormant_items)
    total_consumed = sum(i["shipped"] for i in dormant_items)
sell_rate = (total_consumed / total_assigned) if total_assigned > 0 else 0

# ============================================================
# 9. KPI 카드 (시안 톤)
# ============================================================
st.markdown(f"""
<div class="kpi-row">
  <div class="kpi total"><div class="label">총 품목</div><div class="value">{len(all_items)}건</div></div>
  <div class="kpi emergency"><div class="label">🔴 비상</div><div class="value">{emergency}건</div></div>
  <div class="kpi warning"><div class="label">🟡 경고</div><div class="value">{warning}건</div></div>
  <div class="kpi caution"><div class="label">⚪ 주의</div><div class="value">{caution}건</div></div>
  <div class="kpi amount"><div class="label">정리 대상 금액</div><div class="value">{fmt_won(cleanup_amount)}</div></div>
  <div class="kpi sellrate"><div class="label">재고 소진율</div><div class="value">{sell_rate*100:.1f}%</div></div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 10. 위험 점수 산식 바
# ============================================================
st.markdown("""
<div class="formula-bar">
  <span class="lbl">위험 점수</span>
  <span>Σ (잔존유통기한 점수 × 가용재고 × 원가) ÷ 100,000</span>
  <span class="sep">|</span>
  <span class="lbl">점수</span>
  <span><span class="em-red">≤12M·10</span> · <span class="em-orange">≤18M·5</span> · <span class="em-blue">≤24M·2</span> · 그외·1</span>
  <span class="sep">|</span>
  <span class="lbl">등급</span>
  <span>주의&lt;50 · <span class="em-orange">경고 50~100</span> · <span class="em-red">비상&gt;100</span></span>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 11. 주간 재고 분석 인사이트
# ============================================================
ship_now = sum(i["ship4w"] for i in dormant_items)
ship_prev = sum(i["ship4w_prev"] for i in dormant_items)
momentum = ((ship_now - ship_prev) / ship_prev * 100) if ship_prev > 0 else 0
momentum_sign = "+" if momentum >= 0 else ""
momentum_msg = "소진 모멘텀 회복 중." if momentum >= 0 else "소진 모멘텀 둔화."

by_dept_full = defaultdict(lambda: {"amount": 0, "emergency": 0, "consumed": 0, "assigned": 0})
for it in dormant_items:
    by_dept_full[it["dept"]]["amount"] += it["amount"]
    if it["level"] == "비상":
        by_dept_full[it["dept"]]["emergency"] += 1
for d, c in channels.items():
    by_dept_full[d]["consumed"] = c["consumed"]
    by_dept_full[d]["assigned"] = c["assigned"]

top_dept = max(by_dept_full.items(), key=lambda x: x[1]["amount"]) if by_dept_full else None
if top_dept:
    d_name, d_v = top_dept
    pct_of_total = (d_v["amount"] / cleanup_amount * 100) if cleanup_amount > 0 else 0
    d_rate = (d_v["consumed"] / d_v["assigned"] * 100) if d_v["assigned"] > 0 else 0
    dept_items = [i for i in all_items if i["dept"] == d_name and i["level"] == "비상"]
    top_sku = max(dept_items, key=lambda x: x["score"]) if dept_items else None
    sku_line = f"최우선: {top_sku['name']} ({top_sku['code']}, 위험점수 {top_sku['score']})" if top_sku else ""
    dept_msg = (f"{d_name} 부진 정리 대상 {fmt_won(d_v['amount'])} (부진 전체의 {pct_of_total:.1f}%) · "
                f"비상 {d_v['emergency']}건. 채널 전체 소진율 {d_rate:.1f}%. {sku_line}")
else:
    dept_msg = "부서 데이터가 없습니다."
    d_name = "-"

total_avail = sum(i["avail"] for i in all_items)
near_pct = (total_near_6m / total_avail * 100) if total_avail > 0 else 0
if near_pct < 5:
    expiry_msg = (f"유통기한 6개월 이내 재고 {total_near_6m:,} EA (전체의 {near_pct:.1f}%). "
                  f"단기 폐기 위험은 낮음 — 24개월 이상 장기 재고 분기별 소진 계획 우선.")
else:
    expiry_msg = (f"유통기한 6개월 이내 재고 {total_near_6m:,} EA (전체의 {near_pct:.1f}%). "
                  f"단기 폐기 위험 — 즉시 채널 다변화·할인 검토 필요.")

stagnant = sorted([i for i in dormant_items if i["ship4w"] == 0], key=lambda x: -x["amount"])[:3]
if stagnant:
    s_sum = sum(s["amount"] for s in stagnant)
    s_list = " · ".join(f"{s['name']}({s['amount']/1e8:.2f}억)" for s in stagnant)
    stagnant_msg = (f"최근 4주 출고 0건이면서 위험금액 상위 3건: {s_list}. "
                    f"합계 {fmt_won(s_sum)}, B2B/핸디샵 전환 등 강제 채널 필요.")
else:
    stagnant_msg = "최근 4주 출고 0건인 부진 SKU 없음."

st.markdown(f"""
<div class="insight-section-title">📋 주간 재고 분석 인사이트 <span class="auto-tag">자동 분석</span></div>
<div class="insight-grid">
  <div class="insight blue">
    <div class="title">📈 재고 분석 추이 ① · 출고 모멘텀</div>
    부진 SKU 최근 4주(17W~20W) 출고 {ship_now:,} EA, 직전 4주(13W~16W) {ship_prev:,} EA 대비 <b>{momentum_sign}{momentum:.1f}%</b>. {momentum_msg}
  </div>
  <div class="insight red">
    <div class="title">🔴 실천 필요 부서: {d_name}</div>
    {dept_msg}
  </div>
  <div class="insight green">
    <div class="title">📊 재고 분석 추이 ② · 유통기한 임박</div>
    {expiry_msg}
  </div>
  <div class="insight yellow">
    <div class="title">⚠️ 실천 필요 품목: 정체 SKU</div>
    {stagnant_msg}
  </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 12. 부서별 정리 대상 금액 + 위험도 분포
# ============================================================
by_dept = defaultdict(lambda: {"amount": 0, "avail": 0})
for it in dormant_items:
    by_dept[it["dept"]]["amount"] += it["amount"]
    by_dept[it["dept"]]["avail"] += it["avail"]
dept_df = pd.DataFrame([
    {"부서": d, "정리 금액(원)": v["amount"], "가용재고(EA)": v["avail"]}
    for d, v in sorted(by_dept.items(), key=lambda x: -x[1]["amount"])
])

col_a, col_b = st.columns([1.4, 1])
with col_a:
    st.subheader("부서별 정리 대상 금액")
    fig = px.bar(dept_df, x="부서", y="정리 금액(원)",
                 text=dept_df["정리 금액(원)"].apply(fmt_won))
    fig.update_traces(marker_color="#378ADD", textposition="outside")
    fig.update_yaxes(tickformat=",.0f",
        tickvals=[0, 1e8, 2e8, 3e8, 4e8, 5e8, 6e8],
        ticktext=["0원", "1억원", "2억원", "3억원", "4억원", "5억원", "6억원"])
    fig.update_layout(height=340, margin=dict(t=10, b=20))
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("위험도 분포 (금액 비중)")
    level_amount = {"비상": 0, "경고": 0, "주의": 0}
    for it in shown:
        level_amount[it["level"]] += it["amount"]
    pie_df = pd.DataFrame([{"등급": k, "금액": v} for k, v in level_amount.items()])
    fig = px.pie(pie_df, names="등급", values="금액", color="등급",
                 color_discrete_map={"비상": "#E24B4A", "경고": "#EF9F27", "주의": "#888780"})
    fig.update_traces(textinfo="label+percent")
    fig.update_layout(height=340, margin=dict(t=10, b=20))
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# 13. 필터 적용 후 상세 테이블
# ============================================================
filtered = shown
if sel_dept != "전체":
    filtered = [i for i in filtered if i["dept"] == sel_dept]
if sel_grade != "전체":
    filtered = [i for i in filtered if i["level"] == sel_grade]

st.subheader(f"위험 품목 상세 ({len(filtered)}건 표시 · 소진율 90% 이상 {excluded_count}건 제외)")
priority = sorted(filtered, key=lambda x: (-x["score"] if x["score"] > 0 else 0, -x["amount"]))
detail_df = pd.DataFrame([{
    "위험도": r["level"], "부서": r["dept"], "상품코드": r["code"], "상품명": r["name"],
    "가용재고": r["avail"], "소진율": f'{r["rate"]*100:.1f}%',
    "금액": fmt_won(r["amount"]), "위험점수": r["score"],
} for r in priority])

# 비상=빨강 / 경고=노랑 톤 행 하이라이트
def _highlight_row(row):
    if row["위험도"] == "비상":
        return ["background-color: #FEECEC; color: #B91C1C; font-weight: 600"] * len(row)
    if row["위험도"] == "경고":
        return ["background-color: #FEF6E0; color: #92400E"] * len(row)
    return [""] * len(row)

styled = detail_df.style.apply(_highlight_row, axis=1)
st.dataframe(styled, use_container_width=True, hide_index=True)

# ============================================================
# 14. 부서별 4주 출고 추이 + Top/Bottom 5
# ============================================================
st.subheader("부서별 최근 4주 출고 추이 (17W~20W)")
trend_data = []
for d in sorted(by_dept.keys()):
    items_d = [i for i in dormant_items if i["dept"] == d]
    if items_d:
        trend_data.append({"부서": d, "4주 출고(EA)": sum(i["ship4w"] for i in items_d)})
trend_df = pd.DataFrame(trend_data)
st.bar_chart(trend_df.set_index("부서"))

col_t, col_b2 = st.columns(2)
with col_t:
    st.subheader("🚀 소진율 Top 5 (우수)")
    valid = [i for i in dormant_items if i["base"] > 0 and i["rate"] < 0.9]
    by_w4 = sorted(valid, key=lambda x: -(x["ship4w"] / x["base"]))[:5]
    st.dataframe(pd.DataFrame([{
        "상품명": i["name"][:30], "부서": i["dept"],
        "4주 출고(EA)": i["ship4w"],
        "4주 소진율": f'{i["ship4w"]/i["base"]*100:.1f}%',
    } for i in by_w4]), use_container_width=True, hide_index=True)

with col_b2:
    st.subheader("⚠️ 소진율 Bottom 5 (조치)")
    by_w4_low = sorted(valid, key=lambda x: x["ship4w"] / x["base"])[:5]
    st.dataframe(pd.DataFrame([{
        "상품명": i["name"][:30], "부서": i["dept"],
        "4주 출고(EA)": i["ship4w"],
        "4주 소진율": f'{i["ship4w"]/i["base"]*100:.1f}%',
    } for i in by_w4_low]), use_container_width=True, hide_index=True)

# ============================================================
# 15. 손실 비용 (추정)
# ============================================================
st.subheader("💸 과부진재고 예상 손실 비용 (부서별)")
st.caption("산식: 보관료 + 폐기 비용(가용재고×원가) + 미판매 GP(가용재고×판매원가)")
loss_data = []
for d, v in sorted(by_dept.items(), key=lambda x: -x[1]["amount"]):
    dispose = v["amount"]; gp = dispose * 1.25; store = v["avail"] * 200
    loss_data.append({
        "부서": d, "보관료": fmt_won(store), "폐기 비용": fmt_won(dispose),
        "미판매 GP": fmt_won(gp), "합계": fmt_won(store + dispose + gp),
    })
st.dataframe(pd.DataFrame(loss_data), use_container_width=True, hide_index=True)
st.caption("※ 보관료와 미판매 GP는 임시 추정값.")

# ============================================================
# 16. 푸터
# ============================================================
st.markdown("---")
st.caption(f"데이터 출처: [26년 부진 부동 재고 소진 시트](https://docs.google.com/spreadsheets/d/{SHEET_ID})")
