import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image
from datetime import datetime
import pandas as pd

# --- [1] 기본 설정 (수정 필요한 부분) ---
# 여기에 선생님의 Gemini API 키를 넣어주세요!
GOOGLE_API_KEY = "AIzaSyAEhGG9ekbj_q8up2w_pPtIKu6cFjhWzNo"

# 구글 시트 이름 (아까 만든 파일명과 똑같아야 함)
SHEET_NAME = "수학오답노트_DB"

# 선생님용 관리자 비밀번호 (원하는 걸로 설정)
ADMIN_PASSWORD = "1234" 

# --- [2] Gemini 및 구글 시트 연결 ---
try:
    # 1. Gemini API 키 설정 (Secrets에서 가져오기)
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    else:
        # 혹시 로컬에서 돌릴 때를 대비한 비상용
        genai.configure(api_key=GOOGLE_API_KEY)
    
    # 2. 구글 시트 연결 (파일 대신 Secrets 내용 사용!)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # [핵심 변경] 파일 이름("secrets.json")을 찾는 게 아니라, 입력해둔 비밀번호(Secrets)를 가져옵니다.
    key_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    
except Exception as e:
    st.error(f"오류가 발생했습니다! 내용을 확인해주세요.\n{e}")
    st.stop()

# --- [3] 함수 모음 ---
def get_ai_response(image):
    """Gemini에게 이미지를 주고 분석을 요청하는 함수"""
    model = genai.GenerativeModel('gemini-1.5-flash') # 모델명
    prompt = """
    당신은 수학 선생님입니다. 이 이미지는 학생이 틀린 문제입니다.
    다음 형식으로 답변을 주세요:
    
    [오답원인]
    (학생이 실수한 부분이나 부족한 개념을 1줄로 요약)
    
    [해설]
    (정답과 풀이 과정을 친절하게 설명)
    
    [쌍둥이문제]
    (원본 문제와 숫자는 다르지만 풀이 논리가 같은 문제를 1개 출제)
    
    [정답]
    (쌍둥이 문제의 정답)
    """
    with st.spinner("🤖 AI 선생님이 문제를 분석 중입니다..."):
        response = model.generate_content([prompt, image])
        return response.text

def save_to_sheet(name, pw, unit, result_text):
    """구글 시트에 데이터를 저장하는 함수"""
    date = datetime.now().strftime("%Y-%m-%d")
    # 원인/해설/문제 등을 텍스트 하나에 묶어서 저장 (간소화)
    # 나중에는 이걸 나눠서 저장하면 더 좋습니다.
    row = [date, name, pw, unit, "이미지 준비중", result_text, 0] 
    sheet.append_row(row)

# --- [4] 메인 화면 구성 ---
st.set_page_config(page_title="AI 수학 오답노트", layout="wide")

st.title("💯 AI 수학 오답노트")

# 사이드바: 로그인 및 메뉴
st.sidebar.header("🔑 로그인")
user_name = st.sidebar.text_input("이름", placeholder="예: 김철수")
user_pw = st.sidebar.text_input("비밀번호 (전화번호 뒷자리)", type="password")

# 메뉴 선택
if user_name and user_pw:
    menu = st.sidebar.radio("메뉴 선택", ["📸 문제 찍기", "📒 내 오답노트", "👨‍🏫 선생님 전용"])
    
    # --- 기능 1: 문제 찍기 ---
    if menu == "📸 문제 찍기":
        st.subheader(f"반가워요, {user_name} 학생! 틀린 문제를 찍어볼까요?")
        unit = st.selectbox("단원 선택", ["수학(상)", "수학(하)", "수1", "수2", "미적분", "확통"])
        
        img_file = st.camera_input("문제를 잘 보이게 찍어주세요")
        
        if img_file:
            st.image(img_file, caption="찍은 문제 확인")
            if st.button("🚀 AI 분석 시작"):
                # 이미지 처리
                image = Image.open(img_file)
                
                # AI 분석 요청
                result = get_ai_response(image)
                
                # 결과 출력
                st.info("분석이 완료되었습니다!")
                st.markdown(result)
                
                # 시트에 저장
                save_to_sheet(user_name, user_pw, unit, result)
                st.success("✅ 오답노트에 자동 저장되었습니다!")

    # --- 기능 2: 내 오답노트 ---
    elif menu == "📒 내 오답노트":
        st.subheader(f"📂 {user_name}님의 오답 기록")
        
        # 시트에서 전체 데이터 가져오기
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 내 데이터만 필터링 (이름과 비밀번호가 일치하는 것)
        if not df.empty:
            my_notes = df[(df["학생이름"] == user_name) & (df["비밀번호"] == int(user_pw) if user_pw.isdigit() else user_pw)]
            
            if my_notes.empty:
                st.warning("아직 등록된 오답노트가 없어요.")
            else:
                for idx, row in my_notes.iterrows():
                    with st.expander(f"{row['날짜']} - {row['단원']} (클릭해서 보기)"):
                        st.write(row['오답원인']) # 지금은 전체 텍스트가 여기 들어있음
                        if st.button(f"다시 봤어요! (현재 {row['조회수']}회)", key=f"btn_{idx}"):
                            # 조회수 +1 기능 (간단 구현)
                            # 실제 행 번호 찾기 (시트는 1부터 시작 + 헤더 1줄)
                            real_row_idx = idx + 2 
                            current_count = row['조회수']
                            # 시트 업데이트 (조회수 컬럼이 G열(7번째)라고 가정)
                            sheet.update_cell(real_row_idx, 7, current_count + 1)
                            st.rerun() # 새로고침
        else:
            st.warning("데이터베이스가 비어있습니다.")

    # --- 기능 3: 선생님 전용 ---
    elif menu == "👨‍🏫 선생님 전용":
        if user_pw == ADMIN_PASSWORD:
            st.success("선생님 모드로 접속했습니다.")
            st.write("### 📊 전체 학생 오답 현황")
            
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            st.dataframe(df)
            
            st.download_button("엑셀로 다운로드", df.to_csv().encode('utf-8'), "오답노트_전체.csv")
        else:
            st.error("관리자 비밀번호가 틀렸습니다.")

else:
    st.info("👈 왼쪽에서 이름과 비밀번호를 입력하고 로그인하세요.")