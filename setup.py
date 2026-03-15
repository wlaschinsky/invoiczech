#!/usr/bin/env python3
"""Pomocný skript pro vygenerování bcrypt hashe hesla do .env souboru."""
import getpass
import bcrypt

print("=== Nastavení hesla pro fakturační aplikaci ===\n")
password = getpass.getpass("Zadejte heslo: ")
password2 = getpass.getpass("Potvrďte heslo: ")

if password != password2:
    print("\nChyba: Hesla se neshodují!")
    exit(1)

if len(password) < 8:
    print("\nVarování: Heslo je kratší než 8 znaků.")

hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
print(f"\nPridejte do .env souboru:\nPASSWORD_HASH={hashed}\n")
