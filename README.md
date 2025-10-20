# ToDo
Dieses ToDo App ist eine einfache Umsetzung eines TodoBoards für verschiedene Einsatzbereiche.
Es ist sehr simpel gehalten und verfolgt das Ziel der Aufgabenverfolgung. Alle Daten werden lokal gehalten und sind in Verantwortung des Users.

## Requirements
Für das Design wurde pySide6 verwendet.
Man installiert es mit:

``` pip install pyside6 ```

## Persistierung
Die Aufgaben und die Subtasks werden bei jeder Änderung in ein lokales JSON File gespeichert und auch von da geladen.
Mit einem Klick auf "Export" wird ein html File generiert, welches die erledigten Tasks des aktuellen Monats anzeigt.

## Sinn und Zweck
Oftmals ist das richtige Tool zu finden schwer. Viele bekannte Tools sind Überladen, kosten oder sind einfach nicht genau so wie man sie haben möchte.
Aus diesem Grund habe ich mir selbst schnell ein Tool erstellt um ein schnelles Tasktracking zu ermöglichen.
