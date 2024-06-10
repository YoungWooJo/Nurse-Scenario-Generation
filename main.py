import streamlit as st
from streamlit_option_menu import option_menu
import import_module  # import_module.py를 임포트
from utils import load_css, img_to_base64_str, get_db_connection  # 유틸리티 모듈에서 함수 가져오기
import random
import os
import json
import simulation_list
import disease_info

# 페이지 설정을 wide 모드로
st.set_page_config(layout="wide")

# CSS 스타일 적용
load_css()

# 세션 상태 초기화
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = "메인 페이지"
if 'selected_simulation' not in st.session_state:
    st.session_state['selected_simulation'] = None
if 'selected_disease' not in st.session_state:
    st.session_state['selected_disease'] = None

# 사이드바에 이미지를 중앙 정렬하고, 이미지와 메뉴 사이에 여백을 추가하기 위한 마크다운
st.sidebar.markdown(
    "<div style='text-align: center; margin-bottom: 30px;'><img src='data:image/png;base64,{}' class='sidebar-logo' width='250'></div>".format(
        img_to_base64_str("./image/sidebar_logo.png")
    ), 
    unsafe_allow_html=True
)

# 사이드바 설정
with st.sidebar:
    choice = option_menu("Menu", ["메인 페이지", "시나리오 생성", "시뮬레이션 리스트", "질병 정보"],
                         icons=['house', 'pencil-fill', 'card-list', 'hospital'],
                         menu_icon="app-indicator", default_index=0,
                         styles={
                             "container": {"padding": "4!important", "background-color": "#fafafa"},
                             "icon": {"color": "black", "font-size": "25px"},
                             "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#fafafa"},
                             "nav-link-selected": {"background-color": "#036db3"},
                         }
    )
    if choice != st.session_state['current_page']:
        st.session_state['current_page'] = choice
        st.experimental_rerun()

# 지정된 폴더에서 랜덤 이미지를 선택하여 로드하는 함수
def get_random_image_from_folder(folder_path):
    image_files = [f for f in os.listdir(folder_path) if f.endswith(('png', 'jpg', 'jpeg', 'webp'))]
    if not image_files:
        return None
    random_image = random.choice(image_files)
    return os.path.join(folder_path, random_image)

# 페이지 내용 로드
if st.session_state['current_page'] == "메인 페이지":
    st.title("간호 시뮬레이션 플랫폼")

    # 랜덤 이미지 삽입
    random_image_path = get_random_image_from_folder("./image/mainpage_image")
    if random_image_path:
        image = img_to_base64_str(random_image_path)
        st.markdown(
            "<div class='content-wrapper'><img src='data:image/png;base64,{}' class='mainpage-image'></div>".format(image), 
            unsafe_allow_html=True
        )
    else:
        st.write("이미지를 불러올 수 없습니다.")

    # 두 개의 섹션 나누기
    col1, col2 = st.columns(2)

    # 왼쪽 섹션: 시뮬레이션 리스트 목차
    with col1:
        st.subheader("시뮬레이션 리스트")
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id FROM scenarios ORDER BY created_at DESC LIMIT 5")
        simulations = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if simulations:
            for scenario in simulations:
                parts = scenario['id'].rsplit('_', 2)
                if len(parts) == 3:
                    disease_name, purpose, date_str = parts
                    disease_name = disease_name.replace("_", " ")
                    title = f"{disease_name} {purpose} 시나리오"

                    if st.button(title, key=scenario['id']):
                        st.session_state.sim_list_selected_scenario = scenario
                        st.session_state.current_page = 'scenario_detail'  # 페이지 전환
                        st.experimental_rerun()
                else:
                    st.error(f"Invalid scenario ID format for document ID: {scenario['id']}")
        else:
            st.write("저장된 시뮬레이션 시나리오가 없습니다.")

    # 오른쪽 섹션: 랜덤 질병 정보 5개
    with col2:
        st.subheader("질병 정보")
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT title, paragraphs, info FROM Disease_info")
        all_diseases = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if all_diseases:
            for disease in random.sample(all_diseases, 5):
                if st.button(disease['title'], key=f"disease_{disease['title']}"):
                    st.session_state['selected_disease'] = disease
                    st.session_state['current_page'] = "질병 상세"
                    st.experimental_rerun()

elif st.session_state['current_page'] == "시뮬레이션 상세":
    st.subheader("시뮬레이션 상세 정보")
    if st.session_state['selected_simulation']:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM scenarios WHERE id = %s", (st.session_state['selected_simulation'],))
        selected_simulation = cursor.fetchone()
        cursor.close()
        connection.close()

        if selected_simulation:
            st.write("**환자 정보:**")
            st.json(json.loads(selected_simulation["patient_info"]))
            st.write("**시나리오:**")
            st.write(selected_simulation["scenario"])
        else:
            st.write("선택한 시뮬레이션 정보를 불러올 수 없습니다.")
    if st.button("뒤로가기"):
        st.session_state['current_page'] = "메인 페이지"
        st.session_state['selected_simulation'] = None
        st.experimental_rerun()

elif st.session_state['current_page'] == "질병 상세":
    st.subheader("질병 상세 정보")
    if st.session_state['selected_disease']:
        disease = st.session_state['selected_disease']
        st.write("**Paragraphs:**")
        paragraphs = json.loads(disease['paragraphs'])
        for para in paragraphs:
            st.write(para)
        st.write("**Info:**")
        info = json.loads(disease['info'])
        for key, value in info.items():
            st.write(f"**{key}: {value}**")
    if st.button("뒤로가기"):
        st.session_state['current_page'] = "메인 페이지"
        st.session_state['selected_disease'] = None
        st.experimental_rerun()

elif st.session_state['current_page'] == "시나리오 생성":
    import_module.load_module("scenario_generator")
elif st.session_state['current_page'] == "시뮬레이션 리스트":
    simulation_list.load_page()  # 시뮬레이션 리스트 페이지 로드
elif st.session_state['current_page'] == "질병 정보":
    disease_info.load_page()  # 질병 정보 페이지 로드
