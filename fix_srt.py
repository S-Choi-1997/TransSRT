import re

def fix_srt_format(input_file, output_file):
    """SRT 파일의 형식을 수정: 번호 시간 대사를 각각 별도 줄로 분리"""

    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # SRT 패턴: 번호 시간 --> 시간 대사
    # 예: 1 00:01:30,270 --> 00:01:33,220 Welcome.
    pattern = r'(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3})\s+(.+?)(?=\n\d+\s+\d{2}:|\Z)'

    matches = re.findall(pattern, content, re.DOTALL)

    fixed_lines = []
    for number, timestamp, subtitle_text in matches:
        # 대사에서 불필요한 공백 제거
        subtitle_text = subtitle_text.strip()

        # 올바른 형식으로 작성: 번호, 시간, 대사, 빈 줄
        fixed_lines.append(f"{number}\n{timestamp}\n{subtitle_text}\n")

    # 파일 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))

    print(f"변환 완료: {output_file}")
    print(f"총 {len(matches)}개의 자막 항목 처리됨")

if __name__ == "__main__":
    input_file = "연락올까-영어.srt"
    output_file = "연락올까-영어_fixed.srt"

    fix_srt_format(input_file, output_file)
