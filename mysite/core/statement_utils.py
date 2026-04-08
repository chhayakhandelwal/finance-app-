import pdfplumber
import pytesseract
from PIL import Image
import pdf2image
import re
DATE_REGEXES = [
  re.compile(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b"),   # 24-08-2025
  re.compile(r"\b(\d{2}[-/]\d{2}[-/]\d{2})\b"),   # ✅ 24/08/25 (NEW)
  re.compile(r"\b(\d{4}[-/]\d{2}[-/]\d{2})\b"),
  re.compile(r"\b(\d{2}\s+[A-Za-z]{3,9}\s+\d{4})\b"),
]
# ✅ IMPORTANT: set correct path (already done)
pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"








# ✅ helper cleaner (you were missing this earlier sometimes)
def _clean_text(text: str) -> str:
  return text.replace("\x00", "").strip()








def extract_text(file):
  name = getattr(file, "name", "").lower()




  # =========================
  # ✅ STEP 1: pdfplumber
  # =========================
  if name.endswith(".pdf"):
      try:
          if hasattr(file, "seek"):
              file.seek(0)




          with pdfplumber.open(file) as pdf:
              text = "\n".join((p.extract_text() or "") for p in pdf.pages)




          text = _clean_text(text)




          print("\n--- PDFPLUMBER TEXT SAMPLE ---")
          print(text[:300])




          # ✅ only accept if meaningful
          if len(text) > 1000 and "balance" in text.lower():
              print("✅ USING PDFPLUMBER")
              return text




          print("⚠️ pdfplumber not sufficient → fallback OCR")




      except Exception as e:
          print("PDFPLUMBER ERROR:", str(e))




  # =========================
  # 🔥 STEP 2: OCR (PDF → images)
  # =========================
  try:
      print("🔥 FALLBACK OCR RUNNING")




      if hasattr(file, "seek"):
          file.seek(0)




      images = pdf2image.convert_from_bytes(file.read())




      ocr_text = ""




      for idx, img in enumerate(images):
          try:
              txt = pytesseract.image_to_string(img)
              print(f"\n--- OCR PAGE {idx} SAMPLE ---")
              print(txt[:300])




              ocr_text += txt + "\n"




          except Exception as e:
              print("OCR ERROR:", str(e))




      ocr_text = _clean_text(ocr_text)




      if len(ocr_text) > 50:
          print("✅ OCR SUCCESS")
          return ocr_text




      print("❌ OCR RETURNED EMPTY")




  except Exception as e:
      print("PDF2IMAGE ERROR:", str(e))




  # =========================
  # ✅ STEP 3: IMAGE FILES
  # =========================
  try:
      print("🖼️ IMAGE OCR RUNNING")




      if hasattr(file, "seek"):
          file.seek(0)




      img = Image.open(file).convert("RGB")
      text = pytesseract.image_to_string(img)




      return _clean_text(text)




  except Exception as e:
      print("IMAGE OCR ERROR:", str(e))




  # =========================
  # ❌ FINAL FAIL
  # =========================
  print("❌ ALL METHODS FAILED")
  return ""




from datetime import datetime




def parse_stmt_date(s: str):
  s = s.strip()




  for fmt in [
      "%d-%m-%Y",
      "%d/%m/%Y",
      "%d-%m-%y",   # ✅ important
      "%d/%m/%y",   # ✅ important
      "%Y-%m-%d",
      "%d %b %Y",
      "%d %B %Y",
  ]:
      try:
          return datetime.strptime(s, fmt).date()
      except:
          continue




  return None





