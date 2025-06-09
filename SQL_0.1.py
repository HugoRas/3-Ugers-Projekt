import sqlite3
import matplotlib.pyplot as plt
import serial
import io
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk

#Der oprettes forbindelse til databasen
conn = sqlite3.connect("EKGDATABASE.db", check_same_thread=False)
cursor = conn.cursor()

#Der oprettes tabeller hvis ikke de allerede findes
cursor.execute("""
CREATE TABLE IF NOT EXISTS BRUGERDATA (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Navn TEXT,
    Alder INTEGER,
    KØN TEXT
    )""")
conn.commit()
cursor.execute("""
CREATE TABLE IF NOT EXISTS EKGDATA (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    PatientID INTEGER ,
    Tidspunkt TEXT,
    Data REAL,
    Puls INTEGER,
    FOREIGN KEY (PatientID) REFERENCES BRUGERDATA(Id)
    )""")
conn.commit()

run=True

Navn = input("Skriv dit fulde navn: ")
Alder = int(input("Skriv dit alder: "))
Køn = str(input("Skriv dit køn: "))


cursor.execute("INSERT INTO BRUGERDATA (Navn, Alder, KØN) VALUES (?, ?, ?)", (Navn, Alder, Køn))
patient_id = cursor.lastrowid  # <-- Dette giver ID'et på den indsatte bruger
conn.commit()

print(f"Data gemt! Bruger-ID: {patient_id}")


print("Data gemt!")

conn.close()
