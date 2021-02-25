from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg

import matplotlib
matplotlib.use('Qt5Agg')

import numpy as np
from scipy import signal

import pathlib
import sys
import csv
import pickle
import uuid
import json

import func
from eeg_widgets import *
import config

import logging

pg.setConfigOptions(enableExperimental=config.enablePyQTGraphExperimental)

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

class SWDWindow(QMainWindow):
    def __init__(self, parent, filenames:list=None):
        super(SWDWindow, self).__init__()
        self.setWindowTitle("Spectral analysis")
        self.setWindowModality(Qt.ApplicationModal)
        if not filenames:
            self.filenames = func.open_file_dialog(ftype='csv', multiple_files=True)
        else:
            self.filenames = filenames
        if not self.filenames:
            self.close()

        self.swd_selectors = {}
        self.swd_data = {}
        self.swd_state = {}
        self.swd_plots = {}
        self.spectrum_plots = {}
        self.swd_names = {}
        self.stats = {}

        self.block_reanalysis = False
        self.quantiles = True

    def runnnn(self):
        self.create_gui()
        self.load_files()
        self.create_analysis()

    def load_files(self):
        for swd_filepath_key in self.filenames:
            self.swd_names[swd_filepath_key] = swd_filepath_key.name
            self.swd_plots[swd_filepath_key] = {}
            self.spectrum_plots[swd_filepath_key] = {}
            self.swd_data[swd_filepath_key] = self.load_swd_from_csv(swd_filepath_key)
            self.swd_state[swd_filepath_key] = [True for a in range(len(self.swd_data[swd_filepath_key]['data']))]
    
    def create_gui(self):
        self.create_menu()
        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)
        self.tabs = TabWidget()
        self.tabs.setMinimumSize(600, 200)
        self.tabs.resize(600, 200)
        self.tabs.tbar._editor.editingFinished.connect(lambda: (self.rename_dataset(), self.stats_mw(), self.plot_average_spectrum()))
        self.splitter.addWidget(self.tabs)
        self.tabs_list = []
        self.add_plot()

    
    def create_analysis(self):
        self.run_analysis()
        self.plot_swd_and_spectrums()
        self.stats_mw()
        self.plot_average_spectrum()
    
    def create_menu(self):
        menubar = self.menuBar()
        menu = menubar.addMenu('File')
        export_action = menu.addAction("Export spectral data")
        export_action.triggered.connect(self.export_spectrum)

        export_action = menu.addAction("Export average spectral data")
        export_action.triggered.connect(self.export_average_spectrum)

        quantile_action = QAction('Plot quantiles', menu, checkable=True, checked=True)
        quantile_action.triggered.connect(self.plot_quantiles)
        menu.addAction(quantile_action)

    def plot_quantiles(self):
        self.quantiles=self.sender().isChecked()
        self.plot_average_spectrum()

    def export_spectrum(self):
        '''
        export all valid spectrums
        '''
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
                        func.write_csv_line(file_object=f, line=line) # Excel dialect is not locale-aware :-(

    def export_average_spectrum(self):
        filepath = QFileDialog.getSaveFileName(self, "Save average spectrum", filter="Comma-separated values (*.csv)")
        if not filepath[0]:
            return
        else:
            filepath = pathlib.Path(filepath[0])
        if hasattr (self, 'welch'):
            spectrum_subset = {}
            average_spectrum = {}
            recepit = {}
            for swd_filepath_key in self.swd_state.keys():
                sample_name = self.swd_names[swd_filepath_key]
                mask = [True if self.swd_state[swd_filepath_key][a] else False for a in self.welch['spectrum_id'][swd_filepath_key] ]
                spectrum_subset[sample_name] = self.welch['spectrums'][swd_filepath_key][mask]

                recepit[sample_name] = [a if self.swd_state[swd_filepath_key][a] else False for a in self.welch['spectrum_id'][swd_filepath_key]]
                average_spectrum[sample_name] = np.average(spectrum_subset[sample_name], axis=0)

            recepit_path = filepath.parent / (filepath.stem+'_averaging_log.json')
            
            with open(recepit_path, 'w') as json_file:
                json.dump(recepit, json_file, indent=4)
            with open(filepath, 'w') as f:
                func.write_csv_line(file_object=f, line=[self.swd_data[swd_filepath_key]['sfreq']]) #only last
                func.write_csv_line(file_object=f, line=[''] + list(self.welch['x']))
                for line in average_spectrum.items():
                    func.write_csv_line(file_object=f, line=[line[0]] + list(line[1]))

    def rename_dataset(self):
        old_text, new_text = self.tabs.tbar.old_text, self.tabs.tbar.new_text
        swd_filepath_key = [key for key, value in self.swd_names.items() if value == old_text][0]
        self.swd_names[swd_filepath_key] = new_text

    def load_swd_from_csv(self, fn):
        with open(fn, 'r') as f:
            reader = csv.reader(f, delimiter=';')
            rows = [r for r in reader]
            sfreq = int(float(rows[0][0]))
            swd_array = []
            for row in rows[1:]:
                swd = [float(a.replace(',', '.')) for a in row]
                swd_array.append(swd)
        self.add_swd_tab(swd_array, sfreq, fn) #get this out of function
        return {'sfreq':sfreq, 'data':swd_array}

    def tab_menu(self, fn, event):
        menu = QMenu()
        toggleAct = menu.addAction("Toggle")
        action = menu.exec_(self.mapToGlobal(event))
        if action == toggleAct:
            self.block_reanalysis = True
            [cb.setChecked(not cb.isChecked()) for cb in self.swd_selectors[fn]]
            self.block_reanalysis = False

            self.stats_mw()
            self.plot_average_spectrum()
            self.plot_swd_and_spectrums()
            
    def add_swd_tab(self, swd_array, sfreq, fn):
        tab = MyScrollArea()
        tab.setContextMenuPolicy(Qt.CustomContextMenu)
        tab.customContextMenuRequested.connect(lambda x: self.tab_menu(fn, x))

        self.tabs_list.append(tab)
        self.tabs.addTab(tab, f"{self.swd_names[fn]}")
        
        content_widget = QWidget()
        layout = QGridLayout(content_widget)

        self.swd_selectors[fn]=[QCheckBox(str(a)) for a in range(len(swd_array))]
        [layout.addWidget(a) for a in self.swd_selectors[fn]]
        [sc.setChecked(True) for sc in self.swd_selectors[fn]]
        [a.toggled.connect(lambda:self.toggleAct(fn)) for a in self.swd_selectors[fn]]

        tab.setWidgetResizable(True)
        
        for swd_id, swd in enumerate(swd_array):
            pdi = pg.GraphicsLayoutWidget()
            layout.addWidget(pdi, swd_id, 1)
            p = pdi.addPlot(row=0, col=0)
            self.swd_plots[fn][swd_id] = p
            
            p2 = pdi.addPlot(row=0, col=1)
            self.spectrum_plots[fn][swd_id] = p2

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

    def toggleAct(self, swd_filepath_key):
        self.toggle_single_swd(swd_filepath_key)
        self.draw_swd_plot(swd_filepath_key, int(self.sender().text()))
        if not self.block_reanalysis:
            self.stats_mw()
            self.plot_average_spectrum()

    def run_analysis(self): #runs once
        if self.block_reanalysis:
            return
        else:
            self.welch = func.welch_spectrum(self.swd_data, self.swd_state, normalize=False)
            self.block_reanalysis = True
            for swd_filepath_key in self.swd_state:
                for swd_id in self.welch['rejected_swd'][swd_filepath_key]:
                    self.swd_state[swd_filepath_key][swd_id] = False
                    self.swd_selectors[swd_filepath_key][swd_id].setChecked(False)
            self.block_reanalysis = False
    
    def stats_mw(self):
        significant_freqs, mw = func.statistics_nonparametric(self.welch, self.swd_state, correction=True)
        self.stats['significance'] = significant_freqs
        self.stats['mw'] = mw
    
    def plot_average_spectrum(self):
        func.plot_conditions(self.welch, self.swd_names, self.swd_state, self.sc, self.quantiles)
        console_text = 'Running analysis with:\n' + \
            ''.join([f'{sum(self.swd_state[swd_filepath_key])} valid spectrums in {self.swd_names[swd_filepath_key]} \n' for swd_filepath_key in self.swd_state.keys()]) + '\n' + \
            'Frequency\tTest statistic\tp\n'
        for freq in self.stats['significance']:
            T = self.stats['mw'][freq][0]
            p = self.stats['mw'][freq][1]

            console_text += f'{self.welch["x"][freq]:.2g}\t{T:.2g}\t{p:.2g}\n'
        self.console.setText(console_text)

    def plot_swd_and_spectrums(self):
        for swd_filepath_key in self.welch['spectrums'].keys():
            [i.clear() for i in self.spectrum_plots[swd_filepath_key].values()]
            for swd_id in self.swd_plots[swd_filepath_key].keys():
                self.draw_swd_plot(swd_filepath_key, swd_id)
                self.draw_spectrum_plot(swd_filepath_key, swd_id)
    
    def draw_spectrum_plot(self, swd_filepath_key, swd_id):
        if self.spectrum_plots[swd_filepath_key]:
            try:
                spectrum_id = self.welch['spectrum_id'][swd_filepath_key].index(swd_id)
                p2 = self.spectrum_plots[swd_filepath_key][swd_id]
                spectrum = self.welch['spectrums'][swd_filepath_key][spectrum_id]
                p2.plot(self.welch['x'], spectrum, pen=pg.mkPen(color='w'))
            except ValueError:
                pass

    def draw_swd_plot(self, swd_filepath_key, swd_id):
        plot = self.swd_plots[swd_filepath_key][swd_id]
        swd = self.swd_data[swd_filepath_key]['data'][swd_id]
        sfreq = self.swd_data[swd_filepath_key]['sfreq']
        try:
            spectrum_id = self.welch['spectrum_id'][swd_filepath_key].index(swd_id)
            if self.swd_state[swd_filepath_key][swd_id]:
                color = 'r'
            else:
                color = 'w'
        except ValueError:
            color = 'w'
        plot.plot(np.arange(len(swd))/sfreq, swd, pen=pg.mkPen(color=color))

    def toggle_single_swd(self, swd_filepath_key:str, swd_id:int=None):
        if swd_id is None:
            swd_id = int(self.sender().text())
        self.swd_state[swd_filepath_key][swd_id] = self.sender().isChecked()
        if swd_id not in self.welch['spectrum_id'][swd_filepath_key]:
            self.sender().setChecked(False)
    
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Control and not event.isAutoRepeat():
            [a.SetScrollable(False) for a in self.tabs_list]
    
    def keyReleaseEvent(self, event):
        key = event.key()
        if key == Qt.Key_Control and not event.isAutoRepeat():
            [a.SetScrollable(True) for a in self.tabs_list]

class SpectralWindow(SWDWindow):
    def __init__(self, parent, filenames:list=None):
        super(SpectralWindow, self).__init__(parent)
        self.setWindowTitle("Averaged spectral analysis")
        self.welch = {}
        self.welch['spectrums'] = {}
        self.welch['spectrum_id'] = {}
        self.welch['rejected_swd'] = {}
    
    def create_analysis(self):
        self.plot_spectrums()
        self.stats_mw()
        self.plot_average_spectrum()
    
    def plot_spectrums(self):
        for swd_filepath_key in self.welch['spectrums'].keys():
            [i.clear() for i in self.spectrum_plots[swd_filepath_key].values()]
            for swd_id in self.swd_plots[swd_filepath_key].keys():
                self.draw_swd_plot(swd_filepath_key, swd_id)

    def add_swd_tab(self, swd_array, sfreq, fn):
        tab = MyScrollArea()
        tab.setContextMenuPolicy(Qt.CustomContextMenu)
        tab.customContextMenuRequested.connect(lambda x: self.tab_menu(fn, x))

        self.tabs_list.append(tab)
        self.tabs.addTab(tab, f"{self.swd_names[fn]}")
        
        content_widget = QWidget()
        layout = QGridLayout(content_widget)

        self.swd_selectors[fn]=[QCheckBox(str(a)) for a in range(len(swd_array))]
        [layout.addWidget(a) for a in self.swd_selectors[fn]]
        [sc.setChecked(True) for sc in self.swd_selectors[fn]]
        [a.toggled.connect(lambda:self.toggleAct(fn)) for a in self.swd_selectors[fn]]

        tab.setWidgetResizable(True)
        
        for swd_id, swd in enumerate(swd_array):
            pdi = pg.GraphicsLayoutWidget()
            layout.addWidget(pdi, swd_id, 1)
            p = pdi.addPlot(row=0, col=0)
            self.swd_plots[fn][swd_id] = p
        tab.setWidget(content_widget)

    def load_swd_from_csv(self, fn):
        with open(fn, 'r') as f:
            reader = csv.reader(f, delimiter=';')
            rows = [r for r in reader]
            sfreq = int(float(rows[0][0]))
            self.welch['x'] = [float(a.replace(',', '.')) for a in rows[1][1:]]
            spectrum_array = []
            for row in rows[2:]:
                names = row[0]
                spectrum = [float(a.replace(',', '.')) for a in row[1:]]
                spectrum_array.append(spectrum)
            self.welch['spectrums'][fn] = np.array(spectrum_array)
            self.welch['spectrum_id'][fn] = list(range(len(spectrum_array)))
            self.welch['rejected_swd'][fn] = []

        self.add_swd_tab(spectrum_array, sfreq, fn) #get this out of function
        return {'sfreq':sfreq, 'data':spectrum_array}

class MainWindow(pg.GraphicsWindow):
    def __init__(self, eeg=None):
        super(MainWindow, self).__init__()
        self.eeg = eeg
        self.setBackground(config.settings.value('WINDOW_COLOR'))
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
            eeg['data'] = func.filter_eeg(eeg['data'])
    
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
        
        menu7 = QAction("&Average spectrums", self)
        menu7.triggered.connect(self.compare_avg_spectrum)
        actionAnalysis.addAction(menu7)
        
        menuAbout = menubar.addMenu("About")
        text = f'Spectrum analyzer: version {config.__version__}\n' + \
            'https://github.com/eegdude/swd_analysis/\n' + config.acknow
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
        self.spectral_analysis.runnnn()
        self.spectral_analysis.show()
    
    def compare_avg_spectrum(self):
        self.spectral_analysis = SpectralWindow(self)
        self.spectral_analysis.runnnn()
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
                        func.write_csv_line(file_object=f, line=fragment) # Excel dialect is not locale-aware :-(
            print ('done exports')
    
    def open_file(self, ftype='raw'):
        filename = func.open_file_dialog(ftype)
        eeg = func.open_data_file(filename)
        if eeg:
            self.eeg = eeg
            self.load_eeg(self.eeg)

class MainWidget(pg.GraphicsLayoutWidget):
    def __init__(self, eeg, parent=None):
        super(MainWidget, self).__init__(parent)
        self.setBackground(config.settings.value('WINDOW_COLOR'))
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
    logging.basicConfig(format='%(levelname)s	%(processName)s	%(message)s', level=logging.INFO, filename='log.log')
    logging.getLogger()

    app = QApplication(sys.argv)
    eeg = None

    # filename = pathlib.Path(open('.test_file_path', 'r').read())
    # eeg = func.open_data_file(filename)
    ep = MainWindow(eeg=eeg)

    # fn = pathlib.Path(r"C:\Users\User\Desktop\sdrnk\Эксперимент\Exp_WG_1_male_WG_2_male_22-07-2020_10-32.bdf.pickleWG_1_male_Cor-0 (1).csv")
    # fn1 = pathlib.Path(r"C:\Users\User\Desktop\sdrnk\Эксперимент\Exp_WG_1_male_WG_2_male_22-07-2020_10-32.bdf.pickleWG_1_male_Cor-0 (2).csv")
    # ep = SpectralWindow(None, filenames = [fn, fn1])
    # ep.runnnn()
    # ep.show()

    sys.exit(app.exec_())