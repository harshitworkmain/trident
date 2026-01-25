# -*- coding: utf-8 -*-
"""
PyTorch LSTM Model Training Script
Creates a .pth model file for weather prediction
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from meteostat import Stations, Hourly
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt

class WeatherLSTM(nn.Module):
    def __init__(self, input_size=1, hidden_size=50, num_layers=2, output_size=1, dropout=0.2):
        super(WeatherLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, 
                           batch_first=True, dropout=dropout)
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(hidden_size, 25)
        self.fc2 = nn.Linear(25, output_size)
        
    def forward(self, x):
        # Initialize hidden state on the same device as input
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size, device=x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size, device=x.device)
        
        # LSTM forward pass
        out, _ = self.lstm(x, (h0, c0))
        
        # Take the last output
        out = self.dropout(out[:, -1, :])
        out = torch.relu(self.fc1(out))
        out = self.dropout(out)
        out = self.fc2(out)
        
        return out

def get_historical_weather(city, start_date, end_date, filename="data/chennai_weather.csv"):
    """Fetch historical weather data"""
    stations = Stations().nearby(13.0827, 80.2707)  # Chennai coordinates
    station = stations.fetch(1)
    
    if station.empty:
        print("No weather stations found nearby.")
        return None
    
    station_id = station.index[0]
    weather_data = Hourly(station_id, start_date, end_date).fetch()
    
    if weather_data.empty:
        print("No weather data available.")
        return None
    
    weather_data.reset_index(inplace=True)
    file_exists = os.path.isfile(filename)
    weather_data.to_csv(filename, mode='a', header=not file_exists, index=False)
    print(f"Weather data from {start_date} to {end_date} saved to {filename}")
    return weather_data

def create_sequences(data, time_steps=24):
    """Create time series sequences for LSTM"""
    X, y = [], []
    for i in range(len(data) - time_steps):
        X.append(data[i:i + time_steps].flatten())  # Flatten to 1D
        y.append(data[i + time_steps])
    return np.array(X), np.array(y)

def train_model():
    """Main training function"""
    print("🌤️ Starting PyTorch LSTM Weather Model Training...")
    
    # Check for CUDA availability
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"🖥️ Using device: {device}")
    if torch.cuda.is_available():
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
        print(f"   CUDA Version: {torch.version.cuda}")
        print(f"   GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    # 1. Get weather data
    print("\n📊 Fetching weather data...")
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=730)  # 2 years
    
    # Try to load existing data or fetch new
    if os.path.exists("data/chennai_weather.csv"):
        print("Loading existing weather data...")
        df = pd.read_csv("data/chennai_weather.csv")
    else:
        print("Fetching new weather data...")
        get_historical_weather("Chennai", start_date, end_date)
        df = pd.read_csv("data/chennai_weather.csv")
    
    print(f"Loaded {len(df)} weather records")
    
    # 2. Prepare data
    print("\n🔄 Preparing data...")
    data = df[['temp']].values
    scaler = MinMaxScaler(feature_range=(0, 1))
    data_scaled = scaler.fit_transform(data)
    
    # Create sequences
    time_steps = 24
    X, y = create_sequences(data_scaled, time_steps)
    
    # Split data
    train_size = int(len(X) * 0.8)
    X_train, y_train = X[:train_size], y[:train_size]
    X_test, y_test = X[train_size:], y[train_size:]
    
    # Convert to PyTorch tensors and move to device
    X_train = torch.FloatTensor(X_train).to(device)  # Shape: (samples, time_steps)
    y_train = torch.FloatTensor(y_train).to(device)
    X_test = torch.FloatTensor(X_test).to(device)
    y_test = torch.FloatTensor(y_test).to(device)
    
    # Reshape for LSTM input (samples, time_steps, features)
    # X_train and X_test are (samples, time_steps), we need (samples, time_steps, 1)
    X_train = X_train.unsqueeze(-1)  # Add feature dimension: (samples, time_steps, 1)
    X_test = X_test.unsqueeze(-1)    # Add feature dimension: (samples, time_steps, 1)
    
    print(f"Training samples: {X_train.shape[0]}")
    print(f"Test samples: {X_test.shape[0]}")
    
    # 3. Create model
    print("\n🧠 Creating LSTM model...")
    model = WeatherLSTM(input_size=1, hidden_size=50, num_layers=2, output_size=1, dropout=0.2)
    model = model.to(device)  # Move model to GPU
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    # 4. Train model
    print("\n🏋️ Training model...")
    epochs = 100
    batch_size = 15
    
    # Create data loaders
    train_dataset = TensorDataset(X_train, y_train)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    
    model.train()
    train_losses = []
    
    for epoch in range(epochs):
        epoch_loss = 0
        for batch_X, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
        
        avg_loss = epoch_loss / len(train_loader)
        train_losses.append(avg_loss)
        
        if (epoch + 1) % 5 == 0:
            print(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.6f}")
    
    # 5. Evaluate model
    print("\n📈 Evaluating model...")
    model.eval()
    with torch.no_grad():
        test_predictions = model(X_test)
        test_loss = criterion(test_predictions, y_test)
        print(f"Test Loss: {test_loss:.6f}")
    
    # 6. Save model and scaler
    print("\n💾 Saving model...")
    torch.save({
        'model_state_dict': model.state_dict(),
        'model_architecture': {
            'input_size': 1,
            'hidden_size': 50,
            'num_layers': 2,
            'output_size': 1,
            'dropout': 0.2
        },
        'scaler': scaler,
        'time_steps': time_steps,
        'training_losses': train_losses
    }, 'data/weather_lstm_model.pth')
    
    print("✅ Model saved as 'data/weather_lstm_model.pth'")
    
    # 7. Plot training results
    plt.figure(figsize=(12, 5))
    
    # Plot training loss
    plt.subplot(1, 2, 1)
    plt.plot(train_losses)
    plt.title('Training Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.grid(True)
    
    # Plot predictions vs actual
    plt.subplot(1, 2, 2)
    predictions = test_predictions.cpu().numpy()
    actual = y_test.cpu().numpy()
    
    # Convert back to original scale
    predictions_original = scaler.inverse_transform(predictions)
    actual_original = scaler.inverse_transform(actual.reshape(-1, 1))
    
    plt.plot(actual_original[:100], label='Actual', alpha=0.7)
    plt.plot(predictions_original[:100], label='Predicted', alpha=0.7)
    plt.title('Predictions vs Actual (First 100 samples)')
    plt.xlabel('Time')
    plt.ylabel('Temperature (°C)')
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig('data/training_results.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # 8. Make a sample prediction
    print("\n🔮 Making sample prediction...")
    latest_data = data_scaled[-time_steps:].flatten()  # Flatten to 1D
    latest_tensor = torch.FloatTensor(latest_data).unsqueeze(0).unsqueeze(-1).to(device)  # Shape: (1, time_steps, 1)
    
    model.eval()
    with torch.no_grad():
        prediction = model(latest_tensor)
        prediction_original = scaler.inverse_transform(prediction.cpu().numpy())
        print(f"Predicted temperature for next hour: {prediction_original[0][0]:.2f}°C")
    
    print("\n🎉 Training completed successfully!")
    return model, scaler

if __name__ == "__main__":
    # Install required packages
    print("Installing required packages...")
    os.system("pip install torch torchvision torchaudio numpy pandas matplotlib seaborn scikit-learn meteostat")
    
    # Train the model
    model, scaler = train_model()
