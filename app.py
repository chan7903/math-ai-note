import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image
from datetime import datetime
import pandas as pd
import os
import cloudinary
import cloudinary.uploader

# --- [1] 기본 설정 (선생님 키로 수정 필수!) ---
GOOGLE_API_KEY = "AIzaSyAEhGG9ekbj_q8up2w_pPtIKu6cFjhWzNo"
SHEET_NAME = "수학오답노트_DB"
ADMIN_PASSWORD = "1234"

# --- [2] Cloudinary 설정 (Secrets에서 가져오기) ---
# 나중에 Streamlit Secrets에 이 3개 값을 넣어줄 겁니다.
if "cloudinary" in st.secrets:
    cloudinary.config(
        cloud_name = st.secrets["cloudinary"]["cloud_name"],
        api_key = st.secrets["cloudinary"]["api_key"],
        api_secret = st.secrets["cloudinary"]["api_secret"]
    )

# --- [3] 연결 설정 (Gemini & 구글시트) ---
try:
    # Gemini
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    else:
        genai.configure(api_key=GOOGLE_API_KEY)
    
    # 구글 시트
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if os.path.exists("secrets.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
    else:
        key_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1

except Exception as e:
    st.error(f"연결 오류: {e}")
    st.stop()

# --- [4] 함수 모음 ---
def upload_image(image_file):
    """이미지를 Cloudinary에 업로드하고 URL을 받아오는 함수"""
    try:
        # 이미지를 바로 업로드 (Streamlit 파일을 그대로 전송)
        response = cloudinary.uploader.upload(image_file)
        return response['secure_url']
    except Exception as e:
        st.error(f"이미지 업로드 실패: {e}")
        return "이미지 업로드 실패"

def get_ai_response(image):
    # 2.5 flash가 되신다면 2.5로, 아니면 1.5로 설정
    model = genai.GenerativeModel('gemini-2.5-flash') 
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

def save_to_sheet(name, pw, unit, img_url, result_text):
    date = datetime.now().strftime("%Y-%m-%d")
    # 드디어 img_url(진짜 주소)가 들어갑니다!
    row = [date, name, pw, unit, img_url, result_text, 0] 
    sheet.append_row(row)

# --- [5] 메인 화면 ---
st.set_page_config(page_title="AI 수학 오답노트", layout="wide")
st.title("💯 AI 수학 오답노트")

st.sidebar.header("🔑 로그인")
user_name = st.sidebar.text_input("이름", placeholder="예: 김철수")
user_pw = st.sidebar.text_input("비밀번호", type="password")

if user_name and user_pw:
    menu = st.sidebar.radio("메뉴 선택", ["📸 문제 찍기", "📒 내 오답노트", "👨‍🏫 선생님 전용"])
    
    if menu == "📸 문제 찍기":
        st.subheader(f"반가워요, {user_name} 학생!")
        unit = st.selectbox("단원 선택", ["수학(상)", "수학(하)", "수1", "수2", "미적분", "확통"])
        
        # 파일 업로더와 카메라 동시에 지원 (선택 가능)
        img_file = st.camera_input("문제를 찍어주세요")
        
        if img_file:
            st.image(img_file, caption="찍은 문제 확인")
            if st.button("🚀 AI 분석 및 저장"):
                
                # 1. AI 분석
                image = Image.open(img_file)
                result = get_ai_response(image)
                st.info("분석 완료! 클라우드에 저장 중...")
                
                # 2. 이미지 업로드 (여기가 핵심!)
                # camera_input은 한 번 읽으면 사라지므로 다시 처음으로 되감기
                img_file.seek(0) 
                img_url = upload_image(img_file)
                
                # 3. 시트 저장
                save_to_sheet(user_name, user_pw, unit, img_url, result)
                
                st.markdown(result)
                st.success("✅ 오답노트와 사진이 완벽하게 저장되었습니다!")

    elif menu == "📒 내 오답노트":
        st.subheader(f"📂 {user_name}님의 오답 기록")
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            df['비밀번호'] = df['비밀번호'].astype(str)
            my_notes = df[(df["학생이름"] == user_name) & (df["비밀번호"] == str(user_pw))]
            
            if my_notes.empty:
                st.warning("기록이 없습니다.")
            else:
                for idx, row in my_notes.iterrows():
                    with st.expander(f"{row['날짜']} - {row['단원']}"):
                        # 이미지가 있으면 보여주기!
                        if str(row['이미지URL']).startswith("http"):
                            st.image(row['이미지URL'], caption="내가 틀린 문제")
                        else:
                            st.write("(이미지 없음)")
                            
                        st.write(row['오답원인'])
                        if st.button(f"복습 완료 (현재 {row['조회수']}회)", key=f"btn_{idx}"):
                             real_row_idx = idx + 2
                             sheet.update_cell(real_row_idx, 7, row['조회수'] + 1)
                             st.rerun()
        else:
            st.warning("데이터가 없습니다.")
            
    # 선생님 메뉴는 기존과 동일... (생략하거나 그대로 두셔도 됩니다)
    elif menu == "👨‍🏫 선생님 전용":
        if user_pw == ADMIN_PASSWORD:
            data = sheet.get_all_records()
            st.dataframe(data)
        else:
            st.error("비밀번호 오류")
else:
    st.info("로그인해주세요.")
