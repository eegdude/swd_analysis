from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

import pyqtgraph as pg

import matplotlib
matplotlib.use('Qt5Agg')

import numpy as np

import pathlib
import sys
import collections
import json
import uuid

import func
import swd_io
import containers
from eeg_widgets import *
import config

import logging

from tqdm.auto import tqdm

pg.setConfigOptions(enableExperimental=config.enablePyQTGraphExperimental)

class SWDChannelBox(QWidget):
    """Pop-up allowing for selection of channels containing SWDs to be loaded 
        for further processing

    Args:
        filename (pathlib.Path): window title
        swd_file (dict): nested dictionary containing ['swd_data'] keys for 
            every data channel
    """
    def __init__(self, filename:pathlib.Path, swd_file:dict):
        super(QWidget, self).__init__()
        self.box_name = filename
        layout = QVBoxLayout()
        self.channel_selectors = {}

        self.setLayout(layout)
        self.gb = QGroupBox(str(self.box_name))
        self.gb.setCheckable(True)
        self.gb.setChecked(True)
        vbox = QVBoxLayout()
        self.gb.setLayout(vbox)
        
        for a in swd_file["swd_data"].keys():
            n_swd = len(swd_file['swd_data'][a])
            if n_swd:
                label = f"channel {a}: {n_swd} SWDs"

                if 'swd_state' in swd_file.keys():
                    n_active = sum(swd_file['swd_state'][a].values())
                    label = f"{label}, {n_active} selected"
                if 'welch' in swd_file.keys():
                    n_welch = len(swd_file['welch'][a])
                    label = f"{label}, {n_welch} valid spectrums"
                else:
                    label = f"{label}, no spectrums"

                self.channel_selectors[a] = QCheckBox(label)
        
        [a.setChecked(True) for a in self.channel_selectors.values()]
        [vbox.addWidget(self.channel_selectors[a]) for a in self.channel_selectors]
        layout.addWidget(self.gb)


class IOSwdDialog(QDialog):
    """Dialog to select channels for to export marked SWDs
    """
    def __init__(self, data:list, io_type:str='load'):
        super(IOSwdDialog, self).__init__()
        self.swd_channels = {}
        self.setWindowTitle(f"Select channels to {io_type}")

        scroll = QScrollArea(widgetResizable=True) 
        layout_scroll = QVBoxLayout()
        layout_scroll.addWidget(scroll)
        self.setLayout(layout_scroll)

        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget(scroll)
        layout = QGridLayout(content_widget)
        content_widget.setLayout(layout)
        scroll.setWidget(content_widget) # CRITICAL

        test_pickle = ["swd_data" in list(f.keys()) for f in list(data.values())]
        if sum(test_pickle) < len(test_pickle):
            message = "Incompliant pickle file at\n" + \
                '\n\n'.join([str(filename) for valid, filename in zip(test_pickle, data.keys()) if valid])
            QMessageBox.about(self, "", message)
            return

        self.boxes = [SWDChannelBox(filename, swd_file) for filename, swd_file in data.items()]
        [layout.addWidget(b) for b in self.boxes]
        # [b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed) for b in self.boxes]

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.buttonBox.accepted.connect(self.export)
        self.buttonBox.rejected.connect(self.cancel)
        
        layout.addWidget(self.buttonBox)

        self.resize(600, 800)
        
    def export(self):
        self.swd_channels = {box.box_name:
                [ch_name for ch_name in box.channel_selectors
                    if box.channel_selectors[ch_name].isChecked()]
            for box in self.boxes if box.gb.isChecked()} 
        self.accept()

    def cancel(self):
        self.swd_channels = None
        self.reject()


class SWDWindow(QMainWindow):
    def __init__(self, parent, filenames:list=None):
        super(SWDWindow, self).__init__()
        self.setWindowTitle("Spectral analysis")
        self.setWindowModality(Qt.ApplicationModal)
        self.tabs_container = {}
        self.stats_container = {}

        self.block_reanalysis = False

        self.plot_spread = True
        self.plot_avg = True
        self.plot_significance = True

        self.plot_envelopes = True
        self.plot_peaks = False

        self.n_cols=2
        self.filenames = filenames

        self.run_stat_tests = False


    def spawn_window(self):
        if not self.filenames:
            self.filenames = func.open_file_dialog(ftype='pickle', multiple_files=True)
            if not self.filenames:
                self.close()
                return

        self.create_gui()
        if not self.load_files():
            self.close()
            return

        self.add_swd_tabs()
        if not self.create_analysis():
            self.close()
            return
        self.show()

    def select_swd_channels(self, data):
        channel_selector = IOSwdDialog(data=data, io_type='load')
        channel_selector.setModal(True)
        channel_selector.exec_()
        # channel_selector.buttonBox.accepted.emit()
        return channel_selector.swd_channels

    def load_files(self):
        self.preprocessed_data = swd_io.open_multiple_swd_pickles(self.filenames)
        selected_channels = self.select_swd_channels(self.preprocessed_data)
        if not selected_channels:
            if not self.tabs_container:
                return
            return
        channels_containers = swd_io.create_swd_containers_for_individual_channels(self.preprocessed_data, selected_channels)
        for tab_name, SwdTabData in channels_containers.items():
            self.tabs_container[SwdTabData.uuid] = SwdTabData
            self.tabs_container[SwdTabData.uuid].tab_name = tab_name
        return True

    def add_swd_tabs(self):
        for tab_name, container in tqdm(list(self.tabs_container.items())):
            self.add_swd_tab(container, container.dataset_name) #get this out of function

    def save_containers(self):
        payload = swd_io.containers_to_dict(self.preprocessed_data, self.tabs_container)
        swd_io.update_eeg_processing(payload)

    def create_gui(self):
        self.ep = QShortcut(QKeySequence('Ctrl+='), self)
        self.ep.activated.connect(lambda: self.resize_plots(1.1))
        self.sp = QShortcut(QKeySequence('Ctrl+-'), self)
        self.sp.activated.connect(lambda: self.resize_plots(0.9))

        self.create_menu()
        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)
        self.tabs = TabWidget()
        self.tabs.currentChanged.connect(self.change_tabs)
        self.tabs.setMinimumSize(600, 200)
        self.tabs.resize(600, 200)
        self.splitter.addWidget(self.tabs)
        self.add_mpl_plot()
        self.tabs.tbar._editor.editingFinished.connect(lambda: (self.rename_dataset(), self.nhst_stats(), self.plot_average_spectrum()))
        
        self.pgPen_y = pg.mkPen(color="y", width=1)
        self.pgPen_r = pg.mkPen(color="r", width=1)
        self.pgPen_w = pg.mkPen(color="w", width=1)
        self.pgPen_g = pg.mkPen(color="g", width=1)
        self.pgBrush_b = pg.mkBrush(color='b')

    def change_tabs(self, ):
        if len(self.tabs.uuid_index_dict):
            self.plot_swd_and_spectrums()

    def resize_plots(self, multiptier:float=1):
        for uuid in self.tabs_container:
            for swd_uuid in self.tabs_container[uuid].annotation_dict.keys():
                p = self.tabs_container[uuid].graphics_layouts[swd_uuid]
                newsize = QSize(int(p.size().width()*multiptier), int(p.size().height()*multiptier))
                p.setMinimumSize(newsize)
                p.resize(newsize)

    def create_analysis(self):
        self.process_data()
        self.plot_swd_and_spectrums()
        self.nhst_stats()

        self.plot_average_spectrum()

        return True

    def add_menu_item(self, menu, name='', func=None, shortcut='', checkable=False, checked=False, enabled=True):
        action = QAction(name, menu, checkable=checkable, checked=checked)
        action.setShortcut(shortcut)
        action.triggered.connect(func)
        action.setEnabled(enabled)
        menu.addAction(action)
    
    def create_menu(self):
        menubar = self.menuBar()
        menu = menubar.addMenu('File')
        menu2 = menubar.addMenu('Plotting')
        menu3 = menubar.addMenu('Stats')


        self.add_menu_item(menu, "Update processing files", self.save_containers)

        self.add_menu_item(menu, "Export spectral data", self.export_spectrum, enabled=False)
        self.add_menu_item(menu, "Export average spectral data", self.export_average_spectrum, enabled=False)

        self.add_menu_item(menu, "Export per-swd stats", self.export_stats)
        self.add_menu_item(menu2, "Plot spread", self.plot_spread_func, checkable=True, checked=True)
        self.add_menu_item(menu2, "Plot significance", self.plot_sig_func, checkable=True, checked=True)
        self.add_menu_item(menu2, 'Plot envelopes', self.change_plot_additions_swd, checkable=True, checked=True)
        self.add_menu_item(menu2, 'Plot peaks', self.change_plot_additions_swd, checkable=True, checked=False)
        
        self.add_menu_item(menu3, 'Run tests', self.run_stat_tests_switch, checkable=True, checked=self.run_stat_tests)
        self.add_menu_item(menu3, 'Non-parametric stats', self.stats_type_switch, checkable=True, checked=False)
        
    def run_stat_tests_switch(self):
        self.run_stat_tests = self.sender().isChecked()
        self.nhst_stats()
        self.plot_average_spectrum()

    def stats_type_switch(self):
        print(self.sender().isChecked())
        pass

    def plot_spread_func(self):
        self.plot_spread = self.sender().isChecked()
        self.plot_average_spectrum()

    def plot_sig_func(self):
        self.plot_significance = self.sender().isChecked()
        self.plot_average_spectrum()
    
    def plot_med_func(self):
        self.plot_avg = self.sender().isChecked()
        self.plot_average_spectrum()

    def change_plot_additions_swd(self, peaks=None, envelopes=None):
        """additional features applied to each SWD plot

        Args:
            peaks (bool, optional): _description_. Defaults to False.
            envelopes (bool, optional): _description_. Defaults to False.
        """
        sender = self.sender()
        if sender.text() == 'Plot envelopes':
            self.plot_envelopes = sender.isChecked()
        elif sender.text() == 'Plot peaks':
            self.plot_peaks = sender.isChecked()
        else:
            print(f'Plot action for {sender.text()} is not implemented')

        for tab_uuid in self.tabs_container:
            self.tabs_container[tab_uuid].updated['swd'] = True
        self.plot_swd_and_spectrums()
            

    def export_spectrum(self):
        '''
        export all valid spectrums to csv file
        '''
        dir = QFileDialog.getExistingDirectory(self, "Select Directory")
        if not dir:
            return
        else:
            dir = pathlib.Path(dir)

        if hasattr (self, 'welch'):
            for key in self.welch['spectrums'].keys():
                data = np.vstack([ self.welch['x'], self.welch['spectrums'][key]])
                with open(dir / f'{self.swd_names[key]}.spectrum.csv', 'w') as f:
                    for line in data.T:
                        func.write_csv_line(file_object=f, line=line) # Excel dialect is not locale-aware :-(

    def export_stats(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if not directory:
            return
        else:
            directory = pathlib.Path(directory)
        for container in self.tabs_container.values():
            swd_io.export_stats(container, directory)

    def export_average_spectrum(self):
        ##
        ##

        filepath = QFileDialog.getSaveFileName(self, "Save average spectrum", filter="Comma-separated values (*.average_spectrum.csv)")
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
        new_text = self.tabs.tbar.new_text
        self.tabs_container[self.tabs.tbar.tabData(self.tabs.tbar.currentIndex())].dataset_name = new_text

    def tab_menu(self, tab_uuid, event):
        menu = QMenu()
        toggleMenuAct = menu.addAction("Toggle")
        action = menu.exec_(self.mapToGlobal(event))
        if action == toggleMenuAct:
            self.block_reanalysis = True

            [cb.setChecked(not cb.isChecked()) for cb in self.tabs_container[tab_uuid].swd_selectors.values()]
            self.tabs_container[tab_uuid].updated['swd'] = True
            self.block_reanalysis = False

            self.nhst_stats()
            self.plot_average_spectrum()
            self.plot_swd_and_spectrums()
            
    def create_swd_tab(self, swd_container:containers.SWDTabContainer, tab_name:str):
        
        swd_container.plots = {}
        swd_container.swd_selectors = {uuid:QCheckBox(str(n)) for n, uuid in enumerate(swd_container.swd_state.keys())}
        for swd_uuid, checkbox in swd_container.swd_selectors.items():
            checkbox.swd_uuid = swd_uuid

        tab = MyScrollArea()
        tab.setWidgetResizable(True)
        tab.setContextMenuPolicy(Qt.CustomContextMenu)
        tab.customContextMenuRequested.connect(lambda x: self.tab_menu(swd_container.uuid, x))
        
        tab_index = self.tabs.addTab(tab, f"{tab_name}")
        self.tabs.tbar.setTabData(tab_index, swd_container.uuid)
        self.tabs.uuid_index_dict[tab_index] = swd_container.uuid
        return tab_index
        
    def add_content_to_tab(self, tab_container:containers.SWDTabContainer, tab_index:int):
        tab = self.tabs.widget(tab_index)
        content_widget = QWidget()
        layout = QGridLayout(content_widget)
        # [a.setSizePolicy( QSizePolicy.Fixed, QSizePolicy.Expanding) for a in self.swd_selectors[fn]]
        [layout.addWidget(a) for a in tab_container.swd_selectors.values()]
        [sc.setChecked(tab_container.swd_state[swd_uuid]) for swd_uuid, sc in tab_container.swd_selectors.items()]
        self.add_plots_to_tab(tab_container, layout)
        tab.setWidget(content_widget)
    
    def add_swd_tab(self, swd_container:containers.SWDTabContainer, tab_name:str):
        i = self.create_swd_tab(swd_container, tab_name)
        self.add_content_to_tab(swd_container, i)
        
    def add_plots_to_tab(self, swd_container, layout, tab_index=None):

        # if swd_container.uuid != self.tabs.uuid_index_dict[self.tabs.tbar.currentIndex()]:
        #     return
        swd_container.graphics_layouts = {}

        # n_ = 0
        for n_, (swd_uuid, a) in enumerate(swd_container.swd_selectors.items()):
            a.toggled.connect(lambda:self.toggleAct(swd_container.uuid, swd_uuid))
            swd_container.graphics_layouts[swd_uuid] = MyGraphicsLayoutWidget()
        # for n_, swd_uuid in enumerate(swd_container.annotation_dict):
            layout.addWidget(swd_container.graphics_layouts[swd_uuid], n_, 1)
            
            for col in range(self.n_cols):
                p_ =  FastPlotItem(enableMenu=False, skipFiniteCheck=True)
                swd_container.graphics_layouts[swd_uuid].addItem(p_, row=0, col=col)
                p_.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            swd_container.plots[swd_uuid] = swd_container.graphics_layouts[swd_uuid]
            # n_+=1
    
    def add_mpl_plot(self):
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

    def toggleAct(self, tab_uuid, swd_uuid):
        self.tabs_container[tab_uuid].updated = {'swd':True, 'spectrum':True}
        swd_uuid = self.sender().swd_uuid
        self.toggle_single_swd(tab_uuid, swd_uuid) # check lambda
        self.draw_all_pg_plots(tab_uuid, swd_uuid)
        if not self.block_reanalysis:
            self.nhst_stats()
            self.plot_average_spectrum()


    def process_data(self): #runs once
        if self.block_reanalysis:
            return
        else:
            for uuid in self.tabs_container:
                func.welch_spectrum(self.tabs_container[uuid])
                func.calculate_asymmetry(self.tabs_container[uuid])
            # self.asymmetry = None
            # self.block_reanalysis = True
            # for swd_filepath_key in self.swd_state:
            #     for swd_id in self.welch['rejected_swd'][swd_filepath_key]:
            #         self.swd_state[swd_filepath_key][swd_id] = False
            #         self.swd_selectors[swd_filepath_key][swd_id].setChecked(False)
            # self.block_reanalysis = False
    
    def nhst_stats(self, test = 'mw'):
        if not self.run_stat_tests:
            self.nhst_test = None
            self.stats_container[test] = []
            fd = func.filter_data_by_state(self.tabs_container)
            console_text = ''.join([f'{fd[key].shape[0]} valid spectrums in {self.tabs_container[key].dataset_name} \n' for key in fd.keys()])
            
        else:
            if len(list(self.tabs_container.keys())) >2:
                test='kw'
            if test == 'mw':
                result = func.statistics_mw(self.tabs_container)
            elif test == 'student':
                pass
            elif test == 'kw':
                result = func.statistics_kw(self.tabs_container)
            
            self.nhst_test = test
            
            self.stats_container[test] = result

            fd = func.filter_data_by_state(self.tabs_container)

            console_text = f'Running {test} analysis with:\n' + \
                ''.join([f'{fd[key].shape[0]} valid spectrums in {self.tabs_container[key].dataset_name} \n' for key in fd.keys()]) + '\n' + \
                'Frequency\tTest statistic\tp\n'

            x = list(self.tabs_container.values())[0].spectrum_x
            if len(self.stats_container[test][0]) == 0:
                console_text += f'no signifncant differences found\n'

            for freq in self.stats_container[test][0]:
                T = self.stats_container[test][1][freq][0]
                p = self.stats_container[test][1][freq][1]

                console_text += f'{x[freq]:.2g}\t{T:.2g}\t{p:.2g}\n'
            
                
        self.console.setText(console_text)
        

    def plot_average_spectrum(self):
        ## all values shoud be precomputed in Analysis object
        ##
        func.plot_conditions(self.tabs_container, self.sc, 
                             self.plot_spread, self.plot_avg, 
                             self.plot_significance, self.stats_container, self.nhst_test,
                             method=np.median)

    def plot_swd_and_spectrums(self, ignore_visibility:bool=False):
        for tab_uuid in self.tabs_container:
            if not ignore_visibility:
                if tab_uuid != self.tabs.uuid_index_dict[self.tabs.tbar.currentIndex()]:
                    continue
            for n_, swd_uuid in enumerate(tqdm(self.tabs_container[tab_uuid].annotation_dict)):
                self.draw_all_pg_plots(tab_uuid, swd_uuid)
            self.tabs_container[tab_uuid].updated = {'swd':False, 'spectrum':False}

    
    def draw_spectrum_plot(self, tab_uuid, swd_uuid, col:int=1):
        if not self.tabs_container[tab_uuid].updated['spectrum']:
            return
        
        container = self.tabs_container[tab_uuid]
        plot = container.plots[swd_uuid].getItem(0, col)

        if self.tabs_container[tab_uuid].swd_state[swd_uuid]:
            pen=self.pgPen_g
        else:
            pen=self.pgPen_w
        if swd_uuid in container.welch.keys():
            plot.plot(container.spectrum_x, container.welch[swd_uuid], pen=pen, clear=True)
            

    def draw_swd_plot(self, tab_uuid, swd_uuid, x:list=None, col:int=0):
        if not self.tabs_container[tab_uuid].updated['swd']:
            return
        
        plot = self.tabs_container[tab_uuid].plots[swd_uuid].getItem(0, col)
        swd = self.tabs_container[tab_uuid].swd_data[swd_uuid]
        sfreq = self.tabs_container[tab_uuid].raw_info['info']['sfreq']
        
        if not x:
            x = np.arange(len(swd))/sfreq
        
        if self.tabs_container[tab_uuid].swd_state[swd_uuid]:
            pen = self.pgPen_r
        else:
            pen = self.pgPen_w
        plot.plot(x, swd, pen=pen, clear=True)

        if hasattr(self.tabs_container[tab_uuid], "asymmetry"):
            if self.tabs_container[tab_uuid].asymmetry[swd_uuid]:
                peaks_upper = self.tabs_container[tab_uuid].asymmetry[swd_uuid]['peaks_upper']
                peaks_lower = self.tabs_container[tab_uuid].asymmetry[swd_uuid]['peaks_lower']
                spline_upper = self.tabs_container[tab_uuid].asymmetry[swd_uuid]['spline_upper']
                spline_lower = self.tabs_container[tab_uuid].asymmetry[swd_uuid]['spline_lower']
                
                for peaks, spline in ((peaks_upper, spline_upper), (peaks_lower, spline_lower)):
                    if self.plot_envelopes:
                        plot.plot(np.linspace(x[peaks[0]], x[peaks[-1]], spline.shape[0]), spline,
                        pen=self.pgPen_y)
                        
                    if self.plot_peaks:
                        plot.plot([x[a] for a in peaks], [swd[a] for a in peaks],
                            pen=None, brush=self.pgBrush_b, symbolSize=6)

    def draw_all_pg_plots(self, tab_uuid:str, swd_uuid:str):
        self.draw_swd_plot(tab_uuid, swd_uuid)
        self.draw_spectrum_plot(tab_uuid, swd_uuid)


    def toggle_single_swd(self, uuid:str, swd_uuid:int=None):
        self.tabs_container[uuid].swd_state[swd_uuid] = self.sender().isChecked()
        if swd_uuid not in self.tabs_container[uuid].welch.keys():
            self.sender().setChecked(False)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Control and not event.isAutoRepeat():
            self.tabs.currentWidget().SetScrollable(False)
            for uuid in self.tabs_container.keys():
                [a.SetScrollable(True) for a in self.tabs_container[uuid].graphics_layouts.values()]
    
    def keyReleaseEvent(self, event):
        key = event.key()
        if key == Qt.Key_Control and not event.isAutoRepeat():
            self.tabs.currentWidget().SetScrollable(True)
            for uuid in self.tabs_container.keys():
                [a.SetScrollable(False) for a in self.tabs_container[uuid].graphics_layouts.values()]


class SpectralWindow(SWDWindow):
    
    def __init__(self, parent, filenames:list=None):
        """_summary_

        Args:
            parent (_type_): _description_
            filenames (list, optional): _description_. Defaults to None.
        Attributes:

        """
        super(SpectralWindow, self).__init__(parent, filenames)
        self.setWindowTitle("Average spectral analysis")
        self.datasets_container = {}
        self.n_cols = 1
        self.filenames = filenames
        self.plot_swd_and_spectrums = self.plot_spectrums # &&&
        self.run_stat_tests = True
    
    def create_menu(self):
        menubar = self.menuBar()
        menu = menubar.addMenu('File')

        add_ds_action = menu.addAction("Add dataset")
        add_ds_action.triggered.connect(self.add_dataset)
        export_action = menu.addAction("Save analysis")
        export_action.triggered.connect(self.save_analysis_containers)
        # export_action.setEnabled(False )

        menu2 = menubar.addMenu('Plotting')
        menu3 = menubar.addMenu('Stats')

 
        
        self.add_menu_item(menu2, "Plot spread", self.plot_spread_func, checkable=True, checked=True)

        self.add_menu_item(menu2, "Plot significance", self.plot_sig_func, checkable=True, checked=True)
        self.add_menu_item(menu2, 'Plot median', self.plot_med_func, checkable=True, checked=True)
        # self.add_menu_item(menu2, 'Plot peaks', self.change_plot_additions_swd, checkable=True, checked=False)

        self.add_menu_item(menu3, 'Run tests', self.run_stat_tests_switch, checkable=True, checked=self.run_stat_tests)
        self.add_menu_item(menu3, 'Non-parametric stats', self.stats_type_switch, checkable=True, checked=False)


    def check_files(self):
        for uuid in self.tabs_container:
            if not hasattr(self.tabs_container[uuid], 'welch'):
                QMessageBox.warning(self, "Filter", f"no precomputed spectral data in\n{self.tabs_container[uuid].filename}")
                return
        return True

    def save_analysis_containers(self):
        for container in self.tabs_container:
            payload = swd_io.containers_to_dict(self.preprocessed_data, self.tabs_container)
        swd_io.update_eeg_processing(payload)

    def load_files(self):
        self.preprocessed_data = swd_io.open_multiple_swd_pickles(self.filenames)
        selected_channels = self.select_swd_channels(self.preprocessed_data)
        if not selected_channels:
            if not self.tabs_container:
                return
            return
        
        channels_containers = swd_io.create_swd_containers_for_individual_channels(self.preprocessed_data, selected_channels)
        try:
            w = func.filter_data_by_state(channels_containers)
            w = {k:np.average(w[k], axis=0) for k in w}
        except AttributeError as e:
            QMessageBox.about(self, "", f"{e}")
            return

        ds_uuid = str(uuid.uuid4())
        ds_name = str(len(self.tabs_container))

        data = dict (dataset_uuid = ds_uuid,
            annotation_dict={k:True for k in w},
            swd_uuid_list=None,
            swd_data={k:True for k in w},
            swd_state={k:True for k in w},
            raw_info=None,
            ch_name=None,
            dataset_name=ds_name,
            welch=w,
            spectrum_x=list(channels_containers.values())[0].spectrum_x, # !!!!!!!!!!!!!
            )

        channels_containers[ds_name] =  containers.SWDTabContainer(ds_name, data)
        self.tabs_container[channels_containers[ds_name].uuid] = channels_containers[ds_name] 
        self.tabs_container[channels_containers[ds_name].uuid].tab_name = ds_name
        return channels_containers[ds_name].uuid

    def add_dataset(self, filenames:list=None):
        if not filenames:
            self.filenames = func.open_file_dialog(ftype='pickle', multiple_files=True)
        else:
            self.filenames = filenames
        new_cont_uuid = self.load_files()
        if not new_cont_uuid:
            return
        self.add_swd_tab(self.tabs_container[new_cont_uuid], self.tabs_container[new_cont_uuid].tab_name)
        self.create_analysis()

    def create_analysis(self):
        if not self.check_files():
            self.close()
            return
        self.plot_spectrums()
        self.nhst_stats()
        self.plot_average_spectrum()
                
        return True
    
    def plot_spectrums(self):
        for tab_uuid in self.tabs_container:
            for n_, swd_uuid in enumerate(self.tabs_container[tab_uuid].annotation_dict):
                self.draw_spectrum_plot(tab_uuid, swd_uuid, col=0)
            self.tabs_container[tab_uuid].updated = {'swd':False, 'spectrum':False}

    def toggleAct(self, tab_uuid, swd_uuid):
        self.tabs_container[tab_uuid].updated = {'swd':True, 'spectrum':True}
        swd_uuid = self.sender().swd_uuid
        self.toggle_single_swd(tab_uuid, swd_uuid) # check lambda
        self.draw_spectrum_plot(tab_uuid, swd_uuid, col=0)
        if not self.block_reanalysis:
            self.nhst_stats()
            self.plot_average_spectrum()


class MainWindow(pg.GraphicsLayoutWidget):
    def __init__(self, eeg:func.EEG=None):
        super(MainWindow, self).__init__()
        self.eeg = eeg
        self.setBackground(config.settings.value('WINDOW_COLOR'))
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.create_menu()
        self.load_eeg_plots(self.eeg)

    def load_eeg_plots(self, eeg:func.EEG, filter_data:bool=False):
        if not eeg:
            return
        self.eeg = eeg
        if hasattr(self, 'eeg_plots'):
            self.eeg_plots.setParent(None)
            self.eeg_plots.destroy()
        if filter_data:
           self.eeg.apply_filter()
        
        self.eeg_plots = MainWidget(eeg = self.eeg, parent = self)
        self.setWindowTitle(eeg.filename)
        self.layout.addWidget(self.eeg_plots)

    def save_processing(self):
        if not self.eeg:
            QMessageBox.about(self, "Export SWD", "First load some EEG with annotated SWD!")
            return

        self.create_swd_framgents_from_annotations()
        fn = self.eeg.filename + '.pickle'
        filepath = QFileDialog.getSaveFileName(self, caption="Save annotated raw data", directory=fn, filter='preprocessed EEG (*.pickle) ;; All files(*)')
        if filepath[0]:
            fn = filepath[0]
        else:
            return
        swd_io.save_eeg_processing(self.eeg, fn)

    def add_menu_item(self, menu, name='', func=None, shortcut='', checkable=False, checked=False, enabled=True):
        action = QAction(name, menu, checkable=checkable, checked=checked)
        action.setShortcut(shortcut)
        action.triggered.connect(func)
        action.setEnabled(enabled)
        menu.addAction(action)

    def create_menu(self):
        menubar = QMenuBar(self)

        actionFile = menubar.addMenu("File")
        actionAnalysis = menubar.addMenu("Analysis")
        actionAbout = menubar.addMenu("About")

        self.add_menu_item(actionFile, "&Open raw file", lambda x: self.open_file(ftype='raw'), "Ctrl+O")
        self.add_menu_item(actionFile, "Open &annotated file", lambda x: self.open_file(ftype='pickle'), "Ctrl+Shift+O")
        self.add_menu_item(actionFile, "&Save intermediate file", self.save_processing, "Ctrl+S")

        self.add_menu_item(actionAnalysis, "&Filter", self.filter_and_reload)
        self.add_menu_item(actionAnalysis, "&Detect SWD", self.detect_swd, enabled=False)
        self.add_menu_item(actionAnalysis, "&Export SWD", self.export_SWD, enabled=False)
        self.add_menu_item(actionAnalysis, "&Spectums", self.analyse_spectrum)
        self.add_menu_item(actionAnalysis, "&Average spectrums", self.compare_avg_spectrum)


        text = f'Spectrum analyzer: version {config.__version__}\n' + \
            'https://github.com/eegdude/swd_analysis/\n' + config.acknow
        
        self.add_menu_item(actionAbout, "&About", lambda:QMessageBox.about(self, "Title", text))
        
        self.layout.addWidget(menubar)

    def filter_and_reload(self):
        if not self.eeg:
            QMessageBox.about(self, "Filter", "First load some EEG!")
            return
        self.eeg_plots.setParent(None)
        self.eeg_plots.destroy()
        self.load_eeg_plots(self.eeg, filter_data=True)

    def detect_swd(self):
        return
        
            
    def analyse_spectrum(self):
        self.spectral_analysis = SWDWindow(self)
        self.spectral_analysis.spawn_window()
    
    def compare_avg_spectrum(self):
        self.spectral_analysis = SpectralWindow(self)
        self.spectral_analysis.spawn_window()
    
    def create_swd_framgents_from_annotations(self):
        self.eeg.swd_data = {}
        self.eeg.swd_state = {}

        for ch_name in self.eeg.annotation_dict:
            self.eeg.swd_data[ch_name] = {}
            self.eeg.swd_state[ch_name] = {}
            
            for swd_uuid, annotation in self.eeg.annotation_dict[ch_name].items():
                channel = self.eeg.raw.info['ch_names'].index(ch_name)
                fragment = self.eeg.raw[channel][0][0][int(annotation['onset']):int(annotation['onset']+ annotation['duration'])]
                self.eeg.swd_data[ch_name][swd_uuid] = fragment
                self.eeg.swd_state[ch_name][swd_uuid] = True
    
    def export_SWD(self):
        # deprecating or moving to convertor app
        # refactor - move to standalone
        if not self.eeg:
            QMessageBox.about(self, "Export SWD", "First load some EEG with annotated SWD!")
            return
        self.channel_selector = IOSwdDialog(eeg=self.eeg, io_type='export')
        self.channel_selector.setModal(True)
        self.channel_selector.exec_()
        if self.channel_selector.ch_list:
            for ch_name in self.channel_selector.ch_list:
                with open(self.eeg.raw.info['filename'] + ch_name + '.csv', 'w') as f:
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
            self.load_eeg_plots(self.eeg)


class MainWidget(pg.GraphicsLayoutWidget):
    def __init__(self, eeg, parent=None):
        super(MainWidget, self).__init__(parent)
        self.setBackground(config.settings.value('WINDOW_COLOR'))
        self.eeg = eeg

        if not hasattr(self.eeg, 'annotation_dict'):
            self.eeg.annotation_dict = {a:collections.OrderedDict() for a in self.eeg.raw.info['ch_names']}
            self.eeg.swd_uuid_dict = {a:[] for a in self.eeg.raw.info['ch_names']}
            self.eeg.dataset_name = {a:a for a in self.eeg.raw.info['ch_names']}
            self.eeg.dataset_uuid = {a:str(uuid.uuid4()) for a in self.eeg.raw.info['ch_names']}
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
        self.channel_selectors=[QCheckBox(a) for a in self.eeg.raw.info['ch_names']]
        [self.menu_layout.addWidget(a) for a in self.channel_selectors]
        [a.toggled.connect(self.switch_channels) for a in self.channel_selectors]
        
        [a.setChecked(True) for a in self.channel_selectors]
        # self.channel_selectors[1].setChecked(True)

    def create_eeg_plot(self, channel:int=0):
        ch_name = self.eeg.raw.info['ch_names'][channel]
        p = pg.PlotWidget(background='#000000', title=ch_name)
        p.setAntialiasing(True)
        eeg_plot = EegPlotter(eeg=self.eeg, channel=channel, parent=p)
        p.addItem(eeg_plot, name = ch_name, title=ch_name)

        displayed_channels = [self.eeg.raw.info['ch_names'].index(a) for a in self.eeg_plots.keys()]
        w = np.where((np.array(displayed_channels) - channel)>0)[0]
        if np.size(w):
            position = max(0, np.min(w))
        else:
            position = channel

        self.eeg_layout.insertWidget(position, p)
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
                self.create_eeg_plot(self.eeg.raw.info['ch_names'].index(ch_name))
        else:
            self.eeg_plots[ch_name]['PlotWidget'].setParent(None)
            self.eeg_plots.pop(ch_name)


if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s	%(processName)s	%(message)s', level=logging.INFO, filename='log.log')
    logging.getLogger()

    app = QApplication(sys.argv)
    eeg = None

    path = pathlib.Path(r"test_data/sim/ampl/1/")
    f = list(path.glob('*.pickle'))

    path = pathlib.Path(r"test_data/sim/ampl/2/")
    f1 = list(path.glob('*.pickle'))

    path = pathlib.Path(r"test_data/sim/ampl/3/")
    f2 = list(path.glob('*.pickle'))
    
    # filename3 = r"C:\Data\kenul\dec22\Рафаэль_результаты\Контроль\6_ month\WG_3_male_18-01-2021_14-42.bdf"
    
    # eeg = func.open_data_file(pathlib.Path(filename3))
    # ep = MainWindow(eeg=eeg); ep.show()
    # ep = SWDWindow(None, filenames=f1); ep.spawn_window()
    ep = SpectralWindow(None, filenames=f); ep.spawn_window(); ep.add_dataset(f1);  ep.add_dataset(f2)
    

    sys.exit(app.exec_())