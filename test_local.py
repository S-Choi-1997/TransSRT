"""
Local test script for TransSRT translation
Tests the backend translation logic directly without Cloud Function
Uses test_prompt.txt for custom prompt testing
"""

import sys
import os

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Get absolute paths
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.join(script_dir, 'backend')

# Add backend to Python path FIRST
sys.path.insert(0, backend_path)

# Now import from backend
import srt_parser
import chunker
import translator
from dotenv import load_dotenv

# Use imported modules and classes
SRTParser = srt_parser.SRTParser
create_chunks = chunker.create_chunks
GeminiTranslator = translator.GeminiTranslator
Chunk = chunker.Chunk

# Custom translator class with prompt override
class CustomPromptTranslator(GeminiTranslator):
    """Translator with custom prompt template"""

    def __init__(self, api_key, model, max_concurrent, custom_prompt):
        super().__init__(api_key, model, max_concurrent)
        self.custom_prompt_template = custom_prompt

    def _create_prompt(self, chunk: Chunk) -> str:
        """Override to use custom prompt template"""
        prompt = self.custom_prompt_template

        # Add context if available
        if chunk.previous_context:
            prompt += f"\n\nCONTEXT (previous subtitles for continuity):\n"
            for i, entry in enumerate(chunk.previous_context[-3:], 1):
                prompt += f"  {entry.text}\n"
            prompt += "\n"

        # Add current chunk info
        prompt += f"\nCHUNK INFO: This is chunk {chunk.index}/{chunk.total}\n\n"
        prompt += f"TRANSLATE THESE {len(chunk.entries)} KOREAN SUBTITLES:\n\n"

        for i, entry in enumerate(chunk.entries, 1):
            prompt += f"{i}. {entry.text}\n"

        prompt += f"\n"
        prompt += f"OUTPUT FORMAT (EXACTLY {len(chunk.entries)} LINES):\n"
        prompt += f"1. [English translation of line 1]\n"
        prompt += f"2. [English translation of line 2]\n"
        prompt += f"...\n"
        prompt += f"{len(chunk.entries)}. [English translation of line {len(chunk.entries)}]\n"
        prompt += f"\nREMEMBER: Output MUST contain EXACTLY {len(chunk.entries)} numbered lines. No more, no less."

        return prompt.replace("{count}", str(len(chunk.entries)))

def test_local_translation(srt_file_path, output_path=None, prompt_file='test_prompt.txt'):
    """
    Test translation locally using backend code directly.

    Args:
        srt_file_path: Path to Korean SRT file
        output_path: Optional output path for translated file
        prompt_file: Path to custom prompt file (default: test_prompt.txt)
    """
    # Load environment variables
    load_dotenv('backend/.env')

    api_key = os.getenv('GEMINI_API_KEY')
    model = os.getenv('GEMINI_MODEL', 'gemini-2.5-pro')
    chunk_size = int(os.getenv('CHUNK_SIZE', '150'))
    max_concurrent = int(os.getenv('MAX_CONCURRENT_REQUESTS', '5'))

    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found in backend/.env")
        return

    # Load custom prompt
    if os.path.exists(prompt_file):
        with open(prompt_file, 'r', encoding='utf-8') as f:
            custom_prompt_template = f.read()
        print(f"📝 Using custom prompt from: {prompt_file}")
    else:
        print(f"⚠️  Prompt file not found: {prompt_file}")
        print(f"   Using default prompt from translator.py")
        custom_prompt_template = None

    print(f"🔧 Configuration:")
    print(f"   Model: {model}")
    print(f"   Chunk size: {chunk_size}")
    print(f"   Max concurrent: {max_concurrent}")
    print()

    # Read SRT file
    if not os.path.exists(srt_file_path):
        print(f"❌ Error: File not found: {srt_file_path}")
        return

    with open(srt_file_path, 'r', encoding='utf-8') as f:
        srt_content = f.read()

    print(f"📂 Input file: {srt_file_path}")
    print(f"📊 File size: {len(srt_content)} characters")
    print()

    # Step 1: Parse
    print("🔍 Step 1: Parsing SRT...")
    parser = SRTParser()
    entries = parser.parse(srt_content)
    print(f"   ✅ Parsed {len(entries)} subtitle entries")
    print()

    # Step 2: Chunk
    print("📦 Step 2: Creating chunks...")
    chunks = create_chunks(entries, chunk_size=chunk_size)
    print(f"   ✅ Created {len(chunks)} chunks")
    for i, chunk in enumerate(chunks, 1):
        print(f"      Chunk {i}: {len(chunk.entries)} entries")
    print()

    # Step 3: Translate with custom prompt
    print("🌐 Step 3: Translating with Gemini API...")
    print("⏳ This may take a while...")
    print()

    try:
        # Create custom translator with prompt override
        if custom_prompt_template:
            translator = CustomPromptTranslator(
                api_key=api_key,
                model=model,
                max_concurrent=max_concurrent,
                custom_prompt=custom_prompt_template
            )
            translations = translator.translate_chunks(chunks)
        else:
            # Use default translator
            translations = translator.translate_subtitles(
                chunks=chunks,
                api_key=api_key,
                model=model,
                max_concurrent=max_concurrent
            )
        print(f"   ✅ Translation complete!")
        print()
    except Exception as e:
        print(f"❌ Translation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Reassemble
    print("🔨 Step 4: Reassembling translated SRT...")
    translated_entries = []
    for i, chunk in enumerate(chunks):
        chunk_translations = translations[i]
        for j, entry in enumerate(chunk.entries):
            if j < len(chunk_translations):
                translated_entry = srt_parser.SRTEntry(
                    number=entry.number,
                    timestamp=entry.timestamp,
                    text=chunk_translations[j]
                )
                translated_entries.append(translated_entry)

    # Format output
    srt_formatter = SRTParser()
    translated_srt = srt_formatter.format_output(translated_entries)
    print(f"   ✅ Assembled {len(translated_srt)} characters")
    print()

    # Save output
    if output_path is None:
        base_name = os.path.splitext(srt_file_path)[0]
        output_path = f"{base_name}_local_test.srt"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(translated_srt)

    print(f"💾 Saved to: {output_path}")
    print()

    # Show preview
    print("📝 Preview (first 10 entries):")
    print("=" * 70)
    lines = translated_srt.split('\n')
    preview_lines = []
    entry_count = 0
    for line in lines:
        preview_lines.append(line)
        if line.strip() == '' and entry_count < 10:
            entry_count += 1
        if entry_count >= 10:
            break

    print('\n'.join(preview_lines))
    print("=" * 70)
    print()
    print("✅ Test complete!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_local.py <srt_file_path> [output_path]")
        print("\nExample:")
        print('  python test_local.py "captions_reunion copy.srt"')
        print('  python test_local.py "captions_reunion copy.srt" "output_test.srt"')
        sys.exit(1)

    srt_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    test_local_translation(srt_file, output_file)
