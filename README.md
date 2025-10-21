# ToDo App

Diese ToDo-Applikation ist ein leichtgewichtiges Aufgaben-Board zur Verwaltung von Tasks und Subtasks. Der Schwerpunkt liegt auf einfacher Bedienung, lokaler Datenspeicherung und übersichtlicher Darstellung ohne unnötige Zusatzfunktionen oder Cloud-Anbindung.

---

## Features

- Aufgaben mit Subtasks erstellen, bearbeiten und löschen  
- Lokale, transparente Datenspeicherung in einer JSON-Datei  
- Automatisches Speichern bei jeder Änderung  
- Generierung einer HTML-Übersicht der erledigten Tasks des aktuellen Monats  
- Minimalistisches und übersichtliches Benutzerinterface mit PySide6  

---

## Installation und Ausführung

### Ausführung
``` python todo_tool.py ```

### Voraussetzungen
- Python 3.9 oder höher
- `pip`

### Abhängigkeiten installieren
```bash
pip install pyside6
```

## Persistenz
Alle Daten werden lokal in einer JSON-Datei gespeichert und beim Start der Anwendung automatisch geladen.
Speicherung: ``` ./data/tasks.json ```
Format: JSON, gut lesbar und leicht zu sichern
Über die Export-Funktion wird ein HTML-Report erzeugt, welcher die im aktuellen Monat abgeschlossenen Aufgaben auflistet.
