from PyQt5.QtCore import QSettings

__version__ = 0.2
acknow = 'Icons made by https://www.flaticon.com/authors/eucalyp'
settings = QSettings('MSU', 'swd_analysis')
settings.setValue('WINDOW_COLOR', '#FFFFFF')
# settings.clear()

enablePyQTGraphExperimental = False