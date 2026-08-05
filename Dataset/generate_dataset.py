

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_user_events(num_users=10500, num_events=305000, seed=42):
    np.random.seed(seed)
    print(f"Generating synthetic dataset with {num_events} events for {num_users} users...")

    # Reference data
    countries = ['India', 'United States', 'United Kingdom', 'Canada', 'Germany', 'Australia', 'Brazil', 'Singapore']
    country_weights = [0.45, 0.20, 0.10, 0.05, 0.08, 0.04, 0.05, 0.03]
    
    cities_map = {
        'India': ['Mumbai', 'Bangalore', 'Delhi', 'Hyderabad', 'Pune', 'Chennai'],
        'United States': ['New York', 'San Francisco', 'Austin', 'Seattle', 'Chicago'],
        'United Kingdom': ['London', 'Manchester', 'Birmingham'],
        'Canada': ['Toronto', 'Vancouver', 'Montreal'],
        'Germany': ['Berlin', 'Munich', 'Frankfurt'],
        'Australia': ['Sydney', 'Melbourne', 'Brisbane'],
        'Brazil': ['Sao Paulo', 'Rio de Janeiro'],
        'Singapore': ['Singapore']
    }

    device_types = ['Mobile', 'Tablet', 'Desktop']
    device_weights = [0.70, 0.10, 0.20]

    os_map = {
        'Mobile': ['Android', 'iOS'],
        'Tablet': ['iPadOS', 'Android'],
        'Desktop': ['Windows', 'macOS', 'Linux']
    }
    os_weights = {'Mobile': [0.65, 0.35], 'Tablet': [0.6, 0.4], 'Desktop': [0.7, 0.25, 0.05]}

    app_versions = ['v2.4.1', 'v2.5.0', 'v2.5.1', 'v2.6.0-beta', 'v2.3.8']
    traffic_sources = ['Google Ads', 'Organic Search', 'Social Media (Meta)', 'Direct', 'Referral', 'Email Campaign', 'Affiliate']
    traffic_weights = [0.28, 0.25, 0.20, 0.12, 0.07, 0.05, 0.03]

    event_names = ['App Open', 'Login', 'Signup', 'Search', 'Add to Cart', 'Purchase', 'Watch Video', 'Complete Level', 'Invite Friend', 'Logout']
    event_weights = [0.25, 0.18, 0.03, 0.15, 0.10, 0.06, 0.12, 0.05, 0.04, 0.02]

    campaigns = ['Summer_Promo_2025', 'Retargeting_FB', 'Brand_Search_GGL', 'Influencer_Launch', 'Referral_Boost', 'None']
    campaign_weights = [0.20, 0.15, 0.25, 0.10, 0.10, 0.20]

    # Generate Users
    user_ids = [f"USR_{i:06d}" for i in range(1, num_users + 1)]
    user_countries = np.random.choice(countries, size=num_users, p=country_weights)
    user_traffic = np.random.choice(traffic_sources, size=num_users, p=traffic_weights)
    user_types = np.random.choice(['New', 'Returning'], size=num_users, p=[0.35, 0.65])
    
    start_date = datetime(2025, 1, 1)
    
    records = []
    print("Simulating event streams...")
    
    for _ in range(num_events):
        u_idx = np.random.randint(0, num_users)
        user_id = user_ids[u_idx]
        country = user_countries[u_idx]
        city = np.random.choice(cities_map[country])
        traffic_source = user_traffic[u_idx]
        user_type = user_types[u_idx]
        
        device_type = np.random.choice(device_types, p=device_weights)
        os_choice = np.random.choice(os_map[device_type], p=os_weights[device_type])
        app_version = np.random.choice(app_versions, p=[0.1, 0.4, 0.3, 0.1, 0.1])
        
        # Event timestamp within last 180 days
        day_offset = np.random.randint(0, 180)
        event_date = start_date + timedelta(days=day_offset)


        hour_probs = np.array([
        2, 1, 1, 1, 1, 2,
        4, 6, 8, 7, 6, 5,
        5, 6, 6, 7, 8, 8,
        7, 5, 4, 3, 2, 2
        ], dtype=float)


        hour_probs /= hour_probs.sum()

        hour = np.random.choice(np.arange(24), p=hour_probs)

        minute = np.random.randint(0, 60)
        second = np.random.randint(0, 60)

        event_timestamp = event_date.replace(
        hour=int(hour),
        minute=int(minute),
        second=int(second)
        )
        
        session_id = f"SES_{user_id}_{day_offset}_{np.random.randint(1, 4):02d}"
        event_name = np.random.choice(event_names, p=event_weights)
        
        session_duration = int(np.random.exponential(scale=180)) + 10 # seconds
        
        revenue = 0.0
        purchase_amount = 0.0
        if event_name == 'Purchase':
            purchase_amount = round(np.random.lognormal(mean=3.8, sigma=0.8), 2)
            revenue = purchase_amount
            
        level_completed = np.random.randint(1, 50) if event_name == 'Complete Level' else 0
        subscription = np.random.choice(['Free', 'Monthly', 'Annual'], p=[0.70, 0.20, 0.10])
        campaign = np.random.choice(campaigns, p=campaign_weights)
        retention_day = np.random.choice([1, 3, 7, 14, 30, 60, 90], p=[0.40, 0.20, 0.15, 0.10, 0.08, 0.05, 0.02])

        records.append({
            'user_id': user_id,
            'session_id': session_id,
            'event_date': event_date.strftime('%Y-%m-%d'),
            'event_timestamp': event_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'country': country,
            'city': city,
            'device_type': device_type,
            'os': os_choice,
            'app_version': app_version,
            'traffic_source': traffic_source,
            'user_type': user_type,
            'event_name': event_name,
            'session_duration': session_duration,
            'revenue': revenue,
            'level_completed': level_completed,
            'purchase_amount': purchase_amount,
            'subscription': subscription,
            'campaign': campaign,
            'retention_day': retention_day
        })

    df = pd.DataFrame(records)

    # Introduce intentional missing values, duplicates, and outliers for EDA data-cleaning practice
    print("Introducing controlled missing values and outliers...")
    mask_nan_city = np.random.rand(len(df)) < 0.02
    df.loc[mask_nan_city, 'city'] = np.nan

    mask_nan_ver = np.random.rand(len(df)) < 0.015
    df.loc[mask_nan_ver, 'app_version'] = np.nan

    # Introduce duplicate rows (approx 0.5%)
    duplicates = df.sample(n=int(num_events * 0.005))
    df = pd.concat([df, duplicates], ignore_index=True)

    # Introduce outliers in session duration and purchase amount
    outlier_indices = np.random.choice(df.index, size=50, replace=False)
    df.loc[outlier_indices, 'session_duration'] = 86400 # 24 hours anomaly

    output_path = 'user_events.csv'
    df.to_csv(output_path, index=False)
    print(f"Dataset successfully generated and saved to {output_path}. Total rows: {len(df):,}")

if __name__ == '__main__':
    generate_user_events()