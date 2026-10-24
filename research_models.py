import pandas as pd
import numpy as np
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.arima.model import ARIMA
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import GRU, Dense, Dropout

# 1. لود کردن داده‌ها
df = pd.read_csv("persian_gulf_marine_data.csv")
df['DateTime'] = pd.to_datetime(df['DateTime'])
df.set_index('DateTime', inplace=True)

# 2. ساخت ویژگی‌های تاخیری (Lag Features)
# برای پیش‌بینی ۲۴ ساعت آینده
for i in range(1, 25):
    df[f'SWH_lag_{i}'] = df['SWH (m)'].shift(i)
    df[f'SST_lag_{i}'] = df['SST (C)'].shift(i)

df = df.dropna()

# 3. تعریف X و y
X = df.drop(['SWH (m)', 'SST (C)'], axis=1)
y_swh = df['SWH (m)']
y_sst = df['SST (C)']

# 4. تقسیم داده‌ها به آموزش و تست
split_idx = int(len(df) * 0.8)
X_train, X_test = X[:split_idx], X[split_idx:]
y_swh_train, y_swh_test = y_swh[:split_idx], y_swh[split_idx:]
y_sst_train, y_sst_test = y_sst[:split_idx], y_sst[split_idx:]

# --- مدل‌های یادگیری ماشین ---
models = {
    "Linear Regression": LinearRegression(),
    "Decision Tree": DecisionTreeRegressor(),
    "Random Forest": RandomForestRegressor(n_estimators=100),
    "SVR": SVR(kernel='rbf')
}

print("--- SWH Prediction (Machine Learning) ---")
for name, model in models.items():
    model.fit(X_train, y_swh_train)
    score = model.score(X_test, y_swh_test)
    print(f"{name}: R2 = {score:.3f}")

print("\n--- SST Prediction (Machine Learning) ---")
for name, model in models.items():
    model.fit(X_train, y_sst_train)
    score = model.score(X_test, y_sst_test)
    print(f"{name}: R2 = {score:.3f}")

# --- مدل یادگیری عمیق (GRU-DNN) ---
# داده‌ها را به فرمت 3D برای LSTM/GRU تبدیل می‌کنیم
X_train_3d = np.reshape(X_train.values, (X_train.shape[0], 1, X_train.shape[1]))
X_test_3d = np.reshape(X_test.values, (X_test.shape[0], 1, X_test.shape[1]))

model_gru = Sequential([
    GRU(64, input_shape=(X_train_3d.shape[1], X_train_3d.shape[2]), return_sequences=False),
    Dense(32, activation='relu'),
    Dropout(0.2),
    Dense(1) # خروجی
])

model_gru.compile(optimizer='adam', loss='mse')
print("\n--- Training GRU-DNN for SWH ---")
model_gru.fit(X_train_3d, y_swh_train, epochs=10, batch_size=32, validation_split=0.1, verbose=1)
loss = model_gru.evaluate(X_test_3d, y_swh_test)
print(f"GRU-DNN SWH Loss: {loss:.4f}")

# --- مدل آماری (ARIMA) ---
print("\n--- Fitting ARIMA for SWH ---")
# ARIMA با داده‌های سری زمانی خام
# پارامترها (p,d,q) باید با ACF/PACF تعیین شوند، اینجا ساده انتخاب شده‌اند
arima_model = ARIMA(y_swh_train, order=(5,1,0))
arima_result = arima_model.fit()
print(arima_result.summary().tables[1])