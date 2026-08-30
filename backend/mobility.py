import collections
from pathlib import Path
import warnings

import joblib
import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, render_template, request

warnings.filterwarnings("ignore")

mobility_bp = Blueprint("mobility", __name__, url_prefix="/mobility")

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "mobility_model_final.pkl"

SIGNAL_COLS = ["RSRP", "RSRQ", "SNR", "CQI", "RSSI"]
ROLL_WIN = 5
THRESHOLD = -97

EXCLUDE = {
    "Timestamp",
    "Longitude",
    "Latitude",
    "Operatorname",
    "NetworkMode",
    "State",
    "CELLHEX",
    "NODEHEX",
    "LACHEX",
    "trace_id",
    "future_RSRP",
    "Y",
    "CellID",
    "RAWCELLID",
}

bundle = joblib.load(MODEL_PATH)
MODEL = bundle["model"]
FEATURE_COLS = bundle["feature_cols"]
RT_PARAMS = bundle["rt_params"]

ALPHA_EMA = 0.15
VOL_WINDOW = RT_PARAMS["vol_window"]
RT_THRESH = RT_PARAMS["rt_threshold"]

state = {
    "St_prev": 0.0,
    "Pt_buf": collections.deque(maxlen=VOL_WINDOW + 1),
}


def engineer_features_for_trace(trace_df: pd.DataFrame) -> pd.DataFrame:
    t = trace_df.copy()

    for col in SIGNAL_COLS:
        for lag in [1, 2, 3]:
            t[f"{col}_lag{lag}"] = t[col].shift(lag)

    for col in SIGNAL_COLS:
        t[f"delta_{col}"] = t[col].diff()
        t[f"delta2_{col}"] = t[f"delta_{col}"].diff()

    for col in SIGNAL_COLS:
        t[f"{col}_rmean"] = t[col].rolling(ROLL_WIN, min_periods=1).mean()
        t[f"{col}_rstd"] = t[col].rolling(ROLL_WIN, min_periods=1).std().fillna(0)
        t[f"{col}_rmin"] = t[col].rolling(ROLL_WIN, min_periods=1).min()

    t["rsrp_margin"] = t["RSRP"] - THRESHOLD
    t["rsrp_margin_lag1"] = t["rsrp_margin"].shift(1)
    t["DL_lag1"] = t["DL_bitrate"].shift(1)
    t["UL_lag1"] = t["UL_bitrate"].shift(1)
    t["delta_DL"] = t["DL_bitrate"].diff()
    t["DL_rmean"] = t["DL_bitrate"].rolling(ROLL_WIN, min_periods=1).mean()
    t["Speed_rmean"] = t["Speed"].rolling(ROLL_WIN, min_periods=1).mean()

    return t


def build_X(eng_df: pd.DataFrame) -> pd.DataFrame:
    row = eng_df.tail(1).copy().reset_index(drop=True)
    for col in FEATURE_COLS:
        if col not in row.columns:
            row[col] = np.nan
    return row[FEATURE_COLS].astype(float)


def reset_state():
    state["St_prev"] = 0.0
    state["Pt_buf"] = collections.deque(maxlen=VOL_WINDOW + 1)


@mobility_bp.route("")
@mobility_bp.route("/")
def index():
    return render_template("mobility.html")


@mobility_bp.route("/api/reset", methods=["POST"])
def reset():
    reset_state()
    return jsonify({"status": "ok"})


@mobility_bp.route("/api/status")
def status():
    return jsonify(
        {
            "model": type(MODEL).__name__,
            "features": len(FEATURE_COLS),
            "rt_threshold": RT_THRESH,
            "alpha_ema": ALPHA_EMA,
            "vol_window": VOL_WINDOW,
        }
    )


@mobility_bp.route("/api/debug")
def debug():
    sim_producible = set(
        [f"{c}_lag{lag}" for c in SIGNAL_COLS for lag in [1, 2, 3]]
        + [f"delta_{c}" for c in SIGNAL_COLS]
        + [f"delta2_{c}" for c in SIGNAL_COLS]
        + [f"{c}_rmean" for c in SIGNAL_COLS]
        + [f"{c}_rstd" for c in SIGNAL_COLS]
        + [f"{c}_rmin" for c in SIGNAL_COLS]
        + list(SIGNAL_COLS)
        + [
            "rsrp_margin",
            "rsrp_margin_lag1",
            "DL_bitrate",
            "UL_bitrate",
            "Speed",
            "DL_lag1",
            "UL_lag1",
            "delta_DL",
            "DL_rmean",
            "Speed_rmean",
            "NRxRSRP",
            "NRxRSRQ",
        ]
    )
    present = [f for f in FEATURE_COLS if f in sim_producible]
    missing = [f for f in FEATURE_COLS if f not in sim_producible]
    return jsonify(
        {
            "total": len(FEATURE_COLS),
            "present_in_sim": len(present),
            "filled_with_nan": len(missing),
            "missing": missing,
            "note": "Missing simulation columns are filled with NaN; HistGradientBoosting handles NaN values.",
        }
    )


@mobility_bp.route("/api/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json(force=True)
        rows = data.get("window", [])

        if len(rows) < 2:
            return jsonify(
                {
                    "Pt": 0.0,
                    "St": 0.0,
                    "Vt": 0.0,
                    "Rt": 0.0,
                    "handover": False,
                    "feature_count": 0,
                    "note": "warming_up",
                }
            )

        df = pd.DataFrame(rows)
        base_ts = pd.Timestamp("2024-01-01")
        df["Timestamp"] = [
            base_ts + pd.Timedelta(seconds=int(row.get("t", i)))
            for i, row in enumerate(rows)
        ]
        df["trace_id"] = "sim_trace"
        df["NRxRSRP"] = float(data.get("target_rsrp", float(df["RSRP"].iloc[-1]) - 3))
        df["NRxRSRQ"] = df["RSRQ"].astype(float) - 2.0
        df["Y"] = np.nan

        for col in ["PINGAVG", "PINGMIN", "PINGMAX", "PINGSTDEV", "PINGLOSS", "Longitude", "Latitude"]:
            df[col] = np.nan

        eng = engineer_features_for_trace(df)
        X_t = build_X(eng)
        Pt = float(MODEL.predict_proba(X_t)[0, 1])

        alpha = float(data.get("alpha_ema", ALPHA_EMA))
        St = alpha * Pt + (1 - alpha) * state["St_prev"]
        state["St_prev"] = St

        state["Pt_buf"].append(Pt)
        buf = list(state["Pt_buf"])
        Vt = 0.0
        if len(buf) >= 2:
            diffs = [abs(buf[i] - buf[i - 1]) for i in range(1, len(buf))]
            Vt = min(float(np.mean(diffs)), 1.0)

        Rt = (0.4 * Pt + 0.4 * St) * (1.0 - Vt)

        rt_thr = float(data.get("rt_threshold", RT_THRESH))
        serving_rsrp = float(data.get("serving_rsrp", float(df["RSRP"].iloc[-1])))
        target_rsrp = float(data.get("target_rsrp", serving_rsrp - 1.0))
        handover = bool(Rt > rt_thr and target_rsrp > serving_rsrp)

        return jsonify(
            {
                "Pt": round(Pt, 6),
                "St": round(St, 6),
                "Vt": round(Vt, 6),
                "Rt": round(Rt, 6),
                "handover": handover,
                "feature_count": int(X_t.shape[1]),
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
