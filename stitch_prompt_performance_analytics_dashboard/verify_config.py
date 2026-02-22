import os
import sys
from dotenv import load_dotenv
import anthropic

def verify():
    print("--- Configuration Verification ---")
    
    # Try loading from the expected project root
    root = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(root, ".env")
    print(f"Looking for .env at: {env_path}")
    
    if not os.path.exists(env_path):
        print("ERROR: .env file not found!")
        return
    
    load_dotenv(env_path)
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL")
    
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in environment!")
        return
    
    print(f"API Key loaded (length {len(api_key)})")
    print(f"Model: {model}")
    
    print("\nAttempting minimal Anthropic request...")
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hello"}]
        )
        print("SUCCESS! Claude responded:")
        print(f"'{response.content[0].text}'")
    except Exception as e:
        print(f"FAILED: {str(e)}")

if __name__ == "__main__":
    verify()
