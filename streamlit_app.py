"""
26년 부진·부동 재고 소진 대시보드 (Streamlit Cloud)
Google Sheets 라이브 연동
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
from collections import defaultdict

st.set_page_config(
    page_title="26년 부진·부동 재고 소진 대시보드",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 설정 — 시트 ID 와 시트 GID
# ============================================================
SHEET_ID = "1agL_qDqdc6NicnaBI50J12tebDxe-TspjJRkzh4K6WA"
# 시트가 "웹에 게시(파일 → 공유 → 웹에 게시 → CSV)"되어 있어야 함.
# pub?output=csv 형식은 인증 없이 익명 GET 가능 (401 회피).
EXPORT_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRT7vP8ND1zE_SQEAr_Ox6F5MgfNxldetfTJ9x8IOCjYlTE9a-mot83vUV6SJ4OkvDdpM15saxIMU3Y"
    "/pub?output=csv"
)

# ============================================================
# 데이터 로딩 — 24시간 캐시 (하루 1회 갱신)
# ============================================================
@st.cache_data(ttl=86400, show_spinner="시트에서 데이터를 읽는 중…")
def load_sheet():
    df = pd.read_csv(EXPORT_URL, header=None, dtype=str, keep_default_na=False)
    return df

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

# ============================================================
# 시트 파싱
# ============================================================
def parse_sheet(df):
    rows = df.values.tolist()

    # 채널 요약 (8컬럼 첫 영역)
    channels = {}
    for row in rows[:15]:
        if len(row) < 8:
            continue
        name = str(row[0]).strip()
        if name in ("중국", "글로벌", "글로벌EC", "오프라인", "온라인", "일본", "미주"):
            channels[name] = {
                "sku": int(to_num(row[1])),
                "assigned": to_num(row[2]),
                "remain": to_num(row[3]),
                "consumed": to_num(row[4]),
            }

    # 메인 헤더 (40컬럼)
    main_h_idx = -1
    main_hdr = None
    for i, row in enumerate(rows):
        joined = "|".join(str(c).replace("\n", " ").strip() for c in row)
        if "상품 코드" in joined and "가용재고" in joined and "등급" in joined:
            main_h_idx = i
            main_hdr = [re.sub(r"\s+", " ", str(c)).strip() for c in row]
            break

    if main_h_idx == -1:
        return {"channels": channels, "items": [], "error": "메인 헤더를 찾지 못함"}

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

    # 8컬럼 부서별 영역 (213~ 부근)
    sku_8col = {}
    for i, row in enumerate(rows):
        if len(row) < 8:
            continue
        if i < 200 or i > 450:
            continue
        code = str(row[2]).strip()
        if not re.match(r"^B\w+", code):
            continue
        dept = str(row[1]).strip()
        if dept not in ("중국", "글로벌", "글로벌EC", "오프라인", "온라인", "일본", "미주"):
            continue
        base = to_num(row[6])
        current = to_num(row[7])
        if code not in sku_8col:
            sku_8col[code] = {"dept": dept, "name": str(row[3]).strip(), "base": 0, "current": 0}
        sku_8col[code]["base"] += base
        sku_8col[code]["current"] += current

    # 18컬럼 위험점수
    score_by_code = {}
    expiry_by_code = defaultdict(list)
    near_expiry_by_code = defaultdict(int)
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
        if total_score > 0:
            score_by_code[code] = int(total_score)

    expiry_clean = {}
    for code, lst in expiry_by_code.items():
        by_month = defaultdict(int)
        for m, q in lst:
            by_month[m] += q
        expiry_clean[code] = sorted(by_month.items())

    # 부진 외 SKU 가상행 생성
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

    # 등급 분류
    def classify(it):
        score = score_by_code.get(it["code"])
        if score is not None:
            if score > 100:
                return "비상", score
            elif score >= 50:
                return "경고", score
            else:
                return "주의", score
        if it["level"] in ("비상", "경고", "주의"):
            return it["level"], round(it["amount"] / 100000)
        a = it["amount"]
        if a >= 1e8:
            return "비상", round(a / 100000)
        if a >= 3e7:
            return "경고", round(a / 100000)
        return "주의", round(a / 100000)

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
    }

# ============================================================
# 한국식 금액 포맷
# ============================================================
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
# 메인
# ============================================================
st.title("📦 26년 부진·부동 재고 소진 대시보드")
st.caption("Google Sheets 연동 · 24시간마다 캐시 자동 갱신 (수동 새로고침 가능)")

try:
    df = load_sheet()
    data = parse_sheet(df)
except Exception as e:
    st.error(f"시트 로딩 실패: {e}")
    st.info("시트가 '웹에 게시'되어 있는지 확인하세요. (파일 → 공유 → 웹에 게시)")
    st.stop()

if not data["items"]:
    st.error("메인 데이터를 찾지 못했습니다.")
    st.json(data.get("error", {}))
    st.stop()

channels = data["channels"]
all_items = data["items"]
dormant_items = data["dormant_items"]

# 필터링 (90% 이상 제외)
shown = [i for i in all_items if i["rate"] < 0.9]
excluded_count = len(all_items) - len(shown)

# 사이드바
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

# 필터 적용
filtered = shown
if sel_dept != "전체":
    filtered = [i for i in filtered if i["dept"] == sel_dept]
if sel_grade != "전체":
    filtered = [i for i in filtered if i["level"] == sel_grade]

# KPI
total_assigned = sum(c["assigned"] for c in channels.values())
total_consumed = sum(c["consumed"] for c in channels.values())
sell_rate = total_consumed / total_assigned if total_assigned > 0 else 0
emergency = sum(1 for i in all_items if i["level"] == "비상")
warning = sum(1 for i in all_items if i["level"] == "경고")
caution = sum(1 for i in all_items if i["level"] == "주의")
cleanup_amount = sum(i["amount"] for i in dormant_items)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("총 품목", f"{len(all_items)}건")
c2.metric("🔴 비상", f"{emergency}건")
c3.metric("🟡 경고", f"{warning}건")
c4.metric("⚪ 주의", f"{caution}건")
c5.metric("정리 대상 금액", fmt_won(cleanup_amount))
c6.metric("재고 소진율", f"{sell_rate*100:.1f}%")

st.info(
    "**위험도 분류 기준** — 시트 등급 컬럼 우선. 시안 사양: 비상 > 100점 · 경고 50~100점 · 주의 < 50점"
)

# 부서별 정리 대상 금액
st.subheader("부서별 정리 대상 금액")
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
    fig = px.bar(
        dept_df, x="부서", y="정리 금액(원)",
        text=dept_df["정리 금액(원)"].apply(fmt_won),
    )
    fig.update_traces(marker_color="#378ADD", textposition="outside")
    fig.update_yaxes(
        tickformat=",.0f",
        tickvals=[0, 1e8, 2e8, 3e8, 4e8, 5e8, 6e8],
        ticktext=["0원", "1억원", "2억원", "3억원", "4억원", "5억원", "6억원"],
    )
    fig.update_layout(height=320, margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    # 위험도 분포 (금액)
    level_amount = {"비상": 0, "경고": 0, "주의": 0}
    for it in shown:
        level_amount[it["level"]] += it["amount"]
    pie_df = pd.DataFrame([{"등급": k, "금액": v} for k, v in level_amount.items()])
    fig = px.pie(
        pie_df, names="등급", values="금액",
        color="등급",
        color_discrete_map={"비상": "#E24B4A", "경고": "#EF9F27", "주의": "#888780"},
    )
    fig.update_traces(textinfo="label+percent")
    fig.update_layout(height=320, margin=dict(t=20, b=20), title="위험도 분포 (금액 비중)")
    st.plotly_chart(fig, use_container_width=True)

# 위험 품목 상세
st.subheader(f"위험 품목 상세 ({len(filtered)}건 표시 · 소진율 90% 이상 {excluded_count}건 제외)")
priority = sorted(filtered, key=lambda x: (-x["score"] if x["score"] > 0 else 0, -x["amount"]))[:30]
detail_df = pd.DataFrame([
    {
        "위험도": r["level"],
        "부서": r["dept"],
        "상품코드": r["code"],
        "상품명": r["name"],
        "가용재고": r["avail"],
        "소진율": f'{r["rate"]*100:.1f}%',
        "금액": fmt_won(r["amount"]),
        "위험점수": r["score"],
    } for r in priority
])
st.dataframe(detail_df, use_container_width=True, hide_index=True)

# 부서별 4주 출고 추이
st.subheader("부서별 최근 4주 출고 추이 (17W~20W)")
dept_w = defaultdict(lambda: [0, 0, 0, 0])
for it in dormant_items:
    # 메인 시트 raw 데이터를 다시 가져오긴 어려우니, 합계만 표시
    pass
trend_data = []
for d in sorted(by_dept.keys()):
    items_d = [i for i in dormant_items if i["dept"] == d]
    if items_d:
        ship4 = sum(i["ship4w"] for i in items_d)
        trend_data.append({"부서": d, "4주 출고(EA)": ship4})
trend_df = pd.DataFrame(trend_data)
st.bar_chart(trend_df.set_index("부서"))

# Top/Bottom 5
col_t, col_b = st.columns(2)
with col_t:
    st.subheader("🚀 소진율 Top 5 (우수)")
    valid = [i for i in dormant_items if i["base"] > 0 and i["rate"] < 0.9]
    by_w4 = sorted(valid, key=lambda x: -(x["ship4w"] / x["base"]))[:5]
    top_df = pd.DataFrame([{
        "상품명": i["name"][:30], "부서": i["dept"],
        "4주 출고(EA)": i["ship4w"],
        "소진율": f'{i["ship4w"]/i["base"]*100:.1f}%',
    } for i in by_w4])
    st.dataframe(top_df, use_container_width=True, hide_index=True)

with col_b:
    st.subheader("⚠️ 소진율 Bottom 5 (조치)")
    by_w4_low = sorted(valid, key=lambda x: x["ship4w"] / x["base"])[:5]
    bot_df = pd.DataFrame([{
        "상품명": i["name"][:30], "부서": i["dept"],
        "4주 출고(EA)": i["ship4w"],
        "소진율": f'{i["ship4w"]/i["base"]*100:.1f}%',
    } for i in by_w4_low])
    st.dataframe(bot_df, use_container_width=True, hide_index=True)

# 손실 비용
st.subheader("💸 과부진재고 예상 손실 비용 (부서별)")
st.caption("산식: 보관료 + 폐기 비용(가용재고×원가) + 미판매 GP(가용재고×판매원가)")
loss_data = []
for d, v in sorted(by_dept.items(), key=lambda x: -x[1]["amount"]):
    dispose = v["amount"]
    gp = dispose * 1.25  # 임시: 판매원가 = 원가 × 1.25
    store = v["avail"] * 200  # 임시: EA당 200원
    total = store + dispose + gp
    loss_data.append({
        "부서": d, "보관료": fmt_won(store), "폐기 비용": fmt_won(dispose),
        "미판매 GP": fmt_won(gp), "합계": fmt_won(total),
    })
st.dataframe(pd.DataFrame(loss_data), use_container_width=True, hide_index=True)
st.caption("※ 보관료와 미판매 GP는 임시 추정값. 정확한 데이터로 갱신 시 합계도 재계산됩니다.")

# 푸터
st.markdown("---")
st.caption(f"데이터 출처: [26년 부진 부동 재고 소진 시트](https://docs.google.com/spreadsheets/d/{SHEET_ID})")
