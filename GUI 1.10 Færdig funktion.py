import tkinter as tk
from tkinter import Frame, ttk, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sqlite3
import threading
import io
import serial
from collections import deque
from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d
import numpy as np
from datetime import datetime

COMport = "COM5"
baud = 38400

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
CREATE TABLE IF NOT EXISTS Pulsmålinger (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    PatientID INTEGER,
    Puls INTEGER,
    FOREIGN KEY (PatientID) REFERENCES Brugerdata(Id)
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

class Datahandler():
    def __init__(self, patient_id, stop_event):
        self.patient_id = patient_id
        self.stop_event = stop_event
        self.buffer = deque(maxlen=300)

    def serialdata(self, com):
        try:
            conn_local = sqlite3.connect("EKGDATABASE.db")
            cursor_local = conn_local.cursor()
            ser = serial.Serial(com, baud, timeout=0.001)
            sio = io.TextIOWrapper(io.BufferedReader(ser))

            while not self.stop_event.is_set():
                try:
                    data = sio.readline().strip()
                    if not data:
                        continue

                    value = float(data)
                    self.buffer.append(value)

                    puls = self.beregn_puls() if len(self.buffer) >= 100 else None

                    now = datetime.now().isoformat(timespec='microseconds')
                    cursor_local.execute("""
                        INSERT INTO Ekgdata (PatientID, Data, Tidspunkt, Puls)
                        VALUES (?, ?, ?, ?)
                    """, (self.patient_id, value, now, puls))
                    conn_local.commit()
                except Exception as e:
                    print("Fejl ved læsning/indsættelse:", e)

        except Exception as e:
            print("Serialfejl:", e)

    def beregn_puls(self):
        peaks, _ = find_peaks(self.buffer, height=1000, distance=40, prominence=200)
        if len(peaks) < 2:
            return None
        rr_intervaller = np.diff(peaks)
        if len(rr_intervaller) == 0:
            return None
        rr_mean = np.mean(rr_intervaller)
        fs = 250
        sek_per_peak = rr_mean / fs
        return int(60 / sek_per_peak) if sek_per_peak > 0 else None


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
        self.selected_patient_id = None

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

        tk.Button(self, text="Dynamisk EKG diagram og puls", bg="lightblue",
                  borderwidth=0, highlightthickness=0, padx=10, pady=4,
                  command=lambda: [controller.frames[PageOne].load_patients(), controller.show_frame(PageOne)]).pack(
            pady=(80, 10))

        tk.Button(self, text="Målinger", bg="lightblue",
                  borderwidth=0, highlightthickness=0, padx=10, pady=4,
                  command=lambda: controller.show_frame(PageTwo)).pack()

        tk.Button(self, text="Login / Patienter", bg="lightblue",
                  borderwidth=0, highlightthickness=0, padx=10, pady=4,
                  command=lambda: controller.show_frame(Login)).pack(pady=(10, 0))

class PageOne(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="lightgreen")
        self.controller = controller
        self.ekg_buffer = deque(maxlen=5000)
        self.tid_buffer = deque(maxlen=5000)
        self.smooth_pulse = None  # glattet puls

        tk.Label(self, text="Dynamisk EKG diagram og puls", bg="lightgreen",
                 font=("Helvetica", 18, "bold")).place(relx=0.02, rely=0.02, anchor="nw")

        self.puls_label = tk.Label(self, text="--", font=("Helvetica", 26, "bold"),
                                   fg="red", bg="lightgreen")
        tk.Label(self, text="Puls", font=("Helvetica", 18), bg="lightgreen").place(relx=0.85, rely=0.22)
        self.puls_label.place(relx=0.85, rely=0.3)

        self.patient_var = tk.StringVar()
        self.patient_dropdown = ttk.Combobox(self, textvariable=self.patient_var, state="readonly")
        self.patient_dropdown.place(relx=0.7, rely=0.05)
        self.patient_dropdown.bind("<<ComboboxSelected>>", self.patient_selected)
        self.load_patients()

        container_frame = Frame(self, bg="lightgreen")
        container_frame.place(relx=0.05, rely=0.15)

        plot_frame = Frame(container_frame, width=600, height=350)
        plot_frame.pack()
        plot_frame.pack_propagate(False)

        self.fig = Figure(figsize=(6, 4.5), dpi=100, facecolor='lightgreen')
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(expand=True, fill="both")

        tk.Button(self, text="Tilbage", borderwidth=0, highlightthickness=0,
                  padx=10, pady=4, command=lambda: controller.show_frame(StartPage)).place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        self.update_data()

        # Trådrelateret
        self.data_thread = None
        self.stop_event = None

        # Start-knap
        tk.Button(self, text="Start måling", command=self.start_measurement).place(relx=0.7, rely=0.1)
        # Stop-knap
        tk.Button(self, text="Stop måling", command=self.stop_measurement).place(relx=0.7, rely=0.15)

        self.smooth_pulses = []  # Her gemmer vi alle visninger af smooth puls

    def load_patients(self):
        cursor.execute("SELECT Id, Navn FROM Brugerdata")
        self.patients = cursor.fetchall()
        names = [f"{navn} (ID: {pid})" for pid, navn in self.patients]
        self.patient_dropdown['values'] = names
        if names:
            self.patient_dropdown.current(0)
            self.patient_selected()

    def stop_measurement(self):
        if self.data_thread and self.data_thread.is_alive():
            print("🛑 Måling stoppes manuelt")
            self.stop_event.set()
            self.data_thread.join()
            self.data_thread = None
            self.stop_event = None

            # ✅ Trin 3 – Gem gennemsnit af smooth_pulse i Pulsmålinger
            if self.smooth_pulses:
                avg_pulse = int(round(np.mean(self.smooth_pulses)))
                cursor.execute("INSERT INTO Pulsmålinger (PatientID, Puls) VALUES (?, ?)",
                               (self.controller.selected_patient_id, avg_pulse))
                conn.commit()
                print(f"💾 Gemte gennemsnitlig puls: {avg_pulse}")
                messagebox.showinfo("Måling stoppet", f"Målingen er stoppet.\nGennemsnitlig puls: {avg_pulse} BPM")
            else:
                messagebox.showinfo("Måling stoppet", "Målingen er stoppet, men der blev ikke registreret nogen puls.")
        else:
            messagebox.showinfo("Ingen aktiv måling", "Der kører ingen måling i øjeblikket.")

    def start_measurement(self):
        self.smooth_pulses = []  # Nulstil tidligere målinger

        index = self.patient_dropdown.current()
        if index < 0:
            messagebox.showwarning("Ingen patient", "Vælg en patient først.")
            return

        patient_id, _ = self.patients[index]
        self.controller.selected_patient_id = patient_id

        # Stop evt. gammel tråd
        if self.data_thread and self.data_thread.is_alive():
            print("🛑 Stopper tidligere måling")
            self.stop_event.set()
            self.data_thread.join()

        # Start ny tråd
        print(f"▶️ Starter ny måling for patient {patient_id}")
        self.stop_event = threading.Event()
        self.data_thread = threading.Thread(
            target=lambda: Datahandler(patient_id, self.stop_event).serialdata(COMport),
            daemon=True
        )
        self.data_thread.start()

    def patient_selected(self, event=None):
        index = self.patient_dropdown.current()
        if index >= 0:
            patient_id, _ = self.patients[index]
            self.controller.selected_patient_id = patient_id

    def beregn_puls(self, data, tider):
        if len(data) < 10:
            return None
        try:
            sekunder = np.array([(t - tider[0]).total_seconds() for t in tider])
            signal = np.array(data)

            # Lavpasfilter
            signal = uniform_filter1d(signal, size=5)

            # Find peaks
            peaks, _ = find_peaks(signal, height=1000, distance=200, prominence=300)
            if len(peaks) < 2:
                return None

            # RR-interval (sekunder)
            rr_intervaller = np.diff(sekunder[peaks])
            rr_intervaller = rr_intervaller[(rr_intervaller > 0.3) & (rr_intervaller < 2.0)]  # 30–120 BPM

            if len(rr_intervaller) == 0:
                return None

            rr_mean = np.mean(rr_intervaller[-5:])
            return 60 / rr_mean if rr_mean > 0 else None
        except Exception as e:
            print("Pulsfejl:", e)
            return None

    def update_data(self):
        if not run:
            return

        patient_id = self.controller.selected_patient_id
        if not patient_id:
            self.after(1000, self.update_data)
            return

        cursor.execute("SELECT Data, Puls FROM Ekgdata WHERE PatientID = ? ORDER BY Id DESC LIMIT 150", (patient_id,))
        results = cursor.fetchall()

        if results:
            data_points = [x[0] for x in results][::-1]
            latest_pulse = results[0][1]

            self.ax.clear()
            self.ax.set_facecolor('white')
            self.ax.plot(range(len(data_points)), data_points, color='black')

            # Ny: gitter og aksemærkninger
            self.ax.grid(True, which='both', linestyle='--', linewidth=0.5, color='gray', alpha=0.7)  # <-- ny
            self.ax.set_xlabel("Tid (målepunkt #)")  # <-- ny
            self.ax.set_ylabel("Amplitude (AD værdi)")  # <-- ny
            step = max(1, len(data_points) // 10)  # <-- ny
            self.ax.set_xticks(range(0, len(data_points), step))  # <-- ny
            self.ax.set_xticklabels([str(i) for i in range(0, len(data_points), step)], rotation=45)  # <-- ny

            self.ax.set_title("EKG diagram")
            self.ax.set_ylim(-100, 4500)
            self.ax.set_xlim(0, len(data_points) - 1)
            self.ax.tick_params(axis='both', labelsize=8)
            self.canvas.draw()

            cursor.execute("SELECT Tidspunkt, Data FROM Ekgdata WHERE PatientID = ? ORDER BY Id DESC LIMIT 100", (patient_id,))
            rows = cursor.fetchall()[::-1]

            self.puls_label.config(text=str(latest_pulse))

            for tid, val in rows:
                try:
                    self.ekg_buffer.append(float(val))
                    self.tid_buffer.append(datetime.fromisoformat(tid))
                except:
                    continue

            dynamisk_puls = self.beregn_puls(list(self.ekg_buffer), list(self.tid_buffer))
            if dynamisk_puls:
                if self.smooth_pulse is None:
                    self.smooth_pulse = dynamisk_puls
                else:
                    self.smooth_pulse = 0.3 * dynamisk_puls + 0.7 * self.smooth_pulse  # glat overgang
                self.puls_label.config(text=f"{int(self.smooth_pulse)} BPM")
                self.smooth_pulses.append(self.smooth_pulse)

                # Opdater seneste puls i databasen
                cursor.execute("""
                        UPDATE Ekgdata
                        SET Puls = ?
                        WHERE PatientID = ? AND Id = (
                            SELECT Id FROM Ekgdata WHERE PatientID = ? ORDER BY Id DESC LIMIT 1
                        )
                    """, (int(self.smooth_pulse), patient_id, patient_id))
                conn.commit()
            else:
                self.puls_label.config(text="--")

        self.after(3,self.update_data)

class PageTwo(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="lightblue")
        self.controller = controller

        self.patient_label = tk.Label(self, text="Målinger", font=("Helvetica", 16), bg="lightblue")
        self.patient_label.pack(pady=10)

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

        patient_id = self.controller.selected_patient_id
        if not patient_id:
            self.patient_label.config(text="Målinger (ingen patient valgt)")
            return

        self.patient_label.config(text=f"Målinger for patient ID: {patient_id}")

        cursor.execute("""
                       SELECT strftime('%Y-%m-%d %H:%M:%S', Tidspunkt), Puls, Data
                       FROM Ekgdata
                       WHERE PatientID = ?
                       ORDER BY Tidspunkt DESC
                       LIMIT 100
                       """, (patient_id,))

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
        self.patient_listbox.bind("<<ListboxSelect>>", self.on_patient_select)

        self.back_button = tk.Button(self, text="Tilbage til patientliste", command=self.view_patients)
        self.back_button.grid(row=7, column=0, columnspan=2)
        self.back_button.grid_remove()  # Skjul den fra start

        back_btn = tk.Button(self, text="Tilbage", command=lambda: controller.show_frame(StartPage))
        back_btn.grid(row=10, column=15, columnspan=2, pady=10)

        # Patientliste (venstre)
        self.patient_listbox = tk.Listbox(self, width=40)
        self.patient_listbox.grid(row=6, column=0, padx=(20, 10), pady=10, sticky="n")
        self.patient_listbox.bind("<<ListboxSelect>>", self.on_patient_select)

        # Pulsmålinger (højre)
        self.measurement_listbox = tk.Listbox(self, width=40)
        self.measurement_listbox.grid(row=6, column=1, padx=(10, 20), pady=10, sticky="n")

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
        if self.controller:
            self.controller.frames[PageOne].load_patients()
        self.entry_name.delete(0, tk.END)
        self.entry_age.delete(0, tk.END)
        self.entry_gender.delete(0, tk.END)

    def view_patients(self):
        self.patient_listbox.delete(0, tk.END)
        cursor.execute("SELECT Navn, Alder, KØN FROM Brugerdata")
        for navn, alder, køn in cursor.fetchall():
            self.patient_listbox.insert(tk.END, f"{navn} - {alder} år - {køn}")
        self.back_button.grid_remove()  # Skjul tilbage-knappen

    def on_patient_select(self, event):
        selection = self.patient_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        cursor.execute("SELECT Id, Navn FROM Brugerdata")
        patients = cursor.fetchall()
        if index >= len(patients):
            return

        patient_id, navn = patients[index]

        # Hent pulsmålinger
        cursor.execute("""
                       SELECT Puls
                       FROM Pulsmålinger
                       WHERE PatientID = ?
                       ORDER BY Id DESC
                       LIMIT 5
                       """, (patient_id,))
        målinger = cursor.fetchall()

        # Opdater højre felt (målinger)
        self.measurement_listbox.delete(0, tk.END)
        if målinger:
            self.measurement_listbox.insert(tk.END, f"Seneste pulsmålinger for {navn} (ID {patient_id}):")
            for i, (puls,) in enumerate(målinger, 1):
                self.measurement_listbox.insert(tk.END, f"{i}. {puls} BPM")
        else:
            self.measurement_listbox.insert(tk.END, f"Ingen pulsmålinger fundet for {navn}.")


def on_closing():
    global run
    run = False
    try:
        frame = app.frames[PageOne]
        if frame.data_thread and frame.data_thread.is_alive():
            frame.stop_event.set()
            frame.data_thread.join()
    except:
        pass

    conn.close()
    app.destroy()

if __name__ == "__main__":
    app = App()
    setattr(app, "selected_patient_id", None)
    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()
