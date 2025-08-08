import os
print("Looking for file in:", os.getcwd())


import pickle

# Load your saved model
with open("models/cardio_model.pkl", "rb") as f:
    tree = pickle.load(f)

# Predict function (from your previous code)
def predict(tree, x):
    while isinstance(tree, tuple):
        feat_idx, thresh, left, right = tree
        tree = left if x[feat_idx] <= thresh else right
    return tree

# Category encodings and helper functions
age_category_labels = ["Child", "Teen", "20s", "30s", "40s", "50s", "60s", "70s", "80+"]
age_category_encoding = {label: idx for idx, label in enumerate(age_category_labels)}
bp_category_labels = [
    "Normal", "Elevated", "Hypertension Stage 1", "Hypertension Stage 2", "Hypertensive Crisis", "Unknown"
]
bp_category_encoding = {label: idx for idx, label in enumerate(bp_category_labels)}

def get_age_category(age_years):
    bins = [0, 12, 19, 29, 39, 49, 59, 69, 79, 120]
    labels = age_category_labels
    for i in range(len(bins)-1):
        if bins[i] < age_years <= bins[i+1]:
            return age_category_encoding[labels[i]]
    return None

def get_bp_category(systolic, diastolic):
    if systolic < 120 and diastolic < 80:
        label = "Normal"
    elif 120 <= systolic < 130 and diastolic < 80:
        label = "Elevated"
    elif 130 <= systolic < 140 or 80 <= diastolic < 90:
        label = "Hypertension Stage 1"
    elif 140 <= systolic or 90 <= diastolic:
        label = "Hypertension Stage 2"
    elif systolic >= 180 or diastolic >= 120:
        label = "Hypertensive Crisis"
    else:
        label = "Unknown"
    return bp_category_encoding.get(label, bp_category_encoding["Unknown"])

def encode_input(age, gender, height_cm, weight_kg, ap_hi, ap_lo, cholesterol, gluc, smoke, alco, active):
    age_cat = get_age_category(age)
    bmi = weight_kg / ((height_cm / 100) ** 2)
    bp_cat = get_bp_category(ap_hi, ap_lo)
    health_risk = cholesterol + gluc
    lifestyle_risk = smoke + alco + (1 - active)
    return [age_cat, gender, bmi, bp_cat, health_risk, lifestyle_risk]

def get_input(msg, cast_type=int):
    while True:
        try:
            return cast_type(input(msg))
        except ValueError:
            print("Invalid input. Try again.")

print("Enter patient info for prediction:")
gender = get_input("Gender (1 = Female, 2 = Male): ")
age = get_input("Age (years): ")
height = get_input("Height (cm): ")
weight = get_input("Weight (kg): ")
ap_hi = get_input("Systolic BP (ap_hi): ")
ap_lo = get_input("Diastolic BP (ap_lo): ")
cholesterol = get_input("Cholesterol (1-normal, 2-above normal, 3-well above normal): ")
gluc = get_input("Glucose (1-normal, 2-above normal, 3-well above normal): ")
smoke = get_input("Smoke? (1-yes, 0-no): ")
alco = get_input("Alcohol? (1-yes, 0-no): ")
active = get_input("Physically active? (1-yes, 0-no): ")

features = encode_input(age, gender, height, weight, ap_hi, ap_lo, cholesterol, gluc, smoke, alco, active)
print("Encoded features:", features)

prediction = predict(tree, features)
print("Prediction:", "At cardiovascular risk" if prediction==1 else "Low cardiovascular risk")