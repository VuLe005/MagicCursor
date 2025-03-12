import glob, sys, time, serial, os
import tkinter as tk
import random
import pandas as pd
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from serial import Serial
from threading import Thread, Event
from queue import Queue
# from psychopy.hardware import keyboard


lsl_out = False
save_dir = 'data'  # Directory to save data to
run = 1  # Run number (used for file naming)
save_file_aux = save_dir + f'aux_run-{run}.npy'
save_file_eeg = save_dir + f'eeg_run-{run}.npy'
sampling_rate = 250
CYTON_BOARD_ID = 0  # 0 if no daisy; 2 if using daisy board; 6 if using daisy+wifi shield
BAUD_RATE = 115200
ANALOGUE_MODE = '/2'  # Reads from analog pins A5(D11), A6(D12) and, if no wifi shield, then A7(D13)
# We create the stop event globally so that both parts can signal termination.
stop_event = Event()

def find_openbci_port():
    """Finds the port to which the Cyton Dongle is connected to."""
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
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
            line = ''
            time.sleep(2)
            if s.inWaiting():
                line = ''
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
        exit()
    else:
        return openbci_port

def run_brainflow():
    print(BoardShim.get_board_descr(CYTON_BOARD_ID))
    params = BrainFlowInputParams()
    if CYTON_BOARD_ID != 6:
        params.serial_port = find_openbci_port()
    elif CYTON_BOARD_ID == 6:
        params.ip_port = 9000
    board = BoardShim(CYTON_BOARD_ID, params)
    board.prepare_session()
    res_query = board.config_board('/0')
    print(res_query)
    res_query = board.config_board('//')
    print(res_query)
    res_query = board.config_board(ANALOGUE_MODE)
    print(res_query)
    board.start_stream(45000)
    
    def get_data(queue_in, lsl_out=False):
        while not stop_event.is_set():
            data_in = board.get_board_data()
            timestamp_in = data_in[board.get_timestamp_channel(CYTON_BOARD_ID)]
            eeg_in = data_in[board.get_eeg_channels(CYTON_BOARD_ID)]
            aux_in = data_in[board.get_analog_channels(CYTON_BOARD_ID)]
            if len(timestamp_in) > 0:
                print('queue-in: ', eeg_in.shape, aux_in.shape, timestamp_in.shape)
                queue_in.put((eeg_in, aux_in, timestamp_in))
            time.sleep(0.1)
    
    queue_in = Queue()
    cyton_thread = Thread(target=get_data, args=(queue_in, lsl_out))
    cyton_thread.daemon = True
    cyton_thread.start()
    
    kb = keyboard.Keyboard()
    eeg = np.zeros((8, 0))
    aux = np.zeros((3, 0))
    while not stop_event.is_set():
        time.sleep(0.1)
        keys = kb.getKeys()
        if 'escape' in keys:
            stop_event.set()
            break
        while not queue_in.empty():
            eeg_in, aux_in, timestamp_in = queue_in.get()
            print('queue-out: ', eeg_in.shape, aux_in.shape, timestamp_in.shape)
            eeg = np.hstack((eeg, eeg_in))
            aux = np.hstack((aux, aux_in))
            print('total: ', eeg.shape, aux.shape)
    
    os.makedirs(save_dir, exist_ok=True)
    np.save(save_file_aux, aux)
    np.save(save_file_eeg, eeg)
    # --- End of BrainFlow code ---
    
    # Convert the auxiliary data to a DataFrame and save as CSV
    df_brainflow = pd.DataFrame(aux.T, columns=[f"Aux_Channel_{i}" for i in range(aux.shape[0])])
    df_brainflow.to_csv(os.path.join(save_dir, f'aux_run-{run}.csv'), index=False)

    df_brainflow = pd.DataFrame(eeg.T, columns=[f"EEG_Channel_{i}" for i in range(eeg.shape[0])])
    df_brainflow.to_csv(os.path.join(save_dir, f'EEG_run-{run}.csv'), index=False)
    

#         Tkinter Experiment Code
def run_tkinter():
    root = tk.Tk()
    root.title("Random Moving Ball")
    
    # Get screen dimensions and set full screen
    SCREEN_WIDTH = root.winfo_screenwidth()
    SCREEN_HEIGHT = root.winfo_screenheight()
    root.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}")
    
    canvas = tk.Canvas(root, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, bg="brown")
    canvas.pack()
    
    # Ball properties
    BALL_RADIUS = 20
    MOVE_DISTANCE = min(SCREEN_WIDTH, SCREEN_HEIGHT) // 3
    STEP_DELAY = 50
    REST_DELAY = 500  # 0.5 sec rest
    
    # Center coordinates and ball creation
    center_x = SCREEN_WIDTH // 2
    center_y = SCREEN_HEIGHT // 2
    ball = canvas.create_oval(center_x - BALL_RADIUS, center_y - BALL_RADIUS,
                              center_x + BALL_RADIUS, center_y + BALL_RADIUS,
                              fill="blue")
    
    # Countdown text
    countdown_text = canvas.create_text(center_x, center_y - 100, text="",
                                        font=("Helvetica", 64), fill="black")
    
    # Data storage for Tkinter experiment moves
    move_log = []
    move_count = {"left": 0, "right": 0, "up": 0, "down": 0}
    MAX_MOVES_PER_DIRECTION = 5
    
    def start_countdown():
        countdown_numbers = ["3", "2", "1", "Go!"]
        def show_number(index=0):
            if index < len(countdown_numbers):
                canvas.itemconfig(countdown_text, text=countdown_numbers[index])
                canvas.after(4500, show_number, index + 1)
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
            return  # All moves complete.
    
        velocity = random.randint(5, 20)
    
        # Log data before move starts
        move_log.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "direction": direction,
            "speed": velocity
        })
    
        move_count[direction] += 1
    
        # Set movement vector
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
        df = pd.DataFrame(move_log)
        print(df)
        df.to_csv("move_log.csv", index=False)
        # Signal BrainFlow code to stop (via the shared stop_event)
        stop_event.set()
        root.destroy()
    
    start_countdown()
    root.mainloop()
    return move_log

# =================================================
#       Run Both Experiments Concurrently
# =================================================

# Start BrainFlow experiment in a background thread.
brainflow_thread = Thread(target=run_tkinter)
brainflow_thread.daemon = True
brainflow_thread.start()

# Run the Tkinter experiment in the main thread.
tk_move_log = run_brainflow()