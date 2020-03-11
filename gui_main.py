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
        eeg = {'data':eeg_processing.open_eeg_file(filename),
                'filename':str(filename)}
        return eeg

class MainWindow(pg.GraphicsWindow):
    def __init__(self, eeg=None):
        super(MainWindow, self).__init__()
        self.setBackground('#FFFFFF')
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.eeg = eeg
        self.create_menu()
        self.load_eeg(self.eeg)

    def load_eeg(self, eeg):
        if eeg is None:
            eeg = {'data':None, 'filename':''}
        eeg['data'] = eeg_processing.filter_eeg(eeg['data'])
        self.graph_widget = MainWidget(eeg = eeg['data'], parent = self)
        self.setWindowTitle(eeg['filename'])
        self.layout.addWidget(self.graph_widget)

    def create_menu(self):
        OpenAction = QAction("&Open", self)
        OpenAction.setShortcut("Ctrl+O")
        OpenAction.triggered.connect(self.open_file)
        menubar = QMenuBar(self)
        actionFile = menubar.addMenu("File")
        actionFile.addAction(OpenAction)
        self.layout.addWidget(menubar)
    
    def open_file(self):
        self.eeg = open_file()
        self.graph_widget.setParent(None)
        self.graph_widget.destroy()
        self.load_eeg(self.eeg)

class MainWidget(pg.GraphicsLayoutWidget):
    def __init__(self, eeg, parent=None):
        super(MainWidget, self).__init__(parent)
        self.setBackground('#FFFFFF')
        self.eeg = eeg
        self.channel = 0
        self.eeg_plots = {}
        self.create_window_elements()

    def create_window_elements(self):
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout2 = QHBoxLayout()
        self.layout.addLayout(self.layout2)

        self.menu_layout = QVBoxLayout()
        self.layout2.addLayout(self.menu_layout)

        self.eeg_layout = QVBoxLayout()
        self.layout2.addLayout(self.eeg_layout)
        if self.eeg:
            self.create_channel_switching_buttons()

    def create_channel_switching_buttons(self):
        self.channel_selectors=[QCheckBox(a) for a in self.eeg.info['ch_names']]
        [self.menu_layout.addWidget(a) for a in self.channel_selectors]
        [a.toggled.connect(self.switch_channels) for a in self.channel_selectors]
        
        self.channel_selectors[0].setChecked(True)
        self.channel_selectors[1].setChecked(True)

    def create_eeg_plot(self, channel:int=0):
        ch_name = self.eeg.info['ch_names'][channel]
        p = pg.PlotWidget( background='#000000', title=ch_name)
        p.setAntialiasing(True)
        eeg_plot = EegPlotter(eeg=self.eeg, channel=channel, parent=p)
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
        if direction:
            logging.debug(['key: ', direction])
            list(self.eeg_plots.values())[0]['Curve'].update_plot(caller='keyboard', direction=direction)

    def switch_channels(self):
        ch_name = self.sender().text()
        if self.sender().isChecked():
            if ch_name not in self.eeg_plots.values():
                self.create_eeg_plot(self.eeg.info['ch_names'].index(ch_name))
        else:
            self.eeg_plots[ch_name]['PlotWidget'].setParent(None)
            self.eeg_plots.pop(ch_name)

class EegPlotter(pg.PlotCurveItem):
    def __init__(self, eeg, channel:int=0, parent=None):
        super(EegPlotter,self).__init__()
        self.vb = parent.getViewBox()
        self.vb.disableAutoRange()
        self.range_lines = []
        self.eeg = eeg
        self.channel = channel
        self.last_pos = [None, None]
        self.window_len_sec = 10
        self.scroll_step = 1000 # make adapive?
        self.eeg_start = 5*int(eeg.info['sfreq'])
        self.eeg_stop = self.window_len_sec*int(eeg.info['sfreq'])
        self.max_displayed_len = 1e4
        self.update_plot(eeg_start=self.eeg_start, eeg_stop=self.eeg_stop, init=True)

    def mouseClickEvent(self, ev):
        print ('pltclicked')
        self.manage_region(ev)
    
    def manage_region(self, ev):
        if ev.double():
            if len(self.range_lines) < 2:
                self.range_lines.append(pg.InfiniteLine(int(ev.pos().x())))
                print(self.range_lines[0])
                self.vb.addItem(self.range_lines[-1])
            
            if len(self.range_lines) == 2:
                region = pg.LinearRegionItem(values = [self.range_lines[0].getXPos(),
                                                    self.range_lines[1].getXPos()])
                self.vb.addItem(region, ignoreBounds=True)
                
                self.vb.removeItem(self.range_lines[0])
                self.vb.removeItem(self.range_lines[1])
                self.range_lines = []

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
    eeg = None

    filename = pathlib.Path(open('.test_file_path', 'r').read())
    eeg = {'data':eeg_processing.open_eeg_file(filename),
            'filename':str(filename)}
    eeg['data'] = eeg_processing.filter_eeg(eeg['data'])

    ep = MainWindow()
    ep.show()
    sys.exit(app.exec_())