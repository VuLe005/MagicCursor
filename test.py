import tkinter as tk
import random
import pandas as pd
import time
import glob, sys, serial, os
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from serial import Serial
from threading import Thread, Event
from queue import Queue
#import psychopy.hardware.keyboard  # no longer needed here
import numpy as np

# ===========================
#  BrainFlow Setup Variables
# ===========================
lsl_out = False
save_dir = 'data/misc/'
run = 1  # Run number used for file naming
save_file_aux = os.path.join(save_dir, f'aux_run-{run}.npy')
sampling_rate = 250
CYTON_BOARD_ID = 0  # 0 if no daisy; 2 for daisy; 6 for daisy+wifi shield
BAUD_RATE = 115200
ANALOGUE_MODE = '/2'  # Reads from analog pins A5, A6 and (if no wifi shield) A7

# Stop event to signal termination for BrainFlow thread
stop_event = Event()
brainflow_eeg = np.zeros((8, 0))
brainflow_aux = np.zeros((3, 0))

def find_openbci_port():
    """Find the port for the OpenBCI dongle."""
    if sys.platform.startswith('win'):
        ports = [f'COM{i+1}' for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        ports = glob.glob('/dev/ttyUSB*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/cu.usbserial*')
    else:
        raise EnvironmentError('Error finding ports on your operating system')
    openbci_port = ''
    for port in ports:
        try:
            s = Serial(port=port, baudrate=BAUD_RATE, timeout=None)
            s.write(b'v')
            time.sleep(2)
            line = ''
            if s.inWaiting():
                c = ''
                while '$$$' not in line:
                    c = s.read().decode('utf-8', errors='replace')
                    line += c
                if 'OpenBCI' in line:
                    openbci_port = port
            s.close()
        except (OSError, serial.SerialException):
            pass
    if openbci_port == '':
        raise OSError('Cannot find OpenBCI port.')
    return openbci_port

def brainflow_thread_func():
    """Initialize the board, start streaming, and continuously collect data until signaled to stop."""
    global brainflow_eeg, brainflow_aux
    print(BoardShim.get_board_descr(CYTON_BOARD_ID))
    params = BrainFlowInputParams()
    if CYTON_BOARD_ID != 6:
        params.serial_port = find_openbci_port()
    else:
        params.ip_port = 9000
    board = BoardShim(CYTON_BOARD_ID, params)
    board.prepare_session()
    print(board.config_board('/0'))
    print(board.config_board('//'))
    print(board.config_board(ANALOGUE_MODE))
    board.start_stream(45000)

    # Create a thread-safe queue for board data
    queue_in = Queue()

    def get_data(queue_in):
        while not stop_event.is_set():
            data_in = board.get_board_data()
            timestamp_in = data_in[board.get_timestamp_channel(CYTON_BOARD_ID)]
            eeg_in = data_in[board.get_eeg_channels(CYTON_BOARD_ID)]
            aux_in = data_in[board.get_analog_channels(CYTON_BOARD_ID)]
            if len(timestamp_in) > 0:
                # Optionally print shapes for debugging
                # print('BrainFlow queue-in:', eeg_in.shape, aux_in.shape, timestamp_in.shape)
                queue_in.put((eeg_in, aux_in, timestamp_in))
            time.sleep(0.1)

    # Start a thread to fetch data from the board
    data_thread = Thread(target=get_data, args=(queue_in,))
    data_thread.daemon = True
    data_thread.start()

    # Process data from the queue
    while not stop_event.is_set():
        time.sleep(0.1)
        while not queue_in.empty():
            eeg_in, aux_in, timestamp_in = queue_in.get()
            brainflow_eeg = np.hstack((brainflow_eeg, eeg_in))
            brainflow_aux = np.hstack((brainflow_aux, aux_in))
            # Optionally print the updated shapes
            # print('BrainFlow collected:', brainflow_eeg.shape, brainflow_aux.shape)

    # Stop stream and release board session once stop_event is set
    board.stop_stream()
    board.release_session()

# ================================
#  Tkinter Experiment (GUI) Code
# ================================
def run_tkinter_experiment():
    # Create full-screen window
    root = tk.Tk()
    root.title("Random Moving Ball")
    SCREEN_WIDTH = root.winfo_screenwidth()
    SCREEN_HEIGHT = root.winfo_screenheight()
    root.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}")
    canvas = tk.Canvas(root, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, bg="brown")
    canvas.pack()

    # Ball properties
    BALL_RADIUS = 20
    MOVE_DISTANCE = min(SCREEN_WIDTH, SCREEN_HEIGHT) // 3
    STEP_DELAY = 50
    REST_DELAY = 500  # in milliseconds

    # Center coordinates and ball creation
    center_x = SCREEN_WIDTH // 2
    center_y = SCREEN_HEIGHT // 2
    ball = canvas.create_oval(center_x - BALL_RADIUS, center_y - BALL_RADIUS,
                              center_x + BALL_RADIUS, center_y + BALL_RADIUS,
                              fill="blue")
    countdown_text = canvas.create_text(center_x, center_y - 100, text="",
                                        font=("Helvetica", 64), fill="black")
    move_log = []
    move_count = {"left": 0, "right": 0, "up": 0, "down": 0}
    MAX_MOVES_PER_DIRECTION = 5

    def start_countdown():
        countdown_numbers = ["3", "2", "1", "Go!"]
        def show_number(index=0):
            if index < len(countdown_numbers):
                canvas.itemconfig(countdown_text, text=countdown_numbers[index])
                canvas.after(1000, show_number, index + 1)
            else:
                canvas.itemconfig(countdown_text, text="")
                canvas.after(500, animate_ball)
        show_number()

    def choose_direction():
        valid_directions = [d for d, count in move_count.items() if count < MAX_MOVES_PER_DIRECTION]
        if not valid_directions:
            finish_experiment()
            return None
        return random.choice(valid_directions)

    def animate_ball():
        direction = choose_direction()
        if direction is None:
            return
        velocity = random.randint(5, 20)
        # Log move information with timestamp
        move_log.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "direction": direction,
            "speed": velocity
        })
        move_count[direction] += 1
        dx, dy = 0, 0
        if direction == 'left':
            dx = -velocity
        elif direction == 'right':
            dx = velocity
        elif direction == 'up':
            dy = -velocity
        elif direction == 'down':
            dy = velocity
        moved_distance = 0

        def move_step():
            nonlocal moved_distance
            if moved_distance < MOVE_DISTANCE:
                canvas.move(ball, dx, dy)
                moved_distance += abs(dx) + abs(dy)
                canvas.after(STEP_DELAY, move_step)
            else:
                canvas.after(REST_DELAY, return_to_center)
        move_step()

    def return_to_center():
        coords = canvas.coords(ball)
        current_x = (coords[0] + coords[2]) / 2
        current_y = (coords[1] + coords[3]) / 2
        dx = center_x - current_x
        dy = center_y - current_y
        canvas.move(ball, dx, dy)
        canvas.after(REST_DELAY, animate_ball)

    def finish_experiment():
        # Save move log to CSV
        df = pd.DataFrame(move_log)
        print(df)
        df.to_csv("move_log.csv", index=False)
        # Signal BrainFlow thread to stop and then close the GUI
        stop_event.set()
        root.destroy()

    # Optionally, bind the Escape key to finish the experiment
    root.bind("<Escape>", lambda event: finish_experiment())
    start_countdown()
    root.mainloop()

# ====================================
#  Start Both Experiments Concurrently
# ====================================
# Run BrainFlow acquisition in a background thread.
brainflow_thread = Thread(target=brainflow_thread_func)
brainflow_thread.daemon = True
brainflow_thread.start()

# Run the Tkinter experiment in the main thread.
run_tkinter_experiment()

# After the GUI closes, save BrainFlow auxiliary data.
os.makedirs(save_dir, exist_ok=True)
np.save(save_file_aux, brainflow_aux)
print("BrainFlow auxiliary data saved to:", save_file_aux)
