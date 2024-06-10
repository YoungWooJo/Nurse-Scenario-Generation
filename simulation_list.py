import streamlit as st
import mysql.connector
from fpdf import FPDF
from datetime import datetime
from io import BytesIO
import json
from utils import get_db_connection, save_scenario_to_mariadb  # 추가된 부분

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="scenario",
        password="Skaqn3301",
        database="nursing_scenarios"
    )

def get_scenarios_from_mariadb():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM scenarios ORDER BY created_at DESC")
    scenarios = cursor.fetchall()
    cursor.close()
    connection.close()

    print("Fetched scenarios from DB:")
    for scenario in scenarios:
        print(scenario)

    return scenarios

class PDF(FPDF):
    def header(self):
        self.set_font('NanumGothic', '', 13)

    def chapter_title(self, title):
        self.set_font('NanumGothic', '', 11)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(10)

    def chapter_body(self, body):
        self.set_font('NanumGothic', '', 11)
        self.multi_cell(0, 10, body)
        self.ln()

    def add_chapter(self, title, body):
        self.add_page()
        self.chapter_title(title)
        self.chapter_body(body)

def create_pdf(content):
    pdf = PDF()
    pdf.add_font('NanumGothic', '', 'NanumGothic.ttf', uni=True)
    pdf.add_chapter('', content)
    return pdf

def load_simulation_list():
    st.title("시뮬레이션 리스트")

    search_query = st.text_input("Search by Title", "")
    sort_option = st.selectbox("Sort by", ["Date (Newest First)", "Date (Oldest First)", "Title (A-Z)", "Title (Z-A)"])

    scenarios = get_scenarios_from_mariadb()

    if scenarios:
        if search_query:
            scenarios = [scenario for scenario in scenarios if search_query.lower() in scenario['id'].lower()]

        if sort_option == "Date (Oldest First)":
            scenarios.sort(key=lambda x: x['created_at'])
        elif sort_option == "Title (A-Z)":
            scenarios.sort(key=lambda x: x['id'].lower())
        elif sort_option == "Title (Z-A)":
            scenarios.sort(key=lambda x: x['id'].lower(), reverse=True)

        header_cols = st.columns([4, 3, 3, 2, 1, 1])
        header_cols[0].write("Title")
        header_cols[1].write("질병명")
        header_cols[2].write("목적")
        header_cols[3].write("생성 날짜")
        header_cols[4].write("View")
        header_cols[5].write("Edit")

        for scenario in scenarios:
            parts = scenario['id'].rsplit('_', 2)
            if len(parts) == 3:
                disease_name, purpose, date_str = parts
                disease_name = disease_name.replace("_", " ")
                scenario_date = datetime.strptime(date_str, "%Y%m%d%H%M%S").strftime("%Y.%m.%d %H:%M")
                title = f"{disease_name} {purpose} 시나리오"

                row_cols = st.columns([4, 3, 3, 2, 1, 1])
                row_cols[0].write(title)
                row_cols[1].write(disease_name)
                row_cols[2].write(purpose)
                row_cols[3].write(scenario_date)
                if row_cols[4].button("O", key=f"view_{scenario['id']}"):
                    st.session_state.sim_list_selected_scenario = scenario
                    st.session_state.sim_list_page = 'scenario_detail'
                    st.experimental_rerun()
                if row_cols[5].button("O", key=f"edit_{scenario['id']}"):
                    st.session_state.edit_scenario = scenario
                    st.session_state.sim_list_page = 'edit_scenario'
                    st.experimental_rerun()
            else:
                st.error(f"Invalid scenario ID format for document ID: {scenario['id']}")
    else:
        st.write("저장된 시뮬레이션 시나리오가 없습니다.")

def load_scenario_detail():
    if 'sim_list_selected_scenario' in st.session_state:
        scenario = st.session_state.sim_list_selected_scenario

        print("Selected scenario for detail view:")
        print(scenario)
        
        parts = scenario['id'].rsplit('_', 2)
        if len(parts) == 3:
            disease_name, purpose, date_str = parts
            disease_name = disease_name.replace("_", " ")
            title = f"{disease_name} {purpose} 시나리오"
        else:
            st.error("Invalid scenario ID format.")
            return

        st.title(title)

        patient_overview = scenario.get("patient_overview", "")
        if patient_overview is None:
            patient_overview = ""

        scenario_text = scenario.get("scenario", "")
        if scenario_text is None:
            scenario_text = ""

        st.subheader("환자 개요")
        st.markdown(patient_overview.replace("\n", "<br>"), unsafe_allow_html=True)

        st.subheader("시나리오")
        st.markdown(scenario_text.replace("\n", "<br>"), unsafe_allow_html=True)

        col1, col2, col3 = st.columns([2, 5, 2])

        with col1:
            if st.button("뒤로가기"):
                st.session_state.sim_list_page = 'simulation_list'
                st.experimental_rerun()

        with col3:
            content = f"{disease_name} {purpose} 시나리오\n\n환자 개요\n{patient_overview}\n\n시나리오\n{scenario_text}"
            pdf = create_pdf(content)
            pdf_output = BytesIO()
            pdf.output(pdf_output)
            pdf_output.seek(0)
            st.download_button(label="PDF 다운로드", data=pdf_output, file_name=f"{disease_name} {purpose} 시나리오.pdf", mime="application/pdf")
    else:
        st.write("선택된 시나리오가 없습니다.")

def load_edit_scenario():
    if 'edit_scenario' in st.session_state:
        scenario = st.session_state.edit_scenario
        
        parts = scenario['id'].rsplit('_', 2)
        if len(parts) == 3:
            old_disease_name, old_purpose, date_str = parts
            old_disease_name = old_disease_name.replace("_", " ")
            title = f"Edit {old_disease_name} {old_purpose} 시나리오"
        else:
            st.error("Invalid scenario ID format.")
            return

        st.title(title)

        new_disease_name = st.text_input("질병명", value=old_disease_name)
        new_purpose = st.text_input("목적", value=old_purpose)
        new_patient_overview = st.text_area("환자 개요", value=scenario.get("patient_overview", ""))
        new_scenario_text = st.text_area("시나리오", value=scenario.get("scenario", ""))

        if st.button("Save Changes"):
            new_id = f"{new_disease_name.replace(' ', '_')}_{new_purpose.replace(' ', '_')}_{date_str}"
            new_patient_info = scenario.get('patient_info', '{}')
            try:
                new_patient_info = json.loads(new_patient_info)
                new_patient_info['질병명'] = new_disease_name
                new_patient_info['목적'] = new_purpose
            except json.JSONDecodeError:
                st.error("Invalid patient info format.")
                return

            # 새 시나리오 저장
            save_scenario_to_mariadb(new_patient_info, new_scenario_text, new_id, new_patient_overview)  # 네 개의 인자 전달

            # 기존 시나리오 삭제
            connection = get_db_connection()
            cursor = connection.cursor()
            delete_query = "DELETE FROM scenarios WHERE id = %s"
            cursor.execute(delete_query, (scenario['id'],))
            connection.commit()
            cursor.close()
            connection.close()

            st.success("시나리오가 업데이트되었습니다.")
            st.session_state.sim_list_page = 'simulation_list'
            st.experimental_rerun()

        if st.button("Cancel"):
            st.session_state.sim_list_page = 'simulation_list'
            st.experimental_rerun()
    else:
        st.write("선택된 시나리오가 없습니다.")

def load_page():
    if 'sim_list_page' not in st.session_state:
        st.session_state.sim_list_page = 'simulation_list'

    if st.session_state.sim_list_page == 'simulation_list':
        load_simulation_list()
    elif st.session_state.sim_list_page == 'scenario_detail':
        load_scenario_detail()
    elif st.session_state.sim_list_page == 'edit_scenario':
        load_edit_scenario()

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    load_page()
