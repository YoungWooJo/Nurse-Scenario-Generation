import openai
import os
import tiktoken
from openai import OpenAI

# API key setup
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "API_KEY"))


def num_tokens_from_string(string: str, encoding_name: str) -> int:
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

class OpenAIService:
    def __init__(self):
        self.client = openai  # openai 모듈을 client로 사용합니다.

class PatientOverviewService(OpenAIService):
    def generate_random_details(self, patient_details, summarized_info):
        disease_name = patient_details.get('질병명', '정보 없음')
        purpose = patient_details.get('목적', '정보 없음')

        if summarized_info:
            prompt_message = (
                f"다음 요약 정보, 질병명, 목적을 바탕으로 환자 정보를 생성해주세요:\n"
                f"요약 정보: {summarized_info}\n"
                f"질병명: {disease_name}\n"
                f"목적: {purpose}\n"
            )
        else:
            prompt_message = (
                f"다음 질병명과 목적에 맞춰 환자 정보를 생성해주세요:\n"
                f"질병명: {disease_name}\n"
                f"목적: {purpose}\n"
            )

        for key, value in patient_details.items():
            if value == "랜덤":
                if key == '주호소' or key == '1차 진단명':
                    prompt_message += f"{key}: {disease_name}과 관련된 내용으로 생성해주세요.\n"
                elif key == '약물':
                    age = patient_details.get('나이', '정보 없음')
                    gender = patient_details.get('성별', '정보 없음')
                    prompt_message += f"{key}: {age}세 {gender}에 적합한 일반적인 약물을 제안해주세요.\n"
                else:
                    prompt_message += f"{key}: 랜덤 값 생성해주세요.\n"
            else:
                prompt_message += f"{key}: {value}\n"

        if patient_details.get('몸무게', '') == '랜덤 kg' and patient_details.get('키', '') == '랜덤 cm':
            age = patient_details.get('나이', '정보 없음')
            gender = patient_details.get('성별', '정보 없음')
            prompt_message += f"\n나이: {age}세와 성별: {gender}에 적당한 몸무게와 키를 제안해주세요.\n"

        # 토큰 길이 확인
        max_tokens = 16000  # 16,385 토큰을 넘지 않도록 설정
        token_count = num_tokens_from_string(prompt_message, "cl100k_base")
        if token_count > max_tokens:
            prompt_message = prompt_message[:max_tokens]  # 최대 토큰 수에 맞게 자르기

        chat_completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical professional generating random patient details."},
                {"role": "user", "content": prompt_message}
            ]
        )
        response_content = chat_completion.choices[0].message.content.strip()

        # 결과를 파싱하여 랜덤 필드 업데이트
        for line in response_content.split('\n'):
            if ': ' in line:
                key, value = line.split(': ', 1)
                if key in patient_details and patient_details[key] == "랜덤":
                    patient_details[key] = value  # 실제 값으로 대체

        return patient_details


class PatientCreationService(OpenAIService):
    def create_scenario(self, disease_name, purpose, patient_info_details, summarized_info):
        prompt_message = (
            f"{disease_name}에 대한 {purpose} 시뮬레이션 시나리오를 작성해주세요. "
            f"환자 정보는 다음과 같습니다: {patient_info_details}. "
            "문서의 구성은 환자 개요(Brief description of client), 자세한 상황 설명 순으로 작성해주세요. "
            "해당사항 없음을 입력으로 받으면 없음으로 작성해주세요. "
            "환자개요는 한글로 작성해주세요."
            "각 환자개요 사이에 적절한 줄바꿈을 포함하여 작성해주세요.\n"
            "\n\n"
            "환자 개요(Brief description of client):\n"
            "◦ 질병명(Disease Name):\n"
            "◦ 목적(Purpose):\n"
            "◦ 이름(Name):\n"
            "◦ 성별(Gender):\n"
            "◦ 나이(Age):\n"
            "◦ 키(Height):\n"
            "◦ 몸무게(Weight):\n"
            "◦ 주호소(Chief complaint):\n"
            "◦ 입원경로(History of present illness):\n"
            "◦ 사회력(Social history):\n"
            "◦ 과거질병력(Past medical history):\n"
            "◦ 과거수술력(Past surgical history & date):\n"
            "◦ 가족력(Family medical history):\n"
            "◦ 약물(Medication):\n"
            "◦ 1차 진단명(Primary diagnosis):\n"
            "\n배경 지식:\n"
            "배경 지식은 한글로 작성해주세요."
            f"{summarized_info}\n"            
            "\n자세한 상황 설명을 작성해주세요.\n"
        )

        # 토큰 길이 확인 및 자르기
        max_tokens = 16000  # 16,385 토큰을 넘지 않도록 설정
        token_count = num_tokens_from_string(prompt_message, "cl100k_base")
        if token_count > max_tokens:
            prompt_message = prompt_message[:max_tokens]  # 최대 토큰 수에 맞게 자르기

        chat_completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a nursing department's professor, help the user to generate a patient information."},
                {"role": "user", "content": prompt_message}
            ]
        )
        return chat_completion.choices[0].message.content.strip()



class NursingScenarioService(OpenAIService):
    def create_nursing_scenario(self, patient_info_details, purpose, summarized_info):
        prompt_message = (
            f"다음 환자 정보에 대한 시뮬레이션 시나리오를 작성해주세요:\n"
            f"{patient_info_details}\n"
            f"목적: {purpose}\n"
            "각 단계는 환자의 상태, 예상 간호 중재, 브리핑을 위한 교육 포인트를 포함해야 합니다. "
            "각 항목과 단계 사이에 적절한 줄바꿈을 포함하여 작성해주세요.\n"
            "\n배경 지식:\n"
            "배경 지식은 한글로 작성해주세요."
            f"{summarized_info}\n"
            "\n시나리오 단계의 목차는 꼭 아래 목차를 사용해줘."
            "시나리오 단계(예시):\n"
            "1. Initial Stage:\n"
            "  - 환자 상태: [환자의 상태 설명]\n"
            "  - 예상 간호 중재: [예상 간호 중재 설명]\n"
            "  - 교육 포인트: [교육 포인트 설명]\n"
            "2. 1st state/interval:\n"
            "  - 환자 상태: [환자의 상태 설명]\n"
            "  - 예상 간호 중재: [예상 간호 중재 설명]\n"
            "  - 교육 포인트: [교육 포인트 설명]\n"
            "3. 2nd state/interval:\n"
            "  - 환자 상태: [환자의 상태 설명]\n"
            "  - 예상 간호 중재: [예상 간호 중재 설명]\n"
            "  - 교육 포인트: [교육 포인트 설명]\n"
            "4. 3rd state/interval:\n"
            "  - 환자 상태: [환자의 상태 설명]\n"
            "  - 예상 간호 중재: [예상 간호 중재 설명]\n"
            "  - 교육 포인트: [교육 포인트 설명]\n"
        )

        chat_completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a nursing department's professor. Help the user to generate a nusing scenerio."},
                {"role": "user", "content": prompt_message}
            ]
        )

        scenario = chat_completion.choices[0].message.content.strip()
        return scenario


class ScenarioRevisionService(OpenAIService):
    def revise_scenario_with_feedback(self, edited_scenario, feedback):
        prompt_message = (
            f"다음은 수정된 간호 시나리오입니다. 이 시나리오와 사용자 피드백을 바탕으로 환자 시나리오를 다시 작성해주세요:\n"
            f"수정된 시나리오:\n{edited_scenario}\n"
            f"피드백:\n{feedback}\n"
        )

        chat_completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a nursing department's professor. Help the user to revise a nursing scenario based on provided details and feedback."},
                {"role": "user", "content": prompt_message}
            ]
        )

        revised_scenario = chat_completion.choices[0].message.content.strip()
        return revised_scenario

class SummaryService(OpenAIService):
    def summarize_info(self, info, max_length=500):
        # 정보의 길이가 너무 길면 자르기
        max_tokens = 16000  # 16,385 토큰을 넘지 않도록 설정
        encoding_name = "cl100k_base"
        token_count = num_tokens_from_string(info, encoding_name)
        
        if token_count > max_tokens:
            info = info[:max_tokens]  # 최대 토큰 수에 맞게 자르기

        prompt_message = (
            f"다음 정보를 해당 질병정보의 원인, 증상, 예방, 치료방법 대해서 자세하게 요약해 주세요. 요약은 최대 {max_length}자로 제한됩니다:\n"
            f"{info}\n"
        )
        
        chat_completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional nursing text summarizer."},
                {"role": "user", "content": prompt_message}
            ]
        )
        return chat_completion.choices[0].message.content.strip()

