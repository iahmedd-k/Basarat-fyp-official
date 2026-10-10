import psycopg2
from datetime import date
import pandas as pd
from app.data.features.labeling import DEFAULT_THRESHOLD

DB_URL = "postgresql://neondb_owner:npg_9RQm1usGdEJS@ep-bold-grass-b42cai5z-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require"
FEATURES_PATH = "data/features/features_daily.parquet"

def resolve_all_past_predictions():
    print("Connecting to DB and loading features...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Load features parquet
    features = pd.read_parquet(FEATURES_PATH)
    features["date"] = pd.to_datetime(features["date"]).dt.date
    
    # Query all unresolved past predictions
    cur.execute("""
        SELECT id, symbol, as_of_date, target_date, predicted_direction 
        FROM predictions 
        WHERE target_date <= CURRENT_DATE AND actual_direction IS NULL;
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} unresolved past predictions.")
    
    updated_count = 0
    correct_count = 0
    scored_count = 0
    
    for row_id, symbol, as_of_date, target_date, predicted_direction in rows:
        sym_df = features[features["symbol"] == symbol].sort_values("date")
        
        as_of_close = sym_df.loc[sym_df["date"] == as_of_date, "close"]
        target_close = sym_df.loc[sym_df["date"] == target_date, "close"]
        
        # If target_date is beyond parquet (e.g. 2026-09-21), use latest available close for symbol in parquet
        if as_of_close.empty:
            as_of_close = sym_df.loc[sym_df["date"] <= as_of_date, "close"].tail(1)
        if target_close.empty:
            target_close = sym_df.loc[sym_df["date"] <= target_date, "close"].tail(1)
            
        if as_of_close.empty or target_close.empty:
            print(f"Skipping {symbol} ({as_of_date} -> {target_date}): No price data")
            continue
            
        as_of_p = float(as_of_close.iloc[0])
        target_p = float(target_close.iloc[0])
        
        fwd_return = (target_p - as_of_p) / as_of_p
        
        if fwd_return > DEFAULT_THRESHOLD:
            actual_direction = "bullish"
        elif fwd_return < -DEFAULT_THRESHOLD:
            actual_direction = "bearish"
        else:
            actual_direction = "sideways"
            
        if predicted_direction == "uncertain":
            was_correct = None
        else:
            was_correct = (predicted_direction == actual_direction)
            scored_count += 1
            if was_correct:
                correct_count += 1
                
        cur.execute("""
            UPDATE predictions 
            SET actual_direction = %s, was_correct = %s 
            WHERE id = %s;
        """, (actual_direction, was_correct, row_id))
        updated_count += 1
        print(f"Resolved {symbol} [{as_of_date} -> {target_date}]: Return={fwd_return:+.4f} | Actual={actual_direction} | Pred={predicted_direction} | Correct={was_correct}")
        
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\nSuccessfully updated {updated_count} predictions in database.")
    if scored_count > 0:
        print(f"Scored: {correct_count}/{scored_count} ({round(correct_count/scored_count*100, 1)}% accuracy)")

if __name__ == "__main__":
    resolve_all_past_predictions()
