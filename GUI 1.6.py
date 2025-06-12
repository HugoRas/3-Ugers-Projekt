# ✅ Samlet og rettet version af hele EKG-visualiseringsprogrammet

import tkinter as tk
from tkinter import Frame, ttk
import random
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sqlite3
import threading
import time
from tkinter import messagebox
import io
import serial

# COM-port og baudrate
COMport = "/dev/cu.usbmodem2101"
baud = 38400

# Databaseforbindelse
conn = sqlite3.connect("EKGDATABASE.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS Brugerdata (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Navn TEXT,
    Alder INTEGER,
    KØN TEXT
    )""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS Ekgdata (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    PatientID INTEGER,
    Tidspunkt TEXT,
    Data REAL,
    Puls INTEGER,
    FOREIGN KEY (PatientID) REFERENCES Brugerdata(Id)
    )""")
conn.commit()

run = True

# Datahandler
class Datahandler():
    def __init__(self, conn_local):
        self.conn_local = conn_local
        self.cursor_local = conn_local.cursor()

    def serialdata(self, com):
        try:
            ser = serial.Serial(com, baud, timeout=0.001)
            sio = io.TextIOWrapper(io.BufferedReader(ser))
            while run:
                try:
                    data = sio.readline().strip()
                    if not data:
                        continue
                    self.cursor_local.execute("""
                        INSERT INTO Ekgdata (PatientID, Data, Tidspunkt)
                        VALUES (?, ?, datetime('now'))
                    """, (1, float(data)))
                    self.conn_local.commit()
                except Exception as e:
                    print("Fejl ved læsning/indsættelse:", e)
        except Exception as e:
            print("Serialfejl:", e)

# Baggrundstråd

def data_thread_func():
    global run
    conn_local = sqlite3.connect("EKGDATABASE.db")
    try:
        Datahandler(conn_local).serialdata(COMport)
    finally:
        conn_local.close()

# GUI
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EKG program")
        self.geometry("900x600")
        self.resizable(False, False)

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (900 // 2)
        y = (screen_height // 2) - (600 // 2) - 50
        self.geometry(f"900x600+{x}+{y}")

        container = tk.Frame(self)
        container.pack(fill="both", expand=True)

        self.frames = {}
        self.pulse_history = []

        for F in (StartPage, PageOne, PageTwo, Login):
            frame = F(parent=container, controller=self)
            self.frames[F] = frame
            frame.place(relwidth=1, relheight=1)

        self.show_frame(StartPage)

    def show_frame(self, page_class):
        frame = self.frames[page_class]
        frame.tkraise()

class StartPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="lightblue")
        self.controller = controller

        label = tk.Label(self, text="Hovedmenu", font=("Helvetica", 18, "bold"), bg="lightblue")
        label.place(relx=0.02, rely=0.02, anchor="nw")

        btn1 = tk.Button(self, text="Dynamisk EKG diagram og puls", bg="lightblue",
                         borderwidth=0, highlightthickness=0, padx=10, pady=4,
                         command=lambda: controller.show_frame(PageOne))
        btn1.pack(pady=(80, 10))

        btn2 = tk.Button(self, text="Målinger", bg="lightblue",
                         borderwidth=0, highlightthickness=0, padx=10, pady=4,
                         command=lambda: controller.show_frame(PageTwo))
        btn2.pack()

        btn3 = tk.Button(self, text="Login / Patienter", bg="lightblue",
                         borderwidth=0, highlightthickness=0, padx=10, pady=4,
                         command=lambda: controller.show_frame(Login))
        btn3.pack(pady=(10, 0))

class PageOne(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="lightgreen")
        self.controller = controller

        label = tk.Label(self, text="Dynamisk EKG diagram og puls", bg="lightgreen",
                         font=("Helvetica", 18, "bold"))
        label.place(relx=0.02, rely=0.02, anchor="nw")

        self.puls_label = tk.Label(self, text="--", font=("Helvetica", 26, "bold"),
                                   fg="red", bg="lightgreen")
        tk.Label(self, text="Puls", font=("Helvetica", 18), bg="lightgreen").place(relx=0.85, rely=0.22)
        self.puls_label.place(relx=0.85, rely=0.3)

        container_frame = Frame(self, bg="lightgreen")
        container_frame.place(relx=0.05, rely=0.15)

        plot_frame = Frame(container_frame, width=600, height=350)
        plot_frame.pack()
        plot_frame.pack_propagate(False)

        self.fig = Figure(figsize=(6, 4.5), dpi=100, facecolor='lightgreen')
        self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(expand=True, fill="both")

        back_btn = tk.Button(self, text="Tilbage",
                             borderwidth=0, highlightthickness=0,
                             padx=10, pady=4,
                             command=lambda: controller.show_frame(StartPage))
        back_btn.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        self.update_data()

    def update_data(self):
        if not run:
            return

        cursor.execute("SELECT Data, Puls FROM Ekgdata WHERE PatientID = 1 ORDER BY Id DESC LIMIT 50")
        results = cursor.fetchall()

        if results:
            data_points = [x[0] for x in results][::-1]
            latest_pulse = results[0][1]

            self.ax.clear()
            self.ax.set_facecolor('white')
            self.ax.plot(range(len(data_points)), data_points, color='black')

            for x in range(0, len(data_points) + 1, 5):
                self.ax.axvline(x=x, color='red', linewidth=1.0)
            for y in range(-80, 46, 10):
                self.ax.axhline(y=y, color='red', linewidth=1.0)

            self.ax.set_title("EKG diagram")
            self.ax.set_ylim(-80, 45)
            self.ax.set_xlim(0, len(data_points) - 1)
            self.ax.set_xticks([])
            self.ax.set_yticks(range(-80, 46, 10))
            self.ax.tick_params(axis='y', labelsize=8)

            self.canvas.draw()
            self.puls_label.config(text=str(latest_pulse))

        self.after(100, self.update_data)

class PageTwo(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="lightblue")
        self.controller = controller

        label = tk.Label(self, text="Målinger", font=("Helvetica", 16), bg="lightblue")
        label.pack(pady=10)

        self.tree = ttk.Treeview(self, columns=("Tidspunkt", "Puls", "Data"), show="headings")
        self.tree.heading("Tidspunkt", text="Tidspunkt")
        self.tree.heading("Puls", text="Puls")
        self.tree.heading("Data", text="Data")
        self.tree.column("Tidspunkt", width=200)
        self.tree.column("Puls", width=100)
        self.tree.column("Data", width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        refresh_btn = tk.Button(self, text="Opdater", command=self.refresh_data)
        refresh_btn.pack(pady=5)

        back_btn = tk.Button(self, text="Tilbage",
                             command=lambda: controller.show_frame(StartPage))
        back_btn.pack(pady=10)

        self.refresh_data()

    def refresh_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        cursor.execute("""
            SELECT strftime('%Y-%m-%d %H:%M:%S', Tidspunkt), Puls, Data 
            FROM Ekgdata 
            WHERE PatientID = 1 
            ORDER BY Tidspunkt DESC
            LIMIT 100
        """)

        for row in cursor.fetchall():
            self.tree.insert("", tk.END, values=row)

class Login(tk.Frame):
    def __init__(self, parent, controller=None):
        super().__init__(parent, bg="lightblue")
        self.controller = controller

        self.patient_data = []

        tk.Label(self, text="Patient Login", font=("Helvetica", 16)).grid(row=0, column=0, columnspan=2, pady=10)

        tk.Label(self, text="Navn:").grid(row=1, column=0, sticky="e")
        self.entry_name = tk.Entry(self)
        self.entry_name.grid(row=1, column=1)

        tk.Label(self, text="Alder:").grid(row=2, column=0, sticky="e")
        self.entry_age = tk.Entry(self)
        self.entry_age.grid(row=2, column=1)

        tk.Label(self, text="Køn:").grid(row=3, column=0, sticky="e")
        self.entry_gender = tk.Entry(self)
        self.entry_gender.grid(row=3, column=1)

        submit_button = tk.Button(self, text="Opret patient", command=self.submit_patient)
        submit_button.grid(row=4, column=0, columnspan=2, pady=10)

        view_button = tk.Button(self, text="Se patienter", command=self.view_patients)
        view_button.grid(row=5, column=0, columnspan=2, pady=5)

        self.patient_listbox = tk.Listbox(self, width=50)
        self.patient_listbox.grid(row=6, column=0, columnspan=2, pady=10)

        back_btn = tk.Button(self, text="Tilbage", command=lambda: controller.show_frame(StartPage))
        back_btn.grid(row=7, column=0, columnspan=2, pady=10)

    def submit_patient(self):
        name = self.entry_name.get()
        age = self.entry_age.get()
        gender = self.entry_gender.get()

        if not all([name, age, gender]):
            messagebox.showwarning("Fejl", "Alle felter skal udfyldes!")
            return

        cursor.execute("INSERT INTO Brugerdata (Navn, Alder, KØN) VALUES (?, ?, ?)", (name, age, gender))
        conn.commit()

        messagebox.showinfo("Succes", f"Patient {name} oprettet.")
        self.entry_name.delete(0, tk.END)
        self.entry_age.delete(0, tk.END)
        self.entry_gender.delete(0, tk.END)

    def view_patients(self):
        self.patient_listbox.delete(0, tk.END)
        cursor.execute("SELECT Navn, Alder, KØN FROM Brugerdata")
        for navn, alder, køn in cursor.fetchall():
            self.patient_listbox.insert(tk.END, f"{navn} - {alder} år - {køn}")

# Lukning

def on_closing():
    global run
    run = False
    conn.close()
    app.destroy()

# Start GUI og tråd
if __name__ == "__main__":
    thread = threading.Thread(target=data_thread_func, daemon=True)
    thread.start()
    app = App()
    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()