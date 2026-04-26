import app
import io
client = app.app.test_client()

print("Testing Index:", client.get('/').status_code)
print("Testing Reports:", client.get('/reports').status_code)

# Test upload with dummy image
try:
    with open('test.jpg', 'wb') as f:
        f.write(b'\xFF\xD8\xFF\xE0\x00\x10\x4A\x46\x49\x46\x00\x01\x01\x01\x00\x60\x00\x60\x00\x00\xFF\xDB\x00\x43\x00\xFF\xD9')  # minimal valid jpeg
    
    data = {
        'name': 'Test Patient',
        'age': '30',
        'chromosome': '46',
        'image': (open('test.jpg', 'rb'), 'test.jpg')
    }
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    print("Testing Upload:", resp.status_code)
    
except Exception as e:
    import traceback
    traceback.print_exc()

# Let's also check generate_pdf explicitly
try:
    print("Testing PDF Generation...")
    pdf_filename = app.generate_pdf('John Doe', "30", 46, 46, 'Normal', 'No genetic abnormality detected', 'Reliable detection.', 'test.jpg')
    print("PDF Generated:", pdf_filename)
except Exception as e:
    import traceback
    traceback.print_exc()
