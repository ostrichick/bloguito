import os
import requests
from config import GEMINI_API_KEY

def test_image_generation():
    print("1. Testing Google Imagen 3 API...")
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        result = client.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt='A joyful elderly Korean audience enjoying a colorful modern trot concert with bright stage lights, warm atmosphere, high quality photography',
            config=dict(
                number_of_images=1,
                aspect_ratio="16:9",
            )
        )
        for i, generated_image in enumerate(result.generated_images):
            with open("/tmp/test_imagen.png", "wb") as f:
                f.write(generated_image.image.image_bytes)
            print("Google Imagen 3 image saved to /tmp/test_imagen.png (Size:", os.path.getsize("/tmp/test_imagen.png"), "bytes)")
            return "imagen"
    except Exception as e:
        print("Imagen 3 failed or not enabled on this key:", e)

    print("\n2. Testing Pollinations AI (High quality free fallback)...")
    try:
        prompt = "joyful Korean middle-aged people enjoying a vibrant trot concert, stage lighting, warm photography, 8k"
        url = f"https://image.pollinations.ai/prompt/{prompt}?width=1200&height=675&nologo=true"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            with open("/tmp/test_pollinations.jpg", "wb") as f:
                f.write(resp.content)
            print("Pollinations AI image saved to /tmp/test_pollinations.jpg (Size:", os.path.getsize("/tmp/test_pollinations.jpg"), "bytes)")
            return "pollinations"
    except Exception as e:
        print("Pollinations failed:", e)

    return "none"

if __name__ == "__main__":
    test_image_generation()
