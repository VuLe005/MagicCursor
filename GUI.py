import tkinter as tk
import random
import pandas as pd
import time
from threading import Thread
from pyOpenBCI import OpenBCICyton

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

        # List of raw EOG samples from OpenBCI
        self.eog_data = []

        # Connect to OpenBCI
        self.board = OpenBCICyton(port=board_port)
        self.board_thread = Thread(target=self.start_board_stream)
        self.board_thread.daemon = True

        self.start_countdown()

    def start_board_stream(self, sample_rate=500):
        """Stream data from OpenBCI in a separate thread."""
        def handle_sample(sample):
            # sample.channels is a list of channel readings (floats)
            self.eog_data.append({
                "timestamp": time.time(),  # high-resolution float
                "channels": sample.channels
            })
        try:
            self.board.start_stream(handle_sample, sample_rate=sample_rate)
        except Exception as e:
            print("Error streaming from OpenBCI:", e)

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
        # Wedirection + a float timestamp
        now = time.time()  # float time
        self.move_log.append({
            "timestamp": now,  # float time
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
        # Save event log
        df_events = pd.DataFrame(self.move_log)
        df_events.to_csv("move_log.csv", index=False)

        # Save raw EOG data
        df_eog = pd.DataFrame(self.eog_data)
        df_eog.to_csv("eog_data.csv", index=False)

        self.board.disconnect()
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    root.title("EOG Experiment with OpenBCI")
    experiment = EOGExperiment(root, board_port='COM3')  # Update port if needed
    root.mainloop()
