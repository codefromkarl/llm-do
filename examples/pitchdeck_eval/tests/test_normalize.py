#!/usr/bin/env python3
"""
Unit tests for normalize_filename function

This is a standalone version for testing without importing executor.py
Run with: python tests/test_normalize.py
"""

import re


def normalize_filename(filename: str) -> str:
    """
    Normalize a filename for use as company name.

    This is the hardened version - extracted for testing.
    Copy changes back to executor.py
    """
    # Remove PDF extension (case insensitive)
    name = filename.replace('.pdf', '').replace('.PDF', '')

    # Remove spaces and special chars except hyphens
    name = re.sub(r'[^a-zA-Z0-9-]', '', name.replace(' ', ''))

    return name

def test_normalize_filename():
    cases = [
        ("Company.pdf", "Company"),
        ("Company Name.pdf", "CompanyName"),
        ("Company (YC S24).pdf", "CompanyYCS24"),
        ("Company_Name-2024.pdf", "CompanyName-2024"),
        ("Real-Research.pdf", "Real-Research"),
        ("Startup Name (Batch 2024) - Deck.pdf", "StartupNameBatch2024-Deck"),
        ("Company.PDF", "Company"),
        ("Company.v2.pdf", "Companyv2"),
        ("Company@#$%.pdf", "Company"),
        ("Company123.pdf", "Company123"),
        ("Real Research (YC S24).pdf", "RealResearchYCS24"),
        ("Startup - Deck 2024.pdf", "Startup-Deck2024"),
        ("Company Deck v3.pdf", "CompanyDeckv3"),
        ("My Awesome Startup.pdf", "MyAwesomeStartup"),
    ]

    for original, expected in cases:
        assert normalize_filename(original) == expected
