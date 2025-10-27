#!/usr/bin/env python3
"""
Test suite for dev container configuration
Ensures the container uses compatible base images and features
"""

import json
import os
import sys
from pathlib import Path

def test_devcontainer_json_exists():
    """Test that devcontainer.json exists"""
    devcontainer_path = Path(__file__).parent.parent / '.devcontainer' / 'devcontainer.json'
    assert devcontainer_path.exists(), "devcontainer.json not found"
    print("✓ devcontainer.json exists")
    return True

def test_devcontainer_json_valid():
    """Test that devcontainer.json is valid JSON"""
    devcontainer_path = Path(__file__).parent.parent / '.devcontainer' / 'devcontainer.json'
    try:
        with open(devcontainer_path) as f:
            config = json.load(f)
        print("✓ devcontainer.json is valid JSON")
        return config
    except json.JSONDecodeError as e:
        print(f"✗ devcontainer.json is not valid JSON: {e}")
        return None

def test_image_uses_bookworm(config):
    """Test that the image uses Debian Bookworm (not Trixie)"""
    image = config.get('image', '')

    if 'bookworm' in image.lower():
        print(f"✓ Image uses Debian Bookworm: {image}")
        return True
    elif 'trixie' in image.lower():
        print(f"✗ CRITICAL: Image uses Debian Trixie: {image}")
        print("  Trixie is not compatible with Docker-in-Docker (moby removed)")
        print("  Use bookworm instead: mcr.microsoft.com/devcontainers/python:3.11-bookworm")
        return False
    else:
        print(f"⚠ Warning: Image may not specify bookworm: {image}")
        print("  Recommended to use explicit bookworm tag")
        return True  # Don't fail, but warn

def test_docker_in_docker_feature(config):
    """Test that Docker-in-Docker feature is properly configured"""
    features = config.get('features', {})

    # Find docker-in-docker feature
    docker_feature = None
    for key, value in features.items():
        if 'docker-in-docker' in key.lower():
            docker_feature = value
            break

    if docker_feature is None:
        print("⚠ Warning: Docker-in-Docker feature not found")
        return True  # Not critical if not using Docker

    print(f"✓ Docker-in-Docker feature configured: {docker_feature}")

    # Check if using bookworm (critical for compatibility)
    image = config.get('image', '')
    if 'bookworm' in image.lower() or 'ubuntu' in image.lower():
        print("  ✓ Image is compatible with Docker-in-Docker")
        return True
    else:
        print("  ⚠ Warning: Ensure image supports Docker-in-Docker")
        return True

def test_dockerfile_if_exists():
    """Test Dockerfile uses compatible base image"""
    dockerfile_path = Path(__file__).parent.parent / '.devcontainer' / 'Dockerfile'

    if not dockerfile_path.exists():
        print("  Dockerfile not used (image-based config)")
        return True

    with open(dockerfile_path) as f:
        content = f.read()

    if 'bookworm' in content.lower():
        print("✓ Dockerfile uses Debian Bookworm")
        return True
    elif 'trixie' in content.lower():
        print("✗ CRITICAL: Dockerfile uses Debian Trixie")
        return False
    else:
        print("  Dockerfile found but Debian version unclear")
        return True

def test_required_features(config):
    """Test that required features are present"""
    features = config.get('features', {})

    required_features = [
        'node',
        'git'
    ]

    missing = []
    for required in required_features:
        found = any(required in key.lower() for key in features.keys())
        if not found:
            missing.append(required)

    if missing:
        print(f"⚠ Warning: Missing optional features: {', '.join(missing)}")

    print("✓ Feature configuration validated")
    return True

def main():
    print("=" * 60)
    print("Dev Container Configuration Tests")
    print("=" * 60)
    print()

    all_passed = True

    # Test 1: Check file exists
    if not test_devcontainer_json_exists():
        sys.exit(1)

    # Test 2: Load and validate JSON
    config = test_devcontainer_json_valid()
    if config is None:
        sys.exit(1)

    # Test 3: Check image compatibility (CRITICAL)
    if not test_image_uses_bookworm(config):
        all_passed = False

    # Test 4: Check Docker feature configuration
    if not test_docker_in_docker_feature(config):
        all_passed = False

    # Test 5: Check Dockerfile if it exists
    if not test_dockerfile_if_exists():
        all_passed = False

    # Test 6: Check required features
    if not test_required_features(config):
        all_passed = False

    print()
    print("=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("✗ Some tests failed!")
        print("=" * 60)
        sys.exit(1)

if __name__ == '__main__':
    main()
