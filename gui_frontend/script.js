class EZGripperGUI {
    constructor() {
        this.connected = false;
        this.connectionLogged = false;  // Prevent repeated connection messages
        this.logPaused = false;
        this.init();
    }

    // Coordinate conversion functions
    ezgripperToDisplay(ezgripperPos) {
        // Convert EZGripper coordinates (0% = closed, 100% = open) 
        // to display coordinates (100% = closed, 0% = open)
        return 100.0 - ezgripperPos;
    }

    displayToEzgripper(displayPos) {
        // Convert display coordinates (100% = closed, 0% = open)
        // to EZGripper coordinates (0% = closed, 100% = open)  
        return 100.0 - displayPos;
    }

    init() {
        this.initEventListeners();
        this.startStatusUpdates();
        this.updateModeDisplay();
        this.log('EZGripper GUI initialized in WATCHER MODE', 'success');
    }

    initEventListeners() {
        // Position slider
        const positionSlider = document.getElementById('position-slider');
        const positionValue = document.getElementById('position-value');
        positionSlider.addEventListener('input', (e) => {
            const displayPosition = parseFloat(e.target.value);
            positionValue.textContent = displayPosition + '%';
            // Convert display position to EZGripper position for desired display
            const ezgripperPosition = this.displayToEzgripper(displayPosition);
            document.getElementById('desired-position').textContent = ezgripperPosition.toFixed(1) + '%';
        });

        // Display force settings from config
        this.displayForceSettings();

        // Control buttons
        document.getElementById('go-button').addEventListener('click', () => this.go());
        document.getElementById('stop-button').addEventListener('click', () => this.stop());
        document.getElementById('release-button').addEventListener('click', () => this.release());
        document.getElementById('calibrate-button').addEventListener('click', () => this.calibrate());

        // Preset buttons
        document.querySelectorAll('.btn-preset').forEach(button => {
            button.addEventListener('click', (e) => {
                const position = parseInt(e.target.dataset.position);
                const effort = parseInt(e.target.dataset.effort);
                // Update desired position display immediately
                document.getElementById('desired-position').textContent = position.toFixed(1) + '%';
                document.getElementById('desired-effort').textContent = effort.toFixed(1) + '%';
                // Update sliders to match preset
                document.getElementById('position-slider').value = position;
                document.getElementById('effort-slider').value = effort;
                document.getElementById('position-value').textContent = position + '%';
                document.getElementById('effort-value').textContent = effort + '%';
                this.goToPreset(position, effort);
            });
        });
        
        // Mode control buttons
        document.getElementById('enable-control-btn').addEventListener('click', () => this.enableControlMode());
        document.getElementById('disable-control-btn').addEventListener('click', () => this.disableControlMode());
        
        // Log control buttons
        document.getElementById('log-pause-btn').addEventListener('click', () => this.toggleLogPause());
        document.getElementById('log-clear-btn').addEventListener('click', () => this.clearLog());
    }

    async go() {
        const displayPosition = parseFloat(document.getElementById('position-slider').value);
        // Convert display position to EZGripper coordinates for command
        const ezgripperPosition = this.displayToEzgripper(displayPosition);
        
        await this.sendCommand({
            action: 'go',
            position: ezgripperPosition
        });
        
        this.log(`Go: Position=${displayPosition}% (display) → ${ezgripperPosition.toFixed(1)}% (EZGripper)`, 'info');
    }

    displayForceSettings() {
        // Display force settings from config (these are the actual values being used)
        document.getElementById('moving-force').textContent = '50%';
        document.getElementById('grasping-force').textContent = '15%';
        document.getElementById('idle-force').textContent = '10%';
    }

    async stop() {
        await this.sendCommand({
            action: 'stop'
        });
        
        this.log('Stop command sent', 'warning');
    }

    async release() {
        await this.sendCommand({
            action: 'release'
        });
        
        this.log('Release command sent', 'warning');
    }

    async calibrate() {
        this.log('Starting calibration...', 'warning');
        
        const result = await this.sendCommand({
            action: 'calibrate'
        });
        
        if (result.error) {
            this.log(`Calibration failed: ${result.error}`, 'error');
        } else {
            this.log('Calibration command sent - please wait 5 seconds', 'success');
            this.log('Gripper will close to find zero position, then move to 50%', 'info');
        }
    }

    async goToPreset(position, effort) {
        // Update sliders
        document.getElementById('position-slider').value = position;
        document.getElementById('position-value').textContent = position + '%';
        document.getElementById('effort-slider').value = effort;
        document.getElementById('effort-value').textContent = effort + '%';
        
        // Send command
        await this.sendCommand({
            action: 'go',
            position: position,
            effort: effort
        });
        
        this.log(`Preset: Position=${position}%, Effort=${effort}%`, 'success');
    }

    async fetchWithTimeout(url, options = {}) {
        const timeout = options.timeout || 5000;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        
        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error('Request timeout');
            }
            throw error;
        }
    }

    async sendCommand(command) {
        try {
            const response = await fetch('/command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(command)
            });
            
            const result = await response.json();
            
            if (result.error) {
                this.log(`Command error: ${result.error}`, 'error');
            } else {
                this.log(`Command sent: ${command.action || 'unknown'}`, 'success');
            }
            
            return result;
        } catch (error) {
            this.log(`Network error: ${error.message}`, 'error');
            return { error: error.message };
        }
    }

    async updateStatus() {
        try {
            const response = await fetch('/status');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const state = await response.json();
            this.updateStatusDisplay(state);
            
            if (!this.connected) {
                this.connected = true;
                this.updateConnectionStatus(true);
                if (!this.connectionLogged) {
                    this.log('Connected to gripper', 'success');
                    this.connectionLogged = true;
                }
            }
        } catch (error) {
            if (this.connected) {
                this.connected = false;
                this.connectionLogged = false;  // Reset to allow reconnection message
                this.updateConnectionStatus(false);
                this.log(`Connection lost: ${error.message}`, 'error');
            }
        }
    }

    updateStatusDisplay(data) {
        // Command Interface (Desired Values)
        const cmd = data.command_interface || {};
        const desiredDisplayPos = cmd.desired_position ? this.ezgripperToDisplay(cmd.desired_position) : 0.0;
        document.getElementById('desired-position').textContent = desiredDisplayPos.toFixed(1) + '%';
        document.getElementById('last-command-time').textContent = cmd.timestamp ? this.formatTime(cmd.timestamp) : 'Never';
        
        // State Interface (Actual Values)
        const state = data.state_interface || {};
        const actualDisplayPos = state.actual_position ? this.ezgripperToDisplay(state.actual_position) : 0.0;
        document.getElementById('actual-position').textContent = actualDisplayPos.toFixed(1) + '%';
        document.getElementById('actual-effort').textContent = state.actual_effort ? state.actual_effort.toFixed(1) + '%' : '0.0%';
        document.getElementById('temperature').textContent = state.temperature ? state.temperature.toFixed(1) + '°C' : '0.0°C';
        document.getElementById('state').textContent = state.state || 'unknown';
        document.getElementById('error').textContent = state.error || '0';
        document.getElementById('last-state-time').textContent = state.timestamp ? this.formatTime(state.timestamp) : 'Never';
        
        // Connection Status
        const conn = data.connection_status || {};
        document.getElementById('dds-connected').textContent = conn.dds_connected ? 'Yes' : 'No';
        document.getElementById('dds-connected').className = conn.dds_connected ? 'yes' : 'no';
        
        // Calculate errors
        const posError = Math.abs((cmd.desired_position || 0) - (state.actual_position || 0));
        const effError = Math.abs((cmd.desired_effort || 0) - (state.actual_effort || 0));
        document.getElementById('position-error').textContent = posError.toFixed(1) + '%';
        document.getElementById('effort-error').textContent = effError.toFixed(1) + '%';
        
        // EZGripper-specific status (using actual DDS data)
        document.getElementById('is-calibrated').textContent = state.is_calibrated ? 'Yes' : 'No';
        document.getElementById('serial-number').textContent = state.serial_number || 'Unknown';
        document.getElementById('contact-position').textContent = 
            state.state === 'contact' || state.state === 'grasping' 
                ? state.actual_position.toFixed(1) + '%' : '-';
        document.getElementById('contact-detected').textContent = state.contact_detected ? 'Yes' : 'No';
        document.getElementById('current-ma').textContent = (state.current_ma || 0).toFixed(0) + 'mA';
        document.getElementById('voltage-v').textContent = (state.voltage_v || 0).toFixed(1) + 'V';
        document.getElementById('position-raw').textContent = 
            state.raw_q !== null && state.raw_q !== undefined
                ? state.raw_q.toFixed(3) + 'rad' : '-';
        document.getElementById('last-dds-position').textContent = 
            state.raw_q !== null && state.raw_q !== undefined
                ? this.dex1ToEzgripper(state.raw_q).toFixed(1) + '%' : '-';
        
        // Update connection status based on data freshness
        const now = Date.now() / 1000;
        const stateFresh = (now - (state.timestamp || 0)) < 1.0; // Fresh if less than 1 second old
        this.updateConnectionStatus(conn.dds_connected && stateFresh);
    }

    updateConnectionStatus(connected) {
        this.connected = connected;
    }

    formatTime(timestamp) {
        const date = new Date(timestamp * 1000);
        return date.toLocaleTimeString();
    }
    
    dex1ToEzgripper(q) {
        // Convert from Dex1 radians to EZGripper percentage
        // Reverse of the conversion in the driver
        // Driver: current_q = (0.0 - 5.4) * (pos_pct / 100.0) + 5.4
        // Reverse: pos_pct = (current_q - 5.4) / (0.0 - 5.4) * 100.0
        const pos_pct = (q - 5.4) / (0.0 - 5.4) * 100.0;
        return Math.max(0.0, Math.min(100.0, pos_pct));
    }

    startStatusUpdates() {
        // Update status every 100ms
        setInterval(() => {
            this.updateStatus();
        }, 100);

        // Initial update
        this.updateStatus();
    }

    async enableControlMode() {
        // Show warning dialog
        const warningBox = document.getElementById('mode-warning');
        warningBox.style.display = 'block';
        
        // Wait for user confirmation
        const confirmed = await this.showConfirmDialog(
            'Enable Control Mode',
            'This will allow sending commands to the gripper. Continue?'
        );
        
        warningBox.style.display = 'none';
        
        if (confirmed) {
            try {
                const result = await this.fetchWithTimeout('/mode/enable', {
                    method: 'POST'
                });
                
                if (result.enabled) {
                    this.log('⚠️ CONTROL MODE ENABLED - GUI can now send commands', 'warning');
                    this.updateModeDisplay();
                    this.enableControlButtons();
                } else {
                    this.log(`Failed to enable control mode: ${result.error}`, 'error');
                }
            } catch (error) {
                this.log(`Error enabling control mode: ${error.message}`, 'error');
            }
        }
    }

    async disableControlMode() {
        try {
            const result = await this.fetchWithTimeout('/mode/disable', {
                method: 'POST'
            });
            
            if (result.disabled) {
                this.log('🔒 Returned to WATCHER MODE - GUI cannot send commands', 'info');
                this.updateModeDisplay();
                this.disableControlButtons();
            } else {
                this.log(`Failed to disable control mode: ${result.error}`, 'error');
            }
        } catch (error) {
            this.log(`Error disabling control mode: ${error.message}`, 'error');
        }
    }

    async updateModeDisplay() {
        try {
            const modeInfo = await this.fetchWithTimeout('/mode');
            const modeText = document.getElementById('current-mode');
            const modeIndicator = document.getElementById('mode-indicator');
            
            if (modeInfo.control_mode_enabled) {
                modeText.textContent = 'CONTROL MODE';
                modeIndicator.className = 'indicator-warning';
                this.enableControlButtons();
            } else {
                modeText.textContent = 'WATCHER MODE';
                modeIndicator.className = 'indicator-safe';
                this.disableControlButtons();
            }
        } catch (error) {
            console.error('Failed to get mode info:', error);
        }
    }

    enableControlButtons() {
        document.getElementById('enable-control-btn').style.display = 'none';
        document.getElementById('disable-control-btn').style.display = 'inline-block';
        
        // Enable control buttons
        document.getElementById('go-button').disabled = false;
        document.getElementById('stop-button').disabled = false;
        document.getElementById('release-button').disabled = false;
        document.getElementById('calibrate-button').disabled = false;
        document.getElementById('position-slider').disabled = false;
        document.getElementById('effort-slider').disabled = false;
    }

    disableControlButtons() {
        document.getElementById('enable-control-btn').style.display = 'inline-block';
        document.getElementById('disable-control-btn').style.display = 'none';
        
        // Disable control buttons
        document.getElementById('go-button').disabled = true;
        document.getElementById('stop-button').disabled = true;
        document.getElementById('release-button').disabled = true;
        document.getElementById('calibrate-button').disabled = true;
        document.getElementById('position-slider').disabled = true;
        document.getElementById('effort-slider').disabled = true;
    }

    showConfirmDialog(title, message) {
        return new Promise((resolve) => {
            const confirmed = confirm(`${title}\n\n${message}`);
            resolve(confirmed);
        });
    }

    log(message, type = 'info') {
        const logArea = document.getElementById('log');
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = type;
        logEntry.textContent = `[${timestamp}] ${message}`;
        logArea.appendChild(logEntry);
        
        // Only auto-scroll if not paused and user is at bottom
        if (!this.logPaused && (logArea.scrollHeight - logArea.scrollTop - logArea.clientHeight) < 50) {
            logArea.scrollTop = logArea.scrollHeight;
        }
        
        // Limit log size
        while (logArea.children.length > 500) {
            logArea.removeChild(logArea.firstChild);
        }
    }

    toggleLogPause() {
        this.logPaused = !this.logPaused;
        const pauseBtn = document.getElementById('log-pause-btn');
        if (this.logPaused) {
            pauseBtn.textContent = 'Resume';
            pauseBtn.className = 'btn btn-success';
            this.log('📋 Log paused - scroll to read', 'info');
        } else {
            pauseBtn.textContent = 'Pause';
            pauseBtn.className = 'btn btn-secondary';
            this.log('📋 Log resumed - auto-scroll enabled', 'info');
            // Auto-scroll to bottom when resuming
            const logArea = document.getElementById('log');
            logArea.scrollTop = logArea.scrollHeight;
        }
    }

    clearLog() {
        const logArea = document.getElementById('log');
        logArea.innerHTML = '';
        this.log('📋 Log cleared', 'info');
    }
}

// Initialize GUI when page loads
document.addEventListener('DOMContentLoaded', () => {
    new EZGripperGUI();
});
