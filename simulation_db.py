import streamlit as st
import mysql.connector
from utils import get_db_connection
import json

def get_scenarios_from_mariadb():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM scenarios ORDER BY created_at DESC")
    scenarios = cursor.fetchall()
    cursor.close()
    connection.close()
    return scenarios

def delete_scenarios(scenario_ids):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        format_strings = ','.join(['%s'] * len(scenario_ids))
        cursor.execute(f"DELETE FROM scenarios WHERE id IN ({format_strings})", tuple(scenario_ids))
        connection.commit()
        deleted_rows = cursor.rowcount
        cursor.close()
        connection.close()
        return deleted_rows
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return 0

def get_disease_info_from_mariadb():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Disease_info ORDER BY title ASC")
    disease_info = cursor.fetchall()
    cursor.close()
    connection.close()
    return disease_info

def delete_disease_info(disease_ids):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        format_strings = ','.join(['%s'] * len(disease_ids))
        cursor.execute(f"DELETE FROM Disease_info WHERE id IN ({format_strings})", tuple(disease_ids))
        connection.commit()
        deleted_rows = cursor.rowcount
        cursor.close()
        connection.close()
        return deleted_rows
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return 0

def load_simulation_list():
    st.title("시뮬레이션 리스트")

    scenarios = get_scenarios_from_mariadb()
    selected_scenarios = []

    if scenarios:
        for scenario in scenarios:
            if st.checkbox(f"{scenario['id']} - {scenario['scenario']}", key=scenario['id']):
                selected_scenarios.append(scenario['id'])
        
        if selected_scenarios:
            if st.button("선택된 시나리오 삭제"):
                deleted_rows = delete_scenarios(selected_scenarios)
                if deleted_rows > 0:
                    st.success(f"{deleted_rows}개의 시나리오가 삭제되었습니다.")
                else:
                    st.error("시나리오 삭제에 실패했습니다.")
                st.experimental_rerun()  # Reload the page to update the list
    else:
        st.write("저장된 시뮬레이션 시나리오가 없습니다.")

def load_disease_info_list():
    st.title("Disease Info 리스트")

    disease_info = get_disease_info_from_mariadb()
    selected_disease_info = []

    if disease_info:
        for info in disease_info:
            if st.checkbox(f"{info['title']}", key=info['id']):
                selected_disease_info.append(info['id'])
                # 세부 정보 표시
                st.subheader(f"{info['title']} 세부 정보")
                st.write("Paragraphs:")
                paragraphs = json.loads(info['paragraphs'])
                for paragraph in paragraphs:
                    st.write(paragraph)
                st.write("Info:")
                info_data = json.loads(info['info'])
                for key, value in info_data.items():
                    st.write(f"{key}: {value}")
                st.write("Vector:")
                vector_data = json.loads(info['vector'])
                st.write(vector_data)
        
        if selected_disease_info:
            if st.button("선택된 Disease Info 삭제"):
                deleted_rows = delete_disease_info(selected_disease_info)
                if deleted_rows > 0:
                    st.success(f"{deleted_rows}개의 Disease Info가 삭제되었습니다.")
                else:
                    st.error("Disease Info 삭제에 실패했습니다.")
                st.experimental_rerun()  # Reload the page to update the list
    else:
        st.write("저장된 Disease Info가 없습니다.")

def main():
    st.sidebar.title("메뉴")
    selection = st.sidebar.radio("보기 선택", ["시뮬레이션 리스트", "Disease Info 리스트"])

    if selection == "시뮬레이션 리스트":
        load_simulation_list()
    elif selection == "Disease Info 리스트":
        load_disease_info_list()

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    main()
