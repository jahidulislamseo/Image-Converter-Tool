import os
import io
import base64
import json
from flask import Flask, request, send_file, jsonify, send_from_directory
from PIL import Image, ImageOps, ImageDraw, ImageFont
import zipfile
from openai import OpenAI

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# OpenAI client setup
openai_api_key = os.environ.get("OPENAI_API_KEY")
if openai_api_key:
    try:
        openai_client = OpenAI(api_key=openai_api_key)
        openai_available = True
    except:
        openai_client = None
        openai_available = False
else:
    openai_client = None
    openai_available = False

ALLOWED = {
    "PNG":  ("PNG",  "png",  "image/png"),
    "JPEG": ("JPEG", "jpg",  "image/jpeg"),
    "WEBP": ("WEBP", "webp", "image/webp"),
    "GIF":  ("GIF",  "gif",  "image/gif"),
    "BMP":  ("BMP",  "bmp",  "image/bmp"),
    "TIFF": ("TIFF", "tiff", "image/tiff"),
}

# Serve the index.html file from the 'public' directory at the root URL
@app.route('/')
def index():
    return send_from_directory(os.path.join(app.root_path, 'public'), 'index.html')

def build_save_params(fmt, quality):
    q = max(1, min(int(quality or 85), 100))
    if fmt in ("JPEG", "WEBP"):
        return {"quality": q}
    elif fmt == "PNG":
        comp = max(0, min(9, 9 - int(q / 11.12)))
        return {"optimize": True, "compress_level": comp}
    return {}

def apply_transformations(img, transformations):
    """Apply rotation, flip, and other transformations"""
    if transformations.get('rotate'):
        angle = int(transformations['rotate'])
        if angle in [90, 180, 270]:
            img = img.rotate(-angle, expand=True)
    
    if transformations.get('flip_horizontal'):
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    
    if transformations.get('flip_vertical'):
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    
    return img

def add_watermark(img, watermark_text, position='bottom-right', opacity=128):
    """Add text watermark to image"""
    if not watermark_text:
        return img
    
    # Create a transparent overlay
    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Try to use a nice font, fallback to default
    try:
        font_size = max(20, min(img.width, img.height) // 30)
        font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Get text size
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Calculate position
    margin = 20
    if position == 'bottom-right':
        x = img.width - text_width - margin
        y = img.height - text_height - margin
    elif position == 'bottom-left':
        x = margin
        y = img.height - text_height - margin
    elif position == 'top-right':
        x = img.width - text_width - margin
        y = margin
    elif position == 'top-left':
        x = margin
        y = margin
    else:  # center
        x = (img.width - text_width) // 2
        y = (img.height - text_height) // 2
    
    # Draw text with opacity
    draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, opacity))
    
    # Combine with original image
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    return Image.alpha_composite(img, overlay)

@app.route('/api/analyze-image', methods=['POST'])
def analyze_image():
    """AI-powered image analysis using OpenAI"""
    if not openai_available:
        return jsonify({"error": "AI analysis not available. Please configure OpenAI API key."}), 503
    
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["file"]
    try:
        # Convert image to base64
        img = Image.open(file.stream)
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        # Analyze with OpenAI Vision  
        # the newest OpenAI model is "gpt-4o" for vision tasks
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this image and provide: 1) Description of main subjects, 2) Color analysis, 3) Suggested improvements, 4) Best format recommendations. Respond in JSON format."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        content = response.choices[0].message.content
        try:
            analysis = json.loads(content)
        except:
            # If not valid JSON, return as text
            analysis = content
        
        return jsonify({"success": True, "analysis": analysis})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/convert", methods=["POST"])
def convert():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    files = request.files.getlist("file")
    target = (request.form.get("format") or "PNG").upper()
    if target not in ALLOWED:
        return jsonify({"error": "Unsupported format"}), 400

    mode = (request.form.get("mode") or "none").lower()
    quality = request.form.get("quality", "85")
    
    # New transformation options
    transformations = {
        'rotate': request.form.get('rotate', '0'),
        'flip_horizontal': request.form.get('flip_horizontal') == 'true',
        'flip_vertical': request.form.get('flip_vertical') == 'true'
    }
    
    # Watermark options
    watermark_text = request.form.get('watermark_text', '')
    watermark_position = request.form.get('watermark_position', 'bottom-right')
    watermark_opacity = int(request.form.get('watermark_opacity', '128'))
    
    # Aspect ratio preservation
    preserve_aspect = request.form.get('preserve_aspect') == 'true'

    try:
        output_files = []
        for file in files:
            img = Image.open(file.stream)
            img = ImageOps.exif_transpose(img)
            
            # Apply transformations (rotate, flip)
            img = apply_transformations(img, transformations)

            # Handle resizing with aspect ratio preservation
            if mode == "percent":
                percent = float(request.form.get("percent") or "100")
                if percent != 100:
                    w = max(1, int(img.width * percent / 100))
                    h = max(1, int(img.height * percent / 100))
                    img = img.resize((w, h), Image.Resampling.LANCZOS)
            elif mode == "exact":
                w = int(request.form.get("width") or 0)
                h = int(request.form.get("height") or 0)
                if w > 0 and h > 0:
                    if preserve_aspect:
                        # Calculate the aspect ratio preserving dimensions
                        img_ratio = img.width / img.height
                        target_ratio = w / h
                        
                        if img_ratio > target_ratio:
                            # Image is wider, fit to width
                            new_w = w
                            new_h = int(w / img_ratio)
                        else:
                            # Image is taller, fit to height
                            new_h = h
                            new_w = int(h * img_ratio)
                        
                        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    else:
                        img = img.resize((w, h), Image.Resampling.LANCZOS)
            
            # Add watermark if specified
            if watermark_text:
                img = add_watermark(img, watermark_text, watermark_position, watermark_opacity)

            fmt, ext, mime = ALLOWED[target]

            if fmt in ("JPEG", "BMP", "TIFF") and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            save_params = build_save_params(fmt, quality)
            buf = io.BytesIO()
            img.save(buf, fmt, **save_params)
            buf.seek(0)

            filename = (file.filename or f"image.{ext}").rsplit(".", 1)[0] + f".{ext}"
            output_files.append((filename, buf))

        # Single file download or ZIP based on count
        if len(output_files) == 1:
            filename, buf = output_files[0]
            buf.seek(0)
            fmt, ext, mime = ALLOWED[target]
            return send_file(buf, as_attachment=True, download_name=filename, mimetype=mime)
        else:
            # Multiple files - create ZIP
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filename, buf in output_files:
                    zipf.writestr(filename, buf.read())
            zip_buffer.seek(0)
            return send_file(zip_buffer, as_attachment=True, download_name="images.zip")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/preview', methods=['POST'])
def preview_image():
    """Generate preview of image with applied transformations"""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    
    # Get transformation parameters
    transformations = {
        'rotate': request.form.get('rotate', '0'),
        'flip_horizontal': request.form.get('flip_horizontal') == 'true',
        'flip_vertical': request.form.get('flip_vertical') == 'true'
    }
    
    watermark_text = request.form.get('watermark_text', '')
    watermark_position = request.form.get('watermark_position', 'bottom-right')
    watermark_opacity = int(request.form.get('watermark_opacity', '128'))
    
    try:
        img = Image.open(file.stream)
        img = ImageOps.exif_transpose(img)
        
        # Apply transformations
        img = apply_transformations(img, transformations)
        
        # Add watermark if specified
        if watermark_text:
            img = add_watermark(img, watermark_text, watermark_position, watermark_opacity)
        
        # Create thumbnail for preview (max 400px)
        img.thumbnail((400, 400), Image.Resampling.LANCZOS)
        
        # Convert to base64 for preview
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode()
        
        return jsonify({
            "success": True, 
            "preview": f"data:image/png;base64,{img_base64}",
            "dimensions": {"width": img.width, "height": img.height}
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)