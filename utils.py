import mysql.connector
import streamlit as st
import base64
import json
from datetime import datetime

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="scenario",
        password="Skaqn3301",
        database="nursing_scenarios"
    )

def save_scenario_to_mariadb(patient_info, scenario_text, scenario_id=None, patient_overview=None):
    connection = get_db_connection()
    cursor = connection.cursor()
    
    if scenario_id:
        document_id = scenario_id
    else:
        disease_name = patient_info.get('질병명', 'unknown').replace(" ", "")
        purpose = patient_info.get('목적', 'unknown').replace(" ", "")
        current_time = datetime.now().strftime("%Y%m%d%H%M%S")
        document_id = f"{disease_name}_{purpose}_{current_time}"
    
    patient_info_json = json.dumps(patient_info, ensure_ascii=False)
    insert_query = """
        INSERT INTO scenarios (id, patient_info, scenario, patient_overview, created_at)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(insert_query, (document_id, patient_info_json, scenario_text, patient_overview, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    connection.commit()
    cursor.close()
    connection.close()

def img_to_base64_str(filename):
    with open(filename, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    return encoded_string

def load_css():
    with open("style.css", "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
