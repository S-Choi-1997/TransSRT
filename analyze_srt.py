"""
SRT 파일에서 실제 자막 텍스트만 추출하여 토큰 수와 글자 수를 계산하는 스크립트
"""

import re
import tiktoken


def extract_subtitle_text(srt_file):
    """
    SRT 파일에서 자막 텍스트만 추출

    Args:
        srt_file: SRT 파일 경로

    Returns:
        str: 추출된 자막 텍스트 (모든 자막이 하나의 문자열로 결합됨)
    """
    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # SRT 엔트리를 파싱하기 위한 정규식
    # 번호와 타임스탬프를 제외하고 자막 텍스트만 추출
    pattern = r'\d+\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?=\n\n\d+\n\d{2}:|\Z)'

    matches = re.findall(pattern, content, re.DOTALL)

    # 자막 텍스트만 추출 (타임스탬프는 제외)
    subtitle_texts = [match[1].strip() for match in matches]

    # 모든 자막을 하나의 문자열로 결합
    full_text = ' '.join(subtitle_texts)

    return full_text, subtitle_texts


def count_tokens(text, model="gpt-4"):
    """
    텍스트의 토큰 수를 계산

    Args:
        text: 분석할 텍스트
        model: 사용할 토큰 인코딩 모델 (기본값: gpt-4)

    Returns:
        int: 토큰 수
    """
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)
    return len(tokens)


def analyze_srt(srt_file, model="gpt-4"):
    """
    SRT 파일을 분석하여 토큰 수와 글자 수를 계산

    Args:
        srt_file: SRT 파일 경로
        model: 사용할 토큰 인코딩 모델 (기본값: gpt-4)
    """
    print(f"분석 중: {srt_file}")
    print("=" * 60)

    # 자막 텍스트 추출
    full_text, subtitle_texts = extract_subtitle_text(srt_file)

    # 통계 계산
    total_characters = len(full_text)
    total_characters_no_space = len(full_text.replace(' ', ''))
    total_tokens = count_tokens(full_text, model)
    subtitle_count = len(subtitle_texts)

    # 결과 출력
    print(f"\n[분석 결과]")
    print(f"  - 자막 개수: {subtitle_count:,}개")
    print(f"  - 총 글자 수 (공백 포함): {total_characters:,}자")
    print(f"  - 총 글자 수 (공백 제외): {total_characters_no_space:,}자")
    print(f"  - 토큰 수 ({model}): {total_tokens:,} tokens")
    print(f"  - 평균 자막당 글자 수: {total_characters / subtitle_count:.1f}자")
    print(f"  - 평균 자막당 토큰 수: {total_tokens / subtitle_count:.1f} tokens")

    # 샘플 자막 출력 (처음 3개)
    print(f"\n[샘플 자막 (처음 3개)]")
    for i, subtitle in enumerate(subtitle_texts[:3], 1):
        print(f"  [{i}] {subtitle[:100]}{'...' if len(subtitle) > 100 else ''}")

    return {
        'subtitle_count': subtitle_count,
        'total_characters': total_characters,
        'total_characters_no_space': total_characters_no_space,
        'total_tokens': total_tokens,
        'full_text': full_text,
        'subtitle_texts': subtitle_texts
    }


if __name__ == "__main__":
    # 분석할 SRT 파일 경로
    srt_file = "captions_en.srt"

    # 사용할 토큰 인코딩 모델 선택
    # 옵션: "gpt-4", "gpt-3.5-turbo", "text-davinci-003" 등
    model = "gpt-4"

    try:
        results = analyze_srt(srt_file, model)
    except FileNotFoundError:
        print(f"[오류] '{srt_file}' 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"[오류] 오류 발생: {e}")
