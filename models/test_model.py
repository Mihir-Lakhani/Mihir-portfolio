import pickle

# Load your saved model
with open("cardio_model.pkl", "rb") as f:
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

def encode_input(age, height_cm, weight_kg, ap_hi, ap_lo, cholesterol, gluc, smoke, alco, active):
    age_cat = get_age_category(age)
    bmi = weight_kg / ((height_cm / 100) ** 2)
    bp_cat = get_bp_category(ap_hi, ap_lo)
    health_risk = cholesterol + gluc
    lifestyle_risk = smoke + alco + (1 - active)
    return [age_cat, bmi, bp_cat, health_risk, lifestyle_risk]


import random
def get_random_person():
    age = random.randint(1, 90)
    height = random.randint(140, 200)
    weight = random.randint(45, 120)
    sys = random.randint(90, 190)
    dia = random.randint(60, 120)
    if dia >= sys:
        sys, dia = dia + 10, sys
    cholesterol = random.randint(1, 3)
    gluc = random.randint(1, 3)
    smoke = random.randint(0, 1)
    alco = random.randint(0, 1)
    active = random.randint(0, 1)
    return {
        "age": age, "height": height, "weight": weight,
        "ap_hi": sys, "ap_lo": dia, "cholesterol": cholesterol,
        "gluc": gluc, "smoke": smoke, "alco": alco, "active": active
    }


all_people = [get_random_person() for _ in range(100)]
all_features = [encode_input(
    p['age'], p['height'], p['weight'], p['ap_hi'], p['ap_lo'],
    p['cholesterol'], p['gluc'], p['smoke'], p['alco'], p['active']
) for p in all_people]

all_preds = [predict(tree, feats) for feats in all_features]

for idx, (person, feats, pred) in enumerate(zip(all_people, all_features, all_preds), 1):
    print(f"Person {idx}:")
    print(f"  Raw Data: {person}")
    print(f"  Encoded Features: {feats}")
    print(f"  Prediction: {pred}\n")

results = []
for person, feats, pred in zip(all_people, all_features, all_preds):
    results.append({"raw": person, "features": feats, "prediction": pred})


from collections import Counter
print("Prediction counts:", Counter(all_preds))
