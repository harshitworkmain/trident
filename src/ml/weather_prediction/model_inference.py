# -*- coding: utf-8 -*-
"""
Script to load and use the trained PyTorch LSTM model for weather predictions
"""

import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

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
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size, device=x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size, device=x.device)
        
        out, _ = self.lstm(x, (h0, c0))
        out = self.dropout(out[:, -1, :])
        out = torch.relu(self.fc1(out))
        out = self.dropout(out)
        out = self.fc2(out)
        
        return out

class WeatherPredictor:
    def __init__(self, model_path='data/weather_lstm_model.pth'):
        """Initialize the weather predictor with a trained model"""
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.time_steps = 24
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"🖥️ Using device: {self.device}")
        self.load_model()
    
    def load_model(self):
        """Load the trained model and scaler"""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file {self.model_path} not found. Please train the model first.")
        
        print(f"🔄 Loading model from {self.model_path}...")
        
        # Load model checkpoint
        checkpoint = torch.load(self.model_path, map_location='cpu')
        
        # Recreate model architecture
        arch = checkpoint['model_architecture']
        self.model = WeatherLSTM(
            input_size=arch['input_size'],
            hidden_size=arch['hidden_size'],
            num_layers=arch['num_layers'],
            output_size=arch['output_size'],
            dropout=arch['dropout']
        )
        
        # Load model weights
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model = self.model.to(self.device)  # Move model to GPU
        self.model.eval()
        
        # Load scaler and other parameters
        self.scaler = checkpoint['scaler']
        self.time_steps = checkpoint['time_steps']
        
        print("✅ Model loaded successfully!")
    
    def predict_next_hour(self, temperature_data):
        """Predict temperature for the next hour"""
        if len(temperature_data) < self.time_steps:
            raise ValueError(f"Need at least {self.time_steps} data points for prediction")
        
        # Use last time_steps data points
        recent_data = temperature_data[-self.time_steps:]
        
        # Scale the data
        data_scaled = self.scaler.transform(np.array(recent_data).reshape(-1, 1))
        
        # Convert to tensor and move to device
        input_tensor = torch.FloatTensor(data_scaled.flatten()).unsqueeze(0).unsqueeze(-1).to(self.device)  # Shape: (1, time_steps, 1)
        
        # Make prediction
        with torch.no_grad():
            prediction = self.model(input_tensor)
            prediction_original = self.scaler.inverse_transform(prediction.cpu().numpy())
        
        return prediction_original[0][0]
    
    def predict_multiple_hours(self, temperature_data, hours=24):
        """Predict temperature for multiple hours ahead"""
        predictions = []
        current_data = temperature_data.copy()
        
        for hour in range(hours):
            pred_temp = self.predict_next_hour(current_data)
            predictions.append(pred_temp)
            
            # Add prediction to data for next prediction (sliding window)
            current_data = np.append(current_data, pred_temp)
        
        return predictions
    
    def load_weather_data(self, csv_path='data/chennai_weather.csv'):
        """Load weather data from CSV file"""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Weather data file {csv_path} not found.")
        
        df = pd.read_csv(csv_path)
        return df['temp'].values
    
    def plot_predictions(self, actual_data, predictions, title="Weather Predictions"):
        """Plot actual vs predicted temperatures"""
        plt.figure(figsize=(12, 6))
        
        # Plot actual data
        plt.plot(actual_data[-100:], label='Actual Temperature', alpha=0.7, color='blue')
        
        # Plot predictions
        pred_start = len(actual_data) - 100 + len(actual_data) - 100
        pred_x = range(len(actual_data) - 100, len(actual_data) - 100 + len(predictions))
        plt.plot(pred_x, predictions, label='Predicted Temperature', alpha=0.7, color='red')
        
        plt.title(title)
        plt.xlabel('Time')
        plt.ylabel('Temperature (°C)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

def main():
    """Main function to demonstrate model usage"""
    print("🌤️ Weather Prediction using Trained PyTorch Model")
    print("=" * 50)
    
    try:
        # Initialize predictor
        predictor = WeatherPredictor()
        
        # Load weather data
        print("\n📊 Loading weather data...")
        temperature_data = predictor.load_weather_data()
        print(f"Loaded {len(temperature_data)} temperature records")
        
        # Make single prediction
        print("\n🔮 Making single prediction...")
        next_hour_temp = predictor.predict_next_hour(temperature_data)
        print(f"Predicted temperature for next hour: {next_hour_temp:.2f}°C")
        
        # Make multiple predictions
        print("\n🔮 Making 24-hour predictions...")
        predictions_24h = predictor.predict_multiple_hours(temperature_data, hours=24)
        
        print("24-Hour Temperature Forecast:")
        for i, temp in enumerate(predictions_24h):
            print(f"Hour {i+1:2d}: {temp:.2f}°C")
        
        # Plot predictions
        print("\n📈 Plotting predictions...")
        predictor.plot_predictions(temperature_data, predictions_24h, "24-Hour Temperature Forecast")
        
        # Show recent actual vs predicted comparison
        print("\n📊 Recent data analysis...")
        recent_actual = temperature_data[-24:]
        recent_pred = predictor.predict_multiple_hours(temperature_data[:-24], hours=24)
        
        plt.figure(figsize=(12, 6))
        plt.plot(recent_actual, label='Actual (Last 24h)', marker='o', alpha=0.7)
        plt.plot(recent_pred, label='Predicted (Last 24h)', marker='s', alpha=0.7)
        plt.title('Actual vs Predicted Temperature (Last 24 Hours)')
        plt.xlabel('Hour')
        plt.ylabel('Temperature (°C)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
        
        # Calculate prediction accuracy
        mae = np.mean(np.abs(np.array(recent_actual) - np.array(recent_pred)))
        mse = np.mean((np.array(recent_actual) - np.array(recent_pred)) ** 2)
        rmse = np.sqrt(mse)
        
        print(f"\n📊 Prediction Accuracy Metrics:")
        print(f"Mean Absolute Error: {mae:.2f}°C")
        print(f"Root Mean Square Error: {rmse:.2f}°C")
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Please run 'train_pytorch_model.py' first to create the model.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
