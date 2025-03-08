import tkinter as tk
import random
import pandas as pd
import time

# Create the main window (full screen)
root = tk.Tk()
root.title("Random Moving Ball")

# Get screen width and height
SCREEN_WIDTH = root.winfo_screenwidth()
SCREEN_HEIGHT = root.winfo_screenheight()

# Set window size to full screen
root.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}")

# Create canvas to fit the whole screen
canvas = tk.Canvas(root, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, bg="brown")
canvas.pack()

# Ball properties
BALL_RADIUS = 20
MOVE_DISTANCE = min(SCREEN_WIDTH, SCREEN_HEIGHT) // 3
STEP_DELAY = 50
REST_DELAY = 500  # rest period (0.5 sec)

# Center coordinates
center_x = SCREEN_WIDTH // 2
center_y = SCREEN_HEIGHT // 2

# Create ball at center
ball = canvas.create_oval(center_x - BALL_RADIUS, center_y - BALL_RADIUS,
                          center_x + BALL_RADIUS, center_y + BALL_RADIUS,
                          fill="blue")

# Countdown text
countdown_text = canvas.create_text(center_x, center_y - 100, text="",
                                    font=("Helvetica", 64), fill="black")

# Data storage
move_log = []

# Direction control - 10 moves per direction
move_count = {"left": 0, "right": 0, "up": 0, "down": 0}
MAX_MOVES_PER_DIRECTION = 5

def start_countdown():
    countdown_numbers = ["3", "2", "1", "Go!"]

    def show_number(index=0):
        if index < len(countdown_numbers):
            canvas.itemconfig(countdown_text, text=countdown_numbers[index])
            canvas.after(1000, show_number, index + 1)
        else:
            # Clear 'Go!' and wait 0.5 sec before starting first move
            canvas.itemconfig(countdown_text, text="")
            canvas.after(500, animate_ball)

    show_number()

def choose_direction():
    """Pick a direction that still needs moves."""
    valid_directions = [d for d, count in move_count.items() if count < MAX_MOVES_PER_DIRECTION]
    if not valid_directions:
        finish_experiment()
        return None
    return random.choice(valid_directions)

def animate_ball():
    """Moves ball in a random allowed direction with random speed."""
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
            # Once movement finishes, rest for 0.5 sec at end position
            canvas.after(REST_DELAY, return_to_center)

    move_step()

def return_to_center():
    """Moves ball back to center instantly, then rests again before next move."""
    coords = canvas.coords(ball)
    current_x = (coords[0] + coords[2]) / 2
    current_y = (coords[1] + coords[3]) / 2

    dx = center_x - current_x
    dy = center_y - current_y

    canvas.move(ball, dx, dy)

    # After returning to center, rest for 0.5 sec
    canvas.after(REST_DELAY, animate_ball)

def finish_experiment():
    """After all moves complete, save data and close."""
    df = pd.DataFrame(move_log)
    print(df)
    df.to_csv("move_log.csv", index=False)
    root.destroy()

# Start with countdown
start_countdown()

root.mainloop()