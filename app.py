"""
AutoTest QA Studio — ponto de entrada da GUI.

Interface moderna (CustomTkinter, tema escuro) em `ui/`. A versão anterior
(Tkinter clássico) está preservada em `app_legacy.py` como fallback.

    python app.py
"""

from ui.app_shell import main

if __name__ == "__main__":
    main()
