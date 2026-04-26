from flask import Flask, render_template, request, redirect, url_for, flash
import os
import cv2
import uuid
import numpy as np
from werkzeug.utils import secure_filename
from config import get_db_connection
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "karyovision_secret_key_123"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = ""

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
    u = cursor.fetchone()
    cursor.close()
    conn.close()
    if u:
        return User(id=u[0], username=u[1], email=u[2])
    return None

# Upload folder setup
UPLOAD_FOLDER = 'static/uploads'
REPORTS_FOLDER = 'static/reports'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed image types
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_valid_karyotype(image_path):
    """
    Very strict validation to ensure the image is a genuine karyotype image.
    Uses histogram bimodal properties, extreme color variance rejection, and robust contour logic.
    """
    img_color = cv2.imread(image_path)
    if img_color is None:
        return False
        
    # 1. Color Standard Deviation Check (Reject colorful images immediately)
    # A genuine karyotype is almost purely grayscale.
    color_std = np.std(img_color, axis=2)
    if np.mean(color_std) > 20: 
        return False

    img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
    h, w = img_gray.shape
    
    # 2. Bimodal Histogram / Background Dominance Check
    # Otsu's threshold calculates the optimal separation.
    thresh_val, thresh_img = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # In a karyotype, the light background is dominant (thresh_img == 255)
    white_ratio = np.sum(thresh_img == 255) / (h * w)
    
    # The background should take up at least 65% of the image.
    if not (0.65 < white_ratio < 0.99):
        return False
        
    # 3. Median Intensity Check
    # The background must be light, so the Otsu separator must be high enough.
    if thresh_val < 100:
        return False 

    # 4. Contour Check (Chromosomes must be distinct, dark objects on the light background)
    mask = cv2.bitwise_not(thresh_img)
    
    # Clean up small noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    valid_contours = []
    min_area = (h * w) * 0.0005 # 0.05% of image
    max_area = (h * w) * 0.05   # 5% of image
    
    areas = []
    for c in contours:
        area = cv2.contourArea(c)
        if min_area < area < max_area:
            x, y, w_box, h_box = cv2.boundingRect(c)
            
            # Karyotype blobs are relatively solid but not perfect squares.
            rect_area = w_box * h_box
            extent = area / rect_area if rect_area > 0 else 0
            
            if extent > 0.15: # drop completely scattered pixel clusters
                valid_contours.append(c)
                areas.append(area)
                
    # 5. Strict Object Count (20-80 valid distinct chromosome-like blobs)
    if not (20 <= len(valid_contours) <= 80):
        return False
        
    # 6. Uniform Size Standard Deviation
    if len(areas) > 0:
        mean_area = np.mean(areas)
        std_area = np.std(areas)
        # Rejects if standard deviation is wildly disproportionate
        if std_area > mean_area * 1.5:
            return False

    return True

def analyze_chromosomes(user_count):
    primary_count = user_count
    
    if primary_count == 46:
        result = "Normal"
        diagnosis = "No genetic abnormality detected"
    elif primary_count == 47:
        result = "Abnormal"
        diagnosis = "Down Syndrome (Trisomy 21) or other Trisomy"
    elif primary_count == 45:
        result = "Abnormal"
        diagnosis = "Turner Syndrome or Monosomy"
    elif primary_count > 47:
        result = "Abnormal"
        diagnosis = "Complex chromosomal abnormality detected"
    else:
        result = "Abnormal"
        diagnosis = "Severe chromosomal loss or artifact"
        
    confidence = "Clinical diagnosis based strictly on provided chromosome count."
        
    return result, diagnosis, confidence

def generate_pdf(patient_name, age, user_count, result, diagnosis, confidence, image_filename):
    pdf_filename = f"report_{uuid.uuid4().hex[:8]}.pdf"
    pdf_path = os.path.join(REPORTS_FOLDER, pdf_filename)
    
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    
    # Colors
    white_bg = (1.0, 1.0, 1.0)
    purple_primary = (0.427, 0.157, 0.851)
    navy_text = (0.043, 0.082, 0.263)
    gray_text = (0.4, 0.45, 0.6)
    dark_gray = (0.2, 0.2, 0.2)
    border_color = (0.85, 0.85, 0.9)
    green_status = (0.133, 0.773, 0.369)
    red_status = (0.937, 0.267, 0.267)
    
    # Background
    c.setFillColorRGB(*white_bg)
    c.rect(0, 0, width, height, fill=True, stroke=False)
    
    # Top Purple Bar
    c.setFillColorRGB(*purple_primary)
    c.rect(0, height - 15, width, 15, fill=True, stroke=False)
    
    # Logo square
    c.rect(40, height - 70, 20, 20, fill=True, stroke=False)
    
    # Main Title
    c.setFont("Helvetica-Bold", 24)
    c.setFillColorRGB(*navy_text)
    c.drawString(70, height - 65, "KARYOVISION ANALYTICS")
    
    c.setFont("Helvetica", 11)
    c.setFillColorRGB(*gray_text)
    c.drawString(70, height - 85, "ADVANCED CHROMOSOMAL SCREENING REPORT")
    
    # Date/Time/ID
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    report_id_str = f"#{pdf_filename.split('_')[1][:6].upper()}"
    
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 40, height - 50, f"Date: {current_date}")
    c.drawRightString(width - 40, height - 65, f"Time: {current_time}")
    c.drawRightString(width - 40, height - 80, f"Report ID: {report_id_str}")
    
    # --- PATIENT INFORMATION ---
    y_pos = height - 160
    
    c.setFillColorRGB(0.98, 0.98, 0.99)
    c.setStrokeColorRGB(*border_color)
    c.setLineWidth(1)
    c.roundRect(40, y_pos - 60, width - 80, 80, 8, fill=True, stroke=True)
    
    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(*purple_primary)
    c.drawString(55, y_pos - 10, "PATIENT INFORMATION")
    
    c.setFont("Helvetica", 11)
    c.setFillColorRGB(*dark_gray)
    c.drawString(55, y_pos - 40, "Name:")
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(100, y_pos - 40, f"{patient_name}")
    
    c.setFont("Helvetica", 11)
    c.drawString(width/2 + 50, y_pos - 40, "Age:")
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(width/2 + 90, y_pos - 40, f"{age} Years")
    
    # --- ANALYSIS RESULTS & IMAGE ---
    y_pos -= 110
    
    # Left Column: ANALYSIS RESULTS
    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(*navy_text)
    c.drawString(40, y_pos, "ANALYSIS RESULTS")
    
    c.setStrokeColorRGB(*border_color)
    c.setLineWidth(1.5)
    c.line(40, y_pos - 10, width/2 - 20, y_pos - 10)
    
    c.setFont("Helvetica", 11)
    c.setFillColorRGB(*gray_text)
    c.drawString(40, y_pos - 40, "Assessed Chromosomes:")
    
    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(*dark_gray)
    c.drawRightString(width/2 - 20, y_pos - 40, str(user_count))
    
    c.setStrokeColorRGB(0.9, 0.9, 0.95)
    c.setLineWidth(1)
    c.line(40, y_pos - 55, width/2 - 20, y_pos - 55)
    
    c.setFont("Helvetica", 11)
    c.setFillColorRGB(*gray_text)
    c.drawString(40, y_pos - 80, "Clinical Status:")
    
    c.setFont("Helvetica-Bold", 13)
    if result == "Normal":
        c.setFillColorRGB(*green_status)
        status_text = "NORMAL"
    else:
        c.setFillColorRGB(*red_status)
        status_text = "ABNORMAL"
    c.drawRightString(width/2 - 20, y_pos - 80, status_text)
    
    c.setStrokeColorRGB(0.9, 0.9, 0.95)
    c.setLineWidth(1)
    c.line(40, y_pos - 95, width/2 - 20, y_pos - 95)
    
    # Right Column: IMAGE
    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(*purple_primary)
    c.drawString(width/2 + 20, y_pos, "PROCESSED KARYOTYPE SCAN")
    
    img_box_y = y_pos - 150
    img_box_height = 130
    c.setFillColorRGB(*white_bg)
    c.setStrokeColorRGB(*border_color)
    c.setLineWidth(1)
    c.roundRect(width/2 + 20, img_box_y, width/2 - 60, img_box_height, 8, fill=True, stroke=True)
    
    img_filepath = os.path.join(UPLOAD_FOLDER, image_filename)
    if os.path.exists(img_filepath):
        img = cv2.imread(img_filepath)
        if img is not None:
            ih, iw = img.shape[:2]
            aspect = iw / ih
            max_w = width/2 - 80
            max_h = 110
            
            render_w = min(max_w, max_h * aspect)
            render_h = min(max_h, render_w / aspect)
            
            x_offset = width/2 + 20 + ((width/2 - 60) - render_w) / 2
            y_offset = img_box_y + (img_box_height - render_h) / 2
            
            c.drawImage(img_filepath, x_offset, y_offset, width=render_w, height=render_h, preserveAspectRatio=True)
            
    # --- DISEASE INFORMATION ---
    y_pos -= 200
    
    disease_title = "Unknown Condition"
    disease_description = ""
    disease_color = (0.949, 0.576, 0.204) # Orange
    
    if user_count == 46:
        disease_title = "NORMAL KARYOTYPE"
        disease_description = "46 chromosomes detected. No chromosomal abnormalities identified. Genetic profile is typical and healthy with normal development expected."
        disease_color = green_status
    elif user_count == 47:
        disease_title = "DOWN SYNDROME (TRISOMY 21)"
        disease_description = "47 chromosomes detected with an extra copy of chromosome 21. Characterized by intellectual disability, distinctive facial features, and potential cardiac/gastrointestinal complications."
        disease_color = red_status
    elif user_count == 45:
        disease_title = "TURNER SYNDROME (MONOSOMY)"
        disease_description = "45 chromosomes detected - absence of one X chromosome. Primarily affects females; features include short stature, ovarian dysgenesis, and potential cardiac/renal anomalies."
        disease_color = red_status
    elif user_count > 47:
        disease_title = "COMPLEX CHROMOSOMAL ABNORMALITY"
        disease_description = f"Multiple chromosomal aberrations identified ({user_count} chromosomes). Genetic counseling recommended for comprehensive prognosis and personalized management plan."
    else:
        disease_title = "CHROMOSOMAL LOSS DETECTED"
        disease_description = f"Severe chromosomal loss detected ({user_count} chromosomes). Additional confirmatory testing recommended to establish accurate diagnosis."
        disease_color = red_status
        
    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(*navy_text)
    c.drawString(40, y_pos, "CLINICAL DIAGNOSIS")
    
    c.setStrokeColorRGB(*border_color)
    c.setLineWidth(1.5)
    c.line(40, y_pos - 10, width - 40, y_pos - 10)
    
    c.setFillColorRGB(*white_bg)
    c.setStrokeColorRGB(disease_color[0], disease_color[1], disease_color[2])
    c.setLineWidth(2)
    c.roundRect(40, y_pos - 100, width - 80, 80, 8, fill=True, stroke=True)
    
    # Left vertical colored bar for disease info
    c.setFillColorRGB(disease_color[0], disease_color[1], disease_color[2])
    c.rect(40, y_pos - 100, 6, 80, fill=True, stroke=False)
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y_pos - 40, disease_title)
    
    import textwrap
    wrapped_desc = textwrap.wrap(disease_description, width=95)
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(*dark_gray)
    desc_y = y_pos - 60
    for i, line in enumerate(wrapped_desc[:3]):
        c.drawString(60, desc_y, line)
        desc_y -= 14
        
    # --- FOOTER ---
    c.setFillColorRGB(0.96, 0.96, 0.97)
    c.rect(0, 0, width, 50, fill=True, stroke=False)
    
    c.setStrokeColorRGB(*border_color)
    c.setLineWidth(1)
    c.line(0, 50, width, 50)
    
    c.setFont("Helvetica-Bold", 8)
    c.setFillColorRGB(*navy_text)
    c.drawString(40, 25, "KARYOVISION ANALYTICS")
    
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(*gray_text)
    c.drawString(40, 15, "AI-generated diagnostic assessment. Professional medical validation required.")
    
    c.save()
    return pdf_filename

# Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            flash('Email already registered', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, hashed_pw))
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, password FROM users WHERE email = %s", (email,))
        u = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if u and check_password_hash(u[3], password):
            user = User(id=u[0], username=u[1], email=u[2])
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT result FROM reports")
    all_reports = cursor.fetchall()
    
    total = len(all_reports)
    normal = sum(1 for r in all_reports if r[0] == 'Normal')
    abnormal = total - normal
    
    cursor.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 5")
    recent = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('dashboard.html', total=total, normal=normal, abnormal=abnormal, recent=recent)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        chromosome = request.form['chromosome']

        file = request.files['image']

        filename = None

        # File validation
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # --- INTELLIGENCE VALIDATION ---
            if not is_valid_karyotype(filepath):
                # Clean up the invalid file
                os.remove(filepath)
                return render_template('upload.html', error="Invalid image. Please upload a proper chromosome (karyotype) image.")
                
        else:
            return render_template('upload.html', error="Invalid file type. Please upload a valid image (png, jpg, jpeg).")

        # Analysis logic
        try:
            user_chromosome_count = int(chromosome)
        except ValueError:
            user_chromosome_count = 46
            
        result_status, diagnosis, confidence = analyze_chromosomes(user_chromosome_count)

        # PDF Generation
        pdf_filename = None
        if filename:
            pdf_filename = generate_pdf(name, age, user_chromosome_count, result_status, diagnosis, confidence, filename)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Insert keeping database structure compatible
            cursor.execute("""
                INSERT INTO reports (patient_name, age, chromosome_count, result, image, pdf_report, diagnosis)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, age, user_chromosome_count, result_status, filename, pdf_filename, diagnosis))

            conn.commit()

        except Exception as e:
            print("DB Error:", e)

        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()

        return render_template('result.html',
                               count=user_chromosome_count,
                               result=result_status,
                               condition=diagnosis,
                               image_path=filename,
                               pdf_path=pdf_filename)

    return render_template('upload.html')

@app.route('/reports')
@login_required
def reports():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM reports ORDER BY id DESC")
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('reports.html', reports=data)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get the images/pdf to delete them
    cursor.execute("SELECT image, pdf_report FROM reports WHERE id=%s", (id,))
    file = cursor.fetchone()
    if file:
        if file[0]:
            try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file[0]))
            except: pass
        if file[1]:
            try: os.remove(os.path.join(REPORTS_FOLDER, file[1]))
            except: pass
    
    cursor.execute("DELETE FROM reports WHERE id=%s", (id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash('Report deleted successfully', 'success')
    return redirect(url_for('reports'))

@app.route('/delete_multiple', methods=['POST'])
@login_required
def delete_multiple():
    report_ids = request.form.getlist('report_ids')
    if not report_ids:
        return redirect(url_for('reports'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        format_strings = ','.join(['%s'] * len(report_ids))
        
        # Delete files from disk first
        cursor.execute(f"SELECT image, pdf_report FROM reports WHERE id IN ({format_strings})", tuple(report_ids))
        files = cursor.fetchall()
        for row in files:
            if row[0]:
                try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], row[0]))
                except: pass
            if row[1]:
                try: os.remove(os.path.join(REPORTS_FOLDER, row[1]))
                except: pass
        
        cursor.execute(f"DELETE FROM reports WHERE id IN ({format_strings})", tuple(report_ids))
        conn.commit()
    except Exception as e:
        print("Delete multiple error:", e)
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
            
    flash("Selected reports deleted successfully", "success")
    return redirect(url_for('reports'))

if __name__ == '__main__':
    app.run(debug=True)