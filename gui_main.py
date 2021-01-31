from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

import numpy as np
from scipy import signal

import pathlib
import sys
import csv
import pickle
import uuid
import yaml

import eeg_processing

import logging
__version__ = 0.1
acknow = 'Icons made by https://www.flaticon.com/authors/eucalyp'
settings = QSettings('MSU', 'swd_analysis')
pg.setConfigOptions(enableExperimental=False)
settings.setValue('WINDOW_COLOR', '#FFFFFF')
# settings.clear()

def open_file_dialog(ftype:str='raw', multiple_files:bool=False):
    if ftype == 'raw':
        window_name ='Select *DF file'
        ftype_filter = 'EEG (*.edf, *.bdf) ;; All files(*)'
    elif ftype == 'pickle':
        window_name ='Select .pickle file'
        ftype_filter = 'preprocessed EEG (*.pickle) ;; All files(*)'
    elif ftype == 'csv':
        window_name ='Select .csv file'
        ftype_filter = 'exported SWD (*.csv) ;; All files(*)'
    
    if multiple_files:
        filenames, _ = QFileDialog.getOpenFileNames(None, window_name, str(settings.value('LAST_FILE_LOCATION')), ftype_filter)
    else:
        filename, _ = QFileDialog.getOpenFileName(None, window_name, str(settings.value('LAST_FILE_LOCATION')), ftype_filter)
        filenames = [filename]
    
    if filenames:
        filenames = [pathlib.Path(f) for f in filenames]
        settings.setValue('LAST_FILE_LOCATION', filenames[0].parent)
    if pathlib.WindowsPath('.') in filenames:                                   # фигня с точкой происходит из-за пустого пути
        return []
    if multiple_files:
        return filenames
    else:
        return filenames[0]

def check_filename(filename):
    if filename:
        if filename.exists():
            return True
        else:
            return
    else:
        return

def open_data_file(filename):
    if not check_filename(filename):
        return None

    if filename.suffix == '.pickle':
        with open(filename, 'rb') as f:
            intermediate = pickle.load(f)
            eeg_file_path = pathlib.Path(intermediate['filename'])
            if not check_filename(eeg_file_path):
                buttonReply = QMessageBox.question(None, "No valid EEG for this annotation", f"No file at {eeg_file_path}\nSelect another xdf file?")
                if buttonReply == QMessageBox.Yes:
                    data = open_data_file(open_file_dialog('raw'))
                    if data:
                        data = data['data']
                    else:
                        return None
                else:
                    return None
            else:
                data = eeg_processing.read_xdf_file(eeg_file_path)

            eeg = {'data':data,
                'filename':str(filename)}
            eeg['data'].annotation_dict = intermediate['annotation_dict']

    elif filename.suffix == '.bdf' or filename.suffix == '.edf':
        eeg = {'data':eeg_processing.read_xdf_file(filename),
                'filename':str(filename)}
    else:
        QMessageBox.about(None, "No valid EEG", f"No vaild EEG file at {filename}\nYou can load .pickle or .xdf file")
        return None
    return eeg

def write_csv_line(file_object, line):
    file_object.write(';'.join([str(a).replace('.',',') for a in line]) + '\n')

class EEGRegionItem(pg.LinearRegionItem):
    def __init__(self, parent, **kwargs):
        super(EEGRegionItem, self).__init__(**kwargs)
        self.parent = parent
    
    def mouseClickEvent(self, ev):
        if ev.button() == Qt.RightButton:
            self.parent.remove_annotation(self)

class MyScrollArea(QScrollArea):
    def __init__(self, *args, **kwargs):
        super(MyScrollArea, self).__init__(*args, **kwargs)
        self.scrollable = True
    
    def wheelEvent (self, *args, **kwargs):
        if self.scrollable:
            QScrollArea.wheelEvent(self, *args, **kwargs)
    
    def SetScrollable(self, scrollable:bool):
        self.scrollable = scrollable

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

class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=400):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)

class TabBar(QTabBar):
    def __init__(self, parent=None):
        super(QTabBar, self).__init__(parent)
        self._editor = QLineEdit(self)
        self._editor.setWindowFlags(Qt.Popup)
        self._editor.setFocusProxy(self)
        self._editor.editingFinished.connect(self.handleEditingFinished)
        # self.tabNameChanged = pyqtSignal()
    
    def mouseDoubleClickEvent(self, event):
        index = self.tabAt(event.pos())
        if index >= 0:
            self.editTab(index)

    def editTab(self, index):
        rect = self.tabRect(index)
        self._editor.setFixedSize(rect.size())
        self._editor.move(self.parent().mapToGlobal(rect.topLeft()))
        self._editor.setText(self.tabText(index))
        if not self._editor.isVisible():
            self._editor.show()

    def handleEditingFinished(self):
        index = self.currentIndex()
        if index >= 0:
            self._editor.hide()
            self.new_text = self._editor.text()
            self.old_text = self.tabText(index)
            if self.old_text != self.new_text:
                self.setTabText(index, self.new_text)

class TabWidget(QTabWidget):
    def __init__(self, parent=None):
        super(TabWidget, self).__init__(parent)
        self.tbar = TabBar(self)
        self.setTabBar(self.tbar)
        # self.setDocumentMode(True)
        # self.setTabsClosable(True)
        
class SWDWindow(QMainWindow):
    def __init__(self, parent, filenames:list=None):
        super(SWDWindow, self).__init__()
        self.setWindowTitle("Spectral analysis")
        self.setWindowModality(Qt.ApplicationModal)
        if not filenames:
            filenames = open_file_dialog(ftype='csv', multiple_files=True)
        if not filenames:
            self.close()

        self.create_menu()

        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)
        self.tabs = TabWidget()
        self.tabs.setMinimumSize(600, 200)
        self.tabs.resize(600, 200)


        self.tabs.tbar._editor.editingFinished.connect(lambda: (self.rename_dataset(), self.run_analysis()))
        self.tabs_list = []
        self.channel_selectors = {}
        self.splitter.addWidget(self.tabs)

        self.swd_data = {}
        self.swd_state = {}
        self.swd_plots = {}
        self.spectrum_plots = {}
        self.swd_names = {}
        self.block_reanalysis = False


        for fn in filenames:
            self.swd_names[fn] = fn.name
            self.swd_plots[fn] = []
            self.spectrum_plots[fn] = []
            self.swd_data[fn] = self.load_swd_from_csv(fn)
            self.swd_state[fn] = [True for a in range(len(self.swd_data[fn]))]
        self.add_plot()
        self.run_analysis()
    
    def create_menu(self):
        menubar = self.menuBar()
        menu = menubar.addMenu('File')
        export_action = menu.addAction("Export spectral data")
        export_action.triggered.connect(self.export_spectrum)
    
    def export_spectrum(self):
        dir = QFileDialog.getExistingDirectory(self, "Select Directory")
        if not dir:
            return
        else:
            dir = pathlib.Path(dir)

        if hasattr (self, 'welch'):
            for key in self.welch['spectrums'].keys():
                data = np.vstack([ self.welch['x'], self.welch['spectrums'][key]])
                with open(dir / f'spectrum_{self.swd_names[key]}.csv', 'w') as f:
                    for line in data.T:
                        write_csv_line(file_object=f, line=line) # Excel dialect is not locale-aware :-(

    def rename_dataset(self):
       old_text, new_text = self.tabs.tbar.old_text, self.tabs.tbar.new_text
       filepath_key = [key for key, value in self.swd_names.items() if value == old_text][0]
       self.swd_names[filepath_key] = new_text
    #    run_analysis()

    def load_swd_from_csv(self, fn):
        with open(fn, 'r') as f:
            reader = csv.reader(f, delimiter=';')
            rows = [r for r in reader]
            sfreq = int(float(rows[0][0]))
            swd_array = []
            for row in rows[1:]:
                swd = [float(a.replace(',', '.')) for a in row]
                swd_array.append(swd)
        self.add_swd_tab(swd_array, sfreq, fn)
        return swd_array

    def tab_menu(self, fn, event):
        menu = QMenu()
        toggleAct = menu.addAction("Toggle")
        action = menu.exec_(self.mapToGlobal(event))
        if action == toggleAct:
            self.block_reanalysis = True
            [cb.setChecked(not cb.isChecked()) for cb in self.channel_selectors[fn]]
            self.block_reanalysis = False
            self.run_analysis()
            
    def add_swd_tab(self, swd_array, sfreq, fn):
        tab = MyScrollArea()
        tab.setContextMenuPolicy(Qt.CustomContextMenu)
        tab.customContextMenuRequested.connect(lambda x: self.tab_menu(fn, x))

        self.tabs_list.append(tab)
        self.tabs.addTab(tab, f"{self.swd_names[fn]}")
        
        content_widget = QWidget()
        layout = QGridLayout(content_widget)

        self.channel_selectors[fn]=[QCheckBox(str(a)) for a in range(len(swd_array))]
        [layout.addWidget(a) for a in self.channel_selectors[fn]]
        [sc.setChecked(True) for sc in self.channel_selectors[fn]]
        [a.toggled.connect(lambda: (self.toggle_single_swd(fn), self.run_analysis())) for a in self.channel_selectors[fn]]

        tab.setWidgetResizable(True)
        
        for n, swd in enumerate(swd_array):
            pdi = pg.GraphicsLayoutWidget()
            layout.addWidget(pdi, n, 1)
            p = pdi.addPlot(row=0, col=0)
            p.plot(np.arange(len(swd))/sfreq, swd, pen=pg.mkPen(color='r'))
            self.swd_plots[fn].append(p)
            
            p2 = pdi.addPlot(row=0, col=1)
            self.spectrum_plots[fn].append(p2)

        tab.setWidget(content_widget)
    
    def add_plot(self):
        plot_widget = QWidget()
        plot_layout = QVBoxLayout()
        self.splitter2 = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.splitter2)
        plot_widget.setLayout(plot_layout)
        self.splitter2.addWidget(plot_widget)

        self.sc = MplCanvas(self, width=5, height=4, dpi=100)
        toolbar = NavigationToolbar2QT(self.sc, self)

        plot_layout.addWidget(toolbar)
        self.splitter2.addWidget(self.sc)
        
        self.console = QTextEdit()
        self.splitter2.addWidget(self.console)

    
    def run_analysis(self):
        if self.block_reanalysis:
            return
        else:
            self.welch = eeg_processing.welch_spectrum(self.swd_data, self.swd_state, normalize=False)
            significant_freqs, mw = eeg_processing.statistics_nonparametric(self.welch, correction=True)
            self.welch['significance'] = significant_freqs
            eeg_processing.plot_conditions(self.welch, self.swd_names, self.sc)

            for key in self.welch['spectrums'].keys():
                spectrum_plots = [a for a, b in zip(self.spectrum_plots[key], self.swd_state[key]) if b]
                for n, a in enumerate(self.welch['spectrums'][key]):
                    spectrum_plots[self.welch['spectrum_id'][key][n]].plot(self.welch['x'], a, pen=pg.mkPen(color='w'))
        
        console_text = 'Running analysis with:\n' + \
            ''.join([f'{sum(self.swd_state[key])} fragments in {self.swd_names[key]} \n' for key in self.swd_state.keys()]) + '\n' + \
            'Frequency\tTest statistic\tp\n'

        for freq in significant_freqs:
            console_text += f'{self.welch["x"][freq]}\t{mw[freq][0]:.2g}\t{mw[freq][1]:.2g}\n'
        self.console.setText(console_text)

    def redraw_plot(self, fn, swd_id, active):
        if active:
            pen = pg.mkPen(color='r')
        else:
            pen = pg.mkPen(color='w')
        self.swd_plots[fn][swd_id].clear()
        self.swd_plots[fn][swd_id].plot(self.swd_data[fn][swd_id], pen=pen)

    def toggle_single_swd(self, fn:str, swd_id:str=None):
        if swd_id is None:
            swd_id = int(self.sender().text())
        self.swd_state[fn][swd_id] = not self.swd_state[fn][swd_id]
        self.redraw_plot(fn, swd_id, self.swd_state[fn][swd_id])
    
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Control and not event.isAutoRepeat():
            [a.SetScrollable(False) for a in self.tabs_list]
    
    def keyReleaseEvent(self, event):
        key = event.key()
        if key == Qt.Key_Control and not event.isAutoRepeat():
            [a.SetScrollable(True) for a in self.tabs_list]

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
        if not self.eeg:
            QMessageBox.about(self, "Export SWD", "First load some EEG with annotated SWD!")
            return
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
        OpenAnnAction.setShortcut("Ctrl+Shift+O")
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
        DetectSwdAction.setDisabled(True)
        
        ExportSwdAction = QAction("&Export SWD", self)
        ExportSwdAction.triggered.connect(self.export_SWD)
        actionAnalysis.addAction(ExportSwdAction)
        
        AnalyseSpectrumAction = QAction("&Spectums", self)
        AnalyseSpectrumAction.triggered.connect(self.analyse_spectrum)
        actionAnalysis.addAction(AnalyseSpectrumAction)
        
        menuAbout = menubar.addMenu("About")
        text = f'Spectrum analyzer: version {__version__}\n' + \
            'https://github.com/eegdude/swd_analysis/\n' + acknow
        actionAbout = QAction("&About", self)
        actionAbout.triggered.connect(lambda:QMessageBox.about(self, "Title", text))
        menuAbout.addAction(actionAbout)
        
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
    
    def analyse_spectrum(self):
        self.spectral_analysis = SWDWindow(self)
        self.spectral_analysis.show()
    
    def export_SWD(self):
        if not self.eeg:
            QMessageBox.about(self, "Export SWD", "First load some EEG with annotated SWD!")
            return
        self.channel_selector = ExportSwdDialog(self)
        self.channel_selector.setModal(True)
        self.channel_selector.exec_()
        if self.channel_selector.ch_list:
            for ch_name in self.channel_selector.ch_list:
                with open(self.eeg['filename'] + ch_name + '.csv', 'w') as f:
                    f.write(f"{self.eeg['data'].info['sfreq']}"+ '\n')
                    for annotation in self.eeg_plots.eeg.annotation_dict[ch_name].values():
                        channel = self.eeg_plots.eeg.info['ch_names'].index(ch_name)
                        fragment = self.eeg_plots.eeg[channel][0][0][int(annotation['onset']):int(annotation['onset']+ annotation['duration'])]
                        write_csv_line(file_object=f, line=fragment) # Excel dialect is not locale-aware :-(
            print ('done exports')
    
    def open_file(self, ftype='raw'):
        filename = open_file_dialog(ftype)
        eeg = open_data_file(filename)
        if eeg:
            self.eeg = eeg
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
        p = pg.PlotWidget(background='#000000', title=ch_name)
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

            a = sum([a[1] for a in tv], []) # smallest level ticks
            a.sort()
            if len(a) > 0:
                delta_ticks_sec = (a[1] - a[0])/int(self.eeg.info['sfreq'])
                if delta_ticks_sec > 60:
                    tick_formatter = (60, 'min')
                elif delta_ticks_sec > 3600:
                    tick_formatter = (3600, 'hour')
                elif delta_ticks_sec < 1:
                    tick_formatter = (0.001,'ms')
                else:
                    tick_formatter = (1,'')

            tv = [[[v, '{:.0f} {}'.format(v/int(self.eeg.info['sfreq'])/tick_formatter[0], tick_formatter[1])] for v in tick_level[1]] for tick_level in tv]
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
    # eeg = open_data_file(filename)
    # ep = MainWindow(eeg=eeg)

    # fn = pathlib.Path(r"C:\Data\kenul\raw\28-01-2020_13-51.bdf.pickleWR_5_male_Lcort.csv")
    fn1 = pathlib.Path(r"C:\Users\User\Desktop\sdrnk\Эксперимент\Exp_WG_1_male_WG_2_male_22-07-2020_10-32.bdf.pickleWG_1_male_Cor-0 (2).csv")

    ep = SWDWindow(None, filenames = [fn1])
    ep.show()

    sys.exit(app.exec_())