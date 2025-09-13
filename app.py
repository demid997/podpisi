from flask import Flask, render_template, request, send_file, jsonify
import os
from werkzeug.utils import secure_filename
import PyPDF2
from PIL import Image
import io
from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import base64

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'xlsx', 'jpg', 'jpeg', 'png'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def upload():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return render_template('sign.html', filename=filename)
    return "Неподдерживаемый формат"

@app.route('/sign', methods=['POST'])
def apply_signature():
    data = request.json
    filename = data['filename']
    signature_base64 = data['signature']  # data:image/png;base64,...
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    ext = filename.rsplit('.', 1)[1].lower()

    if ext == 'pdf':
        output_path = apply_signature_to_pdf(filepath, signature_base64)
    elif ext in ['docx']:
        output_path = apply_signature_to_docx(filepath, signature_base64)
    elif ext in ['jpg', 'jpeg', 'png']:
        output_path = apply_signature_to_image(filepath, signature_base64)
    else:
        return jsonify({"error": "Формат не поддерживается"}), 400

    return jsonify({"download_url": f"/download/{os.path.basename(output_path)}"})

def apply_signature_to_pdf(pdf_path, signature_base64):
    # Читаем PDF
    reader = PyPDF2.PdfReader(pdf_path)
    writer = PyPDF2.PdfWriter()
    
    # Создаем новый PDF с подписью
    img_data = base64.b64decode(signature_base64.split(',')[1])
    img = Image.open(io.BytesIO(img_data))
    img_width, img_height = img.size
    scale = 0.1  # масштаб подписи
    
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    width, height = letter
    x = 100
    y = 100
    can.drawImage(
        io.BytesIO(img_data),
        x,
        height - y - img_height * scale,
        width=img_width * scale,
        height=img_height * scale,
        preserveAspectRatio=True
    )
    can.save()
    
    packet.seek(0)
    new_pdf = PyPDF2.PdfReader(packet)
    
    # Добавляем подпись на первую страницу
    page = reader.pages[0]
    page.merge_page(new_pdf.pages[0])
    writer.add_page(page)
    
    for i in range(1, len(reader.pages)):
        writer.add_page(reader.pages[i])
    
    output_path = pdf_path.replace('.pdf', '_signed.pdf')
    with open(output_path, 'wb') as f:
        writer.write(f)
    return output_path

def apply_signature_to_docx(docx_path, signature_base64):
    doc = Document(docx_path)
    img_data = base64.b64decode(signature_base64.split(',')[1])
    img_io = io.BytesIO(img_data)
    
    # Добавляем подпись в конец документа
    doc.add_picture(img_io, width=2000000)  # ~7cm
    output_path = docx_path.replace('.docx', '_signed.docx')
    doc.save(output_path)
    return output_path

def apply_signature_to_image(img_path, signature_base64):
    img = Image.open(img_path)
    sig_img = Image.open(io.BytesIO(base64.b64decode(signature_base64.split(',')[1])))
    
    # Размещаем подпись в правом нижнем углу
    img.paste(sig_img, (img.width - sig_img.width - 20, img.height - sig_img.height - 20), sig_img)
    
    output_path = img_path.replace('.' + img_path.rsplit('.', 1)[1], '_signed.' + img_path.rsplit('.', 1)[1])
    img.save(output_path)
    return output_path

@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
