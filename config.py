from PyQt5.QtCore import QSettings
import configparser
__version__ = 0.2

cfg = configparser.ConfigParser()
cfg.read("config.ini")

nperseg_sec = cfg.getfloat("Welch", 'nperseg_sec') 
noverlap_fraction = cfg.getfloat("Welch", 'noverlap_fraction') 
max_freq = cfg.getfloat("Welch", 'max_freq') 
normalize = cfg.getboolean("Welch", 'normalize')

h_freq = cfg.getfloat("Filter", 'lowpass')
l_freq = cfg.getfloat("Filter", 'highpass')

acknow = 'Icons made by https://www.flaticon.com/authors/eucalyp'
settings = QSettings('MSU', 'swd_analysis')
settings.setValue('WINDOW_COLOR', '#FFFFFF')
# settings.clear()

enablePyQTGraphExperimental = False

decimal_separator = ','
