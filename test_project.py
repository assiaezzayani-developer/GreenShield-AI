import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class TestProject(unittest.TestCase):
 def test_core_files(self):
  for f in ['backend/main.py','frontend/src.jsx','frontend/style.css','backend/.env.example','PAYPAL_SETUP.md']:
   self.assertTrue((ROOT/f).is_file(),f)
 def test_secret_not_bundled(self):
  self.assertFalse((ROOT/'backend/.env').exists())
 def test_key_status_endpoint(self):
  text=(ROOT/'backend/main.py').read_text()
  self.assertIn("'/api/ai/status'",text)
  self.assertIn("dotenv_values(ROOT/'.env')",text)
if __name__=='__main__':unittest.main()
