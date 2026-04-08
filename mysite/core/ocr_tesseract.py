"""
Configure pytesseract to find the tesseract binary.


Django / GUI apps often have a minimal PATH (no Homebrew). We resolve explicitly.
Set TESSERACT_CMD to override (e.g. /opt/homebrew/bin/tesseract).
"""
from __future__ import annotations


import os
import shutil
from pathlib import Path


_configured = False




def configure_tesseract() -> None:
   global _configured
   if _configured:
       return


   import pytesseract


   from django.conf import settings


   cmd = os.environ.get("TESSERACT_CMD") or getattr(settings, "TESSERACT_CMD", None)


   if not cmd:
       cmd = shutil.which("tesseract")


   if not cmd:
       for p in (
           "/opt/homebrew/bin/tesseract",
           "/usr/local/bin/tesseract",
           "/opt/local/bin/tesseract",
       ):
           if Path(p).is_file():
               cmd = p
               break


   if cmd:
       pytesseract.pytesseract.tesseract_cmd = cmd


   _configured = True



