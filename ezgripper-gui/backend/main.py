import asyncio
import socketio
import threading
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorStates_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_

# --- DDS Communication Setup ---
# This GUI will control the 'left' gripper by default.
SIDE = "left"
DOMAIN = 0

ChannelFactoryInitialize(DOMAIN)

# Publisher for commands
cmd_topic_name = f"rt/dex1/{SIDE}/cmd"
cmd_publisher = ChannelPublisher(cmd_topic_name, MotorCmds_)
cmd_publisher.Init()

# Subscriber for state
state_topic_name = f"rt/dex1/{SIDE}/state"
state_subscriber = ChannelSubscriber(state_topic_name, MotorStates_)
state_subscriber.Init()

# --- FastAPI and Socket.IO Setup ---
sio = socketio.AsyncServer(async_mode='asgi')
app = FastAPI()
# Mount the Socket.IO app
app.mount('/socket.io', app=socketio.ASGIApp(sio))
# Serve static files for the frontend
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")

# --- Background DDS Listener ---
stop_event = threading.Event()

def dds_listener():
    """Listens for DDS messages and emits them to clients via Socket.IO."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    print(f"DDS listener thread started for topic: {state_topic_name}")
    while not stop_event.is_set():
        try:
            state_msg = state_subscriber.Read(timeout=1.0) # 1 second timeout
            if state_msg and state_msg.states:
                state = state_msg.states[0]
                # Convert EZGripper position (0-100) to Dex1 radians (0-5.4)
                max_open = 100.0 # Assuming 100% is max open for GUI
                position_100 = (state.q / 5.4) * 100.0
                position_pct = (position_100 / 100.0) * max_open

                loop.run_until_complete(sio.emit('gripper_state', {
                    'position': position_pct,
                    'effort': state.tau_est, # Using estimated torque as effort
                    'grasp_state': 'N/A', # This info is not in MotorStates_
                    'temperature': state.temperature,
                    'error': state.motor_error,
                }))
        except Exception as e:
            print(f"Error in DDS listener: {e}")
            time.sleep(1)
    print("DDS listener thread stopped.")

# --- Socket.IO Event Handlers ---
@sio.event
def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
def disconnect(sid):
    print(f"Client disconnected: {sid}")

def ezgripper_to_dex1_q(position_pct: float) -> float:
    """Convert EZGripper position (0-100) to Dex1 radians (0-5.4)."""
    max_open = 100.0 # Assuming 100% is max open for GUI
    position_100 = (position_pct / max_open) * 100.0
    pct_clamped = max(0.0, min(100.0, position_100))
    return (pct_clamped / 100.0) * 5.4

@sio.event
def control_command(sid, data):
    """Receives a command from the frontend and publishes it to DDS."""
    print(f"Received command from {sid}: {data}")
    command_type = data.get('command')
    pos_pct = data.get('position', 0.0)
    # NOTE: Effort from GUI is not directly used; tau is set for position control.

    q_rads = 0.0
    tau_nm = 3.0 # Default torque for position moves
    is_calibration_cmd = False

    if command_type == 'goto':
        q_rads = ezgripper_to_dex1_q(pos_pct)
    elif command_type == 'close':
        q_rads = ezgripper_to_dex1_q(0)
    elif command_type == 'release':
        q_rads = ezgripper_to_dex1_q(100)
    elif command_type == 'reset':
        q_rads = ezgripper_to_dex1_q(100)
    elif command_type == 'calibrate':
        # Use a special tau value to signal a calibration command to the driver
        is_calibration_cmd = True
        tau_nm = 1.0 # As per driver logic for CALIBRATE command
        print("Calibration command triggered.")

    # Create and publish the DDS command
    motor_cmd = unitree_go_msg_dds__MotorCmd_()
    motor_cmd.q = q_rads
    motor_cmd.dq = 0.0
    motor_cmd.tau = tau_nm
    motor_cmd.kp = 10.0 # Position stiffness
    motor_cmd.kd = 1.0  # Damping

    cmd_msg = MotorCmds_()
    cmd_msg.cmds.append(motor_cmd)
    cmd_publisher.Write(cmd_msg)
    print(f"Published DDS command: q={motor_cmd.q:.2f} rad, tau={motor_cmd.tau:.2f} Nm")

# --- Application Lifecycle ---
@app.on_event("startup")
def startup_event():
    print("Starting DDS listener...")
    dds_thread = threading.Thread(target=dds_listener, daemon=True)
    dds_thread.start()

@app.on_event("shutdown")
def shutdown_event():
    print("Stopping DDS listener...")
    stop_event.set()

if __name__ == '__main__':
    import uvicorn
    print("Starting server...")
    # Note: The main entry point for serving is via uvicorn command
    # uvicorn backend.main:app --reload
    # This block is for direct execution context.
    uvicorn.run(app, host="127.0.0.1", port=8000)
