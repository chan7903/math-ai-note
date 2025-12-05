import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image
from datetime import datetime
import pandas as pd
import os # 파일이 있는지 확인하는 기능

# --- [1] 기본 설정 (여기에 선생님 키를 넣어주세요!) ---
# 컴퓨터에서 실행할 때를 위해 여기에 키를 적어두세요.
# (배포된 웹사이트에서는 자동으로 Secrets에 설정한 키를 우선해서 씁니다)
GOOGLE_API_KEY = "AIzaSyAEhGG9ekbj_q8up2w_pPtIKu6cFjhWzNo"

# 구글 시트 이름 (아까 만든 파일명과 똑같아야 함)
SHEET_NAME = "수학오답노트_DB"

# 선생님용 관리자 비밀번호
ADMIN_PASSWORD = "1234" 

# --- [2] Gemini 및 구글 시트 연결 (만능 버전) ---
try:
    # 1. Gemini API 키 설정
    # (웹사이트에 배포했을 때는 st.secrets를 쓰고, 없으면 위에서 적은 변수를 씁니다)
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    else:
        genai.configure(api_key=GOOGLE_API_KEY)
    
    # 2. 구글 시트 연결
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # [핵심] 컴퓨터에 'secrets.json' 파일이 있는지 확인
    if os.path.exists("secrets.json"):
        # 파일이 있으면 파일 사용 (내 컴퓨터용)
        creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
    else:
        # 파일이 없으면 웹사이트 Secrets 사용 (Streamlit Cloud용)
        # (주의: 배포 시 Secrets에 gcp_service_account 내용을 잘 넣어줘야 함)
        if "gcp_service_account" in st.secrets:
            key_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        else:
            # 로컬인데 파일도 없고, Secrets 설정도 안 된 경우
            st.error("🚨 연결 실패: secrets.json 파일이 없거나 Secrets 설정이 안 되어 있습니다.")
            st.stop()
    
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1

except Exception as e:
    st.error(f"⚠️ 연결 오류가 발생했습니다!\n\n오류 내용: {e}")
    st.stop()

# --- [3] 함수 모음 ---
def get_ai_response(image):
    """Gemini에게 이미지를 주고 분석을 요청하는 함수"""
    # 모델 이름이 정확한지 확인하세요 (gemini-1.5-flash 또는 gemini-pro-vision 등)
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
    """구글 시트에 데이터를 저장하는 함수"""
    date = datetime.now().strftime("%Y-%m-%d")
    # 시트 순서: 날짜, 이름, 비번, 단원, 이미지URL(보류), 오답원인(전체), 조회수
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
                # AI 분석 요청
                image = Image.open(img_file)
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
            # 비밀번호 형식이 숫자/문자 섞여있을 수 있어 문자열로 통일해서 비교
            df['비밀번호'] = df['비밀번호'].astype(str)
            my_notes = df[(df["학생이름"] == user_name) & (df["비밀번호"] == str(user_pw))]
            
            if my_notes.empty:
                st.warning("아직 등록된 오답노트가 없어요.")
            else:
                for idx, row in my_notes.iterrows():
                    with st.expander(f"{row['날짜']} - {row['단원']} (클릭해서 보기)"):
                        st.write(row['오답원인']) 
                        
                        # 버튼 키(key)를 유니크하게 만들기 위해 인덱스 사용
                        if st.button(f"다시 봤어요! (현재 {row['조회수']}회)", key=f"btn_{idx}"):
                            # 조회수 +1 기능
                            # 실제 행 번호 찾기 (데이터가 2행부터 시작하므로 +2)
                            real_row_idx = idx + 2 
                            current_count = row['조회수']
                            # G열(7번째)이 조회수라고 가정
                            sheet.update_cell(real_row_idx, 7, current_count + 1)
                            st.rerun() 
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
            
            # CSV 다운로드 기능
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