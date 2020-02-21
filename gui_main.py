from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg
import numpy as np

import pathlib
import sys

import eeg_processing

import logging

settings = QSettings('MSU', 'swd_analysis')
# settings.clear()
# logging.debug = print

def open_file():
    filename, _ = QFileDialog.getOpenFileName(None, 'Select EEG file', str(settings.value('LAST_FILE_LOCATION')), 'EEG (*.edf, *.bdf) ;; All files(*)')
    if filename:
        filename = pathlib.Path(filename)
        settings.setValue('LAST_FILE_LOCATION', filename.parent)
        eeg = eeg_processing.open_eeg_file(filename)

        return eeg

class MainWindow(pg.GraphicsWindow):
    def __init__(self, eeg, parent=None):
        super(MainWindow, self).__init__(parent)
        self.eeg = eeg

        self.channel = 0

        self.setWindowTitle("EEG plot")
        self.eeg_plots = {}
        self.create_channel_switching_buttons()

    def create_eeg_plot(self, channel=0):
        ch_name = self.eeg.info['ch_names'][channel]
        p = pg.PlotWidget( background='default')
        p.setAntialiasing(False)
        
        eeg_plot = EegPlotter(eeg=self.eeg, channel=channel, vb=p.getViewBox())
        p.addItem(eeg_plot, name = ch_name, title=ch_name)
        self.eeg_layout.addWidget(p)
        self.eeg_plots[ch_name] = {'PlotWidget':p, 'Curve':eeg_plot}
        self.relink_plots()

        return eeg_plot
    
    def relink_plots(self):
        if len(self.eeg_plots.values())>1:
            kk = list(self.eeg_plots.keys())
            [self.eeg_plots[k]['PlotWidget'].setXLink(self.eeg_plots[kk[0]]['PlotWidget'].getViewBox()) for k in kk[1:]]
    
    def keyPressEvent(self, event):
        ev = event.key()
        if ev == Qt.Key_Left or ev == Qt.Key_A:
            direction = 'left'
        elif ev == Qt.Key_Right or ev == Qt.Key_D:
            direction = 'right'
        else:
            direction = None
        logging.debug(['key: ', direction])
        
        list(self.eeg_plots.values())[0]['Curve'].update_plot(caller='keyboard', direction=direction)

    def create_channel_switching_buttons(self):
        self.layout = QHBoxLayout()
        self.eeg_layout = QVBoxLayout()
        self.button_layout = QVBoxLayout()
        self.layout.addLayout(self.button_layout)
        self.layout.addLayout(self.eeg_layout)
        self.setLayout(self.layout)

        self.channel_selectors=[QCheckBox(a) for a in self.eeg.info['ch_names']]
        [self.button_layout.addWidget(a) for a in self.channel_selectors]
        [a.toggled.connect(self.switch_channels) for a in self.channel_selectors]
        
        self.channel_selectors[0].setChecked(True)
        self.channel_selectors[1].setChecked(True)

    def switch_channels(self):
        ch_name = self.sender().text()
        if self.sender().isChecked():
            if ch_name not in self.eeg_plots.values():
                self.create_eeg_plot(self.eeg.info['ch_names'].index(ch_name))
        else:
            self.eeg_plots[ch_name]['PlotWidget'].setParent(None)
            self.eeg_plots.pop(ch_name)

class EegPlotter(pg.PlotCurveItem):
    def __init__(self, eeg, channel, vb, parent=None):
        super(EegPlotter,self).__init__(parent)
        self.vb=vb
        self.eeg = eeg
        self.channel = channel

        self.window_len_sec = 10
        self.eeg_start = int(eeg.info['sfreq'])*5
        self.eeg_stop = int(eeg.info['sfreq']*self.window_len_sec)
        self.max_displayed_len = 1e6
        self.update_plot(eeg_start=self.eeg_start, eeg_stop=self.eeg_stop, init=True)

    def update_plot(self, eeg_start=None, eeg_stop=None, caller:str=None, direction=None, init:bool=None):
        if init:
            self.vb.setRange(xRange=(self.eeg_start, self.eeg_stop), padding=0, update=False)
            return

        x_range = [int(a) for a in self.vb.viewRange()[0]]

        if caller == 'keyboard':
            if direction == 'left':
                self.eeg_stop -= min(1000, self.eeg_start)
                self.eeg_start = max(self.eeg_start-1000, 0)

            elif direction == 'right':
                self.eeg_start += min(1000, abs(self.eeg_stop-self.eeg._data.shape[1]))
                self.eeg_stop = min(self.eeg_stop+1000, self.eeg._data.shape[1])
                    
            elif direction == None:
                return
        else: # mouse
            logging.debug (['x_range', x_range])
            # if self.eeg._data.shape[1] >= x_range[1]:
            self.eeg_stop = min(self.eeg._data.shape[1], x_range[1])
            # if x_range[0] >= 0:
            self.eeg_start = max(x_range[0], 0)

        x = np.arange(self.eeg_start, self.eeg_stop)
        y = self.eeg._data[self.channel, self.eeg_start: self.eeg_stop]
        self.setData(x, y, pen=pg.mkPen(color=pg.intColor(0), width=2), antialias=True)
        self.vb.setRange(xRange=(self.eeg_start, self.eeg_stop), padding=0, update=False)
        
        logging.debug ([0, self.eeg_start, self.eeg_stop, x_range, abs(x_range[1] - x_range[0]), self.eeg._data.shape[1]])

    def viewRangeChanged(self, *, caller:str=None):
        self.update_plot(caller='mouse')
        self.vb.setRange(xRange=(self.eeg_start, self.eeg_stop), padding=0, update=False)

if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s	%(processName)s	%(message)s', level=logging.DEBUG)
    logging.getLogger()

    app = QApplication(sys.argv)
    # eeg = open_file()
    eeg = eeg_processing.open_eeg_file(pathlib.Path(r"C:\Data\kenul\28-01-2020_13-51.bdf"))
    eeg = eeg_processing.filter_eeg(eeg)
    eeg._data = eeg._data[:, :15000]
    ep = MainWindow(eeg)
    ep.show()
    sys.exit(app.exec_())



    # filename = r"C:\Data\kenul\28-01-2020_13-51.bdf"
    # Signal(eeg.get_data()).show()
    # Sleep(filename).show()

