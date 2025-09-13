import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from collections import Counter
import random
import math

df=pd.read_csv(r"C:\\Users\\mihir\\Documents\\Websume\\models\\cardio_train.csv", sep=";")

def encode_categories(df):
    encodings = {}
    for column in df.columns:
        if df[column].dtype == "object" or df[column].dtype.name == "category":
            unique_values = df[column].unique()
            encodings[column] = {val: idx for idx, val in enumerate(unique_values)}
            df[column] = df[column].map(encodings[column])
    return df, encodings

print(df.head())
print(df.info())  
print(df.describe())  
print(df.isnull().sum())  
print(df.dtypes)  

df["age"] = df["age"] // 365

df.fillna(df.median(), inplace=True)

df.drop(columns=["id"], inplace=True)

df["age_category"] = pd.cut(
    df["age"],
    bins=[0, 12, 19, 29, 39, 49, 59, 69, 79, 120],
    labels=["Child", "Teen", "20s", "30s", "40s", "50s", "60s", "70s", "80+"]
)

df["bmi"] = df["weight"] / ((df["height"] / 100) ** 2)

df["bmi_category"] = pd.cut(
    df["bmi"],
    bins=[0, 15, 16, 17, 18.5, 23, 25, 27.5, 30, 32.5, 35, 37.5, 40, 45, 50, 100],
    labels=[
        "Very Severely Underweight",
        "Severely Underweight",
        "Moderately Underweight",
        "Mildly Underweight",
        "Normal (Lower Range)",
        "Normal (Higher Range)",
        "Overweight (Lower)",
        "Overweight (Higher)",
        "Obese Class I (Lower)",
        "Obese Class I (Higher)",
        "Obese Class II (Lower)",
        "Obese Class II (Higher)",
        "Obese Class III (Lower)",
        "Obese Class III (Higher)",
        "Super Obesity"
    ]
)
def categorize_bp(row):
    systolic = row["ap_hi"]
    diastolic = row["ap_lo"]
    
    if systolic < 120 and diastolic < 80:
        return "Normal"
    elif 120 <= systolic < 130 and diastolic < 80:
        return "Elevated"
    elif 130 <= systolic < 140 or 80 <= diastolic < 90:
        return "Hypertension Stage 1"
    elif 140 <= systolic or 90 <= diastolic:
        return "Hypertension Stage 2"
    elif systolic >= 180 or diastolic >= 120:
        return "Hypertensive Crisis"
    else:
        return "Unknown"

df["bp_category"] = df.apply(categorize_bp, axis=1)
df["lifestyle_risk"] = df["smoke"] + df["alco"] + (1 - df["active"])
df["health_risk"] = df["cholesterol"] + df["gluc"]

df = df[["age_category", "bmi", "bp_category", "health_risk", "lifestyle_risk", "cardio"]]


print(df)

df=df.dropna()


df_encoded, encodings = encode_categories(df)

class_counts = df['cardio'].value_counts()

print(class_counts)


def train_test_split_manual(data, test_size=0.2):
    data = data.sample(frac=1).reset_index(drop=True)
    split_idx = int((1 - test_size) * len(data))
    return data.iloc[:split_idx], data.iloc[split_idx:]

train_df, test_df = train_test_split_manual(df, test_size=0.2)
X_train = train_df.drop("cardio", axis=1).values.tolist()
y_train = train_df["cardio"].values.tolist()
X_test = test_df.drop("cardio", axis=1).values.tolist()
y_test = test_df["cardio"].values.tolist()
features = list(train_df.drop("cardio", axis=1).columns)

def entropy(labels):
    total = len(labels)
    counts = Counter(labels)
    return -sum((count/total) * math.log2(count/total) for count in counts.values())

def info_gain(parent, left, right):
    total_len = len(parent)
    return entropy(parent) - (len(left)/total_len)*entropy(left) - (len(right)/total_len)*entropy(right)

def split_data(X, y, feature_idx, threshold):
    X_left, y_left, X_right, y_right = [], [], [], []
    for xi, yi in zip(X, y):
        if xi[feature_idx] <= threshold:
            X_left.append(xi)
            y_left.append(yi)
        else:
            X_right.append(xi)
            y_right.append(yi)
    return X_left, y_left, X_right, y_right

def majority_class(labels):
    return Counter(labels).most_common(1)[0][0]


def build_tree(X, y, features, max_depth=None, min_gain=0.01, depth=0):
    if len(set(y)) == 1:
        return y[0]
    if not features or (max_depth is not None and depth >= max_depth):
        return majority_class(y)

    best_gain = 0
    best_feat, best_thresh = None, None
    best_split = None

    for i in range(len(features)):
        values = set(row[i] for row in X)
        for val in values:
            X_l, y_l, X_r, y_r = split_data(X, y, i, val)
            if y_l and y_r:
                gain = info_gain(y, y_l, y_r)
                if gain > best_gain:
                    best_gain = gain
                    best_feat, best_thresh = i, val
                    best_split = (X_l, y_l, X_r, y_r)

    if best_gain < min_gain or best_split is None:
        return majority_class(y)

    left = build_tree(best_split[0], best_split[1], features, max_depth, min_gain, depth+1)
    right = build_tree(best_split[2], best_split[3], features, max_depth, min_gain, depth+1)
    return (best_feat, best_thresh, left, right)


def predict(tree, x):
    while isinstance(tree, tuple):
        feat_idx, thresh, left, right = tree
        tree = left if x[feat_idx] <= thresh else right
    return tree


def evaluate(tree, X, y):
    preds = [predict(tree, xi) for xi in X]
    acc = sum(1 for pred, actual in zip(preds, y) if pred == actual) / len(y)
    cm = [[0, 0], [0, 0]]
    for pred, actual in zip(preds, y):
        cm[actual][pred] += 1
    return acc, cm




tree = build_tree(X_train, y_train, features, max_depth=12, min_gain=0.01)
accuracy, conf_matrix = evaluate(tree, X_test, y_test)


print(f"Accuracy: {accuracy * 100:.2f}%")
print("Confusion Matrix:")
print(np.array(conf_matrix))



def classification_report_manual(y_true, y_pred):
    labels = sorted(set(y_true))
    report = {}

    for cls in labels:
        tp = sum((yt == cls and yp == cls) for yt, yp in zip(y_true, y_pred))
        fp = sum((yt != cls and yp == cls) for yt, yp in zip(y_true, y_pred))
        fn = sum((yt == cls and yp != cls) for yt, yp in zip(y_true, y_pred))
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        support = sum(yt == cls for yt in y_true)
        report[cls] = {
            "precision": precision,
            "recall": recall,
            "f1-score": f1,
            "support": support
        }
    
    print("\nManual Classification Report:")
    print(f"{'Class':>7} {'Precision':>10} {'Recall':>10} {'F1-score':>10} {'Support':>10}")
    for cls, metrics in report.items():
        print(f"{str(cls):>7} {metrics['precision']:10.2f} {metrics['recall']:10.2f} {metrics['f1-score']:10.2f} {metrics['support']:10}")
        
y_pred = [predict(tree, xi) for xi in X_test]
classification_report_manual(y_test, y_pred)

import pickle

with open("cardio_model.pkl", "wb") as f:
    pickle.dump(tree, f)


import pickle

with open("cardio_model.pkl", "rb") as f:
    loaded_tree = pickle.load(f)

sample_prediction = predict(loaded_tree, X_test[0])
print("Predicted class:", sample_prediction)
