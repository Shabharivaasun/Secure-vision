import cv2
import torch
from datetime import datetime, timedelta
import pyttsx3
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
from twilio.rest import Client
import joblib
import threading
import telebot
import pandas as pd
import numpy as np
import requests
import json
import geocoder


# ========== VIDEO RECORDING FOR CRASH ==========
class SimpleVideoRecorder:
    """Simple video recorder - records frames and saves to file"""
    def __init__(self):
        self.frames = []
        self.is_recording = False
        self.max_frames = 100  # 10 seconds at 10fps
    
    def start(self):
        self.frames = []
        self.is_recording = True
        print("🎥 Recording crash video...")
    
    def add_frame(self, frame):
        if self.is_recording and len(self.frames) < self.max_frames:
            self.frames.append(frame.copy())
    
    def save(self, filepath):
        self.is_recording = False
        if not self.frames:
            return False
        try:
            import cv2
            import os
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            h, w = self.frames[0].shape[:2]
            out = cv2.VideoWriter(filepath, cv2.VideoWriter_fourcc(*'mp4v'), 10, (w, h))
            for f in self.frames:
                out.write(f)
            out.release()
            print(f"✅ Video saved: {filepath}")
            self.frames = []
            return os.path.exists(filepath)
        except Exception as e:
            print(f"❌ Video error: {e}")
            return False

video_recorder = SimpleVideoRecorder()


# ========== CONFIGURATION ==========
class Config:
    # Frame Processing
    PROCESS_EVERY_N_FRAMES = 2
    REQUIRED_CRASH_FRAMES = 3  # Reduced from 5 for faster detection
    
    # Detection Thresholds
    CONFIDENCE_THRESHOLD = 0.5
    CRASH_PROBABILITY_THRESHOLD = 0.50  # Lowered from 0.60 for better detection
    SUDDEN_MOTION_THRESHOLD = 50
    OVERLAP_THRESHOLD = 0.1
    
    # Alert Settings
    ALERT_COOLDOWN_SECONDS = 5
    VIDEO_RECORDING_FRAMES = 50
    VIDEO_FPS = 10.0

    TEAM_WHATSAPP_NUMBERS = [
    'whatsapp:+917806856180',  # Member 1
    'whatsapp:+916382417620',  # Member 2  
    'whatsapp:+918825469695',  # Member 3
]
    
    # Twilio Config
    TWILIO_SID = 'ACd2e5950a2646fb3d9d6ce1da6cc668ca'
    TWILIO_AUTH_TOKEN = '64c2e1f9608a6f84e9957cfff007738e'
    TWILIO_WHATSAPP_NUMBER = 'whatsapp:+14155238886'
    RECEIVER_WHATSAPP = 'whatsapp:+917806856180'
    
    # Telegram Config
    TELEGRAM_BOT_TOKEN = '8016484611:AAEoRTdF-opT_ConzHPG-axdv4ffR5qROec'
    CHAT_ID = '-1003823247107'
    
    # Model Settings
    YOLO_MODEL = 'yolov5n'
    ML_MODEL_PATH = 'crash_prediction_model.pkl'
    INTERESTED_CLASSES = ['car', 'truck', 'motorcycle', 'bus', 'bicycle', 'person']

# ========== GLOBAL VARIABLES ==========
previous_vehicle_positions = []
ml_crash_counter = 0
frame_count = 0
crash_count = 0
last_alert_time = datetime.min
video_writer = None
current_location = None

# ========== LOCATION DETECTION ==========
def get_current_location():
    """Get current location with EXACT GPS option"""
    global current_location
    
    # ═══════════════════════════════════════
    # SET YOUR EXACT GPS COORDINATES HERE
    # ═══════════════════════════════════════
    USE_EXACT_GPS = True
    
    if USE_EXACT_GPS:
        current_location = {
            'latitude': 10.999417,
            'longitude': 77.084361,
            'city': 'Coimbatore',
            'country': 'India',
            'address': 'KIT College of Engineering, Coimbatore, Tamil Nadu, India'
        }
        print(f"✅ GPS: {current_location['address']} ({current_location['latitude']}, {current_location['longitude']})")
        return current_location
    
    try:
        g = geocoder.ip('me')
        if g.ok:
            current_location = {
                'latitude': g.latlng[0],
                'longitude': g.latlng[1],
                'city': g.city,
                'country': g.country,
                'address': g.address
            }
            print(f"✅ IP location: {current_location['city']}, {current_location['country']}")
            return current_location
        else:
            response = requests.get('https://ipapi.co/json/', timeout=5)
            if response.status_code == 200:
                data = response.json()
                current_location = {
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude'),
                    'city': data.get('city'),
                    'country': data.get('country_name'),
                    'address': f"{data.get('city')}, {data.get('region')}, {data.get('country_name')}"
                }
                print(f"✅ IP location: {current_location['city']}")
                return current_location
    except Exception as e:
        print(f"⚠️ Location error: {e}")
    
    current_location = {
        'latitude': 10.999417,
        'longitude': 77.084361,
        'city': 'Coimbatore',
        'country': 'India',
        'address': 'KIT College of Engineering, Coimbatore, Tamil Nadu, India'
    }
    return current_location


def get_location_link():
    """Generate Google Maps link for current location"""
    if current_location:
        lat = current_location['latitude']
        lon = current_location['longitude']
        return f"https://www.google.com/maps?q={lat},{lon}"
    return "https://www.google.com/maps?q=10.8275,77.0604"

def get_location_string():
    """Get formatted location string"""
    if current_location:
        return f"{current_location['address']}\n📍 GPS: {current_location['latitude']:.4f}, {current_location['longitude']:.4f}"
    return "Location: Unknown"

# ========== INITIALIZE SERVICES ==========
def initialize_services():
    """Initialize all external services with error handling"""
    services = {
        'yolo_model': None,
        'ml_model': None,
        'tts_engine': None,
        'twilio_client': None,
        'telegram_bot': None
    }
    
    try:
        print("Loading YOLOv5 model...")
        services['yolo_model'] = torch.hub.load('ultralytics/yolov5', Config.YOLO_MODEL, pretrained=True)
        print("✅ YOLOv5 loaded successfully")
    except Exception as e:
        print(f"❌ Error loading YOLOv5: {e}")
    
    try:
        if os.path.exists(Config.ML_MODEL_PATH):
            services['ml_model'] = joblib.load(Config.ML_MODEL_PATH)
            print("✅ ML model (Random Forest) loaded successfully")
        else:
            print(f"⚠️ ML model not found at {Config.ML_MODEL_PATH}")
    except Exception as e:
        print(f"❌ Error loading ML model: {e}")
    
    try:
        services['tts_engine'] = pyttsx3.init()
        services['tts_engine'].setProperty('rate', 160)
        print("✅ TTS engine initialized")
    except Exception as e:
        print(f"❌ Error initializing TTS: {e}")
    
    try:
        services['twilio_client'] = Client(Config.TWILIO_SID, Config.TWILIO_AUTH_TOKEN)
        print("✅ Twilio client initialized")
    except Exception as e:
        print(f"❌ Error initializing Twilio: {e}")
    
    try:
        services['telegram_bot'] = telebot.TeleBot(Config.TELEGRAM_BOT_TOKEN)
        print("✅ Telegram bot initialized")
    except Exception as e:
        print(f"❌ Error initializing Telegram: {e}")
    
    return services

print("\n" + "="*60)
print("🚨 SECURE VISION - AI Crash Detection System")
print("="*60)
SERVICES = initialize_services()

print("\n🌍 Detecting your location...")
get_current_location()

os.makedirs("alerts", exist_ok=True)

# ========== UTILITY FUNCTIONS ==========
def is_overlap(boxA, boxB):
    """Check if two bounding boxes overlap significantly"""
    ax1, ay1, ax2, ay2 = boxA
    bx1, by1, bx2, by2 = boxB
    
    overlap_x = max(0, min(ax2, bx2) - max(ax1, bx1))
    overlap_y = max(0, min(ay2, by2) - max(ay1, by1))
    overlap_area = overlap_x * overlap_y
    
    areaA = (ax2 - ax1) * (ay2 - ay1)
    areaB = (bx2 - bx1) * (by2 - by1)
    
    if areaA == 0 or areaB == 0:
        return False
    
    return overlap_area > Config.OVERLAP_THRESHOLD * min(areaA, areaB)

# ========== ALERT FUNCTIONS ==========
def send_video_to_telegram(video_path, caption):
    """Send video evidence to Telegram"""
    try:
        if SERVICES['telegram_bot'] and os.path.exists(video_path):
            with open(video_path, 'rb') as video:
                SERVICES['telegram_bot'].send_video(
                    Config.CHAT_ID, 
                    video,
                    caption=caption,
                    supports_streaming=True
                )
            print("✅ Video sent to Telegram group")
            return True
    except Exception as e:
        print(f"❌ Telegram video send error: {e}")
    return False

def send_telegram_message(message):
    """Send text message to Telegram"""
    try:
        if SERVICES['telegram_bot']:
            SERVICES['telegram_bot'].send_message(Config.CHAT_ID, message)
            print("✅ Message sent to Telegram group")
            return True
        else:
            print("❌ Telegram bot not initialized")
            return False
    except Exception as e:
        print(f"❌ Telegram message error: {e}")
        print(f"   Chat ID: {Config.CHAT_ID}")
        print(f"   Bot Token: {Config.TELEGRAM_BOT_TOKEN[:20]}...")
    return False

def send_whatsapp_alert(message):
    """Send WhatsApp alert via Twilio"""
    try:
        if SERVICES['twilio_client']:
            SERVICES['twilio_client'].messages.create(
                body=message,
                from_=Config.TWILIO_WHATSAPP_NUMBER,
                to=Config.RECEIVER_WHATSAPP
            )
            print("✅ WhatsApp alert sent to group")
            return True
        else:
            print("❌ Twilio client not initialized")
            return False
    except Exception as e:
        print(f"❌ WhatsApp alert error: {e}")
        print(f"   From: {Config.TWILIO_WHATSAPP_NUMBER}")
        print(f"   To: {Config.RECEIVER_WHATSAPP}")
    return False

def speak_alert(text):
    """Text-to-speech alert"""
    try:
        if SERVICES['tts_engine']:
            SERVICES['tts_engine'].say(text)
            SERVICES['tts_engine'].runAndWait()
    except Exception as e:
        print(f"❌ TTS error: {e}")

def handle_crash_alert(frame, probability):
    """Handle complete crash alert workflow"""
    global crash_count
    
    now = datetime.now()
    timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
    
    crash_count += 1
    
    # Voice alert
    alert_speech = f"Alert! Crash detected. Crash number {crash_count}. Emergency services notified. Location: {current_location['city'] if current_location else 'Unknown'}"
    threading.Thread(target=speak_alert, args=(alert_speech,), daemon=True).start()
    
    # Prepare alert message
    location_str = get_location_string()
    maps_link = get_location_link()
    
    alert_msg = f"""🚨 CRASH DETECTED! 🚨

⏰ Time: {timestamp}
📊 Crash Probability: {probability:.1%}
🎯 Crash Count: {crash_count}

📍 LOCATION:
{location_str}
🗺️ Map: {maps_link}

⚠️ Emergency Response Required!
"""
    
    # Send alerts

    # Save and send crash video
    timestamp_str = timestamp.replace(' ', '_').replace(':', '-')
    video_file = f"alerts/crash_{timestamp_str}.mp4"
    if video_recorder.save(video_file):
        caption = f"🚨 Crash #{crash_count}\\n⏰ {timestamp}\\n📍 {current_location['city'] if current_location else 'Unknown'}"
        threading.Thread(target=send_video_to_telegram, args=(video_file, caption), daemon=True).start()
    
    threading.Thread(target=send_whatsapp_alert, args=(alert_msg,), daemon=True).start()
    threading.Thread(target=send_telegram_message, args=(alert_msg,), daemon=True).start()
    
    print("\n" + "="*60)
    print(f"🚨 CRASH #{crash_count} DETECTED!")
    print(f"⏰ Time: {timestamp}")
    print(f"📊 Probability: {probability:.1%}")
    print(f"📍 Location: {location_str}")
    print("="*60 + "\n")

# ========== DETECTION LOGIC ==========
def detect_crash(frame, process_frame=True):
    """Main crash detection logic using YOLO + Random Forest ML"""
    global ml_crash_counter, previous_vehicle_positions
    
    vehicles = []
    humans = []
    probability = 0.0
    crash_detected = False
    
    if not process_frame or SERVICES['yolo_model'] is None:
        return vehicles, humans, probability, crash_detected
    
    try:
        results = SERVICES['yolo_model'](frame)
        detections = results.pandas().xyxy[0]
        
        for _, row in detections.iterrows():
            cls = row['name']
            conf = row['confidence']
            
            if cls in Config.INTERESTED_CLASSES and conf > Config.CONFIDENCE_THRESHOLD:
                x1, y1, x2, y2 = map(int, [row['xmin'], row['ymin'], row['xmax'], row['ymax']])
                
                if cls == 'person':
                    humans.append((x1, y1, x2, y2))
                else:
                    vehicles.append((x1, y1, x2, y2))
                
                color = (0, 0, 255) if cls == 'person' else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{cls} {conf:.2f}", (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        if SERVICES['ml_model'] is not None:
            vehicle_count = len(vehicles)
            human_count = len(humans)
            
            overlap_count = 0
            for v in vehicles:
                for h in humans:
                    if is_overlap(v, h):
                        overlap_count += 1
                for v2 in vehicles:
                    if v != v2 and is_overlap(v, v2):
                        overlap_count += 1
            
            sudden_motion = 0
            for i, v in enumerate(vehicles):
                if i < len(previous_vehicle_positions):
                    px1, py1, px2, py2 = previous_vehicle_positions[i]
                    movement = abs(v[0] - px1) + abs(v[1] - py1)
                    if movement > Config.SUDDEN_MOTION_THRESHOLD:
                        sudden_motion += 1
            
            previous_vehicle_positions = vehicles.copy()
            avg_conf = detections['confidence'].mean() if len(detections) > 0 else 0
            speed = 10 + (sudden_motion * 5)
            
            # Only predict crash if there are vehicles AND some action happening
            if vehicle_count >= 2 or (vehicle_count >= 1 and human_count >= 1) or overlap_count > 0 or sudden_motion > 0:
                features = [[vehicle_count, human_count, avg_conf, overlap_count + sudden_motion, speed]]
                probability = SERVICES['ml_model'].predict_proba(features)[0][1]
                
                # Additional checks for crash detection
                if probability > Config.CRASH_PROBABILITY_THRESHOLD:
                    # Require at least one of these conditions:
                    # 1. Multiple vehicles OR
                    # 2. Vehicle + human OR
                    # 3. Overlap detected OR
                    # 4. Sudden motion
                    if (vehicle_count >= 2) or (vehicle_count >= 1 and human_count >= 1) or (overlap_count > 0) or (sudden_motion > 1):
                        ml_crash_counter += 1
                    else:
                        ml_crash_counter = 0
                        probability = probability * 0.5  # Reduce probability if conditions not met
                else:
                    ml_crash_counter = 0
            else:
                # Not enough activity for crash
                probability = 0.0
                ml_crash_counter = 0
            
            crash_detected = ml_crash_counter >= Config.REQUIRED_CRASH_FRAMES
    
    except Exception as e:
        print(f"❌ Detection error: {e}")
    
    return vehicles, humans, probability, crash_detected

# ========== GUI APPLICATION ==========
class CrashDetectionGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🚨 Secure Vision - AI Crash Detection System")
        self.root.geometry("950x650")
        self.root.configure(bg='#f0f0f0')
        
        self.cap = None
        self.using_webcam = False
        self.current_video_path = None
        self.is_playing = False
        self.crash_pause_until = None
        self.playback_delay = 100  # Slower playback (milliseconds between frames)
        
        self.create_widgets()
        
        # Start with webcam by default
        self.start_webcam()
    
    def create_widgets(self):
        """Create GUI widgets"""
        # Header
        header_frame = tk.Frame(self.root, bg='#2c3e50', pady=8)
        header_frame.pack(fill=tk.X)
        
        title_label = tk.Label(
            header_frame, 
            text="🚨 SECURE VISION - AI Crash Detection System",
            font=("Helvetica", 18, "bold"),
            fg="white",
            bg='#2c3e50'
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            header_frame,
            text="ML Model: Random Forest Classifier | Detection: YOLOv5",
            font=("Helvetica", 10),
            fg="#ecf0f1",
            bg='#2c3e50'
        )
        subtitle_label.pack()
        
        # Video frame
        video_container = tk.Frame(self.root, bg='black', relief=tk.SUNKEN, borderwidth=2)
        video_container.pack(pady=10, padx=10)
        
        self.video_frame = tk.Label(video_container, bg="black")
        self.video_frame.pack()
        
        # Status frame
        status_frame = tk.Frame(self.root, bg='#ecf0f1', relief=tk.RAISED, borderwidth=2)
        status_frame.pack(pady=5, padx=10, fill=tk.X)
        
        status_grid = tk.Frame(status_frame, bg='#ecf0f1')
        status_grid.pack(pady=10)
        
        # Left column
        left_col = tk.Frame(status_grid, bg='#ecf0f1')
        left_col.grid(row=0, column=0, padx=20)
        
        self.status_label = tk.Label(
            left_col,
            text="🟢 Webcam Active",
            font=("Helvetica", 12, "bold"),
            fg="#27ae60",
            bg='#ecf0f1'
        )
        self.status_label.pack()
        
        self.location_label = tk.Label(
            left_col,
            text=f"📍 {current_location['city']}, {current_location['country']}" if current_location else "📍 Location: Unknown",
            font=("Helvetica", 10),
            fg="#34495e",
            bg='#ecf0f1'
        )
        self.location_label.pack()
        
        # Middle column
        mid_col = tk.Frame(status_grid, bg='#ecf0f1')
        mid_col.grid(row=0, column=1, padx=20)
        
        self.counter_label = tk.Label(
            mid_col,
            text="Crashes Detected: 0",
            font=("Helvetica", 11, "bold"),
            fg="#e74c3c",
            bg='#ecf0f1'
        )
        self.counter_label.pack()
        
        self.prob_label = tk.Label(
            mid_col,
            text="Crash Probability: 0.0%",
            font=("Helvetica", 10),
            fg="#f39c12",
            bg='#ecf0f1'
        )
        self.prob_label.pack()
        
        # Right column
        right_col = tk.Frame(status_grid, bg='#ecf0f1')
        right_col.grid(row=0, column=2, padx=20)
        
        self.detection_label = tk.Label(
            right_col,
            text="Vehicles: 0 | Humans: 0",
            font=("Helvetica", 10),
            fg="#16a085",
            bg='#ecf0f1'
        )
        self.detection_label.pack()
        
        self.video_info_label = tk.Label(
            right_col,
            text="Webcam active",
            font=("Helvetica", 9),
            fg="#7f8c8d",
            bg='#ecf0f1'
        )
        self.video_info_label.pack()
        
        # Control buttons - Row 1
        button_frame1 = tk.Frame(self.root, bg='#ecf0f1')
        button_frame1.pack(pady=5)
        
        tk.Button(
            button_frame1,
            text="🎥 USE WEBCAM",
            command=self.start_webcam,
            font=("Helvetica", 11, "bold"),
            bg="#3498db",
            fg="white",
            width=20,
            height=2,
            relief=tk.RAISED,
            cursor="hand2"
        ).grid(row=0, column=0, padx=5)
        
        tk.Button(
            button_frame1,
            text="📂 LOAD VIDEO FILE",
            command=self.load_video_file,
            font=("Helvetica", 11, "bold"),
            bg="#27ae60",
            fg="white",
            width=20,
            height=2,
            relief=tk.RAISED,
            cursor="hand2"
        ).grid(row=0, column=1, padx=5)
        
        # Control buttons - Row 2
        button_frame2 = tk.Frame(self.root, bg='#ecf0f1')
        button_frame2.pack(pady=5)
        
        self.play_pause_btn = tk.Button(
            button_frame2,
            text="⏸️ PAUSE",
            command=self.toggle_play_pause,
            font=("Helvetica", 11, "bold"),
            bg="#e67e22",
            fg="white",
            width=15,
            relief=tk.RAISED,
            cursor="hand2"
        )
        self.play_pause_btn.grid(row=0, column=0, padx=5)
        
        self.restart_btn = tk.Button(
            button_frame2,
            text="🔄 RESTART",
            command=self.restart_video,
            font=("Helvetica", 11, "bold"),
            bg="#9b59b6",
            fg="white",
            width=15,
            relief=tk.RAISED,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.restart_btn.grid(row=0, column=1, padx=5)
        
        tk.Button(
            button_frame2,
            text="❌ EXIT",
            command=self.on_closing,
            font=("Helvetica", 11, "bold"),
            bg="#c0392b",
            fg="white",
            width=15,
            relief=tk.RAISED,
            cursor="hand2"
        ).grid(row=0, column=2, padx=5)
        
        # Instructions
        instructions = tk.Label(
            self.root,
            text="📌 Video plays slower for better detection. Pauses 5 seconds when crash detected.\n🎥 Webcam: Normal speed | 📂 Video: Slower playback",
            font=("Helvetica", 9),
            fg="#7f8c8d",
            bg='#f0f0f0',
            justify=tk.CENTER
        )
        instructions.pack(pady=5)
    
    def start_webcam(self):
        """Start webcam"""
        if self.cap:
            self.cap.release()
        
        self.cap = cv2.VideoCapture(0)
        
        if not self.cap.isOpened():
            messagebox.showerror("Error", "Could not open webcam!")
            return
        
        self.using_webcam = True
        self.current_video_path = None
        self.is_playing = True
        
        self.status_label.config(text="🟢 Webcam Active", fg="#27ae60")
        self.video_info_label.config(text="Webcam active")
        self.play_pause_btn.config(text="⏸️ PAUSE", bg="#e67e22", state=tk.NORMAL)
        self.restart_btn.config(state=tk.DISABLED)
        
        print("✅ Webcam started")
        self.update_frame()
    
    def load_video_file(self):
        """Load video file"""
        file_path = filedialog.askopenfilename(
            title="Select Accident Video File",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv"),
                ("MP4 files", "*.mp4"),
                ("AVI files", "*.avi"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            if self.cap:
                self.cap.release()
            
            self.cap = cv2.VideoCapture(file_path)
            
            if not self.cap.isOpened():
                messagebox.showerror("Error", "Could not open video file!")
                return
            
            self.current_video_path = file_path
            self.using_webcam = False
            self.is_playing = True
            
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            frame_count_total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count_total / fps if fps > 0 else 0
            
            filename = os.path.basename(file_path)
            self.video_info_label.config(text=f"📹 {filename} | {duration:.1f}s | {fps:.0f} FPS")
            self.status_label.config(text="🔴 DETECTING...", fg="#e74c3c")
            self.play_pause_btn.config(text="⏸️ PAUSE", bg="#e67e22", state=tk.NORMAL)
            self.restart_btn.config(state=tk.NORMAL)
            
            print(f"✅ Video loaded: {filename}")
            messagebox.showinfo("Video Loaded", f"Video: {filename}\nDuration: {duration:.1f} seconds\n\nPlaying automatically...")
            
            self.update_frame()
    
    def toggle_play_pause(self):
        """Toggle play/pause"""
        if self.is_playing:
            self.is_playing = False
            self.play_pause_btn.config(text="▶️ PLAY", bg="#3498db")
            self.status_label.config(text="⏸️ Paused", fg="#f39c12")
        else:
            self.is_playing = True
            self.play_pause_btn.config(text="⏸️ PAUSE", bg="#e67e22")
            if self.using_webcam:
                self.status_label.config(text="🟢 Webcam Active", fg="#27ae60")
            else:
                self.status_label.config(text="🔴 DETECTING...", fg="#e74c3c")
            self.update_frame()
    
    def restart_video(self):
        """Restart video"""
        if self.cap and not self.using_webcam:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.is_playing = True
            self.play_pause_btn.config(text="⏸️ PAUSE", bg="#e67e22")
            self.status_label.config(text="🔴 DETECTING...", fg="#e74c3c")
            self.update_frame()
    
    def display_frame(self, frame):
        """Display frame in GUI"""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_resized = cv2.resize(frame_rgb, (750, 450))
        imgtk = ImageTk.PhotoImage(Image.fromarray(frame_resized))
        self.video_frame.imgtk = imgtk
        self.video_frame.configure(image=imgtk)
    
    def update_frame(self):
        """Update video frame and perform detection"""
        global frame_count, last_alert_time, crash_count
        
        if not self.cap or not self.cap.isOpened() or not self.is_playing:
            return
        
        # Check if we're in crash pause mode
        now = datetime.now()
        if self.crash_pause_until and now < self.crash_pause_until:
            # Still paused due to crash detection
            # Schedule next check
            delay = 50 if self.using_webcam else self.playback_delay
            self.root.after(delay, self.update_frame)
            return
        
        frame_count += 1
        ret, frame = self.cap.read()
        
        if not ret:
            if not self.using_webcam:
                self.is_playing = False
                self.play_pause_btn.config(text="▶️ REPLAY", bg="#3498db")
                self.status_label.config(text="✅ Video Ended", fg="#27ae60")
                messagebox.showinfo("Video Ended", f"Video playback complete!\n\nTotal crashes detected: {crash_count}")
            return
        
        process_this_frame = (frame_count % Config.PROCESS_EVERY_N_FRAMES == 0)
        vehicles, humans, probability, crash_detected = detect_crash(frame, process_this_frame)
        
        self.prob_label.config(text=f"Crash Probability: {probability:.1%}")
        self.detection_label.config(text=f"Vehicles: {len(vehicles)} | Humans: {len(humans)}")
        
        if crash_detected:
            # Record crash video
            global video_recorder
            if not video_recorder.is_recording:
                video_recorder.start()
            video_recorder.add_frame(frame)
            
            cv2.putText(frame, "CRASH DETECTED!", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            self.status_label.config(text="🔴 CRASH DETECTED!", fg="red")
            
            # Add "PAUSED" text when crash detected
            cv2.putText(frame, "PAUSED FOR 5 SECONDS", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        else:
            cv2.putText(frame, "Monitoring", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        prob_color = (0, 255, 0) if probability < 0.4 else (0, 255, 255) if probability < 0.7 else (0, 0, 255)
        cv2.putText(frame, f"Probability: {probability:.1%}", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, prob_color, 2)
        cv2.putText(frame, f"Vehicles: {len(vehicles)} | Humans: {len(humans)}", (20, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        now = datetime.now()
        if crash_detected and (now - last_alert_time > timedelta(seconds=Config.ALERT_COOLDOWN_SECONDS)):
            last_alert_time = now
            self.counter_label.config(text=f"Crashes Detected: {crash_count + 1}")
            
            # Set pause for 5 seconds when crash detected
            self.crash_pause_until = now + timedelta(seconds=5)
            print(f"🚨 CRASH DETECTED! Pausing for 5 seconds...")
            
            threading.Thread(target=handle_crash_alert, args=(frame.copy(), probability), daemon=True).start()
        
        self.display_frame(frame)
        
        if self.is_playing:
            # Use slower playback for video files, normal speed for webcam
            delay = 30 if self.using_webcam else self.playback_delay
            self.root.after(delay, self.update_frame)
    
    def on_closing(self):
        """Clean up when closing"""
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        self.root.destroy()

# ========== MAIN ==========
def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("Starting GUI Application...")
    print("="*60 + "\n")
    
    if not os.path.exists(Config.ML_MODEL_PATH):
        print(f"\n⚠️ WARNING: ML model not found at {Config.ML_MODEL_PATH}")
        print("Please train the model first using the training notebook.\n")
    
    root = tk.Tk()
    app = CrashDetectionGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    print("✅ GUI ready! Webcam started automatically.\n")
    
    root.mainloop()

if __name__ == "__main__":
    main()