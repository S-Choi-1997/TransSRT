"""
Test script for TransSRT Cloud Function endpoint
Sends a local SRT file to the deployed endpoint and saves the translated result.
"""

import requests
import sys
import os

def test_translate_endpoint(srt_file_path, output_path=None):
    """
    Test the translation endpoint with a local SRT file.

    Args:
        srt_file_path: Path to the Korean SRT file
        output_path: Optional output path for translated file
    """
    # Cloud Function endpoint
    endpoint = "https://asia-northeast3-apsconsulting.cloudfunctions.net/translate-srt"

    # Read the SRT file
    if not os.path.exists(srt_file_path):
        print(f"Error: File not found: {srt_file_path}")
        return

    with open(srt_file_path, 'r', encoding='utf-8') as f:
        srt_content = f.read()

    print(f"📤 Sending file to endpoint: {srt_file_path}")
    print(f"📊 File size: {len(srt_content)} characters")
    print(f"🌐 Endpoint: {endpoint}")
    print("⏳ Translating...")

    # Send POST request
    try:
        response = requests.post(
            endpoint,
            json={'srt_content': srt_content},
            headers={'Content-Type': 'application/json'},
            timeout=600  # 10 minutes timeout
        )

        # Check response
        if response.status_code == 200:
            result = response.json()
            translated_content = result.get('translated_srt', '')

            print(f"✅ Translation successful!")
            print(f"📊 Translated size: {len(translated_content)} characters")

            # Save to file
            if output_path is None:
                base_name = os.path.splitext(srt_file_path)[0]
                output_path = f"{base_name}_translated.srt"

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(translated_content)

            print(f"💾 Saved to: {output_path}")

            # Show preview (first 500 chars)
            print("\n📝 Preview of translation:")
            print("=" * 60)
            print(translated_content[:500])
            print("=" * 60)

        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")

    except requests.exceptions.Timeout:
        print("❌ Request timed out (>10 minutes)")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_endpoint.py <srt_file_path> [output_path]")
        print("\nExample:")
        print('  python test_endpoint.py "captions_reunion copy.srt"')
        print('  python test_endpoint.py "captions_reunion copy.srt" "output_en.srt"')
        sys.exit(1)

    srt_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    test_translate_endpoint(srt_file, output_file)
