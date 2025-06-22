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

COMport = "COM5" #COM Port vælges
baud = 38400 #Baud rate skal matche arduino koden

conn = sqlite3.connect("EKGDATABASE.db", check_same_thread=False) #Forbindelse til databasefil
cursor = conn.cursor()

#Der oprettes 3 tabeller til data hvis de ikke findes
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

#Benyttes til threading mm.
run = True

class Datahandler():
    # Initialiserer Datahandler med patient ID og stop-event. Buffer benyttes til
    def __init__(self, patient_id, stop_event):
        self.patient_id = patient_id #patienten der måles på's ID
        self.stop_event = stop_event #Threading stopper funktion
        self.buffer = deque(maxlen=300) #Dobbeltkø der holder på seneste 300 værdier (Benyttes til pulsberegning)

    # Læser seriel data fra Arduino og indsætter i databasen.
    def serialdata(self, com):
        try:
            conn_local = sqlite3.connect("EKGDATABASE.db") #Lokal forbindelse til Databasen
            cursor_local = conn_local.cursor()
            ser = serial.Serial(com, baud, timeout=0.001) #Åbner serial port
            sio = io.TextIOWrapper(io.BufferedReader(ser))

            while not self.stop_event.is_set(): #Kører en løkke indtil stop_event køres
                try:
                    data = sio.readline().strip() #Fjerne whitespaces fra serialdata
                    if not data:
                        continue

                    value = float(data)  #Gør værdien til en float og gemmer i buffer til beregning
                    self.buffer.append(value)

                    # pulsberegner benyttes, men først når 100 målinger laves
                    puls = self.beregn_puls() if len(self.buffer) >= 100 else None

                    #Variabel med nuværende tid sættes
                    now = datetime.now().isoformat(timespec='microseconds')

                    #De nu fundne værdier sættes ind i databasen
                    cursor_local.execute("""
                        INSERT INTO Ekgdata (PatientID, Data, Tidspunkt, Puls)
                        VALUES (?, ?, ?, ?)
                    """, (self.patient_id, value, now, puls))
                    conn_local.commit()
                except Exception as e:
                    print("Fejl ved læsning/indsættelse:", e)

        except Exception as e:
            print("Serialfejl:", e)

    # Beregner pulsen ud fra peak-detektion i den interne buffer.
    def beregn_puls(self):
        peaks, _ = find_peaks(self.buffer, height=1000, distance=40, prominence=200) #finder signaltoppe vha scipy
        if len(peaks) < 2: #Mindst to peaks skal haves for at regne distance mellem dem
            return None
        rr_intervaller = np.diff(peaks) #Afstanden mellem peaks findes (R til R peak)
        if len(rr_intervaller) == 0:
            return None

        #Gennemsnitsintervallet mellem peaks divideres med samplingfrekvensen for at få varighed i sekunder
        rr_mean = np.mean(rr_intervaller)
        fs = 250
        sek_per_peak = rr_mean / fs
        return int(60 / sek_per_peak) if sek_per_peak > 0 else None # Konverterer sek/beat til BPM


class App(tk.Tk):
    # Initialiserer hoved-GUI'en og konfigurerer navigation mellem sider.
    def __init__(self):
        super().__init__() # Arver fra tk.Tk
        self.title("EKG program") #Titel
        self.geometry("900x600") #Størrelse
        self.resizable(False, False) #Ikke resizable

        #Centrerer vinduet på skærmen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (900 // 2)
        y = (screen_height // 2) - (600 // 2) - 50
        self.geometry(f"900x600+{x}+{y}")

        #Opretter frame til stedholder på undersider
        container = tk.Frame(self)
        container.pack(fill="both", expand=True)

        #Tom dic til at gemme instance af alle frames/sider
        self.frames = {}

        #Benyttes til at gemme pulshistorik og valgt patient
        self.pulse_history = []
        self.selected_patient_id = None

        #For hver variabel opretter og placerer undersider
        for F in (StartPage, PageOne, PageTwo, Login):
            frame = F(parent=container, controller=self)
            self.frames[F] = frame
            frame.place(relwidth=1, relheight=1)

        self.show_frame(StartPage) #Viser StartPage som første side når programmet åbnes

    # Skifter den viste side i GUI'en til den angivne frame.
    def show_frame(self, page_class):
        frame = self.frames[page_class]
        frame.tkraise() #Placerer den øverst i GUI'en

class StartPage(tk.Frame):
    # Initialiserer en side i GUI med de nødvendige widgets.
    def __init__(self, parent, controller):
        super().__init__(parent, bg="lightblue") #arver fra tk.Frame
        self.controller = controller

        label = tk.Label(self, text="Hovedmenu", font=("Helvetica", 18, "bold"), bg="lightblue") #Titel
        label.place(relx=0.02, rely=0.02, anchor="nw") #Placering af titel

        #Første knap. Funktion: Patientlisen opdateres og der skiftes til PageOne
        tk.Button(self, text="EKG diagram og puls", bg="lightblue",
                  borderwidth=0, highlightthickness=0, padx=10, pady=4,
                  command=lambda: [controller.frames[PageOne].load_patients(), controller.show_frame(PageOne)]).pack(
            pady=(80, 10))

        #Anden knap skifter til PageTwo
        tk.Button(self, text="Data over målinger", bg="lightblue",
                  borderwidth=0, highlightthickness=0, padx=10, pady=4,
                  command=lambda: controller.show_frame(PageTwo)).pack()

        #Tredje knap skifter til Login
        tk.Button(self, text="Patienter", bg="lightblue",
                  borderwidth=0, highlightthickness=0, padx=10, pady=4,
                  command=lambda: controller.show_frame(Login)).pack(pady=(10, 0))

class PageOne(tk.Frame):
    # Initialiserer en side i GUI med de nødvendige widgets.
    def __init__(self, parent, controller):
        super().__init__(parent, bg="lightblue") #Arver fra tk.Frame
        self.controller = controller

        # buffere til ekgdata og tid. (Benyttes til pulsberegning)
        self.ekg_buffer = deque(maxlen=5000)
        self.tid_buffer = deque(maxlen=5000)
        self.smooth_pulse = None  # glattet puls variabel

        tk.Label(self, text="EKG diagram og puls", bg="lightblue", #Titel
                 font=("Helvetica", 18, "bold")).place(relx=0.02, rely=0.02, anchor="nw")

        self.puls_label = tk.Label(self, text="--", font=("Helvetica", 26, "bold"),
                                   fg="red", bg="lightblue")
        tk.Label(self, text="Puls", font=("Helvetica", 18), bg="lightblue").place(relx=0.85, rely=0.22) #puls tekst
        self.puls_label.place(relx=0.85, rely=0.3) #Viser aktuel puls. Er bundet til update_data funktionen

        #Dropdown med patientvalg (ID og Navn) Ved valg kaldes patient_selected
        self.patient_var = tk.StringVar()
        # Label til dropdown
        tk.Label(self, text="Vælg patient:", bg="lightblue", font=("Helvetica", 16)).place(relx=0.56, rely=0.053)

        # Dropdown-menu
        self.patient_dropdown = ttk.Combobox(self, textvariable=self.patient_var, state="readonly", width=25)
        self.patient_dropdown.place(relx=0.7, rely=0.05)

        self.patient_dropdown.bind("<<ComboboxSelected>>", self.patient_selected)
        self.load_patients()

        #Rammer til grafområde
        container_frame = Frame(self, bg="lightblue")
        container_frame.place(relx=0.05, rely=0.15)

        plot_frame = Frame(container_frame, width=600, height=350)
        plot_frame.pack()
        plot_frame.pack_propagate(False)

        #Opretter matplotlib figur i TKinter
        self.fig = Figure(figsize=(6, 4.5), dpi=100, facecolor='lightblue')
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(expand=True, fill="both")

        #Knap tilbage til StartPage
        tk.Button(self, text="Tilbage", borderwidth=0, highlightthickness=0,
                  padx=10, pady=4, command=lambda: controller.show_frame(StartPage)).place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        #Starter realtidsopdatering
        self.update_data()

        # Trådrelateret
        self.data_thread = None
        self.stop_event = None

        # Start-knap
        tk.Button(self, text="Start måling", borderwidth=0, highlightthickness=0, padx=10, pady=4, command=self.start_measurement).place(relx=0.7, rely=0.1)
        # Stop-knap
        tk.Button(self, text="Stop måling", borderwidth=0, highlightthickness=0, padx=10, pady=4, command=self.stop_measurement).place(relx=0.7, rely=0.15)

        # Her gemmer vi alle visninger af smooth puls
        self.smooth_pulses = []

    # Indlæser patienter fra databasen til dropdown-menuen.
    def load_patients(self):
        cursor.execute("SELECT Id, Navn FROM Brugerdata") #Henter ID og navn
        self.patients = cursor.fetchall()
        names = [f"{navn} (ID: {pid})" for pid, navn in self.patients] #For hvert navn omdannes det til pæn string
        self.patient_dropdown['values'] = names #Insættes i dropdown
        if names: #Ved navne vælges første patient, og patient_selected kaldes så korrekt ID sættes som variabel
            self.patient_dropdown.current(0)
            self.patient_selected()

    # Stopper målingen og gemmer gennemsnitspulsen i databasen.
    def stop_measurement(self):
        if self.data_thread and self.data_thread.is_alive(): #Tjekker om tråd køres (Der er aktiv måling)
            print("Måling stoppes manuelt") #Sender stop besked til tråd og variable ryddes op
            self.stop_event.set()
            self.data_thread.join()
            self.data_thread = None
            self.stop_event = None

            # Gemmer gennemsnit af smooth_pulse i Pulsmålinger
            if self.smooth_pulses:
                avg_pulse = int(round(np.mean(self.smooth_pulses))) #Gennemsnitspulsen regnes fra liste
                cursor.execute("INSERT INTO Pulsmålinger (PatientID, Puls) VALUES (?, ?)", #Indsættes i DB
                               (self.controller.selected_patient_id, avg_pulse))
                conn.commit()

                #Beskedbokse
                print(f"Gemte gennemsnitlig puls: {avg_pulse}")
                messagebox.showinfo("Måling stoppet", f"Målingen er stoppet.\nGennemsnitlig puls: {avg_pulse} BPM")
            else:
                messagebox.showinfo("Måling stoppet", "Målingen er stoppet, men der blev ikke registreret nogen puls.")
        else:
            messagebox.showinfo("Ingen aktiv måling", "Der kører ingen måling i øjeblikket.")

    # Starter en ny tråd til indsamling af EKG-data.
    def start_measurement(self):
        self.smooth_pulses = []  # Nulstil tidligere målinger

        #Tjekker om patient er valgt
        index = self.patient_dropdown.current()
        if index < 0:
            messagebox.showwarning("Ingen patient", "Vælg en patient først.")
            return

        #Finder ID på valgte patient og gemmer den i variabel
        patient_id, _ = self.patients[index]
        self.controller.selected_patient_id = patient_id

        # Stop evt. gammel tråd
        if self.data_thread and self.data_thread.is_alive():
            print("Stopper tidligere måling")
            self.stop_event.set()
            self.data_thread.join()

        # Start ny tråd
        print(f"Starter ny måling for patient {patient_id}")
        self.stop_event = threading.Event()
        self.data_thread = threading.Thread(
            target=lambda: Datahandler(patient_id, self.stop_event).serialdata(COMport),
            daemon=True
        )
        self.data_thread.start()

    # Registrerer valgt patient fra dropdown-menuen.
    def patient_selected(self, event=None):
        index = self.patient_dropdown.current()
        if index >= 0:
            patient_id, _ = self.patients[index]
            self.controller.selected_patient_id = patient_id

    # Beregner puls baseret på EKG-data og tidsstempler.
    def beregn_puls(self, data, tider):
        if len(data) < 10: #Venter på minimum 10 målinger for at undgå fejlmålinger
            return None
        try:
            sekunder = np.array([(t - tider[0]).total_seconds() for t in tider]) #numpy array med tid i sek ifht 1. mål
            signal = np.array(data) #Array med EKG værdier

            # Lavpasfilter
            signal = uniform_filter1d(signal, size=5)

            # Finder peaks
            peaks, _ = find_peaks(signal, height=1000, distance=200, prominence=300)
            if len(peaks) < 2: # Der skal bruges minimum 2 peaks for at kunne regne puls
                return None

            # RR-interval (sekunder)
            rr_intervaller = np.diff(sekunder[peaks]) #Beregner tid i sek mellem peaks
            rr_intervaller = rr_intervaller[(rr_intervaller > 0.3) & (rr_intervaller < 3.5)]  # Mellem 30–210 BPM

            #Der skal haves gyldige intervaller
            if len(rr_intervaller) == 0:
                return None

            rr_mean = np.mean(rr_intervaller[-5:]) #Gennemsnit fra sidste 5 intervaller
            return 60 / rr_mean if rr_mean > 0 else None #konverterer til BPM fra sek/Beat
        #Går noget galt returneres fejlmedling
        except Exception as e:
            print("Pulsfejl:", e)
            return None

    # Opdaterer graf og puls i realtid med nyeste målinger.
    def update_data(self):
        if not run: #Tjekker om programmet kører
            return

        #Er der ikke valgt en patient så prøv igen om 1 sekund
        patient_id = self.controller.selected_patient_id
        if not patient_id:
            self.after(1000, self.update_data)
            return

        #Henter seneste 150 EKG værdier og tilhørende puls
        cursor.execute("SELECT Data, Puls FROM Ekgdata WHERE PatientID = ? ORDER BY Id DESC LIMIT 150", (patient_id,))
        results = cursor.fetchall()

        #Fås der resultater
        if results:
            data_points = [x[0] for x in results][::-1] #Indeholder amplituder i rækkefølge
            latest_pulse = results[0][1] #Bruges til visning før ny beregning

            #Rydder grafen og tegner ny kurve
            self.ax.clear()
            self.ax.set_facecolor('white')
            self.ax.plot(range(len(data_points)), data_points, color='black')

            # Gitter og aksemærkninger
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

            #Henter seneste 100 målinger inkl tid
            cursor.execute("SELECT Tidspunkt, Data FROM Ekgdata WHERE PatientID = ? ORDER BY Id DESC LIMIT 100", (patient_id,))
            rows = cursor.fetchall()[::-1]

            #Viser seneste kendte beregning
            self.puls_label.config(text=str(latest_pulse))

            #Tilføjer nye målinger til buffers
            for tid, val in rows:
                try:
                    self.ekg_buffer.append(float(val))
                    self.tid_buffer.append(datetime.fromisoformat(tid))
                except:
                    continue

            #Kalder beregn puls med nyeste datapunkter
            dynamisk_puls = self.beregn_puls(list(self.ekg_buffer), list(self.tid_buffer))

            #Udglatter ændringer i puls (exponentielt glidende avg)
            if dynamisk_puls:
                if self.smooth_pulse is None:
                    self.smooth_pulse = dynamisk_puls
                else:
                    self.smooth_pulse = 0.3 * dynamisk_puls + 0.7 * self.smooth_pulse  # glat overgang

                #Viser puls i GUI
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
            #Fås ingen værdier sættes puls til "--"
            else:
                self.puls_label.config(text="--")
        #Kører igen om 3ms (realtid)
        self.after(3,self.update_data)

class PageTwo(tk.Frame):
    # Initialiserer en side i GUI med de nødvendige widgets. Arver fraq tk.Frame
    def __init__(self, parent, controller):
        super().__init__(parent, bg="lightblue")
        self.controller = controller

        self.patient_label = tk.Label(self, text="Målinger", font=("Helvetica", 16), bg="lightblue")
        self.patient_label.pack(pady=10) #Titel

        #Tabel formatering.
        self.tree = ttk.Treeview(self, columns=("Tidspunkt", "Puls", "Data"), show="headings")
        self.tree.heading("Tidspunkt", text="Tidspunkt")
        self.tree.heading("Puls", text="Puls")
        self.tree.heading("Data", text="Data")
        self.tree.column("Tidspunkt", width=200)
        self.tree.column("Puls", width=100)
        self.tree.column("Data", width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        #Opdater knap
        refresh_btn = tk.Button(self, text="Opdater", borderwidth=0, highlightthickness=0, padx=10, pady=4, command=self.refresh_data)
        refresh_btn.pack(pady=10)

        #Tilbage knap
        back_btn = tk.Button(self, text="Tilbage", borderwidth=0, highlightthickness=0, padx=10, pady=4, command=lambda: controller.show_frame(StartPage)).place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        self.refresh_data()

    # Opdaterer tabellen med de nyeste målinger for valgt patient.
    def refresh_data(self):
        for item in self.tree.get_children(): #For hver del i self.tree fra constructer slettes de.
            self.tree.delete(item)

        #Findes patient_id vil den vælge værdierne fra databasen og returnerer hvis ingen patient er valgt
        patient_id = self.controller.selected_patient_id
        if not patient_id:
            self.patient_label.config(text="Målinger (ingen patient valgt)")
            return

        tk.Label(self, text="Målinger", bg="lightblue", #Titel
                 font=("Helvetica", 18, "bold")).place(relx=0.02, rely=0.02, anchor="nw")
        self.patient_label.config(text=f"Patient ID: {patient_id}") #titel på side

        cursor.execute("""
                       SELECT strftime('%Y-%m-%d %H:%M:%S', Tidspunkt), Puls, Data
                       FROM Ekgdata
                       WHERE PatientID = ?
                       ORDER BY Tidspunkt DESC
                       LIMIT 100
                       """, (patient_id,))

        #For hver værdi hentet til cursor indsættes det i tree
        for row in cursor.fetchall():
            self.tree.insert("", tk.END, values=row)


class Login(tk.Frame):
    def __init__(self, parent, controller=None):
        super().__init__(parent, bg="lightblue")
        self.controller = controller
        self.patient_data = []

        # Let styling af combobox så den matcher Entry felter
        style = ttk.Style()
        style.theme_use('default')

        style.configure('TCombobox',
                        fieldbackground='white',  # tekstfelt baggrund
                        background='white',  # widget baggrund (når den ikke er åben)
                        bordercolor='gray',
                        lightcolor='white',
                        darkcolor='white',
                        borderwidth=1,
                        relief='solid',
                        padding=3,
                        font=("Helvetica", 12))

        style.map('TCombobox',
                  fieldbackground=[('readonly', 'white'), ('!readonly', 'white')],
                  background=[('readonly', 'white'), ('!readonly', 'white')],
                  bordercolor=[('focus', 'gray'), ('!focus', 'gray')])

        self._create_title()
        self._create_form()
        self._create_buttons()

    def _create_title(self):
        """Opretter overskriften øverst på siden."""
        tk.Label(
            self,
            text="Patienter",
            bg="lightblue",
            font=("Helvetica", 18, "bold"),
            anchor="w",  # Teksten forankres til venstre
            justify="left"  # Venstrestillet hvis der er flere linjer
        ).pack(fill="x", padx=20, pady=10)

    def _create_form(self):
        """Opretter inputfelterne til navn, alder og køn."""
        form_frame = tk.Frame(self, bg="lightblue")
        form_frame.pack(pady=10)

        self.entry_name = self._create_labeled_entry(form_frame, "Navn")
        self.entry_age = self._create_labeled_entry(form_frame, "Alder")
        self.entry_gender = self._create_labeled_combobox(form_frame, "Køn", ("Mand", "Kvinde", "Andet"))

    def _create_labeled_entry(self, parent, label_text):
        """Hjælpefunktion til at lave label + entry i én række."""
        row = tk.Frame(parent, bg="lightblue")
        row.pack(pady=5, anchor="w")

        tk.Label(row, text=f"{label_text}:", font=("Helvetica", 14),
                 bg="lightblue", width=10, anchor="w").pack(side="left")
        entry = tk.Entry(row, bg="white", highlightthickness=0, bd=0, width=30)
        entry.pack(side="left")
        return entry

    def _create_labeled_combobox(self, parent, label_text, values):
        """Hjælpefunktion til at lave label + combobox i én række."""
        row = tk.Frame(parent, bg="lightblue")
        row.pack(pady=5, anchor="w")

        tk.Label(row, text=f"{label_text}:", font=("Helvetica", 14),
                 bg="lightblue", width=10, anchor="w").pack(side="left")
        var = tk.StringVar()
        combobox = ttk.Combobox(row, textvariable=var, state="readonly",
                                width=28, style='TCombobox')
        combobox["values"] = values
        combobox.pack(side="left")
        return combobox

    def _create_buttons(self):
        """Opretter knapperne til handlinger."""
        button_frame = tk.Frame(self, bg="lightblue")
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="Opret patient", bg="lightblue",
                  borderwidth=0, highlightthickness=0, padx=10, pady=4,
                  command=self.submit_patient).pack(side="left", padx=5)

        tk.Button(button_frame, text="Se patienter", bg="lightblue",
                  borderwidth=0, highlightthickness=0, padx=10, pady=4,
                  command=self.view_patients).pack(side="left", padx=5)

        self.back_button = tk.Button(button_frame, text="Tilbage til patientliste",
                                     command=self.view_patients)
        self.back_button.pack(side="left", padx=5)
        self.back_button.pack_forget()

        # ===== Lister =====
        list_frame = tk.Frame(self, bg="lightblue")
        list_frame.pack(pady=20)

        self.patient_listbox = tk.Listbox(list_frame, width=40)
        self.patient_listbox.pack(side="left", padx=(20, 10))
        self.patient_listbox.bind("<<ListboxSelect>>", self.on_patient_select)

        self.measurement_listbox = tk.Listbox(list_frame, width=40)
        self.measurement_listbox.pack(side="left", padx=(10, 20))

        # ===== Tilbage-knap nederst =====
        bottom_frame = tk.Frame(self, bg="lightblue")
        bottom_frame.pack(fill="both", expand=True)

        tk.Button(bottom_frame, text="Tilbage", bg="lightblue",
                  borderwidth=0, highlightthickness=0, padx=10, pady=4,
                  command=lambda: self.controller.show_frame(StartPage)).pack(side="right", anchor="se", padx=10, pady=10)

    # Opretter ny patient i databasen med navn, alder og køn.
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
        self.entry_gender.set('')  # brug set('') fremfor delete

    # Viser alle patienter i listevisning.
    def view_patients(self):
        self.patient_listbox.delete(0, tk.END)
        cursor.execute("SELECT Navn, Alder, KØN FROM Brugerdata")

        for navn, alder, køn in cursor.fetchall():
            self.patient_listbox.insert(tk.END, f"{navn} - {alder} år - {køn}")
        self.back_button.pack_forget()  # skjul tilbage-knappen

    # Viser pulsmålinger for valgt patient i højre side.
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

        cursor.execute("""
            SELECT Puls
            FROM Pulsmålinger
            WHERE PatientID = ?
            ORDER BY Id DESC
            LIMIT 5
            """, (patient_id,))
        målinger = cursor.fetchall()

        self.measurement_listbox.delete(0, tk.END)
        if målinger:
            self.measurement_listbox.insert(tk.END, f"Seneste pulsmålinger for {navn} (ID {patient_id}):")
            for i, (puls,) in enumerate(målinger, 1):
                self.measurement_listbox.insert(tk.END, f"{i}. {puls} BPM")
        else:
            self.measurement_listbox.insert(tk.END, f"Ingen pulsmålinger fundet for {navn}.")


# Sørger for sikker nedlukning af GUI og tråde.
def on_closing():
    global run
    run = False
    #Tjekker om tråd kører, og lukker den hvis den gør
    try:
        frame = app.frames[PageOne]
        if frame.data_thread and frame.data_thread.is_alive():
            frame.stop_event.set()
            frame.data_thread.join()
    except:
        pass

    conn.close() #Lukker SQL forbindelse
    app.destroy() #Lukker GUI vindue

# Starter hovedprogrammet og konfigurerer lukke-event.
if __name__ == "__main__":
    app = App() #Opretter instans af GUI
    setattr(app, "selected_patient_id", None) #attribut der holder styr på valgte patient
    app.protocol("WM_DELETE_WINDOW", on_closing) #Binder lukkeknappen til "on_closing"
    app.mainloop() #TKinters hovedlykke der holder GUI i gange