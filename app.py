from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate  # Import Migrate
import os
from werkzeug.utils import secure_filename

# Initialize Flask app and SocketIO
app = Flask(__name__)
CORS(app)  # Enable CORS for all domains
socketio = SocketIO(app, cors_allowed_origins=["http://127.0.0.1:5000", "http://localhost:5000"])

# Configure the app for SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav'}
db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Initialize Migrate with Flask app and SQLAlchemy db

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Database models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(120), nullable=False)
    receiver = db.Column(db.String(120), nullable=False)
    message = db.Column(db.String(500), nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class BlockedUser(db.Model):
    blocker = db.Column(db.String(120), nullable=False)
    blocked = db.Column(db.String(120), nullable=False, primary_key=True)

# Initialize the database
with app.app_context():
    db.create_all()

# Function to check if user is blocked
def is_blocked(sender, receiver):
    print(f"Checking if {sender} is blocked by {receiver}")
    blocked_user = BlockedUser.query.filter_by(blocker=sender, blocked=receiver).first()
    if blocked_user:
        print(f"User {receiver} has blocked {sender}")
    else:
        print(f"User {receiver} has not blocked {sender}")
    return blocked_user is not None

# User blocking/unblocking routes
@app.route('/block', methods=['POST'])
def block_user():
    blocker = request.form['blocker']
    blocked = request.form['blocked']
    print(f"Blocking user: {blocker} -> {blocked}")
    new_block = BlockedUser(blocker=blocker, blocked=blocked)
    db.session.add(new_block)
    db.session.commit()
    print(f"User {blocker} successfully blocked {blocked}")
    return jsonify({"message": "User blocked successfully"}), 200

@app.route('/unblock', methods=['POST'])
def unblock_user():
    blocker = request.form['blocker']
    blocked = request.form['blocked']
    print(f"Unblocking user: {blocker} -> {blocked}")
    BlockedUser.query.filter_by(blocker=blocker, blocked=blocked).delete()
    db.session.commit()
    print(f"User {blocker} successfully unblocked {blocked}")
    return jsonify({"message": "User unblocked successfully"}), 200

# WebSocket event for sending message
@socketio.on('message')
def handle_message(data):
    print(f"Received message: {data}")
    
    # Safely get values from the data dictionary
    sender = data.get('sender')
    receiver = data.get('receiver')
    message = data.get('message')
    file_path = data.get('file_path', '')

    # Ensure that both sender and receiver are provided
    if not sender or not receiver:
        print("Sender or receiver is missing in the message data")
        return  # Optionally, you could send an error response back to the frontend

    # Check if the user is blocked
    if is_blocked(receiver, sender):
        print(f"Message from {sender} to {receiver} is blocked. Message not sent.")
        return  # Don't send message if blocked

    # Store message in DB
    new_message = Message(sender=sender, receiver=receiver, message=message, file_path=file_path)
    db.session.add(new_message)
    db.session.commit()
    print(f"Message from {sender} to {receiver} stored in database")

    # Broadcast message to receiver
    emit('new_message', data, room=receiver)
    print(f"Message broadcasted to {receiver}")

# WebSocket event for connecting user
@socketio.on('connect')
def handle_connect():
    print('User connected')

# WebSocket event for disconnecting user
@socketio.on('disconnect')
def handle_disconnect():
    print('User disconnected')

# Handle file upload route
@app.route('/upload', methods=['POST'])
def upload_file():
    print("File upload request received")
    if 'file' not in request.files:
        print("No file part in the request")
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        print("No selected file")
        return 'No selected file', 400
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    print(f"File saved to {file_path}")
    return jsonify({'file_path': file_path})

# Serve the chat page (frontend)
@app.route('/')
def chat():
    print("Rendering chat page")
    return render_template('chat.html')

@app.after_request
def after_request(response):
    print("Adding headers for CORS")
    response.headers.add('Access-Control-Allow-Origin', '*')  # Allow all origins
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')  # Allow headers for JSON data
    return response

# Flask Migrate
if __name__ == '__main__':
    print("Starting the Flask app with SocketIO")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
