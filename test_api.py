import uvicorn
from api.main import app
import threading
import time
import requests

def run_server():
    uvicorn.run(app, host='127.0.0.1', port=8000, log_level='error')

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(3)

try:
    print('=== HEALTH ===')
    r = requests.get('http://127.0.0.1:8000/api/v1/healthz', timeout=5)
    print(r.json())
    
    print('\n=== READY ===')
    r = requests.get('http://127.0.0.1:8000/api/v1/readyz', timeout=5)
    print(r.json())
    
    print('\n=== WARDS ===')
    r = requests.get('http://127.0.0.1:8000/api/v1/wards', timeout=5)
    wards = r.json()
    print('Count:', len(wards))
    for w in wards[:3]:
        print('  {}: {}'.format(w["ward_id"], w["ward_name"]))
    
    print('\n=== RISK (100mm) ===')
    r = requests.post('http://127.0.0.1:8000/api/v1/risk', json={'rainfall_mm': 100, 'duration_hours': 3}, timeout=10)
    risk = r.json()
    print('Top 5 wards:')
    for w in risk['wards'][:5]:
        print('  {}: score={:.3f} level={} depth={}'.format(w["ward_name"], w["risk_score"], w["risk_level"], w["depth_band"]))
    
    print('\n=== SCENARIO (+30% built-up) ===')
    r = requests.post('http://127.0.0.1:8000/api/v1/scenario', json={'rainfall_mm': 100, 'duration_hours': 3, 'builtup_increase_pct': 30}, timeout=10)
    scenario = r.json()
    print('Top 3:')
    for w in scenario['wards'][:3]:
        print('  {}: score={:.3f} level={}'.format(w["ward_name"], w["risk_score"], w["risk_level"]))
    
    print('\n=== ALERTS ===')
    r = requests.post('http://127.0.0.1:8000/api/v1/alerts', json={'ward_ids': [1,2,3], 'rainfall_mm': 150, 'language': 'en', 'channels': ['sms', 'whatsapp']}, timeout=10)
    alerts = r.json()['alerts']
    print('Generated:', len(alerts), 'alerts')
    for a in alerts[:2]:
        print('  {} {}: {}...'.format(a["ward_name"], a["channel"], a["message"][:60]))
    
    print('\n=== SHELTERS ===')
    r = requests.post('http://127.0.0.1:8000/api/v1/shelters', json={'latitude': 13.04, 'longitude': 80.23, 'max_distance_km': 10}, timeout=10)
    shelters = r.json()
    print('Nearby:', len(shelters))
    for s in shelters[:3]:
        print('  {}: {:.1f}km, {}min'.format(s["name"], s["distance_km"], s["walking_time_min"]))
    
    print('\n=== ROADS (200mm) ===')
    r = requests.get('http://127.0.0.1:8000/api/v1/roads/risk?rainfall_mm=200', timeout=10)
    roads = r.json()
    print('Count:', len(roads))
    for rd in roads:
        print('  {}: {} {:.2f}m underpass={}'.format(rd["name"], rd["risk_level"], rd["flood_depth_estimate_m"], rd["is_underpass"]))
    
    print('\n=== VALIDATION ===')
    r = requests.get('http://127.0.0.1:8000/api/v1/validation', timeout=5)
    v = r.json()
    print('Precision@20: {:.2%}'.format(v["precision_at_20"]))
    print('Recall: {:.2%}'.format(v["recall"]))
    print('FPR: {:.2%}'.format(v["false_positive_rate"]))
    
    print('\n=== ALL ENDPOINTS WORKING ===')
    
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()