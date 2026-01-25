# -*- coding: utf-8 -*-
"""
Weather Data Collection Script
Fetches and manages historical weather data for Chennai
"""

import pandas as pd
import numpy as np
from meteostat import Stations, Hourly
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
import seaborn as sns

class WeatherDataCollector:
    def __init__(self, city="Chennai", lat=13.0827, lon=80.2707):
        """Initialize weather data collector for Chennai"""
        self.city = city
        self.lat = lat
        self.lon = lon
        self.station_id = None
        self.data_file = f"data/{city.lower()}_weather.csv"
        
    def find_nearest_station(self):
        """Find the nearest weather station to Chennai"""
        print(f"🔍 Finding nearest weather station to {self.city}...")
        
        stations = Stations().nearby(self.lat, self.lon)
        station = stations.fetch(1)
        
        if station.empty:
            print("❌ No weather stations found nearby.")
            return None
        
        self.station_id = station.index[0]
        station_info = station.iloc[0]
        
        print(f"✅ Found station: {station_info['name']} (ID: {self.station_id})")
        print(f"   Distance: {station_info['distance']:.2f} km")
        print(f"   Elevation: {station_info['elevation']} m")
        
        return self.station_id
    
    def fetch_weather_data(self, start_date, end_date, save_to_file=True):
        """Fetch weather data for the specified date range"""
        if not self.station_id:
            self.find_nearest_station()
        
        if not self.station_id:
            return None
        
        print(f"📊 Fetching weather data from {start_date} to {end_date}...")
        
        try:
            # Get hourly weather data
            weather_data = Hourly(self.station_id, start_date, end_date).fetch()
            
            if weather_data.empty:
                print("❌ No weather data available for the specified period.")
                return None
            
            # Reset index for proper CSV formatting
            weather_data.reset_index(inplace=True)
            
            print(f"✅ Fetched {len(weather_data)} weather records")
            
            # Save to CSV if requested
            if save_to_file:
                file_exists = os.path.isfile(self.data_file)
                weather_data.to_csv(self.data_file, mode='a', header=not file_exists, index=False)
                print(f"💾 Data saved to {self.data_file}")
            
            return weather_data
            
        except Exception as e:
            print(f"❌ Error fetching weather data: {e}")
            return None
    
    def get_historical_data(self, days=730, save_to_file=True):
        """Get historical weather data for the last N days"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        print(f"📅 Fetching last {days} days of weather data...")
        return self.fetch_weather_data(start_date, end_date, save_to_file)
    
    def load_existing_data(self):
        """Load existing weather data from CSV file"""
        if not os.path.exists(self.data_file):
            print(f"❌ Weather data file {self.data_file} not found.")
            return None
        
        print(f"📂 Loading existing weather data from {self.data_file}...")
        df = pd.read_csv(self.data_file)
        print(f"✅ Loaded {len(df)} records")
        
        return df
    
    def clean_data(self, df):
        """Clean and preprocess weather data"""
        print("🧹 Cleaning weather data...")
        
        # Remove duplicates
        initial_count = len(df)
        df = df.drop_duplicates()
        print(f"   Removed {initial_count - len(df)} duplicate records")
        
        # Handle missing values
        missing_before = df.isnull().sum().sum()
        df = df.dropna()
        print(f"   Removed {missing_before} missing values")
        
        # Convert time column to datetime
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df = df.sort_values('time')
        
        # Remove outliers (temperatures outside reasonable range)
        if 'temp' in df.columns:
            temp_outliers = ((df['temp'] < -10) | (df['temp'] > 50)).sum()
            df = df[(df['temp'] >= -10) & (df['temp'] <= 50)]
            print(f"   Removed {temp_outliers} temperature outliers")
        
        print(f"✅ Data cleaning complete. Final dataset: {len(df)} records")
        return df
    
    def analyze_data(self, df):
        """Analyze and visualize weather data"""
        print("\n📊 Weather Data Analysis")
        print("=" * 40)
        
        # Basic statistics
        print("\n📈 Basic Statistics:")
        print(df.describe())
        
        # Data quality check
        print(f"\n🔍 Data Quality:")
        print(f"   Total records: {len(df)}")
        print(f"   Date range: {df['time'].min()} to {df['time'].max()}")
        print(f"   Missing values: {df.isnull().sum().sum()}")
        
        # Temperature analysis
        if 'temp' in df.columns:
            print(f"\n🌡️ Temperature Analysis:")
            print(f"   Average temperature: {df['temp'].mean():.2f}°C")
            print(f"   Min temperature: {df['temp'].min():.2f}°C")
            print(f"   Max temperature: {df['temp'].max():.2f}°C")
            print(f"   Temperature range: {df['temp'].max() - df['temp'].min():.2f}°C")
        
        # Create visualizations
        self.create_visualizations(df)
    
    def create_visualizations(self, df):
        """Create weather data visualizations"""
        print("\n📊 Creating visualizations...")
        
        # Set up the plotting style
        plt.style.use('seaborn-v0_8')
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Weather Data Analysis - {self.city}', fontsize=16)
        
        # 1. Temperature over time
        if 'temp' in df.columns and 'time' in df.columns:
            axes[0, 0].plot(df['time'], df['temp'], alpha=0.7, linewidth=0.5)
            axes[0, 0].set_title('Temperature Over Time')
            axes[0, 0].set_ylabel('Temperature (°C)')
            axes[0, 0].tick_params(axis='x', rotation=45)
        
        # 2. Temperature distribution
        if 'temp' in df.columns:
            axes[0, 1].hist(df['temp'], bins=50, alpha=0.7, color='skyblue', edgecolor='black')
            axes[0, 1].set_title('Temperature Distribution')
            axes[0, 1].set_xlabel('Temperature (°C)')
            axes[0, 1].set_ylabel('Frequency')
        
        # 3. Humidity over time (if available)
        if 'rhum' in df.columns and 'time' in df.columns:
            axes[1, 0].plot(df['time'], df['rhum'], alpha=0.7, color='green', linewidth=0.5)
            axes[1, 0].set_title('Humidity Over Time')
            axes[1, 0].set_ylabel('Humidity (%)')
            axes[1, 0].tick_params(axis='x', rotation=45)
        
        # 4. Wind speed over time (if available)
        if 'wspd' in df.columns and 'time' in df.columns:
            axes[1, 1].plot(df['time'], df['wspd'], alpha=0.7, color='orange', linewidth=0.5)
            axes[1, 1].set_title('Wind Speed Over Time')
            axes[1, 1].set_ylabel('Wind Speed (km/h)')
            axes[1, 1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(f'data/{self.city.lower()}_weather_analysis.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        # Monthly temperature trends
        if 'temp' in df.columns and 'time' in df.columns:
            df['month'] = df['time'].dt.month
            monthly_temp = df.groupby('month')['temp'].agg(['mean', 'min', 'max'])
            
            plt.figure(figsize=(10, 6))
            plt.plot(monthly_temp.index, monthly_temp['mean'], marker='o', label='Average')
            plt.fill_between(monthly_temp.index, monthly_temp['min'], monthly_temp['max'], alpha=0.3, label='Range')
            plt.title(f'Monthly Temperature Trends - {self.city}')
            plt.xlabel('Month')
            plt.ylabel('Temperature (°C)')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(range(1, 13), ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
            plt.tight_layout()
            plt.savefig(f'data/{self.city.lower()}_monthly_trends.png', dpi=300, bbox_inches='tight')
            plt.show()
    
    def export_clean_data(self, df, filename=None):
        """Export cleaned data to a new CSV file"""
        if filename is None:
            filename = f"data/{self.city.lower()}_weather_clean.csv"
        
        df.to_csv(filename, index=False)
        print(f"💾 Clean data exported to {filename}")
        return filename

def main():
    """Main function to demonstrate weather data collection"""
    print("🌤️ Weather Data Collection for Chennai")
    print("=" * 50)
    
    # Initialize collector
    collector = WeatherDataCollector()
    
    # Check if data already exists
    if os.path.exists(collector.data_file):
        print(f"📂 Found existing data file: {collector.data_file}")
        choice = input("Do you want to (1) Load existing data, (2) Fetch new data, or (3) Both? [1/2/3]: ")
    else:
        choice = "2"  # Fetch new data if no existing file
    
    df = None
    
    if choice in ["1", "3"]:
        # Load existing data
        df = collector.load_existing_data()
        if df is not None:
            df = collector.clean_data(df)
            collector.analyze_data(df)
    
    if choice in ["2", "3"]:
        # Fetch new data
        days = int(input("How many days of historical data to fetch? [default: 730]: ") or "730")
        new_data = collector.get_historical_data(days=days)
        
        if new_data is not None:
            if df is not None:
                # Combine with existing data
                df = pd.concat([df, new_data], ignore_index=True)
                df = collector.clean_data(df)
            else:
                df = collector.clean_data(new_data)
            
            collector.analyze_data(df)
    
    if df is not None:
        # Export clean data
        clean_file = collector.export_clean_data(df)
        print(f"\n✅ Weather data collection complete!")
        print(f"   Clean data file: {clean_file}")
        print(f"   Records: {len(df)}")
        print(f"   Date range: {df['time'].min()} to {df['time'].max()}")
    else:
        print("❌ No weather data available.")

if __name__ == "__main__":
    main()
