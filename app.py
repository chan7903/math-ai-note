import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image
from datetime import datetime
import pandas as pd
import os 

# --- [1] 기본 설정 (여기에 선생님 키를 넣어주세요!) ---
GOOGLE_API_KEY = "AIzaSyAEhGG9ekbj_q8up2w_pPtIKu6cFjhWzNo"
SHEET_NAME = "수학오답노트_DB"
ADMIN_PASSWORD = "1234" 

# --- [2] Gemini 및 구글 시트 연결 (안전장치 추가됨) ---
try:
    # 1. Gemini API 키 설정
    # (try-except 구문으로 감싸서, 로컬에서 secrets 파일이 없어도 에러가 안 나게 막았습니다)
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        else:
            genai.configure(api_key=GOOGLE_API_KEY)
    except FileNotFoundError:
        # 로컬이라 secrets 파일이 없으면 그냥 바로 변수값 사용
        genai.configure(api_key=GOOGLE_API_KEY)
    
    # 2. 구글 시트 연결
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 컴퓨터에 secrets.json 파일이 있는지 먼저 확인
    if os.path.exists("secrets.json"):
        # 내 컴퓨터용 (파일 사용)
        creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
    else:
        # 웹사이트 배포용 (Secrets 사용)
        try:
            if "gcp_service_account" in st.secrets:
                key_dict = dict(st.secrets["gcp_service_account"])
                creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
            else:
                st.error("🚨 서버 설정 오류: Secrets에 gcp_service_account가 없습니다.")
                st.stop()
        except FileNotFoundError:
            # 로컬인데 json 파일도 없는 경우
            st.error("🚨 연결 실패: 폴더에 secrets.json 파일이 없습니다. 확인해주세요.")
            st.stop()
    
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1

except Exception as e:
    st.error(f"⚠️ 연결 오류가 발생했습니다!\n\n오류 내용: {e}")
    st.stop()

# --- [3] 함수 모음 ---
def get_ai_response(image):
    model = genai.GenerativeModel('gemini-1.5-flash') 
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
    date = datetime.now().strftime("%Y-%m-%d")
    row = [date, name, pw, unit, "이미지 준비중", result_text, 0] 
    sheet.append_row(row)

# --- [4] 메인 화면 구성 ---
st.set_page_config(page_title="AI 수학 오답노트", layout="wide")

st.title("💯 AI 수학 오답노트")

st.sidebar.header("🔑 로그인")
user_name = st.sidebar.text_input("이름", placeholder="예: 김철수")
user_pw = st.sidebar.text_input("비밀번호 (전화번호 뒷자리)", type="password")

if user_name and user_pw:
    menu = st.sidebar.radio("메뉴 선택", ["📸 문제 찍기", "📒 내 오답노트", "👨‍🏫 선생님 전용"])
    
    if menu == "📸 문제 찍기":
        st.subheader(f"반가워요, {user_name} 학생! 틀린 문제를 찍어볼까요?")
        unit = st.selectbox("단원 선택", ["수학(상)", "수학(하)", "수1", "수2", "미적분", "확통"])
        
        img_file = st.camera_input("문제를 잘 보이게 찍어주세요")
        
        if img_file:
            st.image(img_file, caption="찍은 문제 확인")
            if st.button("🚀 AI 분석 시작"):
                image = Image.open(img_file)
                result = get_ai_response(image)
                st.info("분석이 완료되었습니다!")
                st.markdown(result)
                save_to_sheet(user_name, user_pw, unit, result)
                st.success("✅ 오답노트에 자동 저장되었습니다!")

    elif menu == "📒 내 오답노트":
        st.subheader(f"📂 {user_name}님의 오답 기록")
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            df['비밀번호'] = df['비밀번호'].astype(str)
            my_notes = df[(df["학생이름"] == user_name) & (df["비밀번호"] == str(user_pw))]
            
            if my_notes.empty:
                st.warning("아직 등록된 오답노트가 없어요.")
            else:
                for idx, row in my_notes.iterrows():
                    with st.expander(f"{row['날짜']} - {row['단원']} (클릭해서 보기)"):
                        st.write(row['오답원인']) 
                        if st.button(f"다시 봤어요! (현재 {row['조회수']}회)", key=f"btn_{idx}"):
                            real_row_idx = idx + 2 
                            current_count = row['조회수']
                            sheet.update_cell(real_row_idx, 7, current_count + 1)
                            st.rerun() 
        else:
            st.warning("데이터베이스가 비어있습니다.")

    elif menu == "👨‍🏫 선생님 전용":
        if user_pw == ADMIN_PASSWORD:
            st.success("선생님 모드로 접속했습니다.")
            st.write("### 📊 전체 학생 오답 현황")
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            st.dataframe(df)
            csv = df.to_csv().encode('utf-8')
            st.download_button(
                label="엑셀 데이터 다운로드",
                data=csv,
                file_name='오답노트_전체.csv',
                mime='text/csv',
            )
        else:
            st.error("관리자 비밀번호가 틀렸습니다.")
else:
    st.info("👈 왼쪽에서 이름과 비밀번호를 입력하고 로그인하세요.")