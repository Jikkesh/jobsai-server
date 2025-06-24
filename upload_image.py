import os
from PIL import Image
from io import BytesIO

UPLOAD_DIR = "uploaded_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def slugify(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")

def upload_job_image(image, company_name: str) -> str:
    """
    Accepts a file path (Gradio NamedString), opens it as a PIL image,
    compresses & resizes, and saves it with the company name.
    """

    # If the image is a path (Gradio NamedString), load it
    if hasattr(image, "name"):  # typical for Gradio file inputs
        image = Image.open(image.name)
    elif isinstance(image, str):
        image = Image.open(image)
    else:
        raise TypeError("Unsupported image input type")

    filename = f"{slugify(company_name)}.jpg"
    file_path = os.path.join(UPLOAD_DIR, filename)

    if os.path.exists(file_path):
        return filename
    card_size = (400, 250)
    image = image.convert("RGB")
    image = image.resize(card_size, Image.Resampling.LANCZOS)
    image.save(file_path, format="JPEG", quality=75, optimize=True)

    return filename

