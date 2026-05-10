import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneOut, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib

def evaluate_model(model, X, y):
    loo = LeaveOneOut()
    y_true = []
    y_pred = []
    
    for train_index, test_index in loo.split(X):
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]
        
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        
        y_true.append(y_test.values[0])
        y_pred.append(pred[0])
        
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, average='weighted', zero_division=0)
    recall = recall_score(y_true, y_pred, average='weighted', zero_division=0)
    f1 = f1_score(y_true, y_pred, average='weighted', zero_division=0)
    
    return accuracy, precision, recall, f1

def main():
    # 1. Load data
    df = pd.read_csv('training_data.csv')
    
    # 2. Encode labels
    df['Label_Encoded'] = df['Label'].map({'Stable': 0, 'Moderately Disturbed': 1})
    
    X = df[['MCI', 'SCI', 'ASI']]
    y = df['Label_Encoded']
    
    # 3. Traditional Random Forest
    rf_traditional = RandomForestClassifier(random_state=42)
    acc_trad, prec_trad, rec_trad, f1_trad = evaluate_model(rf_traditional, X, y)
    
    print("--- Traditional Random Forest (LOOCV) ---")
    print(f"Accuracy:  {acc_trad:.4f}")
    print(f"Precision: {prec_trad:.4f}")
    print(f"Recall:    {rec_trad:.4f}")
    print(f"F1-Score:  {f1_trad:.4f}\n")
    
    # 4. GridSearchCV for Optimized Random Forest
    param_grid = {
        'n_estimators': [50, 100, 200],
        'max_depth': [None, 5, 10],
        'min_samples_split': [2, 5],
        'class_weight': ['balanced', 'balanced_subsample', None]
    }
    
    # StratifiedKFold or standard KFold is used by default in GridSearchCV for classification (cv=5 if none provided)
    # But since N=26 and class 0 has 6 samples, cv=5 might have folds with only 1 class 0 sample.
    # Let's use cv=3 to ensure at least 2 class 0 samples per fold.
    grid_search = GridSearchCV(RandomForestClassifier(random_state=42), param_grid, cv=3, scoring='f1_weighted', n_jobs=1)
    grid_search.fit(X, y)
    
    best_params = grid_search.best_params_
    print("--- GridSearchCV Best Parameters ---")
    print(best_params)
    print("\n")
    
    # 5. Evaluate Optimized Model with LOOCV
    rf_optimized = RandomForestClassifier(random_state=42, **best_params)
    acc_opt, prec_opt, rec_opt, f1_opt = evaluate_model(rf_optimized, X, y)
    
    print("--- Optimized Random Forest (LOOCV) ---")
    print(f"Accuracy:  {acc_opt:.4f}")
    print(f"Precision: {prec_opt:.4f}")
    print(f"Recall:    {rec_opt:.4f}")
    print(f"F1-Score:  {f1_opt:.4f}\n")
    
    # 6. Feature Importance Ranking
    rf_optimized.fit(X, y)
    importances = rf_optimized.feature_importances_
    features = X.columns
    print("--- Feature Importance ---")
    for f, imp in zip(features, importances):
        print(f"{f}: {imp:.4f}")
    
    # 7. Save the model
    joblib.dump(rf_optimized, 'sedimentra_rf_model.pkl')
    print("\nModel saved to 'sedimentra_rf_model.pkl'")

if __name__ == '__main__':
    main()
