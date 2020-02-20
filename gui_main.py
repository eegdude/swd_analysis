from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg
import numpy as np

import pathlib
import sys

import eeg_processing

settings = QSettings('MSU', 'swd_analysis')
# settings.clear()


def open_file():
    filename, _ = QFileDialog.getOpenFileName(None, 'Select EEG file', str(settings.value('LAST_FILE_LOCATION')), 'EEG (*.edf, *.bdf) ;; All files(*)')
    if filename:
        filename = pathlib.Path(filename)
        settings.setValue('LAST_FILE_LOCATION', filename.parent)
        eeg = eeg_processing.open_eeg_file(filename)

        return eeg
# class PlotWidgetWithKeyPress(object):

class MainWindow(QWidget):
    def __init__(self, eeg, parent=None):
        super(MainWindow, self).__init__(parent)
        print(eeg._data.shape)
        self.eeg = eeg

        self.channel = 0

        self.setWindowTitle("EEG plot")
        self.create_channel_switching_buttons()

        self.eeg_plot = self.create_eeg_plot()

    def create_eeg_plot(self, channel=0):
        self.p = pg.PlotWidget()
        self.p.setAntialiasing(False)
        
        eeg_plot = EegPlotter(eeg=self.eeg, channel=channel, vb=self.p.getViewBox())
        self.p.addItem(eeg_plot)
        self.layout.addWidget(self.p)
        
        return eeg_plot
   
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.eeg_plot.eeg_start -= 1000
            self.eeg_plot.eeg_stop -= 1000
            print('left')

        if event.key() == Qt.Key_Right:
            self.eeg_plot.eeg_start += 1000
            self.eeg_plot.eeg_stop += 1000
            print('right')

        self.eeg_plot.update_plot(caller='keyboard')

    def create_channel_switching_buttons(self):
        self.layout = QHBoxLayout()
        self.button_layout = QVBoxLayout()
        self.layout.addLayout(self.button_layout)
        self.setLayout(self.layout)

        self.channel_selectors=[QRadioButton(a) for a in eeg.info['ch_names']]
        self.channel_selectors[0].setChecked(True)
        [self.button_layout.addWidget(a) for a in self.channel_selectors]
        [a.toggled.connect(self.switch_channels) for a in self.channel_selectors]



    def switch_channels(self):
        if self.sender().isChecked():
            print ()
            self.p.close()
            self.create_eeg_plot(
                self.eeg.info['ch_names'].index(self.sender().text())
            )
                



class EegPlotter(pg.PlotCurveItem):
    def __init__(self, eeg, channel, vb, parent=None):
        # pg.PlotCurveItem.__init__(self, parent=parent)
        super(EegPlotter,self).__init__(parent)
        self.vb=vb
        self.window_len_sec = 10
        self.eeg = eeg
        self.channel = channel
        self.eeg_start = int(eeg.info['sfreq'])*5
        self.eeg_stop = int(eeg.info['sfreq']*self.window_len_sec)
        self.vb.setRange(xRange=(self.eeg_start, self.eeg_stop), padding=0, update=False)
        self.update_plot(eeg_start=self.eeg_start, eeg_stop=self.eeg_stop)

    def update_plot(self, eeg_start=None, eeg_stop=None, caller:str=None):
        x_range = self.vb.viewRange()[0]
        if x_range[0] < 0 and x_range[1]<0:
            self.eeg_start = 0
            self.eeg_stop=self.window_len_sec*int(eeg.info['sfreq'])
            return
        
        if caller != 'keyboard':
            if not eeg_start:
                self.eeg_start = max(0,int(x_range[0]) - 1)
            if not eeg_stop:
                self.eeg_stop = min(self.eeg._data.shape[1], int(x_range[1] + 2))

        if self.eeg_stop >= self.eeg._data.shape[1] or \
            self.eeg_start >= self.eeg._data.shape[1]:
            return
        
        y = self.eeg._data[self.channel, self.eeg_start: self.eeg_stop]
        x = np.arange(self.eeg_start, self.eeg_stop)
        self.setData(x, y, pen=pg.mkPen(color=pg.intColor(0), width=2), antialias=True)
        
        if caller == 'keyboard':
            self.vb.setRange(xRange=(self.eeg_start, self.eeg_stop), padding=0, update=False)

    def viewRangeChanged(self, *, caller:str=None):
        self.update_plot(caller='mouse')

if __name__ == "__main__":

    app = QApplication(sys.argv)
    # eeg = open_file()
    eeg = eeg_processing.open_eeg_file(pathlib.Path(r"C:\Data\kenul\28-01-2020_13-51.bdf"))
    print(eeg.info)
    eeg = eeg_processing.filter_eeg(eeg)
    ep = MainWindow(eeg)
    ep.show()
    sys.exit(app.exec_())



    # filename = r"C:\Data\kenul\28-01-2020_13-51.bdf"
    # Signal(eeg.get_data()).show()
    # Sleep(filename).show()

