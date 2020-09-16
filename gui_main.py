from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg
import numpy as np
from scipy import signal

import pathlib
import sys
import csv
import pickle
import uuid

import eeg_processing

import logging

settings = QSettings('MSU', 'swd_analysis')
pg.setConfigOptions(enableExperimental=False)
settings.setValue('WINDOW_COLOR', '#FFFFFF')
# settings.clear()

def open_file_dialog(ftype='raw'):
    if ftype == 'raw':
        window_name ='Select *DF file'
        ftype_filter = 'EEG (*.edf, *.bdf) ;; All files(*)'
    elif ftype == 'pickle':
        window_name ='Select .pickle file'
        ftype_filter = 'preprocessed EEG (*.pickle) ;; All files(*)'
    
    filename, _ = QFileDialog.getOpenFileName(None, window_name, str(settings.value('LAST_FILE_LOCATION')), ftype_filter)
    if filename:
        filename = pathlib.Path(filename)
        settings.setValue('LAST_FILE_LOCATION', filename.parent)
    return filename

def open_eeg_file(filename):
    if filename.suffix == '.pickle':
        with open(filename, 'rb') as f:
            intermediate = pickle.load(f)
            eeg = {'data':eeg_processing.open_eeg_file(pathlib.Path(intermediate['filename'])),
                'filename':str(filename)}
            eeg['data'].annotation_dict = intermediate['annotation_dict']

    elif filename.suffix == '.bdf' or filename.suffix == '.edf':
        eeg = {'data':eeg_processing.open_eeg_file(filename),
                'filename':str(filename)}
    return eeg

class EEGRegionItem(pg.LinearRegionItem):
    def __init__(self, parent, **kwargs):
        super(EEGRegionItem, self).__init__(**kwargs)
        self.parent = parent
    
    def mouseClickEvent(self, ev):
        if ev.button() == Qt.RightButton:
            self.parent.remove_annotation(self)

class ExportSwdDialog(QDialog):
    def __init__(self, parent):
        super(ExportSwdDialog, self).__init__()
        self.setWindowTitle("Select channels to export")
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        labels = {a:f"{a} ({len(parent.eeg['data'].annotation_dict[a])} SWDs)" for a in parent.eeg['data'].info['ch_names']}
        self.channel_selectors={a:QCheckBox(labels[a]) for a in labels}
        [self.layout.addWidget(self.channel_selectors[a]) for a in self.channel_selectors]

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.buttonBox.accepted.connect(self.export)
        self.buttonBox.rejected.connect(self.cancel)
        
        self.layout.addWidget(self.buttonBox)
        
        self.ch_list = []

    def export(self):
        self.ch_list = ([a for a in self.channel_selectors if self.channel_selectors[a].isChecked()])
        self.accept()

    def cancel(self):
        self.ch_list = None
        self.reject()
 

class MainWindow(pg.GraphicsWindow):
    def __init__(self, eeg=None):
        super(MainWindow, self).__init__()
        self.eeg = eeg
        self.setBackground(settings.value('WINDOW_COLOR'))
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.create_menu()
        self.load_eeg(self.eeg)

    def load_eeg(self, eeg:dict, filter_data:bool=False):
        if not eeg:
            return
        self.eeg = eeg
        if hasattr(self, 'eeg_plots'):
            self.eeg_plots.setParent(None)
            self.eeg_plots.destroy()
        
        if filter_data:
            eeg['data'] = eeg_processing.filter_eeg(eeg['data'])
    
        self.eeg_plots = MainWidget(eeg = eeg['data'], parent = self)
        self.setWindowTitle(eeg['filename'])
        self.layout.addWidget(self.eeg_plots)

    def save_processed_eeg(self):
        payload = {'filename':self.eeg['filename'],
                'annotation_dict':self.eeg['data'].annotation_dict}
        with open (self.eeg['filename'] + '.pickle', 'wb') as f:
            pickle.dump(payload, f)

    def create_menu(self):
        menubar = QMenuBar(self)

        actionFile = menubar.addMenu("File")

        OpenRawAction = QAction("&Open raw file", self)
        OpenRawAction.setShortcut("Ctrl+O")
        OpenRawAction.triggered.connect(lambda x: self.open_file(ftype='raw'))
        actionFile.addAction(OpenRawAction)

        OpenAnnAction = QAction("Open &annotated file", self)
        OpenAnnAction.triggered.connect(lambda x: self.open_file(ftype='pickle'))
        actionFile.addAction(OpenAnnAction)

        SaveAction = QAction("&Save intermediate file", self)
        SaveAction.setShortcut("Ctrl+S")
        SaveAction.triggered.connect(self.save_processed_eeg)
        actionFile.addAction(SaveAction)

        actionAnalysis = menubar.addMenu("Analysis")
        
        DetectSwdAction = QAction("&Filter", self)
        DetectSwdAction.triggered.connect(self.filter_and_reload)
        actionAnalysis.addAction(DetectSwdAction)

        DetectSwdAction = QAction("&Detect SWD", self)
        DetectSwdAction.triggered.connect(self.detect_swd)
        actionAnalysis.addAction(DetectSwdAction)
        
        ExportSwdAction = QAction("&Export SWD", self)
        ExportSwdAction.triggered.connect(self.export_SWD)
        actionAnalysis.addAction(ExportSwdAction)
        
        self.layout.addWidget(menubar)
    
    def filter_and_reload(self):
        if not self.eeg:
            QMessageBox.about(self, "Filter", "First load some EEG!")

            return
        self.eeg_plots.setParent(None)
        self.eeg_plots.destroy()
        self.load_eeg(self.eeg, filter_data=True)

    def detect_swd(self):
        pass
    
    def export_SWD(self):
        if not self.eeg:
            QMessageBox.about(self, "Export SWD", "First load some EEG with annotated SWD!")
            return
        self.channel_selector = ExportSwdDialog(self)
        self.channel_selector.setModal(True)
        self.channel_selector.exec_()
        from matplotlib import pyplot as plt
        if self.channel_selector.ch_list:
            for ch_name in self.channel_selector.ch_list:
                with open(self.eeg['filename'] + ch_name + '.csv', 'w') as f:
                    for annotation in self.eeg_plots.eeg.annotation_dict[ch_name].values():
                        channel = self.eeg_plots.eeg.info['ch_names'].index(ch_name)
                        fragment = self.eeg_plots.eeg[channel][0][0][int(annotation['onset']):int(annotation['onset']+ annotation['duration'])]
                        f.write(';'.join([str(a).replace('.',',') for a in fragment]) + '\n') # Excel dialect is not locale-aware :-(
        
    def open_file(self, ftype='raw'):
        filename = open_file_dialog(ftype)

        if not filename:
            return
        else:
            self.eeg = open_eeg_file(filename)
        self.load_eeg(self.eeg)

class MainWidget(pg.GraphicsLayoutWidget):
    def __init__(self, eeg, parent=None):
        super(MainWidget, self).__init__(parent)
        self.setBackground(settings.value('WINDOW_COLOR'))
        self.eeg = eeg

        if not hasattr(self.eeg, 'annotation_dict'):
            self.eeg.annotation_dict = {a:{} for a in self.eeg.info['ch_names']}

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
        
        self.channel_selectors[0].setChecked(True) # Development
        self.channel_selectors[1].setChecked(True)

    def create_eeg_plot(self, channel:int=0):
        ch_name = self.eeg.info['ch_names'][channel]
        p = pg.PlotWidget( background='#000000', title=ch_name)
        p.setAntialiasing(True)
        eeg_plot = EegPlotter(eeg=self.eeg, channel=channel, parent=p)
        p.addItem(eeg_plot, name = ch_name, title=ch_name)
        self.eeg_layout.addWidget(p)
        self.eeg_plots[ch_name] = {'PlotWidget':p, 'Curve':eeg_plot}
        self.link_plots()
        return eeg_plot
    
    def link_plots(self):
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
        self.parent = parent
        self.vb = self.parent.getViewBox()
        self.vb.disableAutoRange()
        self.range_lines = []

        self.eeg = eeg
        self.nsamp = self.eeg['data'][1].shape[0]
        self.channel = channel
        self.ch_name = self.eeg.info['ch_names'][self.channel]

        self.last_pos = [None, None]
        self.window_len_sec = 10
        self.scroll_step = 1000 # make adapive?
        self.eeg_start = 5*int(eeg.info['sfreq'])
        self.eeg_stop = self.window_len_sec*int(eeg.info['sfreq'])
        self.max_displayed_len = 1e4
        self.update_plot(eeg_start=self.eeg_start, eeg_stop=self.eeg_stop, init=True)

    def mouseClickEvent(self, ev):
        self.manage_region(ev)
    
    def manage_region(self, ev):
        if ev.double():
            if len(self.range_lines) < 2:
                self.range_lines.append(pg.InfiniteLine(int(ev.pos().x())))
                self.vb.addItem(self.range_lines[-1])
            
            if len(self.range_lines) == 2:
                self.create_region()
                #update annotations 
   
    def add_region(self, values, uuid):
        region = EEGRegionItem(values=values, parent=self)
        region.sigRegionChangeFinished.connect(lambda: self.update_annotation(region))
        region.uuid = uuid
        self.vb.addItem(region, ignoreBounds=True)
        return region

    def draw_region(self):
        region = self.add_region(values = [self.range_lines[0].getXPos(),
            self.range_lines[1].getXPos()],
            uuid = str(uuid.uuid4()))

        self.vb.removeItem(self.range_lines[0])
        self.vb.removeItem(self.range_lines[1])
        self.range_lines = []
        return region

    def create_region(self):
        region = self.draw_region()
        self.update_annotation(region)

    def update_annotation(self, region):
        self.eeg.annotation_dict[self.ch_name][region.uuid] = dict(onset = region.getRegion()[0],
                duration = (region.getRegion()[1] - region.getRegion()[0]),
                orig_time = self.eeg.annotations.orig_time)
    
    def remove_annotation(self,item):
        self.eeg.annotation_dict[self.ch_name].pop(item.uuid, None)
        self.vb.removeItem(item)

    def update_plot(self, eeg_start=None, eeg_stop=None, caller:str=None, direction=None, init:bool=None):
        if init:
            y = self.eeg._data[self.channel, self.eeg_start: self.eeg_stop]
            self.vb.setRange(xRange=(self.eeg_start, self.eeg_stop), yRange=(np.min(y), np.max(y)), padding=0, update=False)
            for annotation in self.eeg.annotation_dict[self.ch_name].items():
                self.add_region(values=[annotation[1]['onset'], annotation[1]['onset'] + annotation[1]['duration']], uuid=annotation[0])

        x_range = [int(a) for a in self.vb.viewRange()[0]]
        if caller == 'keyboard':
            self.scroll_step = (x_range[1]-x_range[0])//4
            if direction == 'left':
                self.eeg_stop -= min(self.scroll_step, self.eeg_start)
                self.eeg_start = max(self.eeg_start-self.scroll_step, 0)
            elif direction == 'right':
                self.eeg_start += min(self.scroll_step, abs(self.eeg_stop-self.nsamp))
                self.eeg_stop = min(self.eeg_stop+self.scroll_step, self.nsamp)
            elif direction == None:
                return
        else: # mouse
            logging.debug (['x_range', x_range])

            self.eeg_stop = min(self.nsamp, x_range[1])
            # if x_range[0] >= 0:
            self.eeg_start = max(x_range[0], 0)
        
        if [self.eeg_start, self.eeg_stop] == self.last_pos: # avoid unnecessary refreshes
            # self.vb.disableAutoRange()
            return
        x = np.arange(self.eeg_start, self.eeg_stop)
        y = self.eeg._data[self.channel, self.eeg_start: self.eeg_stop]
        
        if len(x) > self.max_displayed_len:
            ds_div = int(4*len(x)//self.max_displayed_len)
            '''
                Downsampling from PyQtGraph 'peak' method. To do it here is somehow
                faster then in setData. This produces most acurate graphs when zoomed out.
            '''
            n = len(x) // ds_div
            x1 = np.empty((n,2))
            x1[:] = x[:n*ds_div:ds_div,np.newaxis]
            x = x1.reshape(n*2)
            y1 = np.empty((n,2))
            y2 = y[:n*ds_div].reshape((n, ds_div))
            y1[:,0] = y2.max(axis=1)
            y1[:,1] = y2.min(axis=1)
            y = y1.reshape(n*2)
        else:
            ds_div = 1
        
        self.setData(x=x, y=y, pen=pg.mkPen(color=pg.intColor(0), width=1), antialias=False)#, downsample=True, downsampleMethod='peak')
        self.vb.setRange(xRange=(self.eeg_start, self.eeg_stop), padding=0, update=False)
        self.last_pos = [self.eeg_start, self.eeg_stop]
        logging.debug (f"drawing len {len(y)} downsample {ds_div} start {self.eeg_start} stop {self.eeg_stop} range {x_range} range_samples {abs(x_range[1] - x_range[0])} eeg len {self.nsamp} last {self.last_pos}")

        if len(x) > 0:
            ax = self.parent.getPlotItem().getScale('bottom')
            tv = ax.tickValues(x[0], x[-1], len(x))
            tv = [[[v, '{:.1f}'.format(v*int(self.eeg.info['sfreq'])/1000)] for v in tick_level[1]] for tick_level in tv]
            ax.setTicks(tv)
        
        if self.eeg_stop:
            if (self.parent.parent()):
                mw = self.parent.parent().parent()
                percentage = self.eeg_stop/self.nsamp*100
                mw.setWindowTitle("{} {:.1f}%".format(mw.eeg['filename'], percentage))

    def viewRangeChanged(self, *, caller:str=None):
        self.update_plot(caller=caller)
        self.vb.setRange(xRange=(self.eeg_start, self.eeg_stop), padding=0, update=False)

if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s	%(processName)s	%(message)s', level=logging.ERROR)
    logging.getLogger()

    app = QApplication(sys.argv)
    eeg = None

    filename = pathlib.Path(open('.test_file_path', 'r').read())
    eeg = open_eeg_file(filename)

    ep = MainWindow(eeg=eeg)
    
    ep.show()
    sys.exit(app.exec_())