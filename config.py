from PyQt5.QtCore import QSettings
import configparser
__version__ = 0.5

cfg = configparser.ConfigParser()
cfg.read("config.ini")

nperseg_sec = cfg.getfloat("Welch", 'nperseg_sec') 
noverlap_fraction = cfg.getfloat("Welch", 'noverlap_fraction') 
fmax = cfg.getfloat("Welch", 'max_freq') 
normalize = cfg.getboolean("Welch", 'normalize')

peak_prominence_percentage_from_minmax = cfg.getfloat("SWD", 'peak_prominence_percentage_from_minmax')
invert_SWD = cfg.getboolean("SWD", 'invert_SWD')

h_freq = cfg.getfloat("Filter", 'lowpass')
l_freq = cfg.getfloat("Filter", 'highpass')
notch_freq = cfg.getfloat("Filter", 'notch')

decimal_separator = cfg.get('Export', 'decimal_separator')
csv_sep = cfg.get('Export', 'csv_sep')

acknow = 'Icons made by https://www.flaticon.com/authors/eucalyp\nConsulting on signal processing by @DeadAt0m'
settings = QSettings('MSU', 'swd_analysis')
settings.setValue('WINDOW_COLOR', '#FFFFFF')
# settings.clear()

enablePyQTGraphExperimental = False
