import os
import time
import random
import numpy as np
import pandas as pd
import tkinter as tk
from threading import Thread

from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter

def get_next_filename(prefix="data", ext="csv"):
    """Iterate through filenames until an unused one is found."""
    index = 1
    while os.path.exists(f"{prefix}{index:02d}.{ext}"):
        index += 1
    return f"{prefix}{index:02d}.{ext}"

class EOGExperiment:
    def __init__(self, root, board_port='COM3'):
        self.root = root
        self.SCREEN_WIDTH = root.winfo_screenwidth()
        self.SCREEN_HEIGHT = root.winfo_screenheight()
        root.geometry(f"{self.SCREEN_WIDTH}x{self.SCREEN_HEIGHT}")
        self.canvas = tk.Canvas(root, width=self.SCREEN_WIDTH, height=self.SCREEN_HEIGHT, bg="brown")
        self.canvas.pack()

        # Ball properties
        self.BALL_RADIUS = 20
        self.MOVE_DISTANCE = min(self.SCREEN_WIDTH, self.SCREEN_HEIGHT) // 3
        self.STEP_DELAY = 50
        self.REST_DELAY = 500

        self.center_x = self.SCREEN_WIDTH // 2
        self.center_y = self.SCREEN_HEIGHT // 2
        self.ball = self.canvas.create_oval(self.center_x - self.BALL_RADIUS,
                                            self.center_y - self.BALL_RADIUS,
                                            self.center_x + self.BALL_RADIUS,
                                            self.center_y + self.BALL_RADIUS,
                                            fill="blue")
        self.countdown_text = self.canvas.create_text(self.center_x, self.center_y - 100,
                                                      text="", font=("Helvetica", 64), fill="black")
        self.move_log = []
        self.move_count = {"left": 0, "right": 0, "up": 0, "down": 0}
        self.MAX_MOVES_PER_DIRECTION = 5

        # List to store raw EOG samples from BrainFlow
        self.eog_data = []

        # Set up BrainFlow board
        params = BrainFlowInputParams()
        params.serial_port = board_port
        self.board_id = BoardIds.CYTON_BOARD.value
        self.board = BoardShim(self.board_id, params)
        self.board.prepare_session()
        self.board.start_stream()  # Start streaming

        # Flag to control the streaming thread
        self.running = True
        self.board_thread = Thread(target=self.stream_board_data)
        self.board_thread.daemon = True
        self.board_thread.start()

        # Start the GUI countdown and ball animation
        self.start_countdown()

    def stream_board_data(self):
        """Continuously poll the board for new data and store it."""
        while self.running:
            data = self.board.get_board_data()  # Returns new samples since the last call
            if data.size > 0:
                # data shape: (num_channels, num_samples)
                num_samples = data.shape[1]
                for i in range(num_samples):
                    # Assume first row is timestamp, and remaining rows are channel data
                    timestamp = data[0, i]
                    channels = data[1:, i]
                    self.eog_data.append({
                        "timestamp": timestamp,
                        "channels": channels.tolist()
                    })
            time.sleep(0.1)  # Poll every 100 ms

    def start_countdown(self):
        countdown_numbers = ["3", "2", "1", "Go!"]
        def show_number(index=0):
            if index < len(countdown_numbers):
                self.canvas.itemconfig(self.countdown_text, text=countdown_numbers[index])
                self.canvas.after(1000, show_number, index + 1)
            else:
                self.canvas.itemconfig(self.countdown_text, text="")
                self.canvas.after(500, self.animate_ball)
        show_number()

    def choose_direction(self):
        valid_directions = [d for d, count in self.move_count.items() if count < self.MAX_MOVES_PER_DIRECTION]
        if not valid_directions:
            self.finish_experiment()
            return None
        return random.choice(valid_directions)

    def animate_ball(self):
        direction = self.choose_direction()
        if direction is None:
            return

        velocity = random.randint(5, 20)
        now = time.time()
        self.move_log.append({
            "timestamp": now,
            "direction": direction,
            "speed": velocity
        })
        self.move_count[direction] += 1

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
            if moved_distance < self.MOVE_DISTANCE:
                self.canvas.move(self.ball, dx, dy)
                moved_distance += abs(dx) + abs(dy)
                self.canvas.after(self.STEP_DELAY, move_step)
            else:
                self.canvas.after(self.REST_DELAY, self.return_to_center)
        move_step()

    def return_to_center(self):
        coords = self.canvas.coords(self.ball)
        current_x = (coords[0] + coords[2]) / 2
        current_y = (coords[1] + coords[3]) / 2
        dx = self.center_x - current_x
        dy = self.center_y - current_y
        self.canvas.move(self.ball, dx, dy)
        self.canvas.after(self.REST_DELAY, self.animate_ball)

    def finish_experiment(self):
        # Stop board data streaming
        self.running = False
        self.board_thread.join()

        # Save move log
        df_events = pd.DataFrame(self.move_log)
        df_events.to_csv("move_log.csv", index=False)

        # Save raw EOG data
        df_eog = pd.DataFrame(self.eog_data)
        df_eog.to_csv("eog_data.csv", index=False)

        # Stop and release the BrainFlow session
        self.board.stop_stream()
        self.board.release_session()
        self.root.destroy()


def run_experiment():
    root = tk.Tk()
    root.title("EOG Experiment with BrainFlow")
    experiment = EOGExperiment(root, board_port='COM3')  # Update port if needed
    root.mainloop()


def main():
    # Enable BrainFlow logging
    BoardShim.enable_dev_board_logger()

    # Set up BrainFlow parameters for a standalone demo
    params = BrainFlowInputParams()
    params.serial_port = "COM3"  # Update as needed
    board_id = BoardIds.CYTON_BOARD.value

    board = BoardShim(board_id, params)
    board.prepare_session()
    board.start_stream()
    BoardShim.log_message(LogLevels.LEVEL_INFO.value, 'Sleeping in the main thread')
    time.sleep(10)  # Collect data for 10 seconds
    data = board.get_board_data()
    board.stop_stream()
    board.release_session()

    # Display a sample of the board data
    df = pd.DataFrame(np.transpose(data))
    print('Data From the Board')
    print(df.head(10))

    # Generate a unique filename (data01.csv, data02.csv, etc.)
    filename = get_next_filename(prefix="data", ext="csv")
    print(f"Saving data to {filename}")

    # Save data using BrainFlow’s built-in serialization
    DataFilter.write_file(data, filename, 'w')

    # Optionally, read the file back to verify using BrainFlow's API
    restored_data = DataFilter.read_file(filename)
    restored_df = pd.DataFrame(np.transpose(restored_data))
    print('Data Restored From the File')
    print(restored_df.head(10))


if __name__ == "__main__":
    
    # To run the GUI-based EOG experiment:
    # run_experiment()
    
    # To run the standalone board data collection demo:
    main()
