import sys
import os
import joblib
import pandas as pd

# Add src to path using relative path from script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
src_dir = os.path.join(project_root, "src")
data_dir = os.path.join(project_root, "data")

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

train_df = pd.read_csv(os.path.join(data_dir, "train.csv"))

from src.tfidf_classifier import make_tfidf_pipeline
tfidf_pipe = make_tfidf_pipeline(42)
tfidf_pipe.fit(train_df['body_text'], train_df['label'])
tfidf_pipe_path = os.path.join(data_dir, "tfidf_pipeline.joblib")
joblib.dump(tfidf_pipe, tfidf_pipe_path)
print("TF-IDF pipeline saved")

from src.naive_bayes import make_naive_bayes_pipeline
nb_pipe = make_naive_bayes_pipeline(42)
nb_pipe.fit(train_df['body_text'], train_df['label'])
nb_pipe_path = os.path.join(data_dir, "nb_pipeline.joblib")
joblib.dump(nb_pipe, nb_pipe_path)
print("Naive Bayes pipeline saved")

tfidf_loaded = joblib.load(tfidf_pipe_path)
nb_loaded = joblib.load(nb_pipe_path)
print("Both pipelines load successfully")

sample = "Your account has been suspended. Click hxxp://fake-alert[.]com/verify now"
print(f"TF-IDF proba: {tfidf_loaded.predict_proba([sample])[:, 1][0]:.3f}")
print(f"NB proba: {nb_loaded.predict_proba([sample])[:, 1][0]:.3f}")