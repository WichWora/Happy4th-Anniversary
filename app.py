from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3
import os
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
def init_db():
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    
    # Create clothes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS clothes (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            category TEXT NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create cart table
    c.execute('''
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clothes_id TEXT,
            FOREIGN KEY (clothes_id) REFERENCES clothes (id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload')
def upload_page():
    return render_template('upload.html')

@app.route('/outfit')
def outfit_page():
    return render_template('outfit.html')

# API: Get all clothes
@app.route('/api/clothes', methods=['GET'])
def get_clothes():
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM clothes ORDER BY created_at DESC')
    clothes = [{
        'id': row[0],
        'filename': row[1],
        'image_url': f"/static/uploads/{row[1]}",
        'category': row[2],
        'name': row[3] or row[2]
    } for row in c.fetchall()]
    
    conn.close()
    return jsonify(clothes)

# API: Add new clothes
@app.route('/api/clothes', methods=['POST'])
def add_clothes():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file'}), 400
    
    file = request.files['image']
    category = request.form.get('category', 'tops')
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # Save file
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # Save to database
        conn = sqlite3.connect('wardrobe.db')
        c = conn.cursor()
        
        item_id = str(uuid.uuid4())
        c.execute('INSERT INTO clothes (id, filename, category) VALUES (?, ?, ?)',
                 (item_id, unique_filename, category))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'item': {
                'id': item_id,
                'image_url': f"/static/uploads/{unique_filename}",
                'category': category,
                'name': category
            }
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

# API: Get cart items
@app.route('/api/cart', methods=['GET'])
def get_cart():
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT clothes.* FROM cart
        JOIN clothes ON cart.clothes_id = clothes.id
        ORDER BY cart.id DESC
    ''')
    
    cart_items = [{
        'id': row[0],
        'filename': row[1],
        'image_url': f"/static/uploads/{row[1]}",
        'category': row[2],
        'name': row[3] or row[2]
    } for row in c.fetchall()]
    
    conn.close()
    return jsonify(cart_items)

# API: Add to cart
@app.route('/api/cart', methods=['POST'])
def add_to_cart():
    data = request.json
    clothes_id = data.get('id')
    
    if not clothes_id:
        return jsonify({'error': 'No item ID'}), 400
    
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    
    # Check if item exists
    c.execute('SELECT id FROM clothes WHERE id = ?', (clothes_id,))
    if not c.fetchone():
        conn.close()
        return jsonify({'error': 'Item not found'}), 404
    
    # Remove existing item of same category
    c.execute('''
        DELETE FROM cart 
        WHERE clothes_id IN (
            SELECT id FROM clothes 
            WHERE category = (SELECT category FROM clothes WHERE id = ?)
        )
    ''', (clothes_id,))
    
    # Add to cart
    c.execute('INSERT INTO cart (clothes_id) VALUES (?)', (clothes_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# API: Remove from cart
@app.route('/api/cart/<item_id>', methods=['DELETE'])
def remove_from_cart(item_id):
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    
    c.execute('DELETE FROM cart WHERE clothes_id = ?', (item_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# API: Clear cart
@app.route('/api/cart', methods=['DELETE'])
def clear_cart():
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    
    c.execute('DELETE FROM cart')
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# API: Delete clothes
@app.route('/api/clothes/<item_id>', methods=['DELETE'])
def delete_clothes(item_id):
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    
    # Get filename
    c.execute('SELECT filename FROM clothes WHERE id = ?', (item_id,))
    row = c.fetchone()
    
    if row:
        filename = row[0]
        
        # Delete from cart first
        c.execute('DELETE FROM cart WHERE clothes_id = ?', (item_id,))
        
        # Delete from clothes
        c.execute('DELETE FROM clothes WHERE id = ?', (item_id,))
        
        # Delete file
        try:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass  # Ignore file deletion errors
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, port=5000)