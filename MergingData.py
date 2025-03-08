import pandas as pd
import numpy as np

df_eog = pd.read_csv("eog_data.csv")
df_events = pd.read_csv("move_log.csv")

df_eog[['ch1', 'ch2']] = pd.DataFrame(df_eog['channels'].tolist(), index=df_eog.index)
df_eog.drop(columns=['channels'], inplace=True)

time_window = 2.0  # seconds

def find_direction_for_timestamp(t):
    diffs = np.abs(df_events['timestamp'] - t)
    min_idx = diffs.idxmin()
    min_val = diffs[min_idx]
    if min_val <= time_window:
        return df_events.loc[min_idx, 'direction']
    else:
        return None

df_eog['direction'] = df_eog['timestamp'].apply(find_direction_for_timestamp)

df_eog.to_csv("eog_labeled.csv", index=False)
print("Saved labeled EOG data to eog_labeled.csv")
