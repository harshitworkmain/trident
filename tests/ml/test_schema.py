import math

import jsonschema

from src.ml.wearable.schema import FIELD_NAMES, json_schema, parse_payload

V2_PAYLOAD = {
    'schema': 2, 'device_id': 'TRIDENT-W01', 'fw': '2.0.0', 'seq': 7, 'uptime_ms': 10500,
    'imu': {'acc_max_g': 1.12, 'acc_min_g': 0.91, 'acc_mean_g': 1.01, 'acc_std_g': 0.04,
            'gyro_max_dps': 35.2, 'gyro_mean_dps': 8.1, 'tilt_deg': 12.5, 'n': 75,
            'fall_detected': False},
    'ppg': {'finger_on': True, 'bpm': 78.0, 'rr_ms': [772, 768, 5000], 'spo2': 97.0,
            'spo2_valid': True, 'perfusion': 0.84},
    'eda': {'us': 4.2, 'slope_us_s': 0.01, 'baseline_us': 3.9, 'raw': 1840, 'norm': 0.12},
    'temp': {'skin_c': 33.4},
    'baro': {'hpa': 1009.8, 'dmax_hpa': 0.04},
    'water': {'wet': False},
    'power': {'batt_v': 3.92},
    'gps': {'lat': 13.08, 'lng': 80.27, 'sats': 7, 'hdop': 1.2, 'breached': False},
}

V1_PAYLOAD = {
    'device_id': 'ESP32-01',
    'system': {'mpu_ok': True},
    'fall': {'acc_mag': 1.02, 'gyro_mag': 3.1, 'fall_detected': True},
    'gps': {'lat': 13.08, 'lng': 80.27, 'satellites': 5, 'breached': False},
    'vitals': {'bpm': 81.0, 'spo2': 97.4, 'category': 'Normal'},
    'stress': {'gsr_raw': 1800.0, 'gsr_norm': 0.2, 'level': 'Medium', 'baseline': 1700.0},
}


def test_v2_payload_validates_against_generated_json_schema():
    clean = {**V2_PAYLOAD, 'ppg': {**V2_PAYLOAD['ppg'], 'rr_ms': [772, 768]}}
    jsonschema.validate(clean, json_schema())
    try:
        jsonschema.validate(V2_PAYLOAD, json_schema())  # contains rr 5000 ms
    except jsonschema.ValidationError:
        pass
    else:
        raise AssertionError('out-of-range RR interval should fail JSON Schema validation')


def test_v2_parse_fills_every_field_and_drops_bad_rr():
    frame = parse_payload(V2_PAYLOAD)
    assert frame.schema == 2 and frame.seq == 7
    assert set(frame.values) == set(FIELD_NAMES)
    assert frame.unavailable == []
    assert frame.values['imu_fall_detected'] == 0.0
    assert frame.rr_ms == [772.0, 768.0]
    assert any('rr_ms' in w for w in frame.warnings)


def test_out_of_range_value_becomes_nan_with_warning():
    payload = {**V2_PAYLOAD, 'temp': {'skin_c': 80.0}}
    frame = parse_payload(payload)
    assert math.isnan(frame.values['temp_skin_c'])
    assert any('temp_skin_c' in w for w in frame.warnings)


def test_v1_payload_maps_snapshot_and_never_trusts_spo2():
    frame = parse_payload(V1_PAYLOAD)
    assert frame.schema == 1
    assert frame.values['imu_acc_mean_g'] == 1.02
    assert frame.values['imu_fall_detected'] == 1.0
    assert frame.values['ppg_bpm'] == 81.0
    assert frame.values['ppg_spo2_valid'] == 0.0
    assert math.isnan(frame.values['ppg_spo2'])
    assert math.isnan(frame.values['imu_acc_max_g'])  # interval aggregates unknown in v1


def test_v1_no_finger_hides_bpm():
    payload = {**V1_PAYLOAD, 'vitals': {'bpm': 0, 'spo2': 0, 'category': 'No Finger'}}
    frame = parse_payload(payload)
    assert frame.values['ppg_finger_on'] == 0.0
    assert math.isnan(frame.values['ppg_bpm'])
