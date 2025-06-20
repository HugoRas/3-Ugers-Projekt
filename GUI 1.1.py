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

# Der oprettes forbindelse til databasen
conn = sqlite3.connect("EKGDATABASE.db", check_same_thread=False)
cursor = conn.cursor()

# Der oprettes tabeller hvis ikke de allerede findes
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
    PatientID INTEGER ,
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
    # Ny separat forbindelse i baggrundstråden
    conn_local = sqlite3.connect("EKGDATABASE.db")
    while run:
        try:
            Datahandler(conn_local)
            time.sleep(1)
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

    def get_login_frame(selfself):
        return self.frames[Login]

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

        btn = tk.Button(self, text="Tilbage", borderwidth=0,
                        highlightthickness=0, padx=8, pady=2,
                        command=lambda: controller.show_frame(StartPage))
        btn.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        container_frame = Frame(self, bg="lightgreen")
        container_frame.place(relx=0.58, rely=0.2, anchor="n")

        plot_frame = Frame(container_frame, width=400, height=250)
        plot_frame.pack(side="left")
        plot_frame.pack_propagate(False)

        pulse_frame = Frame(container_frame, width=150, height=250, bg="lightgreen")
        pulse_frame.pack(side="left", padx=(20, 0))
        pulse_frame.pack_propagate(False)

        self.pulse_number_label = tk.Label(pulse_frame, text="--", font=("Helvetica", 26, "bold"),
                                           fg="red", bg="lightgreen")
        tk.Label(pulse_frame, text="Puls", font=("Helvetica", 18), bg="lightgreen").pack(pady=(10, 10))
        self.pulse_number_label.pack(padx=10, pady=(0, 3))

        btn2 = tk.Button(self, text="Gå til pulsmålinger",
                         borderwidth=0, highlightthickness=0, padx=10, pady=4,
                         command=lambda: controller.show_frame(PageTwo))
        btn2.place(relx=0.9, rely=0.4, anchor="e")

        # ✅ Ny korrekt initiering af y_data hentet fra database
        cursor.execute("SELECT Data FROM Ekgdata ORDER BY id DESC LIMIT 50")
        self.y_data = [row[0] for row in cursor.fetchall()[::-1]] or [0] * 50

        self.window_size = 50
        self.current_index = 0

        self.fig = Figure(figsize=(6, 5), dpi=100, facecolor='lightgreen')
        self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(expand=True, fill="both")

        self.after(100, self.update_pulse)
        self.after(100, self.update_plot)

    def update_pulse(self):
        cursor.execute("SELECT Puls FROM EKGDATA ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        new_pulse = result[0] if result else 0
        self.pulse_number_label.config(text=str(new_pulse))

        pulse_history = self.controller.pulse_history
        pulse_history.append(new_pulse)
        if len(pulse_history) > 20:
            pulse_history.pop(0)

        self.after(2000, self.update_pulse)

    def update_plot(self):
        cursor.execute("SELECT Data FROM Ekgdata ORDER BY id DESC LIMIT 50")
        self.y_data = [row[0] for row in cursor.fetchall()[::-1]] or [0] * 50

        data_len = len(self.y_data)
        indices = [(self.current_index + i) % data_len for i in range(self.window_size)]
        window_y = [self.y_data[i] for i in indices]
        window_x = list(range(self.window_size))

        self.ax.clear()
        self.ax.set_facecolor('white')
        self.ax.plot(window_x, window_y, color='black')

        for x in range(self.window_size + 1):
            self.ax.axvline(x=x, color='lightcoral', linewidth=0.5)
        for y in range(0, 16):
            self.ax.axhline(y=y, color='lightcoral', linewidth=0.5)
        for x in range(0, self.window_size + 1, 5):
            self.ax.axvline(x=x, color='red', linewidth=1.0)
        for y in range(0, 16, 5):
            self.ax.axhline(y=y, color='red', linewidth=1.0)

        self.ax.set_title("EKG diagram")
        self.ax.set_ylabel("Lead")
        self.ax.set_ylim(0, 15)
        self.ax.set_xlim(0, self.window_size - 1)
        self.ax.set_xticks([])
        self.ax.set_yticks([])

        self.canvas.draw_idle()
        self.current_index = (self.current_index + 1) % data_len
        self.after(40, self.update_plot)

class PageTwo(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="lightyellow")
        self.controller = controller

        label = tk.Label(self, text="Målinger", bg="lightyellow", font=("Helvetica", 18, "bold"))
        label.place(relx=0.02, rely=0.02, anchor="nw")

        self.create_table()

        btn = tk.Button(self, text="Tilbage", borderwidth=0,
                        highlightthickness=0, padx=8, pady=2,
                        command=lambda: controller.show_frame(StartPage))
        btn.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        btn2 = tk.Button(self, text="Opdater målinger", borderwidth=0, highlightthickness=0, padx=8, pady=2,command=None)
        btn2.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=+10)

    def create_table(self):
        table_frame = tk.Frame(self)
        table_frame.place(relx=0.75, rely=0.1, anchor="n")

        columns = ("Måling", "Puls", "EKG data")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", height=20)

        for col in columns:
            self.table.heading(col, text=col)
            self.table.column(col, anchor="center", width=100)

        self.table.pack()

        sample_data = []
        for i in range(20):
            sample_data.append((i+1, random.randint(50, 95), "+ " + str(random.randint(0, 8)) + "V"))

        for row in sample_data:
            self.table.insert("", "end", values=row)

def on_closing():
    global run
    run = False
    conn.close()
    app.destroy()

class Login(tk.Frame):
    def __init__(self, parent, controller=None):
        super().__init__(parent,bg="lightblue")
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

        patient = {"name": name, "age": age, "gender": gender}
        self.patient_data.append(patient)

        messagebox.showinfo("Succes", f"Patient {name} oprettet.")
        self.entry_name.delete(0, tk.END)
        self.entry_age.delete(0, tk.END)
        self.entry_gender.delete(0, tk.END)

    def view_patients(self):
        self.patient_listbox.delete(0, tk.END)
        for p in self.patient_data:
            self.patient_listbox.insert(tk.END, f"{p['name']} - {p['age']} år - {p['gender']}")


if __name__ == "__main__":
    data_thread = threading.Thread(target=data_thread, daemon=True)  # ✅ FIX: korrekt trådkald
    data_thread.start()
    app = App()
    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()