document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // --- Element References ---
    const btnGoto = document.getElementById('btn-goto');
    const btnClose = document.getElementById('btn-close');
    const btnMemPlus = document.getElementById('btn-mem-plus');
    const btnMem1 = document.getElementById('btn-mem1');
    const btnMem2 = document.getElementById('btn-mem2');
    const btnMem3 = document.getElementById('btn-mem3');
    const btnMem4 = document.getElementById('btn-mem4');
    const btnCalibrate = document.getElementById('btn-calibrate');
    const btnRelease = document.getElementById('btn-release');
    const btnReset = document.getElementById('btn-reset');

    const posGoto = document.getElementById('pos-goto');
    const effGoto = document.getElementById('eff-goto');
    const effClose = document.getElementById('eff-close');

    const statusPos = document.getElementById('status-pos');
    const statusEff = document.getElementById('status-eff');
    const statusGrasp = document.getElementById('status-grasp');
    const statusTemp = document.getElementById('status-temp');
    const statusErr = document.getElementById('status-err');

    // --- State ---
    let memSaveState = false;
    const memorySlots = {
        1: { btn: btnMem1, pos: 10, eff: 100 },
        2: { btn: btnMem2, pos: 50, eff: 100 },
        3: { btn: btnMem3, pos: 0, eff: 20 },
        4: { btn: btnMem4, pos: 40, eff: 100 },
    };

    // --- Functions ---
    function sendCommand(command, data = {}) {
        socket.emit('control_command', { command, ...data });
    }

    function updateMemoryButton(slot) {
        const { btn, pos, eff } = memorySlots[slot];
        btn.textContent = `P${pos} F${eff}`;
    }

    function handleMemoryClick(slot) {
        if (memSaveState) {
            memorySlots[slot].pos = parseInt(posGoto.value, 10);
            memorySlots[slot].eff = parseInt(effGoto.value, 10);
            updateMemoryButton(slot);
            memSaveState = false;
            btnMemPlus.style.backgroundColor = ''; // Reset color
        } else {
            const { pos, eff } = memorySlots[slot];
            sendCommand('goto', { position: pos, effort: eff });
        }
    }

    // --- Event Listeners ---
    btnGoto.addEventListener('click', () => {
        sendCommand('goto', {
            position: parseInt(posGoto.value, 10),
            effort: parseInt(effGoto.value, 10),
        });
    });

    btnClose.addEventListener('click', () => {
        sendCommand('close', { effort: parseInt(effClose.value, 10) });
    });

    btnCalibrate.addEventListener('click', () => sendCommand('calibrate'));
    btnRelease.addEventListener('click', () => sendCommand('release'));
    btnReset.addEventListener('click', () => sendCommand('reset'));

    btnMemPlus.addEventListener('click', () => {
        memSaveState = true;
        btnMemPlus.style.backgroundColor = '#f44336'; // Indicate save mode
    });

    btnMem1.addEventListener('click', () => handleMemoryClick(1));
    btnMem2.addEventListener('click', () => handleMemoryClick(2));
    btnMem3.addEventListener('click', () => handleMemoryClick(3));
    btnMem4.addEventListener('click', () => handleMemoryClick(4));

    // --- Socket.IO Listeners ---
    socket.on('connect', () => {
        console.log('Connected to server');
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from server');
    });

    socket.on('gripper_state', (data) => {
        statusPos.textContent = data.position.toFixed(1);
        statusEff.textContent = data.effort.toFixed(1);
        statusGrasp.textContent = data.grasp_state;
        statusTemp.textContent = `${data.temperature}°C`;
        statusErr.textContent = data.error;
    });

    // Initialize button text
    for (let i = 1; i <= 4; i++) {
        updateMemoryButton(i);
    }
});
