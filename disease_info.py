import streamlit as st
import mysql.connector
import json
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import requests

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="scenario",
        password="Skaqn3301",
        database="nursing_scenarios"
    )

def search_disease_info(title):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    query = "SELECT title, paragraphs, info, vector FROM Disease_info WHERE title LIKE %s OR paragraphs LIKE %s OR info LIKE %s"
    like_query = "%" + title + "%"
    cursor.execute(query, (like_query, like_query, like_query))
    result = cursor.fetchall()
    cursor.close()
    connection.close()
    return result

def get_disease_info_by_title(title):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    query = "SELECT title, paragraphs, info FROM Disease_info WHERE title = %s"
    cursor.execute(query, (title,))
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    return result

def display_disease_info(disease):
    st.subheader(disease['title'])
    st.write("**Paragraphs:**")
    paragraphs = json.loads(disease['paragraphs'])
    for para in paragraphs:
        st.write(para)
    
    st.write("**Info:**")
    info = json.loads(disease['info'])
    for key, value in info.items():
        st.write(f"**{key}:** {value}")

def calculate_similarity(search_query, vectors):
    query_vector = np.array(search_query).reshape(1, -1)
    vectors = np.array(vectors)
    cosine_sim = cosine_similarity(query_vector, vectors)
    return cosine_sim[0]

def translate_to_english(text):
    url_for_deepl = 'https://api-free.deepl.com/v2/translate'
    params = {
        'auth_key': 'e50eeac8-9e87-45dd-a7a1-b2a4cdf9f91c:fx',
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
        return response.json()['translations'][0]["text"]
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        st.error(f"Error parsing translation response: {e}")
        st.error(f"Response content: {response.content}")
        return text

def load_page():
    st.title("질병 정보 검색")

    if "disease_title" not in st.session_state:
        st.session_state.disease_title = None
    if "search_query" not in st.session_state:
        st.session_state.search_query = ""
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "similarity_results" not in st.session_state:
        st.session_state.similarity_results = []

    if st.session_state.disease_title:
        disease = get_disease_info_by_title(st.session_state.disease_title)
        if disease:
            display_disease_info(disease)
        else:
            st.write("해당 질병에 대한 정보를 찾을 수 없습니다.")
        if st.button("뒤로 가기"):
            st.session_state.disease_title = None
            st.experimental_rerun()
    else:
        search_query = st.text_input("질병명을 입력하세요:", st.session_state.search_query)
        if search_query:
            # 한글 입력 여부 확인 및 번역 처리
            if any('\uac00' <= char <= '\ud7a3' for char in search_query):
                search_query = translate_to_english(search_query)
            
            st.session_state.search_query = search_query
            if st.button("검색"):
                search_results = search_disease_info(search_query)
                
                # 검색어가 info와 paragraphs에 포함된 경우만 유지
                filtered_results = []
                for result in search_results:
                    paragraphs = json.loads(result['paragraphs'])
                    info = json.loads(result['info'])
                    paragraphs_text = " ".join(paragraphs).lower()
                    info_text = " ".join([str(value) for key, value in info.items()]).lower()
                    if search_query.lower() in paragraphs_text or search_query.lower() in info_text:
                        filtered_results.append(result)
                
                st.session_state.search_results = filtered_results

                if filtered_results:
                    vectors = [json.loads(d['vector']) for d in filtered_results]
                    search_vector = np.zeros(len(vectors[0]))  # 이 부분은 벡터의 길이에 맞게 수정 필요
                    similarity_scores = calculate_similarity(search_vector, vectors)
                    st.session_state.similarity_results = [
                        {"disease": filtered_results[i], "similarity": similarity_scores[i]}
                        for i in range(len(filtered_results))
                    ]
                    st.session_state.similarity_results.sort(key=lambda x: x["similarity"], reverse=True)
                else:
                    st.session_state.similarity_results = []
                
                st.experimental_rerun()
        
        if st.session_state.similarity_results:
            left_column, right_column = st.columns(2)
            with left_column:
                st.write("**Title에 검색어가 포함된 결과**")
                title_results = [d["disease"] for d in st.session_state.similarity_results if st.session_state.search_query.lower() in d["disease"]["title"].lower()]
                if title_results:
                    st.write(f"총 {len(title_results)}개의 결과가 발견되었습니다.")
                    for disease in title_results:
                        if st.button(disease['title']):
                            st.session_state.disease_title = disease['title']
                            st.experimental_rerun()
                else:
                    st.write("검색 결과가 없습니다.")

            with right_column:
                st.write("**Info나 Paragraphs에 검색어가 포함된 결과**")
                other_results = [d["disease"] for d in st.session_state.similarity_results if st.session_state.search_query.lower() not in d["disease"]["title"].lower()]
                if other_results:
                    st.write(f"총 {len(other_results)}개의 결과가 발견되었습니다.")
                    for disease in other_results:
                        if st.button(disease['title']):
                            st.session_state.disease_title = disease['title']
                            st.experimental_rerun()
                else:
                    st.write("검색 결과가 없습니다.")
        elif st.session_state.search_query:
            st.write("검색 결과가 없습니다.")

if __name__ == "__main__":
    load_page()
