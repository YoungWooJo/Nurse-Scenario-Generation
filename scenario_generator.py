import streamlit as st
from io import BytesIO
from fpdf import FPDF
from GPT_api import NursingScenarioService, SummaryService, ScenarioRevisionService, PatientOverviewService, PatientCreationService
from utils import get_db_connection
from datetime import datetime
import json
import requests
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

# SentenceTransformer 모델 로드
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

def reset_session():
    for key in list(st.session_state.keys()):
        if key.startswith('generator_'):
            del st.session_state[key]
    st.session_state['generator_page'] = 1

def save_scenario_to_mariadb(patient_info, patient_overview, scenario, doc_id=None):
    connection = get_db_connection()
    cursor = connection.cursor()
    
    if doc_id:
        document_id = doc_id
    else:
        disease_name = patient_info.get('질병명', 'unknown').replace(" ", "")
        purpose = patient_info.get('목적', 'unknown').replace(" ", "")
        current_time = datetime.now().strftime("%Y%m%d%H%M%S")
        document_id = f"{disease_name}_{purpose}_{current_time}"
    
    patient_info_json = json.dumps(patient_info, ensure_ascii=False)
    insert_query = """
        INSERT INTO scenarios (id, patient_info, patient_overview, scenario, created_at)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(insert_query, (document_id, patient_info_json, patient_overview, scenario, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    connection.commit()
    cursor.close()
    connection.close()

def create_pdf(content):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font('NanumGothic', '', 'NanumGothic.ttf', uni=True)
    pdf.set_font("NanumGothic", size=12)

    for line in content.split('\n'):
        pdf.multi_cell(0, 10, line, align='L')

    return pdf

def generate_pdf_download_link(pdf):
    pdf_output = BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return st.download_button(
        label="Download PDF",
        data=pdf_output,
        file_name="nursing_scenario.pdf",
        mime="application/pdf"
    )

def format_patient_info(details):
    return ", ".join(f"{key}: {('랜덤' if value == '랜덤' else value)}" for key, value in details.items())

def update_detail():
    key = st.session_state.generator_edit_key
    if key:
        new_value = st.text_input(f"{key}의 새 값을 입력하세요:", value=st.session_state.generator_temp_value, key='generator_new_input')
        if st.button("저장", key='generator_save'):
            st.session_state['generator_generated_patient_details'][key] = new_value
            del st.session_state.generator_edit_key
            st.experimental_rerun()

def next_page():
    if st.session_state.generator_page == 1:
        if 'generator_patient_details' in st.session_state:
            patient_info_fields = [
                '이름', '나이', '성별', '몸무게', '키', '주호소', '입원경로', '사회력',
                '과거병력', '과거수술력', '가족력', '약물', '1차 진단명', '추가사항'
            ]
            for field in patient_info_fields:
                if f"generator_{field}_checkbox" not in st.session_state or not st.session_state[f"generator_{field}_checkbox"]:
                    st.session_state['generator_patient_details'][field] = "해당사항 없음"

            # 요약된 정보가 선택되지 않은 경우를 처리
            if 'selected_info' not in st.session_state or not st.session_state.selected_info:
                summarized_info = ""
            else:
                summary_service = SummaryService()
                selected_info_text = "\n".join([json.dumps(info, ensure_ascii=False) for info in st.session_state.selected_info])
                # 선택된 정보가 너무 많으면 자르기
                max_info_length = 1000
                if len(selected_info_text) > max_info_length:
                    selected_info_text = selected_info_text[:max_info_length] + '...'
                summarized_info = summary_service.summarize_info(selected_info_text, max_length=500)

            st.session_state['generator_summarized_info'] = summarized_info

            overview_service = PatientOverviewService()
            patient_details = st.session_state.get('generator_patient_details', {})
            generated_patient_details = overview_service.generate_random_details(patient_details, summarized_info)
            st.session_state['generator_generated_patient_details'] = generated_patient_details

        st.session_state.generator_page += 1
    elif st.session_state.generator_page == 2:
        st.session_state.generator_page += 1

def prev_page():
    st.session_state.generator_page -= 1

def translate_to_english(text):
    url_for_deepl = 'https://api-free.deepl.com/v2/translate'
    params = {
        'auth_key': 'API_key',  # Replace with your DeepL API key
        'text': text,
        'source_lang': 'KO',
        'target_lang': 'EN'
    }
    response = requests.post(url_for_deepl, data=params, verify=False)
    
    # Check if the request was successful
    if response.status_code != 200:
        st.error(f"Translation request failed with status code: {response.status_code}")
        return text
    
    # Attempt to parse the JSON response
    try:
        translated_text = response.json()['translations'][0]["text"]
        st.session_state['generator_disease_name_translated'] = translated_text
        return translated_text
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        st.error(f"Error parsing translation response: {e}")
        st.error(f"Response content: {response.content}")
        return text

def calculate_similarity(search_vector, vectors):
    query_vector = np.array(search_vector).reshape(1, -1)
    vectors = np.array(vectors)
    cosine_sim = cosine_similarity(query_vector, vectors)
    return cosine_sim[0]

def search_disease_by_vector(query_vector, query_text):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, title, paragraphs, info, vector
        FROM Disease_info
    """)
    results = cursor.fetchall()
    cursor.close()
    connection.close()

    # 벡터 데이터를 추출하여 유사도 계산
    vectors = [json.loads(result['vector']) for result in results]
    similarities = calculate_similarity(query_vector, vectors)
    
    # 유사도가 0.9 이상인 결과 필터링
    threshold = 0.9
    filtered_results = [result for result, similarity in zip(results, similarities) if similarity >= threshold]

    # 검색어가 포함된 결과 추가
    def count_occurrences(text, query):
        return text.lower().count(query.lower())

    for result in results:
        paragraphs_text = " ".join(json.loads(result['paragraphs']))
        info_text = " ".join(value for key, value in json.loads(result['info']).items())
        text_content = paragraphs_text + " " + info_text
        if query_text.lower() in text_content.lower():
            if result not in filtered_results:
                result['occurrences'] = count_occurrences(text_content, query_text)
                filtered_results.append(result)
    
    # 유사도 기준으로 결과 정렬
    sorted_results = sorted(filtered_results, key=lambda x: similarities[results.index(x)] if x in results else 0, reverse=True)

    # 검색어 포함된 결과에서 occurrences 기준으로 상위 10개 추출
    filtered_sorted_results = sorted([result for result in results if 'occurrences' in result],
                                     key=lambda x: x['occurrences'], reverse=True)[:9]

    return sorted_results, filtered_sorted_results

if 'expanded_expanders' not in st.session_state:
    st.session_state['expanded_expanders'] = set()

def toggle_expander(expander_id):
    if expander_id in st.session_state['expanded_expanders']:
        st.session_state['expanded_expanders'].remove(expander_id)
    else:
        st.session_state['expanded_expanders'].add(expander_id)

def load_page():
    if 'generator_page' not in st.session_state:
        st.session_state['generator_page'] = 1

    if 'generator_patient_details' not in st.session_state:
        st.session_state['generator_patient_details'] = {}
        
    if 'generator_generated_patient_info' not in st.session_state:
        st.session_state['generator_generated_patient_info'] = ""
        
    if 'generator_generated_patient_details' not in st.session_state:
        st.session_state['generator_generated_patient_details'] = {}
        
    if 'generator_generated_scenario' not in st.session_state:
        st.session_state['generator_generated_scenario'] = ""
        
    if 'generator_edited_scenario' not in st.session_state:
        st.session_state['generator_edited_scenario'] = ""
        
    if 'generator_feedback' not in st.session_state:
        st.session_state['generator_feedback'] = ""
        
    if 'generator_previous_patient_details' not in st.session_state:
        st.session_state['generator_previous_patient_details'] = {}

    if 'selected_info' not in st.session_state:
        st.session_state['selected_info'] = []

    st.title("간호 시뮬레이션 시나리오 생성")

    if st.session_state.generator_page == 1:
        disease_name = st.text_input("질병명", key="generator_disease_name")
        st.text_input("목적", key="generator_purpose")
        
        if disease_name:
            if any('\uac00' <= char <= '\ud7a3' for char in disease_name):
                disease_name_translated = translate_to_english(disease_name)
                disease_name_translated_singular = disease_name_translated.rstrip('s')
            else:
                disease_name_translated = disease_name
                disease_name_translated_singular = disease_name

            if 'generator_disease_name_translated' in st.session_state:
                st.write(f"번역된 질병명: {st.session_state['generator_disease_name_translated']}")

            # 두 가지 질병명 형태로 벡터 생성
            query_vector_plural = model.encode(st.session_state['generator_disease_name_translated'])
            query_vector_singular = model.encode(disease_name_translated_singular)
            query_text_plural = st.session_state['generator_disease_name_translated']
            query_text_singular = disease_name_translated_singular

            # 각각의 벡터로 검색 수행
            sorted_results_plural, filtered_sorted_results_plural = search_disease_by_vector(query_vector_plural, query_text_plural)
            sorted_results_singular, filtered_sorted_results_singular = search_disease_by_vector(query_vector_singular, query_text_singular)
            
            # 검색 결과 합치기 (중복 제거)
            sorted_results = {result['id']: result for result in sorted_results_plural + sorted_results_singular}.values()
            filtered_sorted_results = {result['id']: result for result in filtered_sorted_results_plural + filtered_sorted_results_singular}.values()

            if sorted_results or filtered_sorted_results:
                st.write(f"총 {len(sorted_results) + len(filtered_sorted_results)}개의 관련 정보가 발견되었습니다.")
                
                # 좌우로 나눠서 결과 출력
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("### 제목에 검색어 포함")
                    for result in sorted_results:
                        if query_text_plural.lower() in result['title'].lower() or query_text_singular.lower() in result['title'].lower():
                            with st.expander(result['title']):
                                st.write("**Paragraphs:**")
                                paragraphs = json.loads(result['paragraphs'])
                                for para in paragraphs:
                                    st.write(para)
                                st.write("**Info:**")
                                info = json.loads(result['info'])
                                for key, value in info.items():
                                    st.write(f"{key}: {value}")
                                if st.checkbox("이 정보를 사용", key=f"generator_use_title_{result['id']}"):
                                    st.session_state.selected_info.append(result)
                
                with col2:
                    st.write("### 내용에 검색어 포함 (빈도 순)")
                    for result in filtered_sorted_results:
                        with st.expander(result['title']):
                            st.write("**Paragraphs:**")
                            paragraphs = json.loads(result['paragraphs'])
                            for para in paragraphs:
                                st.write(para)
                            st.write("**Info:**")
                            info = json.loads(result['info'])
                            for key, value in info.items():
                                st.write(f"{key}: {value}")
                            if st.checkbox("이 정보를 사용", key=f"generator_use_content_{result['id']}"):
                                st.session_state.selected_info.append(result)
            else:
                st.write("관련 정보를 찾을 수 없습니다.")

        patient_details_input()


        st.subheader("현재 입력된 정보")
        disease = st.session_state.get('generator_disease_name', '')
        purpose = st.session_state.get('generator_purpose', '')

        st.session_state['generator_patient_details']['질병명'] = st.session_state.get('generator_disease_name', '')
        st.session_state['generator_patient_details']['목적'] = st.session_state.get('generator_purpose', '')

        if st.session_state['generator_patient_details']:
            for key, value in st.session_state['generator_patient_details'].items():
                if isinstance(value, list):
                    formatted_value = ', '.join(value)
                    st.write(f"{key}: {formatted_value}")
                else:
                    st.write(f"{key}: {value}")

    elif st.session_state.generator_page == 2:
        st.subheader("환자 개요")

        if 'generator_generated_patient_details' in st.session_state:
            for key, value in st.session_state['generator_generated_patient_details'].items():
                if not value:
                    value = "해당사항 없음"
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"{key}: {value}")
                with col2:
                    if st.button(f"수정", key=f"generator_edit_{key}"):
                        st.session_state.generator_edit_key = key
                        st.session_state.generator_temp_value = st.session_state['generator_generated_patient_details'][key] if isinstance(value, list) else str(value)
                        st.experimental_rerun()

            if 'generator_edit_key' in st.session_state and st.session_state.generator_edit_key:
                update_detail()

        if st.button("환자개요 생성"):
            disease = st.session_state['generator_generated_patient_details'].get('질병명', st.session_state.get('generator_disease_name', ''))
            purpose = st.session_state['generator_generated_patient_details'].get('목적', st.session_state.get('generator_purpose', ''))

            if not disease or not purpose:
                st.error("질병명과 목적을 입력해주세요.")
            else:
                gpt_service = PatientCreationService()
                summary_service = SummaryService()
                
                formatted_patient_info = format_patient_info(st.session_state['generator_generated_patient_details'])
                selected_info = "\n".join([json.dumps(info, ensure_ascii=False) for info in st.session_state.selected_info])
                summarized_info = summary_service.summarize_info(selected_info)
                
                scenario = gpt_service.create_scenario(
                    disease,
                    purpose,
                    formatted_patient_info,
                    summarized_info
                )
                st.session_state['generator_generated_patient_info'] = scenario
                st.success("환자 정보가 생성되었습니다!")
                st.session_state.generator_show_scenario_button = True
                
                st.experimental_rerun()
                
        if 'generator_generated_patient_info' in st.session_state:
            st.markdown(
                f'<div style="width: 700px; white-space: pre-wrap;">{st.session_state["generator_generated_patient_info"]}</div>',
                unsafe_allow_html=True
            )

        if st.session_state.get('generator_show_scenario_button'):
            if st.button("환자 시나리오 생성"):
                st.session_state.generator_page = 3
                st.experimental_rerun()

    elif st.session_state.generator_page == 3:
        st.subheader("간호 시나리오")

        if 'generator_generated_patient_info' in st.session_state:
            patient_overview = st.session_state["generator_generated_patient_info"]
            formatted_patient_overview = patient_overview.replace("◦ ", "\n◦ ").replace(":\n", ":\n")
            st.markdown(
                f'<div style="border:1px solid black; padding: 10px; margin-bottom: 20px;">{formatted_patient_overview}</div>',
                unsafe_allow_html=True
            )

        if st.session_state['generator_previous_patient_details'] != st.session_state['generator_generated_patient_details']:
            st.session_state['generator_generated_scenario'] = ""

        if 'generator_generated_scenario' not in st.session_state or not st.session_state['generator_generated_scenario']:
            if 'generator_generated_patient_details' in st.session_state:
                formatted_patient_info = format_patient_info(st.session_state['generator_generated_patient_details'])
                purpose = st.session_state['generator_patient_details'].get('목적', '')

                nursing_service = NursingScenarioService()
                summary_service = SummaryService()
                
                summarized_info = summary_service.summarize_info("\n".join([json.dumps(info, ensure_ascii=False) for info in st.session_state.selected_info]))
                scenario = nursing_service.create_nursing_scenario(
                    formatted_patient_info,
                    purpose,
                    summarized_info
                )
                st.session_state['generator_generated_scenario'] = scenario

        if 'generator_generated_scenario' in st.session_state:
            scenario = st.session_state["generator_generated_scenario"]
            formatted_scenario = "\n\n".join(
                f'<div style="border:1px solid black; padding: 10px; margin-bottom: 20px;">{part.strip()}</div>'
                for part in scenario.split("\n\n")
            )
            st.markdown(
                f'<div style="width: 700px; white-space: pre-wrap;">{formatted_scenario}</div>',
                unsafe_allow_html=True
            )

            with st.expander("시나리오 직접 수정"):
                edited_scenario = st.text_area("수정할 시나리오 내용을 입력하세요:", value=scenario, height=300)

                if st.button("수정 내용 저장"):
                    st.session_state['generator_edited_scenario'] = edited_scenario
                    st.session_state['generator_generated_scenario'] = edited_scenario
                    st.experimental_rerun()
        
            with st.expander("GPT에 피드백 전달"):
                feedback = st.text_input("피드백을 입력하세요 (예: 다시 작성해줘, 시나리오 단계를 3개로 줄여줘 등):")

                if st.button("수정된 내용 반영하여 재생성"):
                    revision_service = ScenarioRevisionService()
                    revised_scenario = revision_service.revise_scenario_with_feedback(
                        st.session_state['generator_generated_scenario'],
                        feedback
                    )
                    st.session_state['generator_generated_scenario'] = revised_scenario
                    st.experimental_rerun()

            if st.button("시나리오 저장"):
                patient_info = st.session_state['generator_generated_patient_details']
                patient_overview = st.session_state['generator_generated_patient_info']
                scenario = st.session_state['generator_generated_scenario']
                save_scenario_to_mariadb(patient_info, patient_overview, scenario)
                st.success("시나리오가 성공적으로 저장되었습니다.")
                reset_session()
                st.experimental_rerun()


    st.session_state['generator_previous_patient_details'] = st.session_state['generator_generated_patient_details']

    if st.session_state.generator_page > 1:
        st.button("이전", on_click=prev_page, key="prev_page")

    if st.session_state.generator_page < 3 and st.session_state.generator_page != 2:
        st.button("다음", on_click=next_page, key="next_page")

def patient_details_input():
    st.subheader("환자 정보")
    st.markdown("""
    <li>간호 시뮬레이션 시나리오에 포함할 환자 정보를 선택하세요.</li>
    <li>선택된 환자 정보에 대한 상세 내용을 입력하지 않으면 무작위 값이 할당됩니다.</li>
    """, unsafe_allow_html=True)

    patient_info_fields = [
        { 'name': '이름', 'label': '이름' },
        { 'name': '나이', 'label': '나이' },
        { 'name': '성별', 'label': '성별', 'options': ['남성', '여성'] },
        { 'name': '몸무게', 'label': '몸무게' },
        { 'name': '키', 'label': '키' },
        { 'name': '주호소', 'label': '주호소', 'options': ['복통', '가슴 통증', '호흡곤란', '두통'] },
        { 'name': '입원경로', 'label': '입원경로', 'options': ['응급실', '외래에서 의사의 추천', '정기검진 후', '사고 후'] },
        { 'name': '사회력', 'label': '사회력'},
        { 'name': '과거병력', 'label': '과거병력', 'options': ['고혈압', '당뇨병', '천식', '심부전'] },
        { 'name': '과거수술력', 'label': '과거수술력', 'options': ['맹장수술','심장판막수술','갑상선 제거술'] },
        { 'name': '가족력', 'label': '가족력', 'options': ['고혈압', '경화증', '암', '심장병'] },
        { 'name': '약물', 'label': '약물', 'options': ['아스피린', ] },
        { 'name': '1차 진단명', 'label': '1차 진단명', 'options': ['심근경색', '폐렴', '뇌졸중', '급성 신부전'] },
        { 'name': '추가사항', 'label': '추가사항' }
    ]

    st.markdown("""
    <style>
    .streamlit-container .stCheckbox {
        display: inline-flex;
        margin-left: 10px;
        margin-right: 10px;
        align-items: center.
    }
    .streamlit-container .stTextInput {
        margin-bottom: 10px.
    }
    .streamlit-container .stExpander > div:first-child {
        margin-bottom: -10px.
    }
    </style>
    """, unsafe_allow_html=True)

    fields_per_row = 4

    sublists = [patient_info_fields[i:i + fields_per_row] for i in range(0, len(patient_info_fields), fields_per_row)]

    for sublist in sublists:
        columns = st.columns(fields_per_row)
        for col, field in zip(columns, sublist):
            with col:
                st.markdown(f"**{field['label']}**")
                field_checked = st.checkbox('', key=f"generator_{field['name']}_checkbox")
                if field_checked:
                    if 'options' in field:
                        with st.expander(f"{field['label']} 선택"):
                            selected_options = []
                            for option in field['options']:
                                if st.checkbox(option, key=f"generator_{field['name']}_{option}"):
                                    selected_options.append(option)
                            other_checked = st.checkbox('기타', key=f"generator_{field['name']}_other_checkbox")
                            if other_checked:
                                other_detail = st.text_input("기타 상세 내용 입력", key=f"generator_{field['name']}_other_input")
                                selected_options.append(other_detail)
                            if not selected_options:
                                selected_options = "랜덤"
                            st.session_state['generator_patient_details'][field['name']] = selected_options
                    else:
                        detail = st.text_input('', key=f"generator_{field['name']}_input")
                        if field['name'] == '몸무게':
                            if not detail:
                                detail = "랜덤"
                            else:
                                detail = f"{detail}"
                        elif field['name'] == '키':
                            if not detail:
                                detail = "랜덤"
                            else:
                                detail = f"{detail}"
                        else:
                            if not detail:
                                detail = "랜덤"
                        st.session_state['generator_patient_details'][field['name']] = detail
                else:
                    if field['name'] in st.session_state['generator_patient_details']:
                        del st.session_state['generator_patient_details'][field['name']]

    def deselect_all():
        for field in patient_info_fields:
            st.session_state[f"generator_{field['name']}_checkbox"] = False
            if f"generator_{field['name']}_other_checkbox" in st.session_state:
                st.session_state[f"generator_{field['name']}_other_checkbox"] = False
                if f"generator_{field['name']}_other_input" in st.session_state:
                    st.session_state[f"generator_{field['name']}_other_input"] = ""

    if st.button("전체 해제", on_click=deselect_all):
        pass

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    load_page()
