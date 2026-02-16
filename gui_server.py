#!/usr/bin/env python3
"""
Independent GUI Server for EZGripper
Connects to existing DDS interfaces without modifying driver flow
"""

import asyncio
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EZGripperGUIHandler(BaseHTTPRequestHandler):
    """HTTP API handler for GUI"""
    
    def __init__(self, gui_server, *args, **kwargs):
        self.gui_server = gui_server
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Get current state from DDS
            state = self.gui_server.get_current_state()
            response = json.dumps(state).encode()
            self.wfile.write(response)
        elif self.path == '/' or self.path == '/index.html':
            self.serve_file('gui_frontend/index.html', 'text/html')
        elif self.path == '/style.css':
            self.serve_file('gui_frontend/style.css', 'text/css')
        elif self.path == '/script.js':
            self.serve_file('gui_frontend/script.js', 'application/javascript')
        elif self.path == '/favicon.ico':
            # Return a simple 1x1 transparent GIF to avoid 404
            self.send_response(200)
            self.send_header('Content-type', 'image/gif')
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(bytes.fromhex('4749463839610100010000000021F90401000000002C00000000010001000002024401003B'))
        elif self.path == '/mode':
            # Get current mode
            mode_info = {
                'watcher_mode': self.gui_server.watcher_mode,
                'control_mode_enabled': self.gui_server.control_mode_enabled
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(mode_info).encode())
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests for commands"""
        if self.path == '/command':
            # Send command to gripper
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                command = json.loads(post_data.decode('utf-8'))
                result = self.gui_server.send_command(command)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        elif self.path == '/mode/enable':
            # Enable control mode
            result = self.gui_server.enable_control_mode()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        elif self.path == '/mode/disable':
            # Disable control mode
            result = self.gui_server.disable_control_mode()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        else:
            self.send_error(404)
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def serve_file(self, filename, content_type):
        """Serve static files"""
        try:
            with open(filename, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)
    
    def log_message(self, format, *args):
        """Suppress HTTP logging"""
        pass


class EZGripperGUIServer:
    """Independent GUI Server that connects to existing DDS"""
    
    def __init__(self, side='left', domain=0, http_port=8000):
        self.side = side
        self.domain = domain
        self.http_port = http_port
        
        # Start in watcher mode by default - safe monitoring only
        self.watcher_mode = True
        self.control_mode_enabled = False
        
        # DDS topics - proper interface separation
        self.dex1_cmd_topic = f"rt/dex1/{side}/cmd"
        self.dex1_state_topic = f"rt/dex1/{side}/state"
        self.telemetry_topic = f"rt/gripper/{side}/telemetry"
        
        # Current state cache - separate for command and state interfaces
        self.command_state = {
            'desired_position': 0.0,
            'desired_effort': 0.0,
            'timestamp': time.time()
        }
        
        self.actual_state = {
            'actual_position': 0.0,
            'actual_effort': 0.0,
            'temperature': 0.0,
            'error': 0,
            'state': 'idle',
            'timestamp': time.time()
        }
        
        # Initialize DDS connection
        self.init_dds()
        
        # Start HTTP server
        self.start_http_server()
    
    def init_dds(self):
        """Initialize DDS connection to existing topics"""
        try:
            # Import here to avoid dependency issues if not available
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
            from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorStates_
            
            ChannelFactoryInitialize(self.domain)
            
            # Always subscribe to state topics (watcher mode always available)
            self.dex1_state_subscriber = ChannelSubscriber(self.dex1_state_topic, MotorStates_)
            self.dex1_state_subscriber.Init(self.dex1_state_callback)
            
            # EZGripper Interface - Subscriber for state (rich status data)
            from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_
            ezgripper_state_topic = f"rt/ezgripper/{self.side}/state"
            self.ezgripper_state_subscriber = ChannelSubscriber(ezgripper_state_topic, String_)
            self.ezgripper_state_subscriber.Init(self.ezgripper_state_callback)
            
            # Command publishers only in control mode
            if self.control_mode_enabled:
                # Dex1 Interface - Publisher for commands (to existing driver)
                self.dex1_cmd_publisher = ChannelPublisher(self.dex1_cmd_topic, MotorCmds_)
                self.dex1_cmd_publisher.Init()
                
                # Dex1 Interface - Subscriber for commands (to see what we're sending)
                self.dex1_cmd_subscriber = ChannelSubscriber(self.dex1_cmd_topic, MotorCmds_)
                self.dex1_cmd_subscriber.Init(self.dex1_command_callback)
                
                # EZGripper Interface - Publisher for admin commands
                ezgripper_admin_topic = f"rt/ezgripper/{self.side}/admin"
                self.ezgripper_admin_publisher = ChannelPublisher(ezgripper_admin_topic, String_)
                self.ezgripper_admin_publisher.Init()
                
                logger.info(f"Connected to DDS topics (CONTROL MODE):")
                logger.info(f"  Dex1: {self.dex1_cmd_topic} → {self.dex1_state_topic}")
                logger.info(f"  EZGripper: {ezgripper_admin_topic} → {ezgripper_state_topic}")
            else:
                # Watcher mode - no command publishers
                self.dex1_cmd_publisher = None
                self.dex1_cmd_subscriber = None
                self.ezgripper_admin_publisher = None
                
                logger.info(f"Connected to DDS topics (WATCHER MODE):")
                logger.info(f"  Dex1: {self.dex1_state_topic} (read-only)")
                logger.info(f"  EZGripper: {ezgripper_state_topic} (read-only)")
            
        except ImportError as e:
            logger.error(f"DDS not available: {e}")
            logger.info("Running in simulation mode")
            self.cmd_publisher = None
            self.state_subscriber = None
            
        except Exception as e:
            logger.error(f"DDS initialization failed: {e}")
            self.dex1_cmd_publisher = None
            self.dex1_state_subscriber = None
            self.dex1_cmd_subscriber = None
            self.telemetry_subscriber = None
    
    def dex1_command_callback(self, msg):
        """Callback for DDS command messages (to see what we're sending)"""
        try:
            if hasattr(msg, 'cmds') and len(msg.cmds) > 0:
                cmd = msg.cmds[0]
                
                # Extract desired values from command
                desired_q = getattr(cmd, 'q', 0.0)
                desired_tau = getattr(cmd, 'tau', 0.0)
                
                # Convert to GUI units
                desired_pos_pct = self.dex1_to_ezgripper(desired_q)
                desired_eff_pct = desired_tau * 10.0
                
                self.command_state.update({
                    'desired_position': desired_pos_pct,
                    'desired_effort': desired_eff_pct,
                    'timestamp': time.time()
                })
                
                logger.debug(f"Command: desired_pos={desired_pos_pct:.1f}%, desired_eff={desired_eff_pct:.1f}%")
                
        except Exception as e:
            logger.error(f"Dex1 command callback error: {e}")
    
    def telemetry_callback(self, msg):
        """Callback for EZGripper telemetry messages (rich status data)"""
        try:
            # Parse JSON telemetry data
            import json
            telemetry_data = json.loads(msg.data)
            
            # Extract rich telemetry information
            position_data = telemetry_data.get('position', {})
            grasp_data = telemetry_data.get('grasp_manager', {})
            contact_data = telemetry_data.get('contact_detection', {})
            health_data = telemetry_data.get('health', {})
            
            # Update actual state with rich telemetry data
            self.actual_state.update({
                'actual_position': position_data.get('actual_pct', 0.0),
                'actual_effort': grasp_data.get('managed_effort_pct', 0.0),
                'temperature': health_data.get('temperature_c', 0.0),
                'state': grasp_data.get('state', 'unknown'),
                'timestamp': telemetry_data.get('timestamp', time.time()),
                
                # Rich telemetry data
                'commanded_position': position_data.get('commanded_pct', 0.0),
                'position_error': position_data.get('error_pct', 0.0),
                'contact_detected': contact_data.get('detected', False),
                'current_ma': health_data.get('current_ma', 0.0),
                'voltage_v': health_data.get('voltage_v', 0.0),
                'is_moving': health_data.get('is_moving', False),
                'temperature_trend': health_data.get('temperature_trend', 'unknown'),
                'hardware_error': telemetry_data.get('hardware_error', 0),
                'hardware_error_description': telemetry_data.get('hardware_error_description', ''),
                
                # Calibration and error status (will be added to telemetry)
                'is_calibrated': False,  # TODO: Add to telemetry
                'serial_number': '',      # TODO: Add to telemetry
            })
            
            logger.debug(f"Telemetry: pos={self.actual_state['actual_position']:.1f}%, "
                        f"state={self.actual_state['state']}, "
                        f"temp={self.actual_state['temperature']:.1f}°C")
                
        except Exception as e:
            logger.error(f"EZGripper state callback error: {e}")
    
    def ezgripper_state_callback(self, msg):
        """Callback for EZGripper state messages (rich status data)"""
        try:
            # Parse JSON state data
            import json
            state_data = json.loads(msg.data)
            
            # Extract rich EZGripper state information
            position_data = state_data.get('position', {})
            grasp_data = state_data.get('grasp_manager', {})
            hardware_data = state_data.get('hardware', {})
            calibration_data = state_data.get('calibration', {})
            health_data = state_data.get('health', {})
            
            # Update actual state with rich EZGripper data
            self.actual_state.update({
                'actual_position': position_data.get('actual_pct', 0.0),
                'actual_effort': state_data.get('effort', {}).get('actual_pct', 0.0),
                'temperature': hardware_data.get('temperature_c', 0.0),
                'state': grasp_data.get('state_name', 'unknown').lower(),
                'timestamp': state_data.get('timestamp', time.time()),
                
                # Rich EZGripper data
                'current_ma': hardware_data.get('current_ma', 0.0),
                'voltage_v': hardware_data.get('voltage_v', 0.0),
                'hardware_error': hardware_data.get('error', 0),
                'hardware_error_description': hardware_data.get('error_description', ''),
                'is_calibrated': calibration_data.get('is_calibrated', False),
                'calibration_offset': calibration_data.get('offset', 0.0),
                'serial_number': calibration_data.get('serial_number', ''),
                'is_moving': health_data.get('is_moving', False),
                'temperature_trend': health_data.get('temperature_trend', 'unknown'),
                'contact_detected': health_data.get('contact_detected', False),
                'error_recovery_available': state_data.get('error_recovery', {}).get('available', False),
            })
            
            logger.debug(f"EZGripper State: pos={self.actual_state['actual_position']:.1f}%, "
                        f"state={self.actual_state['state']}, "
                        f"calibrated={self.actual_state['is_calibrated']}")
                
        except Exception as e:
            logger.error(f"EZGripper state callback error: {e}")
    
    def dex1_state_callback(self, msg):
        """Callback for DDS state messages"""
        try:
            # Parse the actual DDS message structure from the driver
            if hasattr(msg, 'states') and len(msg.states) > 0:
                state = msg.states[0]
                
                # Extract actual values from DDS message
                position_q = getattr(state, 'q', 0.0)
                effort_tau = getattr(state, 'tau', 0.0)
                temperature = getattr(state, 'temperature', 0)
                mode = getattr(state, 'mode', 0)
                lost = getattr(state, 'lost', 0)
                reserve = getattr(state, 'reserve', [0, 0])
                
                # Convert from DDS units to GUI units
                # Position: convert from radians back to percentage
                position_pct = self.dex1_to_ezgripper(position_q)
                
                # Effort: convert from DDS units back to percentage
                effort_pct = effort_tau * 10.0  # Driver divides by 10, so multiply back
                
                # Map mode back to grasp state
                mode_to_state = {
                    0: 'idle',
                    1: 'moving',
                    2: 'contact', 
                    3: 'grasping',
                    255: 'error'
                }
                grasp_state = mode_to_state.get(mode, 'unknown')
                
                # Extract error from reserve field
                error_code = reserve[0] if isinstance(reserve, list) and len(reserve) > 0 else 0
                
                self.actual_state.update({
                    'actual_position': position_pct,
                    'actual_effort': effort_pct,
                    'temperature': float(temperature),
                    'error': error_code,
                    'state': grasp_state,
                    'timestamp': time.time()
                })
                
                logger.debug(f"DDS State: actual_pos={position_pct:.1f}%, actual_eff={effort_pct:.1f}%, temp={temperature}°C, state={grasp_state}")
            else:
                logger.warning("Received DDS message without states array")
                
        except Exception as e:
            logger.error(f"State callback error: {e}")
    
    def dex1_to_ezgripper(self, q):
        """Convert from Dex1 radians to EZGripper percentage"""
        # Reverse of the conversion in the driver
        # Driver: current_q = (0.0 - 5.4) * (pos_pct / 100.0) + 5.4
        # Reverse: pos_pct = (current_q - 5.4) / (0.0 - 5.4) * 100.0
        pos_pct = (q - 5.4) / (0.0 - 5.4) * 100.0
        return max(0.0, min(100.0, pos_pct))
    
    def enable_control_mode(self):
        """Enable control mode with warning"""
        if self.control_mode_enabled:
            return {"already_enabled": True}
        
        logger.warning("🚨 ENABLING CONTROL MODE - GUI can now send commands")
        self.control_mode_enabled = True
        self.watcher_mode = False
        
        # Initialize command publishers using existing DDS infrastructure
        try:
            from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber
            from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_
            from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_
            
            # Dex1 command publisher
            self.dex1_cmd_publisher = ChannelPublisher(self.dex1_cmd_topic, MotorCmds_)
            self.dex1_cmd_publisher.Init()
            
            # Dex1 command subscriber (to see what we're sending)
            self.dex1_cmd_subscriber = ChannelSubscriber(self.dex1_cmd_topic, MotorCmds_)
            self.dex1_cmd_subscriber.Init(self.dex1_command_callback)
            
            # EZGripper admin publisher
            ezgripper_admin_topic = f"rt/ezgripper/{self.side}/admin"
            self.ezgripper_admin_publisher = ChannelPublisher(ezgripper_admin_topic, String_)
            self.ezgripper_admin_publisher.Init()
            
            logger.info("✅ Control mode enabled - command publishers initialized")
            return {"enabled": True}
            
        except Exception as e:
            logger.error(f"Failed to enable control mode: {e}")
            self.control_mode_enabled = False
            self.watcher_mode = True
            return {"error": str(e)}
    
    def disable_control_mode(self):
        """Disable control mode - return to watcher mode"""
        if not self.control_mode_enabled:
            return {"already_disabled": True}
        
        logger.info("🔒 DISABLING CONTROL MODE - returning to watcher mode")
        self.control_mode_enabled = False
        self.watcher_mode = True
        
        # Remove command publishers
        self.dex1_cmd_publisher = None
        self.dex1_cmd_subscriber = None
        self.ezgripper_admin_publisher = None
        
        return {"disabled": True}
    
    def send_command(self, command):
        """Send command via DDS to existing driver"""
        try:
            if self.watcher_mode:
                logger.warning("Command rejected - GUI is in WATCHER MODE")
                return {"error": "GUI is in watcher mode - cannot send commands"}
            
            if self.dex1_cmd_publisher is None:
                logger.warning("DDS not available - simulating command")
                return {"simulated": True, "command": command}
            
            # Handle calibration command (special case)
            if 'action' in command and command['action'] == 'calibrate':
                return self.send_calibration_command()
            
            # Create command message matching the driver's expected format
            from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_
            from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_
            
            cmd_msg = unitree_go_msg_dds__MotorCmd_()
            cmd_msg.mode = 0  # Position mode
            cmd_msg.dq = 0.0  # Velocity command
            cmd_msg.reserve = [0, 0, 0]  # Reserved field (array of 3 ints)
            
            if 'action' in command:
                action = command['action']
                
                if action == 'go' and 'position' in command and 'effort' in command:
                    # Convert GUI units to DDS units
                    pos_pct = command['position']
                    eff_pct = command['effort']
                    
                    # Convert position to radians (driver conversion)
                    q = (0.0 - 5.4) * (pos_pct / 100.0) + 5.4
                    
                    # Convert effort to DDS units (driver divides by 10)
                    tau = eff_pct / 10.0
                    
                    # Set motor command
                    cmd_msg.q = q
                    cmd_msg.tau = tau
                    cmd_msg.kp = 0.0  # Position gain
                    cmd_msg.kd = 0.0  # Damping gain
                    
                    logger.info(f"Go command: pos={pos_pct:.1f}%→{q:.3f}rad, eff={eff_pct:.1f}%→{tau:.1f}")
                    
                elif action == 'stop':
                    # Stop command - zero effort
                    cmd_msg.q = 0.0
                    cmd_msg.tau = 0.0
                    cmd_msg.kp = 0.0
                    cmd_msg.kd = 0.0
                    
                    logger.info("Stop command sent")
                    
                elif action == 'release':
                    # Release command - zero effort, maintain position
                    cmd_msg.tau = 0.0
                    cmd_msg.kp = 0.0
                    cmd_msg.kd = 0.0
                    
                    logger.info("Release command sent")
            
            # Create command array and send
            cmd_msgs = MotorCmds_()
            cmd_msgs.cmds = [cmd_msg]
            
            # Send the command
            self.dex1_cmd_publisher.Write(cmd_msgs)
            
            return {"sent": True, "command": command}
            
        except Exception as e:
            logger.error(f"Send command error: {e}")
            return {"error": str(e)}
    
    def send_calibration_command(self):
        """Send calibration command via EZGripper interface"""
        try:
            logger.info("Sending calibration command via EZGripper interface...")
            
            # Create EZGripper command message
            cmd_data = {
                'action': 2,  # EZGripperAction.CALIBRATE
                'parameters': {}
            }
            
            # Send via EZGripper interface
            import json
            from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_
            
            json_str = json.dumps(cmd_data)
            msg = String_(data=json_str)
            self.ezgripper_admin_publisher.Write(msg)
            
            logger.info("Calibration command sent via EZGripper interface")
            return {"sent": True, "command": "calibrate"}
            
        except Exception as e:
            logger.error(f"Calibration command error: {e}")
            return {"error": str(e)}
    
    def get_current_state(self):
        """Get current gripper state from both DDS interfaces"""
        return {
            'command_interface': self.command_state.copy(),
            'state_interface': self.actual_state.copy(),
            'connection_status': {
                'dds_connected': self.dex1_cmd_publisher is not None,
                'last_command_time': self.command_state.get('timestamp', 0),
                'last_state_time': self.actual_state.get('timestamp', 0)
            }
        }
    
    def start_http_server(self):
        """Start HTTP server for GUI"""
        def handler(*args, **kwargs):
            return EZGripperGUIHandler(self, *args, **kwargs)
        
        self.http_server = HTTPServer(('0.0.0.0', self.http_port), handler)
        
        # Start server in separate thread
        server_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        server_thread.start()
        
        logger.info(f"GUI server started at http://0.0.0.0:{self.http_port}")
    
    def run(self):
        """Main run loop"""
        try:
            logger.info("GUI server running... Press Ctrl+C to stop")
            while True:
                time.sleep(1)
                # Update timestamps to show server is alive
                self.command_state['timestamp'] = time.time()
                self.actual_state['timestamp'] = time.time()
        except KeyboardInterrupt:
            logger.info("Stopping GUI server...")
            self.http_server.shutdown()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="EZGripper GUI Server")
    parser.add_argument("--side", default="left", choices=["left", "right"], help="Gripper side")
    parser.add_argument("--domain", type=int, default=0, help="DDS domain")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    logging.basicConfig(level=getattr(logging, args.log_level))
    
    # Create and run server
    server = EZGripperGUIServer(side=args.side, domain=args.domain, http_port=args.port)
    server.run()


if __name__ == "__main__":
    main()
