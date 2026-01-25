# -*- coding: utf-8 -*-
"""
Graph-based Risk Analysis Script
Implements risk propagation, flood modeling, and storm tracking using NetworkX
"""

import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import MultiPoint, Polygon
import geopandas as gpd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class RiskPropagationAnalyzer:
    def __init__(self):
        """Initialize the risk propagation analyzer"""
        self.areas = {
            "Marina Beach": {"temp": 32, "humidity": 80, "wind_speed": 18, "risk": 0.9, "lat": 13.0500, "lon": 80.2824},
            "Besant Nagar": {"temp": 31, "humidity": 78, "wind_speed": 17, "risk": 0.85, "lat": 13.0007, "lon": 80.2667},
            "Thiruvanmiyur": {"temp": 30, "humidity": 75, "wind_speed": 15, "risk": 0.7, "lat": 12.9847, "lon": 80.2599},
            "Adyar": {"temp": 31, "humidity": 74, "wind_speed": 12, "risk": 0.65, "lat": 13.0067, "lon": 80.2565},
            "Mylapore": {"temp": 32, "humidity": 76, "wind_speed": 13, "risk": 0.7, "lat": 13.0330, "lon": 80.2684},
            "Santhome": {"temp": 32, "humidity": 79, "wind_speed": 14, "risk": 0.8, "lat": 13.0311, "lon": 80.2761},
            "T. Nagar": {"temp": 33, "humidity": 70, "wind_speed": 10, "risk": 0.6, "lat": 13.0418, "lon": 80.2337},
            "Velachery": {"temp": 30, "humidity": 72, "wind_speed": 11, "risk": 0.5, "lat": 12.9815, "lon": 80.2180},
            "Perungudi": {"temp": 29, "humidity": 73, "wind_speed": 12, "risk": 0.55, "lat": 12.9623, "lon": 80.2433},
            "Sholinganallur": {"temp": 28, "humidity": 75, "wind_speed": 14, "risk": 0.6, "lat": 12.9091, "lon": 80.2270}
        }
        
        self.G = nx.Graph()
        self.setup_graph()
    
    def setup_graph(self):
        """Setup the risk propagation graph"""
        print("🏗️ Setting up risk propagation graph...")
        
        # Add nodes to the graph
        for area, data in self.areas.items():
            self.G.add_node(area, **data)
        
        # Define connections between coastal neighborhoods
        edges = [
            ("Marina Beach", "Santhome"),
            ("Santhome", "Mylapore"),
            ("Mylapore", "Adyar"),
            ("Adyar", "Besant Nagar"),
            ("Besant Nagar", "Thiruvanmiyur"),
            ("Thiruvanmiyur", "Velachery"),
            ("Velachery", "Perungudi"),
            ("Perungudi", "Sholinganallur"),
            ("Besant Nagar", "Marina Beach"),
            ("Thiruvanmiyur", "Adyar"),
            ("Mylapore", "T. Nagar"),
            ("T. Nagar", "Velachery")
        ]
        
        # Add weighted edges based on weather parameter differences
        for edge in edges:
            area1, area2 = edge
            weight = (abs(self.areas[area1]["temp"] - self.areas[area2]["temp"]) +
                     abs(self.areas[area1]["wind_speed"] - self.areas[area2]["wind_speed"]) +
                     abs(self.areas[area1]["humidity"] - self.areas[area2]["humidity"]) / 10)
            self.G.add_edge(area1, area2, weight=weight)
        
        print(f"✅ Graph created with {self.G.number_of_nodes()} nodes and {self.G.number_of_edges()} edges")
    
    def propagate_risk(self, iterations=5, decay_factor=0.75):
        """Simulate risk propagation across regions over time"""
        print(f"\n🌊 Running risk propagation simulation ({iterations} iterations)...")
        
        for step in range(iterations):
            new_risk = {}
            for node in self.G.nodes():
                neighbors = list(self.G.neighbors(node))
                if neighbors:
                    risk_sum = sum(self.G.nodes[neighbor]["risk"] * decay_factor for neighbor in neighbors)
                    new_risk[node] = min(1.0, risk_sum / len(neighbors))
                else:
                    new_risk[node] = self.G.nodes[node]["risk"]
            
            # Update risk values
            for node in self.G.nodes():
                self.G.nodes[node]["risk"] = new_risk[node]
            
            print(f"Iteration {step+1}: Risk Levels - {dict(sorted(new_risk.items(), key=lambda x: x[1], reverse=True))}")
        
        return new_risk
    
    def visualize_risk_graph(self):
        """Visualize the risk propagation graph"""
        print("\n📊 Creating risk propagation visualization...")
        
        # Get risk values for coloring
        risk_values = [self.G.nodes[node]["risk"] for node in self.G.nodes()]
        
        # Create colormap based on risk levels
        node_colors = [plt.cm.Reds(risk) for risk in risk_values]
        
        # Get edge weights for thickness
        edge_weights = [self.G[u][v]['weight'] / 10 for u, v in self.G.edges()]
        
        # Create the plot
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(self.G, seed=42)
        
        # Draw the graph
        nx.draw(self.G, pos, 
                with_labels=True, 
                node_size=2000, 
                node_color=node_colors, 
                edge_color='gray', 
                width=edge_weights, 
                font_size=10, 
                font_weight='bold')
        
        # Add risk level annotations
        for node, (x, y) in pos.items():
            risk = self.G.nodes[node]["risk"]
            plt.text(x, y+0.1, f"{risk:.2f}", ha='center', va='bottom', 
                    fontsize=8, bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7))
        
        plt.title("Weather Risk Propagation - Chennai Coastal Areas", fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig('data/risk_propagation_graph.png', dpi=300, bbox_inches='tight')
        plt.show()
    
    def analyze_risk_centrality(self):
        """Analyze risk centrality and identify critical areas"""
        print("\n🔍 Analyzing risk centrality...")
        
        # Calculate various centrality measures
        degree_centrality = nx.degree_centrality(self.G)
        betweenness_centrality = nx.betweenness_centrality(self.G)
        closeness_centrality = nx.closeness_centrality(self.G)
        
        # Create centrality analysis
        centrality_df = pd.DataFrame({
            'Area': list(self.areas.keys()),
            'Risk_Level': [self.G.nodes[area]["risk"] for area in self.areas.keys()],
            'Degree_Centrality': [degree_centrality[area] for area in self.areas.keys()],
            'Betweenness_Centrality': [betweenness_centrality[area] for area in self.areas.keys()],
            'Closeness_Centrality': [closeness_centrality[area] for area in self.areas.keys()]
        })
        
        # Sort by risk level
        centrality_df = centrality_df.sort_values('Risk_Level', ascending=False)
        
        print("\n📊 Risk and Centrality Analysis:")
        print(centrality_df.round(3))
        
        # Identify critical areas (high risk + high centrality)
        critical_areas = centrality_df[
            (centrality_df['Risk_Level'] > 0.7) & 
            (centrality_df['Betweenness_Centrality'] > 0.1)
        ]
        
        print(f"\n⚠️ Critical Areas (High Risk + High Centrality):")
        for _, area in critical_areas.iterrows():
            print(f"   {area['Area']}: Risk={area['Risk_Level']:.2f}, Centrality={area['Betweenness_Centrality']:.3f}")
        
        return centrality_df

class FloodModelingAnalyzer:
    def __init__(self):
        """Initialize the flood modeling analyzer"""
        self.G = nx.DiGraph()
        self.setup_water_network()
    
    def setup_water_network(self):
        """Setup the water flow network"""
        print("🌊 Setting up water flow network...")
        
        # Add edges with water flow capacities (m³/s)
        edges = [
            ("Source", "Marina Beach", 50),
            ("Source", "Adyar River", 40),
            ("Adyar River", "Marina Beach", 20),
            ("Adyar River", "Mylapore", 30),
            ("Marina Beach", "Mylapore", 25),
            ("Mylapore", "T. Nagar", 35),
            ("Mylapore", "Kodambakkam", 15),
            ("T. Nagar", "Sink", 40),
            ("Kodambakkam", "Sink", 20)
        ]
        
        for u, v, cap in edges:
            self.G.add_edge(u, v, capacity=cap)
        
        print(f"✅ Water network created with {self.G.number_of_nodes()} nodes and {self.G.number_of_edges()} edges")
    
    def analyze_water_flow(self):
        """Analyze maximum water flow and identify flood risks"""
        print("\n🌊 Analyzing water flow...")
        
        # Compute maximum flow
        flow_value, flow_dict = nx.maximum_flow(self.G, "Source", "Sink")
        
        print(f"🔹 Maximum Water Flow Capacity: {flow_value} m³/s")
        print(f"\n🔹 Flow Distribution Across Regions:")
        
        for u, flows in flow_dict.items():
            for v, f in flows.items():
                if f > 0:
                    print(f"   {u} → {v}: {f} m³/s")
        
        # Define drainage capacity thresholds
        drainage_capacity = {
            "Marina Beach": 40,
            "Adyar River": 35,
            "Mylapore": 30,
            "T. Nagar": 45,
            "Kodambakkam": 20
        }
        
        # Identify flood-prone areas
        flood_risk_areas = []
        for node, capacity in drainage_capacity.items():
            if node in self.G.nodes():
                total_inflow = sum(flow_dict[prev][node] for prev in self.G.predecessors(node))
                if total_inflow > capacity:
                    flood_risk_areas.append(node)
        
        print(f"\n🔹 High Flood Risk Areas (Exceeding Drainage Capacity):")
        if flood_risk_areas:
            for area in flood_risk_areas:
                print(f"   ⚠ {area} (Risk Level: HIGH)")
        else:
            print("   ✅ No areas exceed drainage capacity.")
        
        # Compute critical zones
        centrality = nx.betweenness_centrality(self.G, weight="capacity")
        critical_zones = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:3]
        
        print(f"\n🔹 Critical Water Flow Zones (High Betweenness Centrality):")
        for node, value in critical_zones:
            print(f"   🌊 {node}: {round(value, 3)}")
        
        return flow_value, flow_dict, flood_risk_areas, critical_zones
    
    def visualize_water_network(self, flood_risk_areas):
        """Visualize the water flow network with flood risks"""
        print("\n📊 Creating water flow network visualization...")
        
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(self.G, seed=42)
        
        # Draw the main network
        nx.draw(self.G, pos, 
                with_labels=True, 
                node_color="lightblue", 
                edge_color="gray", 
                node_size=3000, 
                font_size=10, 
                font_weight="bold")
        
        # Highlight flood-prone areas in red
        if flood_risk_areas:
            nx.draw_networkx_nodes(self.G, pos, 
                                 nodelist=flood_risk_areas, 
                                 node_color="red", 
                                 node_size=3500, 
                                 alpha=0.6)
        
        # Draw edge labels (capacity values)
        edge_labels = {(u, v): f"{d['capacity']} m³/s" for u, v, d in self.G.edges(data=True)}
        nx.draw_networkx_edge_labels(self.G, pos, edge_labels=edge_labels, font_size=9)
        
        plt.title("Water Flow Network for Chennai Flood Risk Prediction", fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig('data/flood_risk_network.png', dpi=300, bbox_inches='tight')
        plt.show()

class StormTrackingAnalyzer:
    def __init__(self):
        """Initialize the storm tracking analyzer"""
        self.locations = {0: "Bay of Bengal", 1: "Marina Beach", 2: "Mylapore", 3: "T. Nagar", 4: "Kodambakkam"}
        self.storm_graph = []
        self.V = len(self.locations)
        self.setup_storm_network()
    
    def setup_storm_network(self):
        """Setup the storm tracking network"""
        print("🌪️ Setting up storm tracking network...")
        
        # Add storm movement edges with wind speeds as weights
        edges = [
            (0, 1, 10),  # Bay of Bengal → Marina Beach
            (1, 2, 15),  # Marina Beach → Mylapore
            (2, 3, 8),   # Mylapore → T. Nagar
            (3, 4, 12),  # T. Nagar → Kodambakkam
            (0, 2, 20),  # Direct Bay of Bengal → Mylapore
            (1, 3, 25)   # Direct Marina Beach → T. Nagar
        ]
        
        for u, v, w in edges:
            self.storm_graph.append((u, v, w))
        
        print(f"✅ Storm network created with {len(self.storm_graph)} storm paths")
    
    def bellman_ford_storm_path(self, src=0):
        """Compute shortest storm path using Bellman-Ford algorithm"""
        print(f"\n🌪️ Computing storm path from {self.locations[src]}...")
        
        dist = {i: float("inf") for i in range(self.V)}
        dist[src] = 0
        
        # Relax all edges |V| - 1 times
        for _ in range(self.V - 1):
            for u, v, w in self.storm_graph:
                if dist[u] != float("inf") and dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
        
        # Convert results to location names
        storm_path = {self.locations[i]: dist[i] for i in range(self.V)}
        
        print("🌪️ Shortest Storm Path Prediction:")
        for loc, time in sorted(storm_path.items(), key=lambda x: x[1]):
            print(f"   {loc}: {time} (relative travel time)")
        
        return storm_path
    
    def visualize_storm_tracking(self):
        """Visualize the storm tracking network"""
        print("\n📊 Creating storm tracking visualization...")
        
        # Create NetworkX graph for visualization
        G = nx.DiGraph()
        for u, v, w in self.storm_graph:
            G.add_edge(self.locations[u], self.locations[v], weight=w)
        
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(G, seed=42)
        
        # Draw nodes and edges
        nx.draw(G, pos, 
                with_labels=True, 
                node_color="lightblue", 
                edge_color="gray", 
                node_size=3000, 
                font_size=10, 
                font_weight="bold")
        
        # Highlight storm start point
        nx.draw_networkx_nodes(G, pos, 
                             nodelist=["Bay of Bengal"], 
                             node_color="red", 
                             node_size=3500, 
                             alpha=0.7)
        
        # Draw edge labels (wind speeds)
        edge_labels = {(u, v): f"{d['weight']} km/h" for u, v, d in G.edges(data=True)}
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=9)
        
        plt.title("Storm Path Prediction Using Bellman-Ford Algorithm", fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig('data/storm_tracking_network.png', dpi=300, bbox_inches='tight')
        plt.show()

class GeospatialRiskAnalyzer:
    def __init__(self, areas_data):
        """Initialize geospatial risk analyzer"""
        self.areas = areas_data
        self.affected_points = [(data["lat"], data["lon"]) for data in areas_data.values()]
    
    def compute_convex_hull(self):
        """Compute convex hull of affected areas"""
        print("\n🗺️ Computing convex hull of affected areas...")
        
        hull = MultiPoint(self.affected_points).convex_hull
        print(f"Convex Hull Boundary: {hull}")
        
        return hull
    
    def visualize_risk_zones(self, hull):
        """Visualize risk zones on a map"""
        print("\n📊 Creating geospatial risk visualization...")
        
        # Convert hull to GeoDataFrame
        gdf = gpd.GeoDataFrame({'geometry': [hull]})
        
        # Create the plot
        fig, ax = plt.subplots(figsize=(12, 10))
        gdf.plot(ax=ax, color="red", alpha=0.5, edgecolor="black")
        
        # Add affected points
        x, y = zip(*self.affected_points)
        ax.scatter(x, y, color="blue", s=100, label="Affected Areas", zorder=2)
        
        # Annotate each point with area name
        for area, (lat, lon) in zip(self.areas.keys(), self.affected_points):
            ax.text(lat, lon, area, fontsize=10, ha='right', 
                   color="black", 
                   bbox=dict(facecolor='white', alpha=0.7, edgecolor='black'))
        
        plt.title("Convex Hull of Affected Coastal Areas in Chennai", fontsize=14, fontweight='bold')
        plt.xlabel("Latitude")
        plt.ylabel("Longitude")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig('data/geospatial_risk_zones.png', dpi=300, bbox_inches='tight')
        plt.show()
    
    def update_risk_zones(self, new_points):
        """Update risk zones with new affected points"""
        print("\n🔄 Updating risk zones with new affected points...")
        
        updated_points = self.affected_points + new_points
        updated_hull = MultiPoint(updated_points).convex_hull
        
        print(f"Updated Convex Hull Boundary: {updated_hull}")
        return updated_hull

def main():
    """Main function to run all graph-based risk analyses"""
    print("🌊 Graph-based Risk Analysis for Chennai")
    print("=" * 50)
    
    # 1. Risk Propagation Analysis
    print("\n1️⃣ RISK PROPAGATION ANALYSIS")
    print("-" * 30)
    risk_analyzer = RiskPropagationAnalyzer()
    risk_analyzer.propagate_risk(iterations=5)
    risk_analyzer.visualize_risk_graph()
    centrality_df = risk_analyzer.analyze_risk_centrality()
    
    # 2. Flood Modeling Analysis
    print("\n2️⃣ FLOOD MODELING ANALYSIS")
    print("-" * 30)
    flood_analyzer = FloodModelingAnalyzer()
    flow_value, flow_dict, flood_risk_areas, critical_zones = flood_analyzer.analyze_water_flow()
    flood_analyzer.visualize_water_network(flood_risk_areas)
    
    # 3. Storm Tracking Analysis
    print("\n3️⃣ STORM TRACKING ANALYSIS")
    print("-" * 30)
    storm_analyzer = StormTrackingAnalyzer()
    storm_path = storm_analyzer.bellman_ford_storm_path()
    storm_analyzer.visualize_storm_tracking()
    
    # 4. Geospatial Risk Analysis
    print("\n4️⃣ GEOSPATIAL RISK ANALYSIS")
    print("-" * 30)
    geo_analyzer = GeospatialRiskAnalyzer(risk_analyzer.areas)
    hull = geo_analyzer.compute_convex_hull()
    geo_analyzer.visualize_risk_zones(hull)
    
    # Example: Update with new affected points
    new_affected_points = [(12.8900, 80.2200), (13.0600, 80.2900)]
    updated_hull = geo_analyzer.update_risk_zones(new_affected_points)
    
    print("\n✅ All graph-based risk analyses completed!")
    print("📁 Generated files:")
    print("   - data/risk_propagation_graph.png")
    print("   - data/flood_risk_network.png") 
    print("   - data/storm_tracking_network.png")
    print("   - data/geospatial_risk_zones.png")

if __name__ == "__main__":
    main()
