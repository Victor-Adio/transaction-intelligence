"""
Hybrid Search page — main demo page.
Accessible from the Streamlit sidebar page navigator.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
from app import main

main()
