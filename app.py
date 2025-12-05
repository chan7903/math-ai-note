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

# --- [2] 페이지 디자인 설정 (가장 먼저 실행되어야 함) ---
# 로고 파일(logo.png)이 GitHub에 올라가 있어야 합니다.
try:
    img = Image.open("logo.png")
    st.set_page_config(page_title="MA학원 AI 오답 도우미", page_icon=img, layout="wide")
except FileNotFoundError:
    # 로고 파일이 없을 경우 기본 아이콘 사용
    st.set_page_config(page_title="MA학원 AI 오답 도우미", page_icon="📚", layout="wide")

# --- [3] Cloudinary 및 API 연결 설정 ---
if "cloudinary" in st.secrets:
    cloudinary.config(
        cloud_name = st.secrets["cloudinary"]["cloud_name"],
        api_key = st.secrets["cloudinary"]["api_key"],
        api_secret = st.secrets["cloudinary"]["api_secret"]
    )

try:
    # Gemini 연결
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    else:
        genai.configure(api_key=GOOGLE_API_KEY)
    
    # 구글 시트 연결
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
    """이미지를 Cloudinary에 업로드"""
    try:
        response = cloudinary.uploader.upload(image_file)
        return response['secure_url']
    except Exception:
        return "이미지 업로드 실패"

def get_ai_response(image):
    """친절한 과외쌤 페르소나로 분석 요청"""
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # --- 말투와 형식을 지정하는 핵심 프롬프트 ---
    prompt = """
    당신은 친절하고 자상한 수학 개인 과외 선생님입니다. 학생이 틀린 문제를 사진으로 찍어 보냈습니다.
    학생이 주눅 들지 않게 격려해주고, 이해하기 쉽게 설명해주세요.

    **반드시 다음 형식과 순서를 정확히 지켜서 답변해주세요.** 각 항목 사이에는 '---'로 구분선을 넣어주세요.

    [오답원인]
    (학생이 어떤 개념을 놓쳤거나 실수했는지 부드럽게 짚어주세요. 예: "아고, 이 부분에서 계산 실수가 있었네! 괜찮아, 다시 보면 돼.")
    ---
    [친절한 해설]
    (정답으로 가는 과정을 차근차근 설명해주세요.)
    ---
    [쌍둥이 문제]
    (원본 문제와 숫자만 다르고 풀이 방식이 똑같은 문제를 하나 만들어주세요.)
    ---
    [쌍둥이 문제 정답 및 풀이]
    (위 쌍둥이 문제의 정답과 해설을 적어주세요.)
    """
    with st.spinner("🤖 친절한 AI 쌤이 문제를 꼼꼼히 보고 있어요..."):
        response = model.generate_content([prompt, image])
        return response.text

def save_to_sheet(name, pw, unit, img_url, result_text):
    date = datetime.now().strftime("%Y-%m-%d")
    row = [date, name, pw, unit, img_url, result_text, 0] 
    sheet.append_row(row)

# --- [5] 메인 화면 구성 ---
# 메인 타이틀 (로고가 있으면 같이 보여줌)
try:
    col1, col2 = st.columns([1, 5])
    with col1:
        st.image("logo.png", width=80)
    with col2:
        st.title("MA학원 AI 오답 도우미")
except FileNotFoundError:
    st.title("📚 MA학원 AI 오답 도우미")

st.markdown("---") # 구분선

# 사이드바 디자인
st.sidebar.header("🔑 학생 로그인")
st.sidebar.info("학원에서 등록한 이름과 비밀번호를 입력하세요.")
user_name = st.sidebar.text_input("이름", placeholder="예: 김철수")
user_pw = st.sidebar.text_input("비밀번호", type="password")

if user_name and user_pw:
    st.sidebar.success(f"환영합니다, {user_name}님!")
    menu = st.sidebar.radio("메뉴 선택", ["📸 문제 찍기 & 분석", "📒 내 오답노트 보기", "👨‍🏫 선생님 관리 페이지"])
    
    # === 메뉴 1: 문제 찍기 ===
    if menu == "📸 문제 찍기 & 분석":
        st.subheader(f"👋 안녕, {user_name}! 오늘도 화이팅 해보자!")
        st.write("틀린 문제를 찍으면 쌤이 친절하게 알려줄게.")
        
        col1, col2 = st.columns(2)
        with col1:
            unit = st.selectbox("어떤 단원 문제야?", ["수학(상)", "수학(하)", "수1", "수2", "미적분", "확통"])
        with col2:
            img_file = st.camera_input("문제를 잘 보이게 찍어줘!")
        
        if img_file:
            st.write("📸 찍힌 사진 확인:")
            st.image(img_file, width=400)
            
            if st.button("🚀 AI 쌤한테 물어보기 (클릭!)", type="primary"):
                
                # 1. AI 분석
                image = Image.open(img_file)
                result_text = get_ai_response(image)
                
                # 2. 이미지 업로드
                img_file.seek(0) 
                img_url = upload_image(img_file)
                
                # 3. 시트 저장
                save_to_sheet(user_name, user_pw, unit, img_url, result_text)
                
                # 4. 결과 화면 예쁘게 보여주기 (탭핑 및 파싱)
                try:
                    # '---' 기준으로 텍스트를 나눕니다.
                    parts = result_text.split('---')
                    cause = parts[0].replace('[오답원인]', '').strip()
                    explanation = parts[1].replace('[친절한 해설]', '').strip()
                    twin_prob = parts[2].replace('[쌍둥이 문제]', '').strip()
                    twin_ans = parts[3].replace('[쌍둥이 문제 정답 및 풀이]', '').strip()

                    st.success("분석 끝! 아래 탭을 눌러서 확인해봐.")
                    
                    # 탭 디자인 적용
                    tab1, tab2 = st.tabs(["🔍 오답 분석 & 해설", "📝 쌍둥이 문제 도전!"])
                    
                    with tab1:
                        st.subheader("💡 왜 틀렸을까?")
                        st.warning(cause) # 강조 박스
                        st.divider()
                        st.subheader("📘 친절한 해설")
                        st.markdown(explanation)
                        
                    with tab2:
                        st.subheader("🔥 쌍둥이 문제 도전!")
                        st.write("개념을 알았으니 비슷한 문제를 풀어보자.")
                        st.info(twin_prob) # 문제 박스
                        st.write("") # 여백
                        # 정답 숨기기 기능 (Expander)
                        with st.expander("궁금하면 클릭! 정답과 해설 보기 🤫"):
                            st.markdown(twin_ans)
                            
                except Exception:
                    # 혹시라도 AI가 형식을 안 지켰을 경우를 대비한 안전장치
                    st.warning("AI 쌤이 답변 형식을 조금 다르게 보냈네! 그래도 내용은 맞아.")
                    st.markdown(result_text)

    # === 메뉴 2: 내 오답노트 ===
    elif menu == "📒 내 오답노트 보기":
        st.subheader(f"📂 {user_name}의 오답 기록장")
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            df['비밀번호'] = df['비밀번호'].astype(str)
            my_notes = df[(df["학생이름"] == user_name) & (df["비밀번호"] == str(user_pw))]
            
            if my_notes.empty:
                st.info("아직 등록된 오답노트가 없어. 문제를 찍어볼까?")
            else:
                st.write(f"총 {len(my_notes)}개의 오답 노트가 있어.")
                for idx, row in my_notes.iterrows():
                    # 날짜와 단원으로 깔끔하게 표시
                    with st.expander(f"📅 {row['날짜']} | [{row['단원']}] 복습하기 (클릭)"):
                        col_a, col_b = st.columns([1, 2])
                        with col_a:
                            if str(row['이미지URL']).startswith("http"):
                                st.image(row['이미지URL'], caption="내가 틀린 문제")
                            else:
                                st.write("(이미지 없음)")
                        with col_b:
                            st.markdown(f"**[오답 원인 요약]**\n\n{row['오답원인'].split('---')[0].replace('[오답원인]','').strip()}")
                            st.write("---")
                            # 전체 내용은 너무 기니까 버튼 누르면 보이게 하거나, 지금은 요약만 보여줌.
                            # (전체 내용을 깔끔하게 보여주려면 DB 구조 변경이 필요해서 일단은 이렇게 유지합니다.)
                            st.caption("상세 해설과 쌍둥이 문제는 '문제 찍기' 직후 화면에서 가장 잘 보입니다.")

                        if st.button(f"👍 복습 완료! (현재 {row['조회수']}회 봄)", key=f"btn_{idx}"):
                             real_row_idx = idx + 2
                             sheet.update_cell(real_row_idx, 7, row['조회수'] + 1)
                             st.rerun()
        else:
             st.info("데이터베이스가 비어있습니다.")

    # === 메뉴 3: 선생님 전용 ===
    elif menu == "👨‍🏫 선생님 관리 페이지":
        st.sidebar.markdown("---")
        admin_pw = st.sidebar.text_input("관리자 비밀번호", type="password")
        if admin_pw == ADMIN_PASSWORD:
            st.success("관리자 모드 접속 완료")
            st.write("### 📊 전체 학생 오답 현황")
            data = sheet.get_all_records()
            st.dataframe(data)
        elif admin_pw:
             st.sidebar.error("관리자 비밀번호가 틀렸습니다.")

else:
    # 로그인 전 화면
    st.markdown("### 👈 왼쪽 사이드바에서 로그인해주세요.")
    st.image("https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYWRiNDVlMmI1NTI5YmI4NWYyN2FlY2E1YmY3ZThhZTVhZDc1YTZmOSZlcD12MV9pbnRlcm5hbF9naWZzX2dpZklkJmN0PWc/xT9IgG50Fb7Mi0prBC/giphy.gif", width=300)
    st.write("수학, 더 이상 혼자 힘들어하지 마세요! AI 쌤이 도와줄게요.")
