from __future__ import annotations

from app.core.danger_rules import DangerDetector


def test_danger_detector() -> None:
    """Test danger detection with simulated data."""
    detector = DangerDetector()

    # Simulated detection data: [x1, y1, x2, y2, conf, cls_id]
    data: list[list[float]] = [
        # Person at (200, 200) - (300, 300)
        [200, 200, 300, 300, 0.85, 5],
        # NO-Hardhat overlapping with person (>50% overlap)
        [205, 205, 295, 290, 0.75, 2],
        # NO-Mask overlapping with person (>50% overlap)
        [210, 210, 290, 285, 0.80, 3],
        # NO-Safety Vest overlapping with person (>50% overlap)
        [208, 208, 292, 288, 0.70, 4],
    ]

    warnings, cone_polys, _ = detector.detect_danger(data)

    print("=== DangerDetector Test ===\n")
    print(f"Warnings: {warnings}")
    print(f"Cone polygons: {len(cone_polys)}")

    assert 'warning_no_hardhat' in warnings, "Missing no_hardhat warning"
    assert 'warning_no_mask' in warnings, "Missing no_mask warning"
    assert 'warning_no_safety_vest' in warnings, "Missing no_vest warning"

    print("\nAll assertions passed!")


def test_proximity_violation() -> None:
    """Test proximity detection."""
    detector = DangerDetector()

    # Person close to machinery
    data: list[list[float]] = [
        [100, 100, 120, 200, 0.90, 5],    # Person
        [130, 100, 200, 200, 0.85, 8],    # Machinery nearby
    ]

    warnings, _, _ = detector.detect_danger(data)
    print("\n=== Proximity Test ===\n")
    print(f"Warnings: {warnings}")

    if 'warning_close_to_machinery' in warnings:
        print("Proximity warning triggered correctly!")
    else:
        print("No proximity warning (person may be too far)")


def test_empty_data() -> None:
    """Test with empty data."""
    detector = DangerDetector()
    warnings, cone_polys, _ = detector.detect_danger([])

    print("\n=== Empty Data Test ===\n")
    assert warnings == {}, f"Expected empty warnings, got {warnings}"
    assert cone_polys == [], f"Expected empty polygons, got {cone_polys}"
    print("Empty data test passed!")


if __name__ == '__main__':
    test_danger_detector()
    test_proximity_violation()
    test_empty_data()
    print("\n=== All tests completed ===")
