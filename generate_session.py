#!/usr/bin/env python3
"""Generate Pyrogram session string"""
from pyrogram import Client

API_ID = 32898997
API_HASH = "8e90b1a4457198c9e0564fe91baf0b46"

with Client("session_gen", api_id=API_ID, api_hash=API_HASH, in_memory=True) as app:
    session_string = app.export_session_string()
    print(f"\n\nYour session string:\n{session_string}\n")
