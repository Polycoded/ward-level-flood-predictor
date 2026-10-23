"""Sample flood test case used by the terminal (console) voice demo.

Ward 168 (internal id) = GCC ward 14. The nearest relief camp is computed from
data/processed/shelters.parquet (13 OSM shelters) using the ward centroid.
"""

TEST_CASE = {
    "ward_name": "Ward 14",
    "risk_level": "high",
    "depth_band": "0.5-1.0m",
    "rainfall_mm": 120.0,
    "duration_hours": 6.0,
    "language": "en",
    "shelter_name": "DAV Primary Secondary School",
    "shelter_distance_km": 12.75,
    "shelter_direction": "south-west",
    "shelter_bearing_deg": 222.8,
    "shelter_latitude": 13.06493,
    "shelter_longitude": 80.22256,
    "shelter_capacity": 300,
}


def shelter_context() -> str:
    return (
        f"Nearest relief camp: {TEST_CASE['shelter_name']} "
        f"(capacity {TEST_CASE['shelter_capacity']}), about "
        f"{TEST_CASE['shelter_distance_km']:.1f} km {TEST_CASE['shelter_direction']} "
        f"of the ward centre (bearing {TEST_CASE['shelter_bearing_deg']:.0f} degrees). "
        f"Coordinates: {TEST_CASE['shelter_latitude']:.5f}, "
        f"{TEST_CASE['shelter_longitude']:.5f}."
    )


def opening_script(language: str = "en") -> str:
    """Short opening (~12-15 s) so the demo starts fast."""
    if language == "ta":
        return (
            "வார்டு 14 க்கு வெள்ள எச்சரிக்கை. தென்மேற்கில் சுமார் 12.8 கிலோமீட்டர் "
            "தொலைவில் உள்ள DAV Primary Secondary School நிவாரண முகாமுக்குச் செல்லுங்கள். "
            "திசையைக் கேட்க directions எனச் சொல்லுங்கள். இது ஒரு பயிற்சி."
        )
    return (
        "Flood warning for Ward 14. Move to DAV Primary Secondary School, about "
        "12.8 kilometres south-west. Say directions to hear that again. This is a test."
    )

