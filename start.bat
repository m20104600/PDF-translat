@echo off
echo Starting PDFMathTranslate-next WebUI...
set PDF2ZH_UI_LANG=zh
python -m pdf2zh_next.main --gui
pause
