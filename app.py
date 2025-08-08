from flask import Flask, request, render_template
import pickle
import matplotlib
matplotlib.use('Agg')  # Use a non-GUI backend for server environments

import matplotlib.pyplot as plt
import numpy as np
import os
from sklearn.metrics import confusion_matrix, roc_curve, auc, precision_recall_curve
import seaborn as sns

app = Flask(__name__)

# Load your saved model
with open("models/cardio_model.pkl", "rb") as f:
    tree = pickle.load(f)

def predict(tree, x):
    while isinstance(tree, tuple):
        feat_idx, thresh, left, right = tree
        tree = left if x[feat_idx] <= thresh else right
    return tree

# Encodings and helper functions (same as your existing code)

age_category_labels = ["Child", "Teen", "20s", "30s", "40s", "50s", "60s", "70s", "80+"]
age_category_encoding = {label: idx for idx, label in enumerate(age_category_labels)}

bp_category_labels = [
    "Normal", "Elevated", "Hypertension Stage 1", "Hypertension Stage 2", "Hypertensive Crisis", "Unknown"
]

gender_encoding = {"Female": 1, "Male": 2}  # Place here

bp_category_encoding = {label: idx for idx, label in enumerate(bp_category_labels)}

def get_age_category(age_years):
    bins = [0, 12, 19, 29, 39, 49, 59, 69, 79, 120]
    labels = age_category_labels
    for i in range(len(bins) - 1):
        if bins[i] < age_years <= bins[i + 1]:
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


# Add your encoding functions here...
@app.route('/')
def index():
    return render_template('index.html')

@app.route("/cardio", methods=["GET", "POST"])
def cardio():
    prediction = None
    show_graphs = False
    if request.method == "POST":
        try:
            data = request.form
            
            features = encode_input(
                age=int(data["age"]),
                gender=int(data["gender"]),
                height_cm=float(data["height"]),
                weight_kg=float(data["weight"]),
                ap_hi=int(data["ap_hi"]),
                ap_lo=int(data["ap_lo"]),
                cholesterol=int(data["cholesterol"]),
                gluc=int(data["gluc"]),
                smoke=int(data["smoke"]),
                alco=int(data["alco"]),
                active=int(data["active"])
            )
            pred = predict(tree, features)
            prediction = "Based on the input data, our model suggests a higher-than-average risk of cardiovascular disease. While this is not a definitive diagnosis, it is a strong signal to take preventive measures. It’s important to understand that such models can overpredict in some scenarios, but it's always best to err on the side of caution. Please consult a medical professional to undergo proper clinical assessment and personalized advice." if pred == 1 else "According to our AI model, your current data indicates a low risk of cardiovascular disease. However, please note that predictive models are not a substitute for professional medical evaluation. In real-world cases, approximately 1 in 5 individuals flagged as low risk may still develop cardiovascular issues. If you experience symptoms or have concerns, consult a certified healthcare provider without delay."
            generate_cardio_graphs()  # Only generate after prediction
            show_graphs = True
        except Exception as e:
            prediction = "Error: " + str(e)
    return render_template("cardio.html", prediction=prediction, show_graphs=show_graphs)

def generate_cardio_graphs():
    static_dir = os.path.join(os.getcwd(), "static")

    # Simulate data (replace with your real test data and predictions)
    y_true = np.random.choice([0, 1], size=100, p=[0.7, 0.3])
    y_pred = np.random.choice([0, 1], size=100, p=[0.7, 0.3])
    y_scores = np.random.rand(100)  # Simulated probability scores

    # Prediction distribution
    plt.figure(figsize=(5,3))
    plt.title("Cardio Risk Prediction Distribution")
    plt.bar(['Low Risk', 'At Risk'], [np.sum(y_pred==0), np.sum(y_pred==1)], color=['#4caf50', '#e53935'])
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(static_dir, "cardio_pred_distribution.png"))
    plt.close()

    # Age distribution (simulate)
    sample_ages = np.random.normal(45, 12, 100)
    plt.figure(figsize=(5,3))
    plt.title("Age Distribution")
    plt.hist(sample_ages, bins=10, color='#1976d2', alpha=0.7)
    plt.xlabel("Age")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(static_dir, "cardio_age_distribution.png"))
    plt.close()

    # BMI distribution (simulate)
    sample_bmi = np.random.normal(27, 4, 100)
    plt.figure(figsize=(5,3))
    plt.title("BMI Distribution")
    plt.hist(sample_bmi, bins=10, color='#ffb300', alpha=0.7)
    plt.xlabel("BMI")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(static_dir, "cardio_bmi_distribution.png"))
    plt.close()

    # ROC Curve
    fpr, tpr, _ = roc_curve(y_true, y_scores)
    roc_auc = auc(fpr, tpr)
    plt.figure(figsize=(5,4))
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.2f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Receiver Operating Characteristic')
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(os.path.join(static_dir, "cardio_roc_curve.png"))
    plt.close()

    # Precision-Recall Curve
    precision, recall, _ = precision_recall_curve(y_true, y_scores)
    plt.figure(figsize=(5,4))
    plt.plot(recall, precision, color='purple', lw=2)
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Curve')
    plt.tight_layout()
    plt.savefig(os.path.join(static_dir, "cardio_pr_curve.png"))
    plt.close()

# Call this once at startup (or after model retrain)
generate_cardio_graphs()

@app.route('/contact', methods=['POST'])
def contact():
    name = request.form['name']
    email = request.form['email']
    message = request.form['message']
    # You can save to a database, send an email, or log it
    # Example: print to console
    print(f"New message from {name} ({email}): {message}")
    return render_template('index.html', success=True)

if __name__ == "__main__":

    app.run(host="0.0.0.0", debug=True, port=5000)
