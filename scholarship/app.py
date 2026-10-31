"""
학자금비서 (ScholarSecretary) - 대학생 맞춤형 장학금 관리 & AI 자소서 첨삭 플랫폼
실행:  pip install streamlit plotly pandas google-genai
       streamlit run app.py
개발자 Gemini 키:  .streamlit/secrets.toml 의 GEMINI_API_KEY = "..." 또는 환경변수 GEMINI_API_KEY
       키가 없거나 네트워크 통신이 불가할 때만 '안심 데모 분석 리포트'로 전환됩니다.
"""
import calendar
import io
import json
import logging
import os
import re
import time
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("scholarsecretary")

# ─────────────────────────────────────────────────────────────
# 0. 페이지 설정 & 테마(CSS)
# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="학자금비서", page_icon="🎓", layout="wide")

NAVY, SLATE_BG, SKY, GRAY = "#0F172A", "#F8FAFC", "#60A5FA", "#E2E8F0"

st.markdown(
    f"""
<style>
.stApp {{ background:{SLATE_BG}; color:{NAVY}; }}
header[data-testid="stHeader"] {{ display: none !important; }}
.block-container {{ padding-top:1rem !important; padding-bottom:2rem; max-width:1200px; }}
[data-testid="stVerticalBlock"] {{ gap:0.6rem; }}
section[data-testid="stSidebar"] {{ background:{NAVY}; }}
section[data-testid="stSidebar"] * {{ color:#E2E8F0; }}
section[data-testid="stSidebar"] input, section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] [data-baseweb="select"] * {{ color:{NAVY} !important; }}
h1,h2,h3,h4 {{ color:{NAVY}; letter-spacing:-0.02em; }}
div[data-testid="stRadio"] > div[role="radiogroup"] {{ gap:0.4rem; flex-wrap:wrap; }}
div[data-testid="stRadio"] label {{ background:#fff; border:1px solid {GRAY}; border-radius:999px;
    padding:0.25rem 0.9rem; }}
div[data-testid="stRadio"] label:has(input:checked) {{ background:{NAVY}; border-color:{NAVY}; }}
div[data-testid="stRadio"] label:has(input:checked) * {{ color:#fff !important; }}
div[data-testid="stRadio"] label > div:first-child {{ display:none; }}
.stButton > button {{ border-radius:10px; border:1px solid {NAVY}; background:#fff; color:{NAVY}; font-weight:600; }}
.stButton > button:hover {{ background:{SKY}; border-color:{SKY}; color:{NAVY}; }}
.stButton > button[kind="primary"] {{ background:{NAVY}; color:#fff; }}
.card {{ background:#fff; border:1px solid {GRAY}; border-radius:14px; padding:0.9rem 1.1rem; }}
.chip {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.75rem;
    font-weight:600; margin-right:4px; background:{GRAY}; color:{NAVY}; }}
.b-red {{ background:#FEE2E2; color:#B91C1C; }}
.b-yellow {{ background:#FEF3C7; color:#B45309; }}
.b-green {{ background:#DCFCE7; color:#15803D; }}
.b-gray {{ background:{GRAY}; color:#475569; }}
.b-navy {{ background:{NAVY}; color:#fff; }}
.b-sky {{ background:#DBEAFE; color:#1D4ED8; }}
.bar {{ height:6px; border-radius:6px; background:{GRAY}; overflow:hidden; margin-top:6px; }}
.bar > div {{ height:100%; background:{SKY}; }}
.hero {{ background:{NAVY}; color:#fff; border-radius:14px; padding:0.8rem 1.1rem; font-weight:700; }}
.muted {{ color:#64748B; font-size:0.85rem; }}
.cal {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
.cal th {{ background:{NAVY}; color:#fff; padding:6px 0; font-size:0.85rem; text-align:center; }}
.cal td {{ height:100px; vertical-align:top; border:1px solid {GRAY}; padding:4px 5px; background:#fff; overflow:hidden; }}
.cal td.empty {{ background:#F1F5F9; }}
.cal td.today {{ outline:2px solid {SKY}; outline-offset:-2px; background:#EFF6FF; }}
.cal .dn {{ font-size:0.8rem; font-weight:700; }}
.cal .sun {{ color:#DC2626; }}
.cal .ev {{ display:block; font-size:0.68rem; padding:1px 6px; border-radius:999px; margin-top:3px;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:600; }}
</style>
""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────
# 1. 데이터
# ─────────────────────────────────────────────────────────────
TODAY = date.today()
STATUSES = ["준비 중", "지원 완료", "서류 합격", "최종 수혜 성공 🎉", "탈락"]
SUCCESS = "최종 수혜 성공 🎉"
NAV = ["🏠 대시보드", "🔍 장학금 탐색", "✍️ AI 자소서 첨삭", "📅 장학금 캘린더", "💬 커뮤니티"]
CATS = ["전체", "교내", "지자체", "교외", "근로"]
INCOME_OPTIONS = list(range(0, 11))  # 0~10구간


def _s(i, name, cat, kind, amount, offset, gpa, income, region, years, kw, url):
    return dict(id=i, name=name, cat=cat, kind=kind, amount=amount,
                deadline=TODAY + timedelta(days=offset), min_gpa=gpa, max_income=income,
                region=region, min_years=years, keywords=kw, url=url)


SCHOLARSHIPS = [
    _s(1, "교내 성적우수장학금", "교내", "등록금성", 2_000_000, 12, 3.5, 10, None, 0,
       ["학업 성취", "꾸준함", "자기주도 학습"], "https://example.ac.kr/s1"),
    _s(2, "교내 소득연계 희망장학금", "교내", "등록금성", 1_500_000, 3, 3.0, 5, None, 0,
       ["성장 의지", "책임감", "나눔"], "https://example.ac.kr/s2"),
    _s(3, "용인시 인재육성장학금", "지자체", "등록금성", 1_000_000, 6, 3.0, 10, "용인시", 2,
       ["지역 기여", "리더십", "성실성"], "https://example.go.kr/s3"),
    _s(4, "경기도 청년 생활안정 장학금", "지자체", "생활비성", 1_200_000, 20, 2.5, 6, "경기도", 1,
       ["자립", "생활 계획", "성장 스토리"], "https://example.go.kr/s4"),
    _s(5, "미래인재재단 글로벌 장학금", "교외", "등록금성", 4_000_000, 35, 4.0, 4, None, 0,
       ["글로벌 역량", "도전", "비전"], "https://example.org/s5"),
    _s(6, "교내 근로장학생", "근로", "근로성", 600_000, 0, 2.5, 10, None, 0,
       ["성실", "협업", "책임감"], "https://example.ac.kr/s6"),
    _s(7, "지역사회공헌 생활비 지원", "교외", "생활비성", 800_000, 9, 3.0, 8, None, 0,
       ["사회공헌", "봉사 경험", "공동체"], "https://example.org/s7"),
    _s(8, "공공기관 서포터즈 근로장학", "근로", "근로성", 900_000, 45, 3.0, 10, None, 0,
       ["커뮤니케이션", "기획력", "실행력"], "https://example.go.kr/s8"),
    _s(9, "서울시 인재장학금", "지자체", "등록금성", 2_000_000, 5, 3.3, 7, "서울", 1,
       ["지역 이해", "공익", "리더십"], "https://example.go.kr/s9"),
    _s(10, "해외 어학연수 생활비 지원", "교외", "생활비성", 1_500_000, 60, 3.8, 7, None, 0,
       ["어학 역량", "목표 의식", "국제 감각"], "https://example.org/s10"),
]
SCH_BY_ID = {s["id"]: s for s in SCHOLARSHIPS}


def init_state():
    ss = st.session_state
    ss.setdefault("profile", dict(name="이OO", univ="한국외국어대학교", gpa=3.8, income=9,
                                  region="경기도 용인시", region_years=2, tuition=4_000_000))
    ss.setdefault("apps", {1: {"status": "준비 중"}, 6: {"status": "지원 완료"}})
    ss.setdefault("posts", [
        dict(id=3, title="근로장학 면접 후기", author="김OO", cat="후기",
             content="질문은 근무 가능 시간과 협업 경험 위주였어요. 시간표를 미리 정리해 가면 좋습니다.",
             likes=7, date=str(TODAY - timedelta(days=1))),
        dict(id=2, title="자소서에 숫자를 꼭 넣으세요", author="박OO", cat="팁",
             content="'열심히 했다' 대신 '주 10시간, 6개월' 같은 수치를 넣었더니 피드백이 확 달라졌어요.",
             likes=12, date=str(TODAY - timedelta(days=3))),
        dict(id=1, title="지자체 장학금은 거주 기간 확인!", author="최OO", cat="팁",
             content="전입일 기준 거주 2년 요건이 많아서 주민등록초본을 미리 떼어두세요.",
             likes=4, date=str(TODAY - timedelta(days=6))),
    ])
    ss.setdefault("nav", NAV[0])
    ss.setdefault("fit_min", 80)
    ss.setdefault("cal_year", TODAY.year)
    ss.setdefault("cal_month", TODAY.month)
    ss.setdefault("cat", "전체")
    ss.setdefault("ai_report", None)
    ss.setdefault("ai_error", None)
    ss.setdefault("ai_log", [])
    ss.setdefault("ocr_msg", None)
    ss.setdefault("profile_msg", None)


init_state()
ss = st.session_state

# ─────────────────────────────────────────────────────────────
# 2. 핵심 로직
# ─────────────────────────────────────────────────────────────
def evaluate(s, p):
    """지원 자격(Pass/Fail) 및 적합도(%) 계산. Pass 이면 80~100, Fail 이면 최대 79."""
    reasons, ok = [], True
    gpa_ok = p["gpa"] >= s["min_gpa"]
    inc_ok = p["income"] <= s["max_income"]
    if s["region"] is None:
        reg_ok = True
    else:
        reg_ok = s["region"] in p["region"] and p["region_years"] >= s["min_years"]
    reasons.append(("학점", gpa_ok, f"{p['gpa']:.1f} / 기준 {s['min_gpa']:.1f}↑"))
    reasons.append(("소득", inc_ok, f"{p['income']}구간 / 기준 {s['max_income']}구간↓"))
    if s["region"]:
        reasons.append(("거주지", reg_ok, f"{s['region']} {s['min_years']}년↑"))
    ok = gpa_ok and inc_ok and reg_ok
    if ok:
        gm = (p["gpa"] - s["min_gpa"]) / max(4.5 - s["min_gpa"], 0.1)
        im = (s["max_income"] - p["income"]) / max(s["max_income"], 1)
        fit = 80 + min(20, round(gm * 10 + im * 10))
    else:
        g = 1 if gpa_ok else max(0, 1 - (s["min_gpa"] - p["gpa"]) / 1.0)
        i = 1 if inc_ok else max(0, 1 - (p["income"] - s["max_income"]) / 5)
        r = 1 if reg_ok else 0
        fit = min(79, round(100 * (0.4 * g + 0.35 * i + 0.25 * r)))
    return dict(ok=ok, fit=fit, reasons=reasons)


def confirmed_amount():
    return sum(SCH_BY_ID[i]["amount"] for i, a in ss.apps.items() if a["status"] == SUCCESS)


def waiver_ratio():
    t = ss.profile["tuition"]
    try:
        return confirmed_amount() / t * 100
    except ZeroDivisionError:
        return 0.0


def tuition_covered():
    return ss.profile["tuition"] > 0 and waiver_ratio() >= 100


def visible_scholarships():
    """스마트 필터링: 등록금 100% 충족 시 '등록금성' 공고는 (신청 중인 것 제외) 목록에서 제외."""
    out = []
    for s in SCHOLARSHIPS:
        if tuition_covered() and s["kind"] == "등록금성" and s["id"] not in ss.apps:
            continue
        out.append(s)
    return out


def dday_info(d):
    n = (d - TODAY).days
    if n < 0:
        return "마감", "b-gray", n
    if n == 0:
        return "D-0", "b-red", n
    if n <= 7:
        return f"D-{n}", "b-yellow", n
    return f"D-{n}", "b-green", n


def won(n):
    return f"{int(n):,}원"


# 콜백 (즉시 모든 탭에 반영)
def add_app(sid):
    ss.apps[sid] = {"status": "준비 중"}


def del_app(sid):
    ss.apps.pop(sid, None)
    ss.pop(f"status_{sid}", None)


def go_explore():
    """대시보드 스마트 알림 -> 탐색 탭 이동, 슬라이더 기본 80%, 검색/카테고리 초기화."""
    ss.nav = NAV[1]
    ss.fit_min = 80
    ss.pop("fit_slider", None)
    ss.ex_q = ""
    ss.cat = "전체"


def shift_month(delta):
    m = ss.cal_month + delta
    y = ss.cal_year
    if m < 1:
        m, y = 12, y - 1
    elif m > 12:
        m, y = 1, y + 1
    ss.cal_year, ss.cal_month = y, m


def goto_today():
    ss.cal_year, ss.cal_month = TODAY.year, TODAY.month


def search_text(s):
    return " ".join([s["name"], s["cat"], s["kind"], s["region"] or "", " ".join(s["keywords"]),
                     f"학점 {s['min_gpa']:.1f} 소득 {s['max_income']}구간"]).lower()


def like_post(pid):
    for p in ss.posts:
        if p["id"] == pid:
            p["likes"] += 1


def apply_ocr():
    ss.profile["gpa"] = 4.2
    ss.profile["income"] = 3
    ss.ocr_msg = "✅ AI 추출 완료: 학점 3.8 ➔ 4.2 / 소득분위 9 ➔ 3구간 으로 갱신되었습니다."


# ─────────────────────────────────────────────────────────────
# 3. 사이드바
# ─────────────────────────────────────────────────────────────
p = ss.profile
with st.sidebar:
    st.markdown("## 🎓 학자금비서")
    st.markdown(
        f"""
**{p['name']}** · {p['univ']}  
- 학점 **{p['gpa']:.1f} / 4.5**
- 소득분위 **{p['income']}구간**
- 거주지 **{p['region']}** ({p['region_years']}년 이상)
- 실제 등록금 **{won(p['tuition'])}**
"""
    )
    if ss.profile_msg:
        st.success(ss.profile_msg)
        ss.profile_msg = None

    with st.expander("✏️ 프로필 직접 수정"):
        with st.form("profile_form"):
            n_name = st.text_input("이름", p["name"])
            n_univ = st.text_input("대학교", p["univ"])
            n_gpa = st.number_input("학점 (4.5 만점)", 0.0, 4.5, float(p["gpa"]), 0.1)
            n_inc = st.selectbox("소득분위", INCOME_OPTIONS, index=INCOME_OPTIONS.index(p["income"]))
            n_reg = st.text_input("거주지", p["region"])
            n_yrs = st.number_input("거주 기간(년)", 0, 50, int(p["region_years"]))
            n_tui = st.number_input("실제 등록금(원)", 0, 100_000_000, int(p["tuition"]), 100_000)
            if st.form_submit_button("저장", use_container_width=True):
                ss.profile = dict(name=n_name, univ=n_univ, gpa=float(n_gpa), income=int(n_inc),
                                  region=n_reg, region_years=int(n_yrs), tuition=int(n_tui))
                ss.profile_msg = "프로필이 저장되어 모든 공고의 적합도가 재계산되었습니다."
                st.rerun()

    st.markdown("---")
    st.markdown("#### 📄 성적표·증명서 OCR (시연)")
    up = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"], label_visibility="collapsed")
    if up is not None:
        st.image(up, use_container_width=True)
    st.button("🤖 AI 추출 데이터 적용", disabled=up is None, on_click=apply_ocr, use_container_width=True)
    if ss.ocr_msg:
        st.success(ss.ocr_msg)

# ─────────────────────────────────────────────────────────────
# 4. 내비게이션 (버튼으로 탭 자동 이동이 가능하도록 radio 사용)
# ─────────────────────────────────────────────────────────────
st.radio("메뉴", NAV, horizontal=True, key="nav", label_visibility="collapsed")
page = ss.nav


# ─────────────────────────────────────────────────────────────
# TAB 1. 대시보드
# ─────────────────────────────────────────────────────────────
def donut(ratio):
    if ratio <= 0:
        vals, cols = [1], [GRAY]
    elif ratio < 100:
        vals, cols = [ratio, 100 - ratio], [SKY, GRAY]
    elif ratio == 100:
        vals, cols = [1], [SKY]
    else:
        vals, cols = [1], [NAVY]
    fig = go.Figure(go.Pie(values=vals, hole=0.74, marker=dict(colors=cols), sort=False,
                           direction="clockwise", textinfo="none", hoverinfo="skip", rotation=0))
    fig.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=0, b=0), height=260,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(text=f"<b>{ratio:.0f}%</b><br><span style='font-size:12px'>등록금 감면</span>",
                          x=0.5, y=0.5, showarrow=False, font=dict(size=30, color=NAVY))],
    )
    return fig


def build_csv():
    rows = []
    for sid in sorted(ss.apps, key=lambda i: SCH_BY_ID[i]["deadline"]):
        s, app = SCH_BY_ID[sid], ss.apps[sid]
        rows.append({
            "장학금명": s["name"], "카테고리": s["cat"], "유형": s["kind"],
            "마감일": str(s["deadline"]), "진행 상태": app["status"].replace(" 🎉", ""),
            "지원 금액(원)": s["amount"],
            "확정 수혜 금액(원)": s["amount"] if app["status"] == SUCCESS else 0,
        })
    df = pd.DataFrame(rows, columns=["장학금명", "카테고리", "유형", "마감일", "진행 상태",
                                     "지원 금액(원)", "확정 수혜 금액(원)"])
    total = pd.DataFrame([{"장학금명": "합계 (확정 수혜 금액)", "확정 수혜 금액(원)": confirmed_amount()}])
    df = pd.concat([df, total], ignore_index=True).fillna("")
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8-sig")  # 엑셀에서 한글이 깨지지 않도록 BOM 포함


def render_csv_export():
    st.markdown("### 📥 내보내기")
    st.download_button("📄 신청 목록 · 수혜 금액 CSV 다운로드", data=build_csv(),
                       file_name=f"scholarship_{TODAY}.csv", mime="text/csv",
                       key="csv_download")


def render_dashboard():
    prof = ss.profile
    ratio = waiver_ratio()
    got = confirmed_amount()
    left, right = st.columns([1, 1.35], gap="medium")
    with left:
        st.plotly_chart(donut(ratio), use_container_width=True, config={"displayModeBar": False})
    with right:
        st.markdown(f"### {prof['name']}님의 장학 현황")
        m1, m2, m3 = st.columns(3)
        m1.metric("확정 수혜 금액", won(got))
        m2.metric("실제 등록금", won(prof["tuition"]))
        m3.metric("관리 중인 신청", f"{len(ss.apps)}건")
        if prof["tuition"] <= 0:
            st.info("등록금이 0원으로 설정되어 감면 비율은 0%로 고정됩니다.")
        elif ratio >= 100:
            extra = got - prof["tuition"]
            st.markdown(f"<div class='hero'>🎉 등록금 전액 감면 + 생활비 {won(extra)} 추가 수혜 확정!</div>",
                        unsafe_allow_html=True)

        # 스마트 알림 카드
        managed = set(ss.apps)
        recs = [s for s in visible_scholarships()
                if s["id"] not in managed and evaluate(s, prof)["fit"] >= 80
                and dday_info(s["deadline"])[2] >= 0]
        with st.container(border=True):
            st.markdown("**🔔 맞춤 장학금 스마트 알림**")
            if recs:
                names = ", ".join(s["name"] for s in recs[:2]) + (" 외" if len(recs) > 2 else "")
                st.write(f"적합도 80% 이상 신규 공고 **{len(recs)}건** — {names}")
                st.button("추천 공고 탐색으로 이동 →", on_click=go_explore, key="go_explore", type="primary")
            else:
                st.write("지금 추천할 신규 공고가 없어요. 프로필을 갱신하면 새 추천이 나타납니다.")

    st.markdown("### 📋 내 신청 및 수혜 관리")
    if not ss.apps:
        st.info("아직 관리 중인 신청이 없습니다. '장학금 탐색'에서 추가해 보세요.")
    for sid in sorted(ss.apps, key=lambda i: SCH_BY_ID[i]["deadline"]):
        s, app = SCH_BY_ID[sid], ss.apps[sid]
        label, cls, _ = dday_info(s["deadline"])
        with st.container(border=True):
            c1, c2, c3 = st.columns([3.2, 2, 1])
            c1.markdown(
                f"**{s['name']}**  \n<span class='chip'>{s['cat']}</span><span class='chip'>{s['kind']}</span>"
                f"<span class='chip {cls}'>{label}</span> <span class='muted'>마감 {s['deadline']} · {won(s['amount'])}</span>",
                unsafe_allow_html=True)
            new = c2.selectbox("진행 상태", STATUSES, index=STATUSES.index(app["status"]),
                               key=f"status_{sid}", label_visibility="collapsed")
            c3.button("🗑️ 삭제", key=f"dash_del_{sid}", on_click=del_app, args=(sid,),
                      use_container_width=True)
            if new != app["status"]:
                app["status"] = new
                st.rerun()

    render_csv_export()


# ─────────────────────────────────────────────────────────────
# TAB 2. 장학금 탐색
# ─────────────────────────────────────────────────────────────
def render_explore():
    prof = ss.profile
    st.markdown("### 🔍 장학금 탐색")
    st.text_input("🔎 검색", key="ex_q",
                  placeholder="장학금 이름·카테고리·자격 키워드 (예: 용인시 인재육성장학금, 성적, 근로, 용인)")
    f1, f2 = st.columns([3, 2])
    f1.radio("카테고리", CATS, horizontal=True, key="cat", label_visibility="collapsed")
    f2.slider("최소 적합도 (%)", 0, 100, value=ss.fit_min, step=5, key="fit_slider")
    ss.fit_min = ss.fit_slider

    if tuition_covered():
        st.success("🎓 등록금을 100% 이상 채우셨어요! '등록금성' 공고는 제외하고 생활비성·근로성 장학금을 우선 추천합니다.")

    items = visible_scholarships()
    if ss.cat != "전체":
        items = [s for s in items if s["cat"] == ss.cat]
    terms = ss.ex_q.lower().split()
    if terms:
        items = [s for s in items if all(t in search_text(s) for t in terms)]
    rows = [(s, evaluate(s, prof)) for s in items]
    rows = [(s, e) for s, e in rows if e["fit"] >= ss.fit_min]
    # 정렬: 생활비/근로성 우선(등록금 충족 시) → 적합도 ↓ → 마감 임박
    cov = tuition_covered()
    rows.sort(key=lambda r: (-(cov and r[0]["kind"] != "등록금성"), -r[1]["fit"], r[0]["deadline"]))

    if not rows:
        st.info("조건에 맞는 공고가 없습니다. 필터를 조정해 보세요.")
        return
    st.caption(f"총 {len(rows)}건")
    for s, e in rows:
        label, cls, _ = dday_info(s["deadline"])
        pf = "<span class='chip b-green'>Pass</span>" if e["ok"] else "<span class='chip b-red'>Fail</span>"
        why = " · ".join(f"{'✅' if ok else '❌'} {k} {d}" for k, ok, d in e["reasons"])
        with st.container(border=True):
            c1, c2 = st.columns([4, 1.4])
            c1.markdown(
                f"**{s['name']}** &nbsp;{pf}<span class='chip {cls}'>{label}</span>  \n"
                f"<span class='chip'>{s['cat']}</span><span class='chip b-sky'>{s['kind']}</span>"
                f"<span class='muted'>지원금 {won(s['amount'])} · 마감 {s['deadline']}</span>  \n"
                f"<span class='muted'>{why}</span>  \n"
                f"<span class='muted'>적합도 <b>{e['fit']}%</b></span>"
                f"<div class='bar'><div style='width:{e['fit']}%'></div></div>",
                unsafe_allow_html=True)
            with c2:
                if s["id"] in ss.apps:
                    st.markdown("<span class='chip b-navy'>✅ 이미 신청 관리 중</span>", unsafe_allow_html=True)
                    st.button("🗑️ 신청 취소", key=f"ex_del_{s['id']}", on_click=del_app, args=(s["id"],),
                              use_container_width=True)
                else:
                    st.button("➕ 신청 관리 목록에 추가", key=f"ex_add_{s['id']}", on_click=add_app,
                              args=(s["id"],), type="primary", use_container_width=True)


# ─────────────────────────────────────────────────────────────
# TAB 3. AI 자소서 첨삭
# ─────────────────────────────────────────────────────────────
def demo_report(title, keywords, essay):
    has_num = bool(re.search(r"\d", essay))
    return dict(
        keywords=(keywords + ["성장", "책임감", "진정성"])[:3],
        strengths=[
            "지원 동기와 본인의 경험이 자연스럽게 연결되어 읽는 흐름이 좋습니다.",
            f"'{title}'의 취지에 공감하는 태도가 문장 곳곳에서 드러납니다.",
        ] if essay.strip() else ["작성된 내용이 없어 일반 가이드를 제공합니다."],
        improvements=[
            "활동 기간·횟수·성과를 숫자로 제시해 보세요. (예: 6개월간 주 10시간, 참여자 30% 증가)"
            if not has_num else "이미 수치가 포함되어 있어요. 수치의 '비교 기준'(전/후)을 덧붙이면 더 설득력이 생깁니다.",
            "추상적 표현(열심히, 최선을) 대신 구체적 상황 → 행동 → 결과(STAR) 순서로 한 사례를 깊게 서술하세요.",
            "마지막 문단에 장학금 수혜 후 계획(학업·사회 기여)을 2~3문장으로 명확히 제시하세요.",
        ],
        source="안심 데모 분석 리포트",
    )


# ── Gemini 연동 ────────────────────────────────────────────
MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]


class NetworkUnavailable(Exception):
    """네트워크 통신 자체가 불가능한 경우(이때만 데모 리포트로 전환)."""


def clean_key(raw):
    """공백/개행/따옴표/'GEMINI_API_KEY=' 접두어 오타를 제거. 키 형식(AIzaSy..., AQ... 등)은 검사하지 않는다."""
    if raw is None:
        return ""
    k = str(raw).strip()
    k = re.sub(r"^(export\s+)?GEMINI_API_KEY\s*=\s*", "", k)
    k = k.strip().strip("'\"`“”‘’").strip()
    return re.sub(r"\s+", "", k)


def get_api_key():
    """개발자 키만 사용: st.secrets["GEMINI_API_KEY"] -> 환경변수 GEMINI_API_KEY 순서."""
    try:
        key = clean_key(st.secrets["GEMINI_API_KEY"])
    except Exception:  # secrets.toml 없음 / 키 없음
        key = ""
    return key or clean_key(os.environ.get("GEMINI_API_KEY"))


def mask_key(key):
    return f"{key[:6]}…{key[-4:]}" if len(key) > 12 else "***"


def is_network_error(e):
    names = " ".join(c.__name__ for c in type(e).__mro__).lower()
    msg = str(e).lower()
    name_hits = ("connecterror", "connecttimeout", "readtimeout", "timeout", "connectionerror",
                 "networkerror", "gaierror", "connectionrefused")
    msg_hits = ("getaddrinfo", "name or service not known", "temporary failure in name resolution",
                "connection refused", "network is unreachable", "failed to establish a new connection",
                "connection error", "timed out")
    return any(t in names for t in name_hits) or any(t in msg for t in msg_hits)


def is_transient(msg):
    return any(t in msg for t in ("429", "500", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded"))


def explain_error(e, key):
    msg = str(e).replace(key, "***") if key else str(e)
    if any(t in msg for t in ("API_KEY_INVALID", "API key not valid", "401", "403",
                              "PERMISSION_DENIED", "UNAUTHENTICATED")):
        hint = "API 키가 거부되었습니다. 키를 다시 복사했는지, Google AI Studio에서 키가 활성 상태인지 확인하세요."
    elif "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        hint = "API 사용량 한도를 초과했습니다. 잠시 후 다시 시도하세요."
    elif "404" in msg or "NOT_FOUND" in msg:
        hint = "사용 가능한 Gemini 모델을 찾지 못했습니다. google-genai 버전을 업데이트해 보세요."
    elif isinstance(e, RuntimeError) and "설치" in msg:
        hint = msg
    elif isinstance(e, ValueError):
        hint = "Gemini 응답을 해석하지 못했습니다. 다시 시도해 주세요."
    else:
        hint = "Gemini 호출 중 오류가 발생했습니다."
    return f"{hint}\n\n상세: {type(e).__name__}: {msg[:300]}"


def build_prompt(title, keywords, essay):
    return "\n".join([
        "당신은 장학금 자기소개서 첨삭 전문가입니다.",
        "장학금 공고: " + title,
        "참고 키워드 후보: " + ", ".join(keywords),
        "[자기소개서 시작]",
        essay,
        "[자기소개서 끝]",
        "아래 JSON 형식으로만 한국어로 답하세요. 다른 설명은 쓰지 마세요.",
        '{"keywords": ["공고 맞춤 추천 키워드 3개"], '
        '"strengths": ["강점 피드백 2~3개"], '
        '"improvements": ["수치화/구체화 보완 가이드 3개"]}',
    ])


def call_model(key, model, prompt):
    """최신 google-genai 우선, 없으면 구버전 google-generativeai 사용."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        genai = None
    if genai is not None:
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model=model, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.4))
        return resp.text
    try:
        import google.generativeai as legacy
    except ImportError:
        raise RuntimeError("Gemini SDK 미설치: pip install google-genai")
    legacy.configure(api_key=key)
    resp = legacy.GenerativeModel(model).generate_content(
        prompt, generation_config={"response_mime_type": "application/json", "temperature": 0.4})
    return resp.text


def parse_report(text):
    if not text:
        raise ValueError("빈 응답")
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("JSON 형식 아님")
    data = json.loads(t[a:b + 1])
    for k in ("keywords", "strengths", "improvements"):
        if not isinstance(data.get(k), list) or not data[k]:
            raise ValueError(f"'{k}' 항목 누락")
        data[k] = [str(x) for x in data[k]]
    data["keywords"] = data["keywords"][:3]
    return data


def run_gemini(title, keywords, essay, trace):
    """모델 폴백 + 재시도. 네트워크 불가 시에만 NetworkUnavailable, 그 외 오류는 그대로 raise."""
    key = get_api_key()
    prompt = build_prompt(title, keywords, essay)
    last_err = None
    for model in MODELS:
        for attempt in (1, 2):
            try:
                trace.append(f"[호출] 모델={model} 시도={attempt}")
                data = parse_report(call_model(key, model, prompt))
                data["source"] = f"Gemini AI 분석 ({model})"
                trace.append("[성공] 실제 Gemini 응답을 사용합니다.")
                return data
            except Exception as e:
                last_err = e
                msg = str(e).replace(key, "***")
                trace.append(f"[실패] {type(e).__name__}: {msg[:200]}")
                LOGGER.warning("Gemini 호출 실패 model=%s attempt=%s key=%s: %s: %s",
                               model, attempt, mask_key(key), type(e).__name__, msg[:300])
                if isinstance(e, RuntimeError) and "설치" in msg:
                    raise
                if is_network_error(e):
                    if attempt == 1:
                        time.sleep(1)
                        continue
                    raise NetworkUnavailable(msg) from e
                if "404" in msg or "NOT_FOUND" in msg:
                    break  # 다음 모델로
                if is_transient(msg):
                    time.sleep(1.5 * attempt)
                    continue
                if isinstance(e, ValueError):
                    if attempt == 1:
                        continue
                    break
                raise  # 키 거부(401/403) 등은 즉시 사용자에게 안내
    raise last_err or RuntimeError("모델 호출 실패")


def generate_report(title, kws, essay):
    trace, report = [], None
    ss.ai_error = None
    key = get_api_key()
    with st.spinner("분석 중..."):
        if not key:
            trace.append("API 키 없음: st.secrets / 환경변수 GEMINI_API_KEY 모두 비어 있음 → 데모 리포트")
            report = demo_report(title, kws, essay)
            report["source"] = "안심 데모 분석 리포트 (API 키 미설정)"
        else:
            trace.append(f"API 키 인식: {mask_key(key)} (길이 {len(key)})")
            if not re.fullmatch(r"[A-Za-z0-9_\-.~]{10,}", key):
                trace.append("주의: 키에 예상 밖의 문자가 있습니다. 그래도 호출을 시도합니다.")
            try:
                report = run_gemini(title, kws, essay, trace)
            except NetworkUnavailable:
                trace.append("네트워크 통신 불가 → 데모 리포트")
                report = demo_report(title, kws, essay)
                report["source"] = "안심 데모 분석 리포트 (네트워크 통신 불가)"
            except Exception as e:
                LOGGER.exception("Gemini 분석 실패")
                ss.ai_error = explain_error(e, key)
    ss.ai_log = trace
    if report:
        report["title"] = title
    ss.ai_report = report


def render_ai():
    st.markdown("### ✍️ AI 자소서 첨삭")
    mode = st.radio("장학금 선택 방식", ["📋 신청 관리 목록에서 선택", "🔎 공고명/URL 직접 입력"],
                    horizontal=True)
    title, kws = "", ["성장", "책임감", "진정성"]
    if mode.startswith("📋"):
        if ss.apps:
            ids = list(ss.apps)
            sid = st.selectbox("신청 중인 장학금", ids, format_func=lambda i: SCH_BY_ID[i]["name"])
            title, kws = SCH_BY_ID[sid]["name"], SCH_BY_ID[sid]["keywords"]
        else:
            st.info("신청 관리 목록이 비어 있어요. 탐색 탭에서 추가하거나 '직접 입력'을 이용하세요.")
    else:
        title = st.text_input("장학금 공고명 또는 URL", placeholder="예) ○○재단 미래인재 장학금 / https://...")
        for s in SCHOLARSHIPS:  # 공고명이 일치하면 키워드 활용
            if s["name"] in title or s["url"] in title:
                kws = s["keywords"]

    essay = st.text_area("자기소개서 / 지원동기", height=260, key="essay",
                         placeholder="여기에 자기소개서를 붙여넣고 Ctrl+Enter(또는 영역 밖 클릭)로 반영하세요.")
    n = len(essay)
    color = "#15803D" if n >= 500 else "#B45309"
    st.markdown(f"<span style='color:{color};font-weight:600'>현재 {n:,}자 / 권장 500자 이상</span>",
                unsafe_allow_html=True)

    if st.button("🤖 AI 첨삭 받기", type="primary", disabled=not (essay.strip() and title.strip())):
        generate_report(title, kws, essay)
    if not (essay.strip() and title.strip()):
        st.caption("장학금과 자기소개서 내용을 입력하면 버튼이 활성화됩니다.")

    if ss.ai_error:
        st.error(ss.ai_error)
    if ss.ai_log:
        with st.expander("🛠️ 디버그 로그"):
            st.code("\n".join(ss.ai_log))

    r = ss.ai_report
    if r:
        st.markdown(f"#### 📑 첨삭 리포트 — {r.get('title', '')}")
        st.caption(f"분석 방식: {r['source']}")
        st.markdown("**🔑 공고 맞춤 추천 키워드 3선**")
        st.markdown("".join(f"<span class='chip b-sky'>#{k}</span>" for k in r["keywords"]),
                    unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("**💪 강점 피드백**")
            for x in r["strengths"]:
                st.markdown(f"- {x}")
        with st.container(border=True):
            st.markdown("**🛠️ 수치화/구체화 보완 가이드**")
            for x in r["improvements"]:
                st.markdown(f"- {x}")


# ─────────────────────────────────────────────────────────────
# TAB 4. 장학금 캘린더
# ─────────────────────────────────────────────────────────────
def render_calendar():
    st.markdown("### 📅 장학금 캘린더")
    y, m = ss.cal_year, ss.cal_month
    n1, n2, n3, n4 = st.columns([1, 3, 1, 1])
    n1.button("< 이전 달", on_click=shift_month, args=(-1,), key="cal_prev", use_container_width=True)
    n2.markdown(f"<h3 style='text-align:center;margin:0'>{y}년 {m}월</h3>", unsafe_allow_html=True)
    n3.button("다음 달 >", on_click=shift_month, args=(1,), key="cal_next", use_container_width=True)
    n4.button("오늘", on_click=goto_today, key="cal_today", use_container_width=True)

    if not ss.apps:
        st.info("신청 관리 목록이 비어 있습니다. 공고를 추가하면 마감일이 달력에 표시됩니다.")
    events = {}
    for sid, app in ss.apps.items():
        d = SCH_BY_ID[sid]["deadline"]
        if d.year == y and d.month == m:
            events.setdefault(d.day, []).append((SCH_BY_ID[sid], app))

    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(y, m)
    html = ["<table class='cal'><thead><tr>"]
    html += [f"<th>{w}</th>" for w in "일월화수목금토"]
    html.append("</tr></thead><tbody>")
    for wk in weeks:
        html.append("<tr>")
        for idx, day in enumerate(wk):
            if day == 0:
                html.append("<td class='empty'></td>")
                continue
            td_cls = "today" if date(y, m, day) == TODAY else ""
            num_cls = "sun" if idx == 0 else ""
            chips = "".join(
                f"<span class='ev {dday_info(s['deadline'])[1]}' title='{s['name']} · {a['status']}'>{s['name']}</span>"
                for s, a in events.get(day, []))
            html.append(f"<td class='{td_cls}'><div class='dn {num_cls}'>{day}</div>{chips}</td>")
        html.append("</tr>")
    html.append("</tbody></table>")
    st.markdown("".join(html), unsafe_allow_html=True)
    total = sum(len(v) for v in events.values())
    st.caption(f"{y}년 {m}월 마감 {total}건 · 칩 색상: 🟥 D-0 / 🟨 D-7 이하 / 🟩 D-8 이상 / ⬜ 마감")


# ─────────────────────────────────────────────────────────────
# TAB 5. 커뮤니티
# ─────────────────────────────────────────────────────────────
def render_community():
    st.markdown("### 💬 커뮤니티 (후기/팁)")
    with st.expander("✍️ 새 글 작성하기"):
        with st.form("post_form", clear_on_submit=True):
            t = st.text_input("제목")
            c = st.selectbox("분류", ["후기", "팁", "질문"])
            body = st.text_area("내용", height=120)
            if st.form_submit_button("등록", type="primary"):
                if t.strip() and body.strip():
                    new_id = max([x["id"] for x in ss.posts], default=0) + 1
                    ss.posts.insert(0, dict(id=new_id, title=t.strip(), author=ss.profile["name"],
                                            cat=c, content=body.strip(), likes=0, date=str(TODAY)))
                    st.rerun()
                else:
                    st.warning("제목과 내용을 모두 입력해 주세요.")
    st.text_input("🔎 게시글 검색", key="post_q", placeholder="제목 또는 본문 키워드")
    st.radio("분류", ["전체", "후기", "팁", "질문"], horizontal=True, key="post_cat",
             label_visibility="collapsed")
    q = ss.post_q.strip().lower()
    posts = [x for x in ss.posts
             if (ss.post_cat == "전체" or x["cat"] == ss.post_cat)
             and (not q or q in x["title"].lower() or q in x["content"].lower())]
    if not posts:
        st.info("조건에 맞는 게시글이 없습니다.")
    for post in posts:
        with st.container(border=True):
            st.markdown(f"**[{post['cat']}] {post['title']}**")
            st.caption(f"{post['author']} · {post['date']}")
            st.write(post["content"])
            st.button(f"👍 추천하기  {post['likes']}", key=f"like_{post['id']}", on_click=like_post,
                      args=(post["id"],))


# ─────────────────────────────────────────────────────────────
# 렌더링
# ─────────────────────────────────────────────────────────────
{
    NAV[0]: render_dashboard,
    NAV[1]: render_explore,
    NAV[2]: render_ai,
    NAV[3]: render_calendar,
    NAV[4]: render_community,
}[page]()
