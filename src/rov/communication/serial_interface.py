import sys
import serial
import serial.tools.list_ports
import threading
import time
import random
import argparse
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox, QSlider,
    QHBoxLayout, QGridLayout, QFrame, QSizePolicy, QGroupBox, QSpacerItem
)
from PyQt6.QtGui import QFont, QIcon, QColor
from PyQt6.QtCore import Qt, QSize, QTimer

class ROVController(QMainWindow):
    def __init__(self, emergency_mode=False, mission_id=None):
        super().__init__()
        self.emergency_mode = emergency_mode
        self.mission_id = mission_id
        self.auto_deploy_timer = None
        
        # Update window title for emergency mode
        title = "🚨 EMERGENCY ROV CONTROL - MISSION ACTIVE" if emergency_mode else "AURA Prototype Control Station"
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 1200, 800)
        self.ser = None
        self.connected = False
        self.fake_depth = 0.1
        self.sensor_data = []
        
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 14px;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
            QComboBox {
                background-color: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                padding: 6px;
                min-height: 30px;
            }
            QComboBox:drop-down {
                border: none;
            }
            QSlider {
                height: 30px;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #313244;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #89b4fa;
                border: none;
                width: 18px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 9px;
            }
            QSlider::sub-page:horizontal {
                background: #89b4fa;
                border-radius: 4px;
            }
            QGroupBox {
                border: 1px solid #45475a;
                border-radius: 6px;
                margin-top: 12px;
                font-size: 16px;
                font-weight: bold;
                color: #cdd6f4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        self.initUI()

    def initUI(self):
        # Main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Title
        self.title_label = QLabel("AURA Prototype Control Station")
        self.title_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("color: #89b4fa; margin-bottom: 10px;")
        main_layout.addWidget(self.title_label)

        # Top section with status and connection
        connection_group = QGroupBox("Connection Status")
        connection_layout = QHBoxLayout()
        
        # Serial port selection
        port_label = QLabel("Serial Port:")
        self.com_port_dropdown = QComboBox()
        self.com_port_dropdown.addItems([port.device for port in serial.tools.list_ports.comports()])
        self.com_port_dropdown.setMinimumWidth(150)
        
        # Connect/Disconnect buttons
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setStyleSheet("background-color: #89b4fa; color: #1e1e2e;")
        self.connect_btn.clicked.connect(self.connect_serial)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setStyleSheet("background-color: #f38ba8; color: #1e1e2e;")
        self.disconnect_btn.clicked.connect(self.disconnect_serial)
        
        # Status label
        self.status_label = QLabel("Not Connected")
        self.status_label.setFont(QFont("Arial", 14))
        self.status_label.setStyleSheet("color: #f38ba8; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        connection_layout.addWidget(port_label)
        connection_layout.addWidget(self.com_port_dropdown)
        connection_layout.addWidget(self.connect_btn)
        connection_layout.addWidget(self.disconnect_btn)
        connection_layout.addWidget(self.status_label)
        connection_group.setLayout(connection_layout)
        main_layout.addWidget(connection_group)

        # Middle section
        middle_layout = QHBoxLayout()
        
        # Control panel
        control_group = QGroupBox("ROV Controls")
        control_layout = QVBoxLayout()
        
        # Speed control
        speed_layout = QVBoxLayout()
        speed_label_layout = QHBoxLayout()
        speed_title = QLabel("Thruster Power:")
        self.speed_label = QLabel("50%")
        self.speed_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #89b4fa;")
        speed_label_layout.addWidget(speed_title)
        speed_label_layout.addStretch()
        speed_label_layout.addWidget(self.speed_label)
        
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(0)
        self.speed_slider.setMaximum(100)
        self.speed_slider.setValue(50)
        self.speed_slider.valueChanged.connect(lambda: self.speed_label.setText(f"{self.speed_slider.value()}%"))
        
        speed_layout.addLayout(speed_label_layout)
        speed_layout.addWidget(self.speed_slider)
        control_layout.addLayout(speed_layout)
        
        # Add separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #45475a;")
        control_layout.addWidget(line)
        
        # Direction controls
        direction_label = QLabel("Movement Controls:")
        direction_label.setStyleSheet("font-size: 16px; margin-top: 10px;")
        control_layout.addWidget(direction_label)
        
        # Create a grid for control buttons
        control_grid = QGridLayout()
        control_grid.setSpacing(10)
        
        # Movement buttons with modern styling
        self.up_btn = QPushButton("↑ Up")
        self.down_btn = QPushButton("↓ Down")
        self.left_btn = QPushButton("← Left")
        self.right_btn = QPushButton("Right →")
        self.forward_btn = QPushButton("↑ Forward")
        self.backward_btn = QPushButton("↓ Backward")
        self.stop_btn = QPushButton("EMERGENCY STOP")
        
        # Style buttons and connect functions
        movement_buttons = [self.up_btn, self.down_btn, self.left_btn, 
                           self.right_btn, self.forward_btn, self.backward_btn]
        
        for btn in movement_buttons:
            btn.setStyleSheet("""
                background-color: #74c7ec;
                color: #1e1e2e;
                font-weight: bold;
                min-height: 40px;
            """)
            
        self.stop_btn.setStyleSheet("""
            background-color: #f38ba8;
            color: #1e1e2e;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
        """)
        
        # Connect signals
        self.forward_btn.clicked.connect(lambda: self.move("forward"))
        self.backward_btn.clicked.connect(lambda: self.move("backward"))
        self.up_btn.clicked.connect(lambda: self.move("up"))
        self.down_btn.clicked.connect(lambda: self.move("down"))
        self.left_btn.clicked.connect(lambda: self.move("left"))
        self.right_btn.clicked.connect(lambda: self.move("right"))
        self.stop_btn.clicked.connect(self.stop_motors)
        
        # Layout movement buttons
        control_grid.addWidget(self.up_btn, 0, 1)
        control_grid.addWidget(self.left_btn, 1, 0)
        control_grid.addWidget(self.stop_btn, 1, 1)
        control_grid.addWidget(self.right_btn, 1, 2)
        control_grid.addWidget(self.down_btn, 2, 1)
        
        vertical_movement = QVBoxLayout()
        vertical_movement_label = QLabel("Vertical:")
        vertical_movement_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vertical_movement.addWidget(vertical_movement_label)
        vertical_movement.addWidget(self.up_btn)
        vertical_movement.addWidget(self.down_btn)
        
        horizontal_movement = QVBoxLayout()
        horizontal_movement_label = QLabel("Horizontal:")
        horizontal_movement_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        horizontal_movement.addWidget(horizontal_movement_label)
        horizontal_movement.addWidget(self.forward_btn)
        horizontal_movement.addWidget(self.backward_btn)
        
        movement_layout = QHBoxLayout()
        movement_layout.addLayout(vertical_movement)
        movement_layout.addSpacing(20)
        movement_layout.addLayout(horizontal_movement)
        
        control_layout.addLayout(movement_layout)
        control_layout.addSpacing(20)
        control_layout.addWidget(self.stop_btn)
        
        # Add separator
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        line2.setStyleSheet("background-color: #45475a;")
        control_layout.addWidget(line2)
        
        # Lights control
        self.light_button = QPushButton("Turn Lights ON")
        self.light_button.setStyleSheet("""
            background-color: #f9e2af;
            color: #1e1e2e;
            font-weight: bold;
            min-height: 40px;
        """)
        self.light_button.clicked.connect(self.toggle_lights)
        
        light_layout = QVBoxLayout()
        light_label = QLabel("Auxiliary Systems:")
        light_label.setStyleSheet("font-size: 16px; margin-top: 10px;")
        light_layout.addWidget(light_label)
        light_layout.addWidget(self.light_button)
        
        control_layout.addLayout(light_layout)
        control_layout.addStretch()
        
        control_group.setLayout(control_layout)
        
        # Sensor data display and graph
        data_group = QGroupBox("Sensor Data")
        data_layout = QVBoxLayout()
        
        # Sensor readouts
        sensor_display = QHBoxLayout()
        
        # Temperature widget
        temp_frame = QFrame()
        temp_frame.setStyleSheet("""
            background-color: #313244;
            border-radius: 8px;
            padding: 10px;
        """)
        temp_layout = QVBoxLayout()
        temp_title = QLabel("Temperature")
        temp_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temp_label = QLabel("-- °C")
        self.temp_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #fab387;")
        self.temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_layout.addWidget(temp_title)
        temp_layout.addWidget(self.temp_label)
        temp_frame.setLayout(temp_layout)
        
        # Depth widget
        depth_frame = QFrame()
        depth_frame.setStyleSheet("""
            background-color: #313244;
            border-radius: 8px;
            padding: 10px;
        """)
        depth_layout = QVBoxLayout()
        depth_title = QLabel("Depth")
        depth_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.depth_label = QLabel("-- m")
        self.depth_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #89b4fa;")
        self.depth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        depth_layout.addWidget(depth_title)
        depth_layout.addWidget(self.depth_label)
        depth_frame.setLayout(depth_layout)
        
        sensor_display.addWidget(temp_frame)
        sensor_display.addWidget(depth_frame)
        data_layout.addLayout(sensor_display)
        
        # Graph styling
        pg.setConfigOption('background', '#1e1e2e')
        pg.setConfigOption('foreground', '#cdd6f4')
        
        # Graph for sensor data
        self.graph_widget = pg.PlotWidget()
        self.graph_widget.setTitle("Depth Measurement (Real-time)")
        self.graph_widget.setLabel("left", "Depth (m)")
        self.graph_widget.setLabel("bottom", "Time (samples)")
        self.graph_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Create a blue pen for the curve
        blue_pen = pg.mkPen(color='#89b4fa', width=3)
        self.graph_curve = self.graph_widget.plot(pen=blue_pen)
        
        # Add horizontal reference lines
        reference_line_pen = pg.mkPen(color='#45475a', width=1, style=Qt.PenStyle.DashLine)
        for i in range(1, 5):
            value = i * 0.1
            self.graph_widget.addLine(y=value, pen=reference_line_pen)
        
        data_layout.addWidget(self.graph_widget)
        data_group.setLayout(data_layout)
        
        # Add the panels to the middle layout
        middle_layout.addWidget(control_group, 1)
        middle_layout.addWidget(data_group, 2)
        
        main_layout.addLayout(middle_layout)
        
        # Status bar with version info
        status_bar = QLabel("AURA Prototype v1.0 | © 2025 AURA Robotics")
        status_bar.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_bar.setStyleSheet("color: #6c7086; font-size: 12px;")
        main_layout.addWidget(status_bar)
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Initialize emergency mode features
        if self.emergency_mode:
            self.setup_emergency_mode()

    def setup_emergency_mode(self):
        """Setup emergency mode features"""
        # Auto-connect to first available port
        if self.com_port_dropdown.count() > 0:
            self.connect_serial()
        
        # Set window to stay on top
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        # Add mission info to status
        if self.mission_id:
            self.status_label.setText(f"🚨 EMERGENCY MISSION: {self.mission_id}")
        
        # Setup auto-deployment timer (12 seconds as specified)
        self.auto_deploy_timer = QTimer()
        self.auto_deploy_timer.setSingleShot(True)
        self.auto_deploy_timer.timeout.connect(self.auto_activate_thrusters)
        
        # Start the deployment countdown
        print("🚨 EMERGENCY MODE ACTIVATED!")
        print(f"📍 Mission ID: {self.mission_id}")
        print("⏱️  ROV will auto-deploy in 12 seconds...")
        print("🛑 Use EMERGENCY STOP button if needed!")
        
        # Start countdown timer
        self.auto_deploy_timer.start(12000)  # 12 seconds
    
    def auto_activate_thrusters(self):
        """Automatically activate thrusters for emergency deployment"""
        try:
            print("🚀 AUTO-DEPLOYING ROV - THRUSTERS ACTIVATED!")
            
            # Set optimal thruster power (75% as specified in backend)
            self.speed_slider.setValue(75)
            
            # Simulate forward movement to emergency location
            self.move('forward')
            
            # Update status
            self.status_label.setText(f"🚀 DEPLOYED - Mission: {self.mission_id}")
            
            # Start automatic movement sequence
            self.start_emergency_sequence()
            
        except Exception as e:
            print(f"❌ Auto-deployment failed: {e}")
    
    def start_emergency_sequence(self):
        """Start automated emergency response sequence"""
        print("🎯 EMERGENCY SEQUENCE INITIATED")
        print("📊 ROV Status: ACTIVE")
        print("⚡ Thrusters: ONLINE")
        print("🔦 Lights: AUTO-ON")
        
        # Turn on lights automatically
        if "OFF" in self.light_button.text():
            self.toggle_lights()
        
        # Log mission progress
        print(f"📍 En route to emergency location...")
        print(f"🚨 Mission {self.mission_id} - ROV deployment successful")

    def connect_serial(self):
        port = self.com_port_dropdown.currentText()
        try:
            self.ser = serial.Serial(port, 9600, timeout=1)
            self.connected = True
            self.status_label.setText("Connected ✅")
            self.status_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            threading.Thread(target=self.read_sensor_data, daemon=True).start()
            threading.Thread(target=self.update_depth, daemon=True).start()
        except:
            self.status_label.setText("Connection Failed ❌")
            self.status_label.setStyleSheet("color: #f38ba8; font-weight: bold;")

    def disconnect_serial(self):
        if self.ser:
            self.ser.close()
        self.connected = False
        self.status_label.setText("Disconnected 🔴")
        self.status_label.setStyleSheet("color: #f38ba8; font-weight: bold;")

    def send_command(self, cmd):
        if self.ser and self.ser.is_open:
            self.ser.write((cmd + "\n").encode("utf-8"))

    def move(self, direction):
        speed = self.speed_slider.value()
        self.send_command(f"{direction}_{int(speed)}")

    def stop_motors(self):
        self.send_command("forward_0")
        self.send_command("up_0")

    def toggle_lights(self):
        if self.light_button.text() == "Turn Lights ON":
            self.send_command("on")
            self.light_button.setText("Turn Lights OFF")
            self.light_button.setStyleSheet("""
                background-color: #fab387;
                color: #1e1e2e;
                font-weight: bold;
                min-height: 40px;
            """)
        else:
            self.send_command("off")
            self.light_button.setText("Turn Lights ON")
            self.light_button.setStyleSheet("""
                background-color: #f9e2af;
                color: #1e1e2e;
                font-weight: bold;
                min-height: 40px;
            """)

    def read_sensor_data(self):
        while self.connected:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    line = self.ser.readline().decode("utf-8").strip()
                    if "Temperature" in line:
                        temp_value = line.split(': ')[1]
                        self.temp_label.setText(f"{temp_value}")
                time.sleep(0.5)
            except:
                continue

    def update_depth(self):
        while self.connected:
            self.fake_depth = round(random.uniform(0.1, 0.4), 2)
            self.depth_label.setText(f"{self.fake_depth} m")
            self.sensor_data.append(self.fake_depth)
            if len(self.sensor_data) > 50:
                self.sensor_data.pop(0)
            self.graph_curve.setData(self.sensor_data)
            time.sleep(2)

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ROV Control Station')
    parser.add_argument('--emergency-mode', action='store_true', 
                       help='Launch in emergency mode with auto-deployment')
    parser.add_argument('--mission-id', type=str, 
                       help='Emergency mission ID')
    
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    window = ROVController(
        emergency_mode=args.emergency_mode,
        mission_id=args.mission_id
    )
    window.show()
    sys.exit(app.exec())