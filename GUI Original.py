"""✅

Krav:
- leve op til IT2 forventninger
- Modtage signal fra Arduino boardet serielt RS232
- Vise målinger ✅
- Gemme data i database (SQL). Minimum:
    - EKG-data
    - Patientdata
- Vise EKG-diagram + dynamisk EKG-diagram som opdateres passende ✅
- Beregne aktuel puls ✅
- Have relevante automatiserede tests (unit-tests)
    - Eks. test der kontrolerer data gemmes og genkaldes

"""
import tkinter as tk
from tkinter import Frame
from tkinter import ttk
import random
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


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

        for F in (StartPage, PageOne, PageTwo):
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

        self.y_data = [5, 7, 9, 7, 6, 10, 14, 7, 0, 7, 7, 11, 4, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7]
        self.window_size = 50
        self.current_index = 0

        self.fig = Figure(figsize=(6, 5), dpi=100, facecolor='lightgreen')
        self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(expand=True, fill="both")

        # Venter med at starte opdateringsloops til efter opstart
        self.after(100, self.update_pulse)
        self.after(100, self.update_plot)

    def update_pulse(self):
        new_pulse = random.randint(50, 95)
        self.pulse_number_label.config(text=str(new_pulse))

        pulse_history = self.controller.pulse_history
        pulse_history.append(new_pulse)
        if len(pulse_history) > 20:
            pulse_history.pop(0)

        self.after(2000, self.update_pulse)

    def update_plot(self):
        data_len = len(self.y_data)
        indices = [(self.current_index + i) % data_len for i in range(self.window_size)]
        window_y = [self.y_data[i] for i in indices]
        window_x = list(range(self.window_size))

        self.ax.clear()
        self.ax.set_facecolor('white')
        self.ax.plot(window_x, window_y, color='black')

        # Gitter
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

        # Kald create_table for at oprette og vise tabellen
        self.create_table()

        btn = tk.Button(self, text="Tilbage", borderwidth=0,
                        highlightthickness=0, padx=8, pady=2,
                        command=lambda: controller.show_frame(StartPage))
        btn.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        btn2 = tk.Button(self, text="Opdater målinger", borderwidth=0,
                         highlightthickness=0, padx=8, pady=2,
                         command=None)
        btn2.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=+10)  # northeast = øverste højre hjørne

    def create_table(self):
        table_frame = tk.Frame(self)
        table_frame.place(relx=0.75, rely=0.1, anchor="n")

        # Definér kolonner
        columns = ("Måling", "Puls", "EKG data")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", height=20)

        # Konfigurer kolonner og overskrifter
        for col in columns:
            self.table.heading(col, text=col)
            self.table.column(col, anchor="center", width=100)

        self.table.pack()

        # Eksempeldata (kan senere udskiftes med database-data)
        sample_data = []  # opret tom liste udenfor loop

        for i in range(20):
            sample_data.append((i + 1, random.randint(50, 95), "+ " + str(random.randint(0, 8)) + "V"))

        for row in sample_data:
            self.table.insert("", "end", values=row)


if __name__ == "__main__":
    app = App()
    app.mainloop()
