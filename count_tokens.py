import re
import tiktoken

def count_subtitle_tokens(srt_file):
    """SRT 파일에서 자막 내용만 추출하여 토큰 수 계산"""

    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # SRT 패턴: 번호 시간 --> 시간 대사
    pattern = r'(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3})\s+(.+?)(?=\n\d+\s+\d{2}:|\Z)'

    matches = re.findall(pattern, content, re.DOTALL)

    # 자막 내용만 추출
    subtitles = []
    for number, timestamp, subtitle_text in matches:
        subtitle_text = subtitle_text.strip()
        subtitles.append(subtitle_text)

    # 모든 자막을 하나의 텍스트로 결합
    full_text = '\n'.join(subtitles)

    # tiktoken으로 토큰 수 계산 (GPT-4 기준)
    encoding = tiktoken.encoding_for_model("gpt-4")
    tokens = encoding.encode(full_text)
    token_count = len(tokens)

    # 결과 출력
    print(f"파일: {srt_file}")
    print(f"자막 항목 수: {len(subtitles)}개")
    print(f"전체 문자 수: {len(full_text):,}자")
    print(f"토큰 수 (GPT-4): {token_count:,}개")
    print(f"\n예상 비용 (입력 기준):")
    print(f"  GPT-4: ${token_count * 0.00003:.4f}")
    print(f"  GPT-4-turbo: ${token_count * 0.00001:.4f}")
    print(f"  GPT-3.5-turbo: ${token_count * 0.0000005:.6f}")

    return token_count, full_text

if __name__ == "__main__":
    srt_file = "연락올까-영어.srt"

    try:
        count_subtitle_tokens(srt_file)
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {srt_file}")
    except Exception as e:
        print(f"오류 발생: {e}")
