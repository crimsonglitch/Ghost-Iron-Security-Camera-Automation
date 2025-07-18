import sys
import os
import cv2
import sqlite3
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QLineEdit, QComboBox, QTabWidget, 
                             QGridLayout, QMessageBox, QFileDialog, QGroupBox, QDateEdit, 
                             QTimeEdit, QListWidget, QStackedWidget, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, QDateTime, QDate, QTime
from PyQt5.QtGui import QImage, QPixmap, QIcon

# Database initialization
def init_databases():
    # Personnel database
    conn = sqlite3.connect('personnel.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS personnel
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 username TEXT UNIQUE,
                 password TEXT,
                 authority TEXT)''')
    
    # Default admin account (if not exists)
    c.execute("SELECT * FROM personnel WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO personnel (username, password, authority) VALUES (?, ?, ?)",
                  ('admin', 'admin123', 'admin'))
    
    conn.commit()
    conn.close()
    
    # Camera recordings database
    conn = sqlite3.connect('camera_recordings.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS recordings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 camera_id INTEGER,
                 start_time TEXT,
                 file_path TEXT)''')
    conn.commit()
    conn.close()

# Camera widget class
class CameraWidget(QLabel):
    def __init__(self, camera_id, parent=None):
        super().__init__(parent)
        self.camera_id = camera_id
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: black;")
        self.setMinimumSize(320, 240)
        
    def update_frame(self, frame):
        if frame is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.setPixmap(QPixmap.fromImage(q_img).scaled(
                self.width(), self.height(), Qt.KeepAspectRatio))

# Login Window
class LoginWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Security Camera System - Login")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        self.logo_label = QLabel()
        self.logo_label.setPixmap(QPixmap("logo.png").scaled(200, 200, Qt.KeepAspectRatio))
        self.logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.logo_label)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        layout.addWidget(self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)
        
        self.login_btn = QPushButton("Login")
        self.login_btn.clicked.connect(self.login_check)
        layout.addWidget(self.login_btn)
        
        self.setLayout(layout)
    
    def login_check(self):
        username = self.username_input.text()
        password = self.password_input.text()
        
        conn = sqlite3.connect('personnel.db')
        c = conn.cursor()
        c.execute("SELECT * FROM personnel WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        
        if user:
            self.parent.username = user[1]
            self.parent.authority = user[3]
            self.parent.init_ui()
            self.close()
        else:
            QMessageBox.warning(self, "Error", "Invalid username or password!")

# Main Application Window
class CameraSystem(QMainWindow):
    def __init__(self):
        super().__init__()
        self.username = None
        self.authority = None
        self.cameras = []
        self.camera_widgets = []
        self.recording_managers = []
        self.login_window = LoginWindow(self)
        self.login_window.show()
        
        # Camera configuration
        self.camera_count = 4
        self.camera_layout = QGridLayout()
        
        # Recording settings
        self.recording_duration = 10  # minutes
        self.recording_folder = "recordings"
        if not os.path.exists(self.recording_folder):
            os.makedirs(self.recording_folder)
    
    def init_ui(self):
        self.setWindowTitle(f"Security Camera System - {self.username} ({self.authority})")
        self.setMinimumSize(1280, 720)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Menu bar
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        if self.authority == 'admin':
            admin_action = file_menu.addAction('Admin Panel')
            admin_action.triggered.connect(self.open_admin_panel)
        
        logout_action = file_menu.addAction('Logout')
        logout_action.triggered.connect(self.logout)
        
        # Tabs
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Live View Tab
        self.live_view_tab = QWidget()
        self.live_view_layout = QVBoxLayout()
        self.live_view_tab.setLayout(self.live_view_layout)
        
        self.camera_container = QWidget()
        self.camera_container.setLayout(self.camera_layout)
        self.live_view_layout.addWidget(self.camera_container)
        
        self.tab_widget.addTab(self.live_view_tab, "Live View")
        
        # History Tab
        self.history_tab = QWidget()
        self.history_layout = QVBoxLayout()
        self.history_tab.setLayout(self.history_layout)
        
        # Filter section
        filter_group = QGroupBox("Filters")
        filter_layout = QHBoxLayout()
        
        self.camera_filter_combo = QComboBox()
        self.camera_filter_combo.addItem("All Cameras", -1)
        for i in range(self.camera_count):
            self.camera_filter_combo.addItem(f"Camera {i+1}", i)
        
        self.date_filter = QDateEdit()
        self.date_filter.setDate(QDate.currentDate())
        self.date_filter.setCalendarPopup(True)
        
        self.filter_btn = QPushButton("Filter")
        self.filter_btn.clicked.connect(self.filter_recordings)
        
        filter_layout.addWidget(QLabel("Camera:"))
        filter_layout.addWidget(self.camera_filter_combo)
        filter_layout.addWidget(QLabel("Date:"))
        filter_layout.addWidget(self.date_filter)
        filter_layout.addWidget(self.filter_btn)
        filter_group.setLayout(filter_layout)
        self.history_layout.addWidget(filter_group)
        
        # Recordings list
        self.recordings_list = QListWidget()
        self.recordings_list.itemDoubleClicked.connect(self.play_recording)
        self.history_layout.addWidget(self.recordings_list)
        
        # Recording player
        self.recording_player = CameraWidget(0)
        self.recording_player.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.history_layout.addWidget(self.recording_player)
        
        self.tab_widget.addTab(self.history_tab, "History")
        
        # Mixed Mode Tab (Live + History)
        if self.authority == 'admin':
            self.mixed_mode_tab = QWidget()
            self.mixed_mode_layout = QHBoxLayout()
            self.mixed_mode_tab.setLayout(self.mixed_mode_layout)
            
            # Live section
            live_group = QGroupBox("Live View")
            live_layout = QVBoxLayout()
            self.mixed_live_widget = CameraWidget(0)
            live_layout.addWidget(self.mixed_live_widget)
            live_group.setLayout(live_layout)
            self.mixed_mode_layout.addWidget(live_group)
            
            # History section
            history_group = QGroupBox("Recordings")
            history_layout = QVBoxLayout()
            
            self.mixed_recordings_list = QListWidget()
            self.mixed_recordings_list.itemDoubleClicked.connect(self.play_mixed_recording)
            history_layout.addWidget(self.mixed_recordings_list)
            
            self.mixed_player = CameraWidget(0)
            history_layout.addWidget(self.mixed_player)
            
            history_group.setLayout(history_layout)
            self.mixed_mode_layout.addWidget(history_group)
            
            self.tab_widget.addTab(self.mixed_mode_tab, "Mixed Mode")
        
        # Initialize cameras
        self.initialize_cameras()
        
        # Initialize recording managers
        self.initialize_recording_managers()
        
        # Update recordings list
        self.filter_recordings()
        
        # Start timers
        self.live_update_timer = QTimer()
        self.live_update_timer.timeout.connect(self.update_live)
        self.live_update_timer.start(30)  # ~30 FPS
        
        if self.authority == 'admin':
            self.mixed_update_timer = QTimer()
            self.mixed_update_timer.timeout.connect(self.update_mixed)
            self.mixed_update_timer.start(30)
    
    def initialize_cameras(self):
        # Clear existing widgets
        for i in reversed(range(self.camera_layout.count())): 
            self.camera_layout.itemAt(i).widget().setParent(None)
        
        self.cameras = []
        self.camera_widgets = []
        
        # Initialize cameras
        for i in range(self.camera_count):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                self.cameras.append(cap)
                
                # Create camera widget
                camera_widget = CameraWidget(i)
                self.camera_widgets.append(camera_widget)
                
                # Add widget to layout (2x2 grid)
                row = i // 2
                col = i % 2
                self.camera_layout.addWidget(camera_widget, row, col)
            else:
                print(f"Camera {i} initialization failed!")
                self.cameras.append(None)
                self.camera_widgets.append(None)
    
    def initialize_recording_managers(self):
        self.recording_managers = []
        
        for i in range(self.camera_count):
            if self.cameras[i] is not None:
                recording_manager = RecordingManager(i, self.recording_folder, self.recording_duration)
                self.recording_managers.append(recording_manager)
            else:
                self.recording_managers.append(None)
    
    def update_live(self):
        for i, (camera, widget) in enumerate(zip(self.cameras, self.camera_widgets)):
            if camera is not None and widget is not None:
                ret, frame = camera.read()
                if ret:
                    widget.update_frame(frame)
                    
                    # Send frame to recording manager
                    if self.recording_managers[i] is not None:
                        self.recording_managers[i].record_frame(frame)
    
    def update_mixed(self):
        if self.cameras[0] is not None and hasattr(self, 'mixed_live_widget'):
            ret, frame = self.cameras[0].read()
            if ret:
                self.mixed_live_widget.update_frame(frame)
    
    def filter_recordings(self):
        self.recordings_list.clear()
        
        camera_id = self.camera_filter_combo.currentData()
        date = self.date_filter.date().toString("yyyy-MM-dd")
        
        conn = sqlite3.connect('camera_recordings.db')
        c = conn.cursor()
        
        if camera_id == -1:  # All cameras
            c.execute("SELECT * FROM recordings WHERE start_time LIKE ? ORDER BY start_time DESC", 
                     (f"{date}%",))
        else:
            c.execute("SELECT * FROM recordings WHERE camera_id=? AND start_time LIKE ? ORDER BY start_time DESC", 
                     (camera_id, f"{date}%"))
        
        recordings = c.fetchall()
        conn.close()
        
        for recording in recordings:
            item_text = f"Camera {recording[1]} - {recording[2]}"
            self.recordings_list.addItem(item_text)
            self.recordings_list.item(self.recordings_list.count()-1).setData(Qt.UserRole, recording[3])
        
        if self.authority == 'admin':
            self.mixed_recordings_list.clear()
            for recording in recordings:
                item_text = f"Camera {recording[1]} - {recording[2]}"
                self.mixed_recordings_list.addItem(item_text)
                self.mixed_recordings_list.item(self.mixed_recordings_list.count()-1).setData(Qt.UserRole, recording[3])
    
    def play_recording(self, item):
        file_path = item.data(Qt.UserRole)
        self.play_video(file_path, self.recording_player)
    
    def play_mixed_recording(self, item):
        file_path = item.data(Qt.UserRole)
        self.play_video(file_path, self.mixed_player)
    
    def play_video(self, file_path, widget):
        if hasattr(self, 'video_cap'):
            self.video_cap.release()
        
        self.video_cap = cv2.VideoCapture(file_path)
        
        if not hasattr(self, 'video_timer'):
            self.video_timer = QTimer()
            self.video_timer.timeout.connect(lambda: self.update_video(widget))
        
        self.video_timer.start(30)
    
    def update_video(self, widget):
        ret, frame = self.video_cap.read()
        if ret:
            widget.update_frame(frame)
        else:
            self.video_timer.stop()
            self.video_cap.release()
    
    def open_admin_panel(self):
        self.admin_panel = AdminPanel(self)
        self.admin_panel.show()
    
    def logout(self):
        # Release resources
        for camera in self.cameras:
            if camera is not None:
                camera.release()
        
        for recording_manager in self.recording_managers:
            if recording_manager is not None:
                recording_manager.stop_recording()
        
        if hasattr(self, 'video_cap'):
            self.video_cap.release()
        
        self.login_window.show()
        self.close()

# Recording Manager Class
class RecordingManager:
    def __init__(self, camera_id, recording_folder, recording_duration_min):
        self.camera_id = camera_id
        self.recording_folder = recording_folder
        self.recording_duration = recording_duration_min * 60  # convert to seconds
        self.recording_start = None
        self.video_writer = None
        self.file_path = None
    
    def record_frame(self, frame):
        now = datetime.now()
        
        # Check if new recording should be started
        if self.recording_start is None or (now - self.recording_start).total_seconds() > self.recording_duration:
            self.stop_recording()
            self.start_recording(now)
        
        # Write frame
        if self.video_writer is not None:
            self.video_writer.write(frame)
    
    def start_recording(self, start_time):
        self.recording_start = start_time
        file_name = f"camera_{self.camera_id}_{start_time.strftime('%Y%m%d_%H%M%S')}.avi"
        self.file_path = os.path.join(self.recording_folder, file_name)
        
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.video_writer = cv2.VideoWriter(self.file_path, fourcc, 20.0, (640, 480))
        
        # Save to database
        conn = sqlite3.connect('camera_recordings.db')
        c = conn.cursor()
        c.execute("INSERT INTO recordings (camera_id, start_time, file_path) VALUES (?, ?, ?)",
                  (self.camera_id, start_time.strftime("%Y-%m-%d %H:%M:%S"), self.file_path))
        conn.commit()
        conn.close()
    
    def stop_recording(self):
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
            self.recording_start = None

# Admin Panel
class AdminPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Admin Panel")
        self.setFixedSize(600, 400)
        
        layout = QVBoxLayout()
        
        # Personnel Management
        personnel_group = QGroupBox("Personnel Management")
        personnel_layout = QVBoxLayout()
        
        # Personnel list
        self.personnel_list = QListWidget()
        self.personnel_list.itemClicked.connect(self.personnel_selected)
        personnel_layout.addWidget(self.personnel_list)
        
        # Personnel details
        detail_layout = QHBoxLayout()
        
        left_layout = QVBoxLayout()
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        left_layout.addWidget(self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        left_layout.addWidget(self.password_input)
        
        self.authority_combo = QComboBox()
        self.authority_combo.addItems(["security", "admin"])
        left_layout.addWidget(self.authority_combo)
        
        detail_layout.addLayout(left_layout)
        
        right_layout = QVBoxLayout()
        self.add_btn = QPushButton("Add New")
        self.add_btn.clicked.connect(self.add_personnel)
        right_layout.addWidget(self.add_btn)
        
        self.update_btn = QPushButton("Update")
        self.update_btn.clicked.connect(self.update_personnel)
        right_layout.addWidget(self.update_btn)
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete_personnel)
        right_layout.addWidget(self.delete_btn)
        
        detail_layout.addLayout(right_layout)
        personnel_layout.addLayout(detail_layout)
        personnel_group.setLayout(personnel_layout)
        layout.addWidget(personnel_group)
        
        # System Settings
        settings_group = QGroupBox("System Settings")
        settings_layout = QVBoxLayout()
        
        self.camera_count_input = QLineEdit()
        self.camera_count_input.setPlaceholderText(f"Current Camera Count: {self.parent.camera_count}")
        settings_layout.addWidget(self.camera_count_input)
        
        self.recording_duration_input = QLineEdit()
        self.recording_duration_input.setPlaceholderText(f"Recording Duration (min): {self.parent.recording_duration}")
        settings_layout.addWidget(self.recording_duration_input)
        
        self.recording_folder_btn = QPushButton("Change Recording Folder")
        self.recording_folder_btn.clicked.connect(self.change_recording_folder)
        settings_layout.addWidget(self.recording_folder_btn)
        
        self.save_settings_btn = QPushButton("Save Settings")
        self.save_settings_btn.clicked.connect(self.save_settings)
        settings_layout.addWidget(self.save_settings_btn)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        self.setLayout(layout)
        
        # Update personnel list
        self.update_personnel_list()
    
    def update_personnel_list(self):
        self.personnel_list.clear()
        
        conn = sqlite3.connect('personnel.db')
        c = conn.cursor()
        c.execute("SELECT * FROM personnel")
        personnel = c.fetchall()
        conn.close()
        
        for person in personnel:
            item_text = f"{person[1]} ({person[3]})"
            self.personnel_list.addItem(item_text)
            self.personnel_list.item(self.personnel_list.count()-1).setData(Qt.UserRole, person[0])
    
    def personnel_selected(self, item):
        person_id = item.data(Qt.UserRole)
        
        conn = sqlite3.connect('personnel.db')
        c = conn.cursor()
        c.execute("SELECT * FROM personnel WHERE id=?", (person_id,))
        person = c.fetchone()
        conn.close()
        
        if person:
            self.username_input.setText(person[1])
            self.password_input.setText(person[2])
            self.authority_combo.setCurrentText(person[3])
    
    def add_personnel(self):
        username = self.username_input.text()
        password = self.password_input.text()
        authority = self.authority_combo.currentText()
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Username and password cannot be empty!")
            return
        
        conn = sqlite3.connect('personnel.db')
        c = conn.cursor()
        
        try:
            c.execute("INSERT INTO personnel (username, password, authority) VALUES (?, ?, ?)",
                      (username, password, authority))
            conn.commit()
            QMessageBox.information(self, "Success", "Personnel added successfully!")
            self.update_personnel_list()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "Username already exists!")
        finally:
            conn.close()
    
    def update_personnel(self):
        current_item = self.personnel_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Error", "Please select a personnel!")
            return
        
        person_id = current_item.data(Qt.UserRole)
        username = self.username_input.text()
        password = self.password_input.text()
        authority = self.authority_combo.currentText()
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Username and password cannot be empty!")
            return
        
        conn = sqlite3.connect('personnel.db')
        c = conn.cursor()
        
        try:
            c.execute("UPDATE personnel SET username=?, password=?, authority=? WHERE id=?",
                      (username, password, authority, person_id))
            conn.commit()
            QMessageBox.information(self, "Success", "Personnel updated successfully!")
            self.update_personnel_list()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "Username already exists!")
        finally:
            conn.close()
    
    def delete_personnel(self):
        current_item = self.personnel_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Error", "Please select a personnel!")
            return
        
        person_id = current_item.data(Qt.UserRole)
        
        # Check if admin
        conn = sqlite3.connect('personnel.db')
        c = conn.cursor()
        c.execute("SELECT authority FROM personnel WHERE id=?", (person_id,))
        authority = c.fetchone()[0]
        
        if authority == "admin":
            QMessageBox.warning(self, "Error", "Admin account cannot be deleted!")
            conn.close()
            return
        
        reply = QMessageBox.question(self, 'Confirmation', 'Are you sure you want to delete this personnel?',
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            c.execute("DELETE FROM personnel WHERE id=?", (person_id,))
            conn.commit()
            QMessageBox.information(self, "Success", "Personnel deleted successfully!")
            self.update_personnel_list()
        
        conn.close()
    
    def change_recording_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Recording Folder")
        if folder:
            self.parent.recording_folder = folder
            QMessageBox.information(self, "Success", f"Recording folder set to {folder}!")
    
    def save_settings(self):
        # Camera count
        if self.camera_count_input.text():
            try:
                new_count = int(self.camera_count_input.text())
                if new_count > 0:
                    self.parent.camera_count = new_count
                    self.parent.initialize_cameras()
                    self.parent.initialize_recording_managers()
                else:
                    QMessageBox.warning(self, "Error", "Camera count must be greater than 0!")
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid camera count!")
        
        # Recording duration
        if self.recording_duration_input.text():
            try:
                new_duration = int(self.recording_duration_input.text())
                if new_duration > 0:
                    self.parent.recording_duration = new_duration
                    for manager in self.parent.recording_managers:
                        if manager is not None:
                            manager.recording_duration = new_duration * 60
                else:
                    QMessageBox.warning(self, "Error", "Recording duration must be greater than 0!")
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid recording duration!")
        
        QMessageBox.information(self, "Success", "Settings saved successfully!")

# Start application
if __name__ == "__main__":
    init_databases()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Check logo file
    if not os.path.exists("logo.png"):
        # Create default logo (optional)
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (200, 200), color=(70, 130, 180))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
        d.text((10, 80), "Security Camera\n      System", fill=(255, 255, 255), font=font)
        img.save("logo.png")
    
    window = CameraSystem()
    sys.exit(app.exec_())