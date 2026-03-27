# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Shared test configuration.

Forces the ENVIRONMENT to ``development`` so tests always use
the InMemoryStore backend.
"""
import os

os.environ["ENVIRONMENT"] = "development"
