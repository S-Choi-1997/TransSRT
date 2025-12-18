import google.generativeai as genai

# API 키 설정
genai.configure(api_key="AIzaSyAhhgre0HCa1YLtoyHFkrgN60i1SSJjZxA")

# 모델 생성
model = genai.GenerativeModel("gemini-1.5-flash")

# 간단한 테스트
response = model.generate_content("안녕하세요를 영어로 번역해주세요")

print("응답:")
print(response.text)
