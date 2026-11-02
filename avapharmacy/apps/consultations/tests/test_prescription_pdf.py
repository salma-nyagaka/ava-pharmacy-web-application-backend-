import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import skipUnless

from django.test import TestCase
from django.urls import reverse
from apps.consultations.models import ClinicianPrescription
from . import test_privacy as fixtures


@skipUnless(shutil.which('pdftotext') and shutil.which('pdfinfo'), 'Poppler is required to inspect PDF content and pagination.')
class ConsultationPrescriptionPDFTests(TestCase):
    setUp = fixtures.ConsultationPrivacyTests.setUp

    def test_long_medicine_and_instructions_wrap_across_pages_without_losing_content(self):
        name = ('Synthetic QA medicine & variant ' * 8) + 'TAIL-OF-MEDICINE'
        notes = ('Synthetic instructions only. ' * 12) + 'TAIL-OF-INSTRUCTIONS'
        prescription = ClinicianPrescription.objects.create(clinician=self.clinician, consultation=self.consultation, patient_name='Synthetic PDF QA', items=[{'drug_name': name, 'quantity': 3, 'dose': 'QA only', 'notes': notes} for _ in range(24)])
        self.client.force_authenticate(self.clinician_user)
        response = self.client.get(reverse('doctor-prescription-pdf', args=[prescription.pk]))
        self.assertEqual(response.status_code, 200)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prescription.pdf'
            path.write_bytes(response.content)
            content = subprocess.check_output(['pdftotext', str(path), '-'], text=True)
            info = subprocess.check_output(['pdfinfo', str(path)], text=True)
        self.assertEqual(content.count('TAIL-OF-MEDICINE'), 24)
        self.assertEqual(content.count('TAIL-OF-INSTRUCTIONS'), 24)
        self.assertEqual(content.count('Quantity: 3'), 24)
        pages = int(next(line.split(':')[1] for line in info.splitlines() if line.startswith('Pages:')))
        self.assertGreater(pages, 1)
