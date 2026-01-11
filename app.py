import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import altair as alt
from streamlit_option_menu import option_menu
from streamlit_calendar import calendar

# --- 1. 기본 설정 및 모바일 스타일링 ---
st.set_page_config(page_title="스마트 학습 관리", layout="mobile", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 5rem; }
        .fixed-bottom-menu {
            position: fixed; bottom: 0; left: 0; width: 100%; z-index: 99999;
            background-color: white; border-top: 1px solid #e0e0e0;
            padding: 5px 0; text-align: center;
        }
        .stApp { margin-bottom: 80px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 유틸리티 함수 ---
def format_time(minutes):
    """분을 'X시간 Y분'으로 변환"""
    try:
        minutes = int(minutes)
        h = minutes // 60
        m = minutes % 60
        return f"{h}시간 {m}분" if h > 0 else f"{m}분"
    except:
        return "0분"

@st.cache_resource
def get_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    import os
    if os.path.exists("service_account.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
    return gspread.authorize(creds)

# --- 3. 데이터 로드 ---
try:
    client = get_connection()
    sh = client.open("Tutoring_DB")
    ws_students = sh.worksheet("Students")
    ws_logs = sh.worksheet("StudyLogs")
    ws_homework = sh.worksheet("Homework")
    ws_summaries = sh.worksheet("Summaries")
except Exception as e:
    st.error(f"DB 연결 오류: {e}")
    st.stop()

# --- 4. 로그인 화면 ---
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'user_name': "", 'role': ""})

if not st.session_state['logged_in']:
    st.title("🔐 Login")
    input_pw = st.text_input("비밀번호 (4자리)", type="password")
    if st.button("로그인", use_container_width=True):
        users = ws_students.get_all_records()
        for u in users:
            if str(u['비밀번호']) == str(input_pw):
                st.session_state.update({'logged_in': True, 'user_name': u['이름'], 'role': u['역할']})
                st.rerun()
        st.error("비밀번호를 확인하세요.")
    st.stop()

# ================= 메인 앱 =================
user_name = st.session_state['user_name']
user_role = st.session_state['role']

col1, col2 = st.columns([3, 1])
col1.subheader(f"👋 {user_name}님")
if col2.button("로그아웃"):
    st.session_state['logged_in'] = False
    st.rerun()

# --- 하단 메뉴 구성 ---
if user_role == "Teacher":
    menu = ["홈", "수업기록", "학생관리"]
    icons = ["house", "pencil", "people"]
else: # Student
    menu = ["홈", "공부기록", "과제체크", "알림장"] # 알림장 추가
    icons = ["house", "clock", "check2-square", "bell"]

with st.container():
    st.markdown('<div class="fixed-bottom-menu">', unsafe_allow_html=True)
    selected = option_menu(None, menu, icons=icons, default_index=0, orientation="horizontal")
    st.markdown('</div>', unsafe_allow_html=True)

# --- 페이지별 기능 ---

# 1. 홈 (캘린더 & 통계)
if selected == "홈":
    st.title("📅 Calendar")
    logs = pd.DataFrame(ws_logs.get_all_records())
    hws = pd.DataFrame(ws_homework.get_all_records())
    
    events = []
    # 공부 기록 (파랑)
    if not logs.empty:
        my_logs = logs if user_role == 'Teacher' else logs[logs['이름'] == user_name]
        for _, r in my_logs.iterrows():
            events.append({"title": f"📖 {r['과목']} ({format_time(r['시간(분)'])}", "start": str(r['날짜']), "backgroundColor": "#3788d8"})
    
    # 과제 기록 (초록/빨강)
    if not hws.empty:
        my_hws = hws if user_role == 'Teacher' else hws[hws['이름'] == user_name]
        for _, r in my_hws.iterrows():
            color = "#28a745" if str(r['완료여부'])=='TRUE' else "#dc3545"
            events.append({"title": f"📝 {r['내용']}", "start": str(r['날짜']), "backgroundColor": color})
            
    calendar(events=events, options={"initialView": "dayGridMonth", "headerToolbar": {"left": "prev,next", "center": "title", "right": "today"}})

    # 월간 요약
    st.divider()
    st.subheader("📊 이번 달 요약")
    this_month = datetime.now().strftime("%Y-%m")
    
    total_time = 0
    hw_rate = 0
    
    if not logs.empty:
        m_logs = my_logs[my_logs['날짜'].astype(str).str.startswith(this_month)]
        total_time = m_logs['시간(분)'].sum()
        
    if not hws.empty:
        m_hws = my_hws[my_hws['날짜'].astype(str).str.startswith(this_month)]
        if len(m_hws) > 0:
            done = len(m_hws[m_hws['완료여부']=='TRUE'])
            hw_rate = (done / len(m_hws)) * 100
            
    c1, c2 = st.columns(2)
    c1.metric("총 학습", format_time(total_time))
    c2.metric("과제 달성", f"{hw_rate:.0f}%")

# 2. 공부기록 (학생)
elif selected == "공부기록":
    st.title("✍️ Study Log")
    with st.form("log_form"):
        date = st.date_input("날짜", datetime.now())
        subj = st.selectbox("과목", ["국어", "수학", "영어", "탐구", "기타"])
        h = st.number_input("시간", 0, 24, 1)
        m = st.number_input("분", 0, 59, 0)
        memo = st.text_input("메모")
        if st.form_submit_button("저장", use_container_width=True):
            mins = h*60 + m
            if mins > 0:
                ws_logs.append_row([str(date), user_name, subj, mins, memo])
                st.success("저장 완료!")

# 3. 과제체크 (학생)
elif selected == "과제체크":
    st.title("✅ To-Do")
    hws = pd.DataFrame(ws_homework.get_all_records())
    if not hws.empty:
        my_hws = hws[hws['이름'] == user_name].sort_values('날짜', ascending=False)
        for i, row in my_hws.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{row['날짜']}** {row['내용']}")
                is_done = row['완료여부'] == 'TRUE'
                if c2.checkbox("완료", is_done, key=f"k_{row['ID']}") != is_done:
                    cell = ws_homework.find(str(row['ID']))
                    ws_homework.update_cell(cell.row, 5, "FALSE" if is_done else "TRUE")
                    st.rerun()

# 4. 알림장 (학생용 - 선생님이 쓴 글 보기)
elif selected == "알림장":
    st.title("📢 선생님 말씀")
    sums = pd.DataFrame(ws_summaries.get_all_records())
    if not sums.empty:
        # 내 이름으로 된 기록만 필터링
        my_sums = sums[sums['학생이름'] == user_name].sort_values('날짜', ascending=False)
        if not my_sums.empty:
            for _, row in my_sums.iterrows():
                with st.expander(f"📅 {row['날짜']} 수업 기록", expanded=True):
                    st.markdown(f"**[수업 내용]**\n\n{row['수업내용']}")
                    st.divider()
                    st.markdown(f"**[숙제 및 공지]**\n\n{row['숙제및공지']}")
        else:
            st.info("아직 등록된 수업 기록이 없어요.")
    else:
        st.info("기록이 없습니다.")

# 5. 수업기록 (선생님)
elif selected == "수업기록":
    st.title("📝 수업 일지 작성")
    students = pd.DataFrame(ws_students.get_all_records())
    s_list = students[students['역할']=='Student']['이름'].tolist()
    
    with st.form("t_form"):
        date = st.date_input("날짜", datetime.now())
        who = st.selectbox("학생", s_list)
        content = st.text_area("수업 내용")
        notice = st.text_area("숙제/공지")
        if st.form_submit_button("일지 저장", use_container_width=True):
            ws_summaries.append_row([str(date), who, content, notice])
            st.success("저장되었습니다!")

# 6. 학생관리 (선생님)
elif selected == "학생관리":
    st.title("👥 학생 DB")
    st.dataframe(ws_students.get_all_records())
    st.caption("수정은 구글 시트에서 해주세요.")
