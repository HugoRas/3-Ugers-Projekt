import tkinter as tk
from tkinter import Frame
from tkinter import ttk
import random
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sqlite3
import threading
import time
from tkinter import messagebox

# Database connection
conn = sqlite3.connect("EKGDATABASE.db", check_same_thread=False)
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS Brugerdata (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Navn TEXT,
    Alder INTEGER,
    KØN TEXT
    )""")
conn.commit()
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


class Datahandler():
    def __init__(self, conn_local):
        cursor_local = conn_local.cursor()
        puls = random.randrange(30, 180)
        data = random.randrange(-70, 35)
        cursor_local.execute("""
            INSERT INTO Ekgdata (PatientID, puls, data, Tidspunkt)
            VALUES (?, ?, ?, datetime('now'))
        """, (1, puls, data))
        conn_local.commit()


def data_thread():
    global run
    conn_local = sqlite3.connect("EKGDATABASE.db")
    while run:
        try:
            Datahandler(conn_local)
            time.sleep(0.1)
            conn_local.commit()
        except Exception as e:
            print("FEJL i data_thread:", e)
            break
    conn_local.close()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EKG program")

        width = 900
        height = 600
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2) - 50
        self.geometry(f"{width}x{height}+{x}+{y}")

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
        super().__init__(parent, bg="lightblue")
        self.controller = controller

        # Header
        label = tk.Label(self, text="Dynamisk EKG Diagram", font=("Helvetica", 16), bg="lightblue")
        label.pack(pady=10)

        # Create figure for EKG plot
        self.fig = Figure(figsize=(8, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("EKG Signal")
        self.ax.set_xlabel("Tid")
        self.ax.set_ylabel("Amplitude")

        # Create canvas for matplotlib figure
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Puls display
        self.puls_label = tk.Label(self, text="Puls: --", font=("Helvetica", 14), bg="lightblue")
        self.puls_label.pack(pady=10)

        # Back button
        back_btn = tk.Button(self, text="Tilbage",
                             command=lambda: controller.show_frame(StartPage))
        back_btn.pack(pady=10)

        # Start data update thread
        self.update_data()

    def update_data(self):
        if not run:  # Check if application is still running
            return

        # Get latest data from database
        cursor.execute("SELECT Data, Puls FROM Ekgdata WHERE PatientID = 1 ORDER BY Id DESC LIMIT 50")
        results = cursor.fetchall()

        if results:
            data_points = [x[0] for x in results]
            latest_pulse = results[-1][1]

            # Update plot
            self.ax.clear()
            self.ax.plot(data_points, 'b-')
            self.ax.set_title("EKG Signal")
            self.ax.set_xlabel("Tid")
            self.ax.set_ylabel("Amplitude")
            self.canvas.draw()

            # Update pulse display
            self.puls_label.config(text=f"Puls: {latest_pulse}")

        # Schedule next update
        self.after(100, self.update_data)


class PageTwo(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="lightblue")
        self.controller = controller

        label = tk.Label(self, text="Målinger", font=("Helvetica", 16), bg="lightblue")
        label.pack(pady=10)

        # Create treeview for measurements
        self.tree = ttk.Treeview(self, columns=("Tidspunkt", "Puls", "Data"), show="headings")
        self.tree.heading("Tidspunkt", text="Tidspunkt")
        self.tree.heading("Puls", text="Puls")
        self.tree.heading("Data", text="Data")
        self.tree.column("Tidspunkt", width=200)
        self.tree.column("Puls", width=100)
        self.tree.column("Data", width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Refresh button
        refresh_btn = tk.Button(self, text="Opdater", command=self.refresh_data)
        refresh_btn.pack(pady=5)

        # Back button
        back_btn = tk.Button(self, text="Tilbage",
                             command=lambda: controller.show_frame(StartPage))
        back_btn.pack(pady=10)

        # Initial data load
        self.refresh_data()

    def refresh_data(self):
        # Clear existing data
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Get data from database
        cursor.execute("""
            SELECT strftime('%Y-%m-%d %H:%M:%S', Tidspunkt), Puls, Data 
            FROM Ekgdata 
            WHERE PatientID = 1 
            ORDER BY Tidspunkt DESC
            LIMIT 100
        """)

        # Insert data into treeview
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


def on_closing():
    global run
    run = False
    conn.close()
    app.destroy()


if __name__ == "__main__":
    data_thread = threading.Thread(target=data_thread, daemon=True)
    data_thread.start()
    app = App()
    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()