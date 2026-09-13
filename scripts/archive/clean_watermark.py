from PIL import Image

def clean_watermark(input_path, output_path):
    im = Image.open(input_path)
    w, h = im.size
    print(f"Original size: {w}x{h}")
    # Pollinations watermark is in the bottom right corner (last ~32px)
    # We crop the bottom 36px and resize back or keep aspect ratio
    cropped = im.crop((0, 0, w, h - 36))
    # Resize to exact 1200x675
    final_im = cropped.resize((1200, 675), Image.Resampling.LANCZOS)
    final_im.save(output_path, "JPEG", quality=95)
    print(f"Cleaned image saved to {output_path} with size {final_im.size}")

if __name__ == "__main__":
    clean_watermark("/tmp/test_pollinations.jpg", "/tmp/test_cleaned.jpg")
