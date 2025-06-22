import unittest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
import sys
import os

# Tilføj sti til GUI-filen så den kan importeres
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import GUI_final_2_0 as gui  # Sørg for at navnet matcher din fil

class TestGUI(unittest.TestCase):
    def setUp(self):
        # Mock controller og patientvalg
        self.mock_controller = MagicMock()
        self.mock_controller.selected_patient_id = 1

        # Initialiser PageOne med mocks
        self.page = gui.PageOne(parent=None, controller=self.mock_controller)
        self.page.patient_dropdown = MagicMock()
        self.page.patient_dropdown.current.return_value = 0
        self.page.patients = [(1, "Test Person")]
        self.page.controller.selected_patient_id = 1

    def test_patient_selected_index_negativ(self):
        self.page.patient_dropdown.current.return_value = -1
        self.page.patient_selected()
        self.assertEqual(self.page.controller.selected_patient_id, 1)

    def test_load_patients_dropdown_values(self):
        # Mock fetchall før kald
        gui.cursor = MagicMock()
        gui.cursor.fetchall.return_value = [(1, "Test Person"), (2, "Anna Hansen")]

        self.page.patient_dropdown = MagicMock()
        self.page.patient_dropdown.current.return_value = 0
        self.page.load_patients()

        expected = ["Test Person (ID: 1)", "Anna Hansen (ID: 2)"]
        self.page.patient_dropdown.__setitem__.assert_called_with('values', expected)

    def test_beregn_puls_invalid_rr(self):
        data = [1200, 0, 0, 0, 1200, 0, 0, 0]
        tider = [datetime.now() + timedelta(seconds=i * 10) for i in range(len(data))]
        result = self.page.beregn_puls(data, tider)
        self.assertIsNone(result)

    def test_beregn_puls_mindre_end_10(self):
        data = [1000, 1020]
        tider = [datetime.now(), datetime.now() + timedelta(milliseconds=10)]
        result = self.page.beregn_puls(data, tider)
        self.assertIsNone(result)

    def test_beregn_puls_valide_peak_intervaller(self):
        base_time = datetime.now()
        data = []
        tider = []

        for i in range(6):
            # Baseline før peak
            for _ in range(250):
                data.append(0)
                tider.append(base_time + timedelta(milliseconds=4 * len(tider)))

            # Bredt og højt peak
            peak_values = [1000, 2000, 3000, 2000, 1000]
            for val in peak_values:
                data.append(val)
                tider.append(base_time + timedelta(milliseconds=4 * len(tider)))

            # Efter peak
            for _ in range(50):
                data.append(0)
                tider.append(base_time + timedelta(milliseconds=4 * len(tider)))

        result = self.page.beregn_puls(data, tider)
        print("Valide peak test:", result)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, float)
        self.assertTrue(30 < result < 200)

    def test_update_data_uden_patient(self):
        self.page.controller.selected_patient_id = None
        self.page.after = MagicMock()
        self.page.update_data()
        self.page.after.assert_called_once()

    def test_beregn_puls_tom_data(self):
        result = self.page.beregn_puls([], [])
        self.assertIsNone(result)

    def test_beregn_puls_for_faa_peaks(self):
        data = [0]*10 + [1200] + [0]*10  # Kun ét peak
        tider = [datetime.now() + timedelta(milliseconds=40 * i) for i in range(len(data))]
        result = self.page.beregn_puls(data, tider,)
        self.assertIsNone(result)

    def test_pulsberegning_med_valid_peaks(self):
        data = []
        tider = []
        now = datetime.now()
        interval = 250

        for i in range(6):
            data += [200] * interval
            tider += [now + timedelta(milliseconds=4 * len(tider)) for _ in range(interval)]

            # Lav et bredt peak, så det overlever lavpasfilter
            peak_values = [1000, 2000, 3000, 2000, 1000]
            data += peak_values
            tider += [now + timedelta(milliseconds=4 * len(tider)) for _ in peak_values]

        result = self.page.beregn_puls(data, tider)
        print("Resultat af pulsberegning:", result)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, float)
        self.assertTrue(30 < result < 200)



if __name__ == '__main__':
    unittest.main()
