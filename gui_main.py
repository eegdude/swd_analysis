from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg
import numpy as np
import scipy

import pathlib
import sys

import eeg_processing


import logging

settings = QSettings('MSU', 'swd_analysis')
pg.setConfigOptions(enableExperimental=False)
# settings.clear()

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

    def create_eeg_plot(self, channel:int=0):
        ch_name = self.eeg.info['ch_names'][channel]
        p = pg.PlotWidget( background='#FFFFFF')
        p.setAntialiasing(True)
        
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
            [self.eeg_plots[k]['PlotWidget'].setYLink(self.eeg_plots[kk[0]]['PlotWidget'].getViewBox()) for k in kk[1:]]

    
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
    def __init__(self, eeg, vb, channel:int=0, parent=None):
        super(EegPlotter,self).__init__()
        self.vb = vb
        self.vb.disableAutoRange()
        self.eeg = eeg
        self.channel = channel
        self.last_pos = [None, None]
        self.window_len_sec = 10
        self.scroll_step = 1000 # make adapive?
        self.eeg_start = 5*int(eeg.info['sfreq'])
        self.eeg_stop = self.window_len_sec*int(eeg.info['sfreq'])
        self.max_displayed_len = 1e4
        self.update_plot(eeg_start=self.eeg_start, eeg_stop=self.eeg_stop, init=True)

    def update_plot(self, eeg_start=None, eeg_stop=None, caller:str=None, direction=None, init:bool=None):
        if init:
            y = self.eeg._data[self.channel, self.eeg_start: self.eeg_stop]
            self.vb.setRange(xRange=(self.eeg_start, self.eeg_stop), yRange=(np.min(y), np.max(y)), padding=0, update=False)
            return

        x_range = [int(a) for a in self.vb.viewRange()[0]]
        if caller == 'keyboard':
            self.scroll_step = (x_range[1]-x_range[0])//4
            if direction == 'left':
                self.eeg_stop -= min(self.scroll_step, self.eeg_start)
                self.eeg_start = max(self.eeg_start-self.scroll_step, 0)
            elif direction == 'right':
                self.eeg_start += min(self.scroll_step, abs(self.eeg_stop-self.eeg._data.shape[1]))
                self.eeg_stop = min(self.eeg_stop+self.scroll_step, self.eeg._data.shape[1])
            elif direction == None:
                return
        else: # mouse
            logging.debug (['x_range', x_range])
            # if self.eeg._data.shape[1] >= x_range[1]:
            self.eeg_stop = min(self.eeg._data.shape[1], x_range[1])
            # if x_range[0] >= 0:
            self.eeg_start = max(x_range[0], 0)
        
        if [self.eeg_start, self.eeg_stop] == self.last_pos: # avoid unnecessary refreshes
            # self.vb.disableAutoRange()
            return
        x = np.arange(self.eeg_start, self.eeg_stop)
        y = self.eeg._data[self.channel, self.eeg_start: self.eeg_stop]
        
        if len(x) > self.max_displayed_len:
            ds_div = int(2*len(x)//self.max_displayed_len)
            x, y = x[::ds_div], scipy.signal.decimate(y, ds_div, ftype='fir')
        else:
            ds_div = 1

        self.setData(x=x, y=y, pen=pg.mkPen(color=pg.intColor(0), width=1), antialias=True)
        self.vb.setRange(xRange=(self.eeg_start, self.eeg_stop), padding=0, update=False)
        self.last_pos = [self.eeg_start, self.eeg_stop]
        logging.debug (f"drawing len {len(y)} downsample {ds_div} start {self.eeg_start} stop {self.eeg_stop} range {x_range} range_samples {abs(x_range[1] - x_range[0])} eeg len {self.eeg._data.shape[1]} last {self.last_pos}")

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
    # eeg._data = eeg._data[:, :15000]
    ep = MainWindow(eeg)
    ep.setBackground('#FFFFFF')
    ep.show()
    sys.exit(app.exec_())