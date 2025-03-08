import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score

# 1) Load Labeled EOG Data
df = pd.read_csv("eog_labeled.csv")

# Drop rows where direction is NaN (no movement label)
df.dropna(subset=['direction'], inplace=True)

# Extract channels
eog_ch1 = df['ch1'].values
eog_ch2 = df['ch2'].values
labels  = df['direction'].values

# 2) Define a Bandpass Filter (0.5 - 35 Hz example)
fs = 500.0  # or 250.0, whichever your board uses
lowcut = 0.5
highcut = 35.0
order = 4

def butter_bandpass(lowcut, highcut, fs, order=4):
    from scipy.signal import butter
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return b, a

def filter_signal(signal, b, a):
    from scipy.signal import filtfilt
    return filtfilt(b, a, signal)

b, a = butter_bandpass(lowcut, highcut, fs, order)

filtered_ch1 = filter_signal(eog_ch1, b, a)
filtered_ch2 = filter_signal(eog_ch2, b, a)

# 3) Voltage Difference Feature
# Sometimes EOG classification is easier if we look at difference or ratio
diff = filtered_ch2 - filtered_ch1

# 4) Build Feature Matrix
# Let's do a simple approach: X has [filtered_ch1, filtered_ch2, diff]
X = np.column_stack((filtered_ch1, filtered_ch2, diff))
y = labels

# 5) Train/Test Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 6) Train an SVM
clf = SVC(kernel='linear')  # or 'rbf', etc.
clf.fit(X_train, y_train)

# 7) Evaluate
y_pred = clf.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print("Accuracy:", accuracy)

# Print some predictions
for pred_label, true_label in zip(y_pred[:10], y_test[:10]):
    print(f"Pred: {pred_label}, True: {true_label}")
