"""EEG-specific widgets, mostly subclassed from PyQtGraph

Returns:
    [type]: [description]
"""
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg
from pyqtgraph import functions as fn
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
import uuid
import numpy as np
import logging
import warnings

import config
import func

import weakref

pg.setConfigOptions(enableExperimental=config.enablePyQTGraphExperimental)
translate = QCoreApplication.translate

class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(481, 840)
        self.averageGroup = QGroupBox(Form)
        self.averageGroup.setGeometry(QRect(0, 640, 242, 182))
        self.averageGroup.setCheckable(True)
        self.averageGroup.setChecked(False)
        self.averageGroup.setObjectName("averageGroup")
        self.gridLayout_5 = QGridLayout(self.averageGroup)
        self.gridLayout_5.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_5.setSpacing(0)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.avgParamList = QListWidget(self.averageGroup)
        self.avgParamList.setObjectName("avgParamList")
        self.gridLayout_5.addWidget(self.avgParamList, 0, 0, 1, 1)
        self.decimateGroup = QFrame(Form)
        self.decimateGroup.setGeometry(QRect(10, 140, 191, 171))
        self.decimateGroup.setObjectName("decimateGroup")
        self.gridLayout_4 = QGridLayout(self.decimateGroup)
        self.gridLayout_4.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_4.setSpacing(0)
        self.gridLayout_4.setObjectName("gridLayout_4")
        self.clipToViewCheck = QCheckBox(self.decimateGroup)
        self.clipToViewCheck.setObjectName("clipToViewCheck")
        self.gridLayout_4.addWidget(self.clipToViewCheck, 7, 0, 1, 3)
        self.maxTracesCheck = QCheckBox(self.decimateGroup)
        self.maxTracesCheck.setObjectName("maxTracesCheck")
        self.gridLayout_4.addWidget(self.maxTracesCheck, 8, 0, 1, 2)
        self.downsampleCheck = QCheckBox(self.decimateGroup)
        self.downsampleCheck.setObjectName("downsampleCheck")
        self.gridLayout_4.addWidget(self.downsampleCheck, 0, 0, 1, 3)
        self.peakRadio = QRadioButton(self.decimateGroup)
        self.peakRadio.setChecked(True)
        self.peakRadio.setObjectName("peakRadio")
        self.gridLayout_4.addWidget(self.peakRadio, 6, 1, 1, 2)
        self.maxTracesSpin = QSpinBox(self.decimateGroup)
        self.maxTracesSpin.setObjectName("maxTracesSpin")
        self.gridLayout_4.addWidget(self.maxTracesSpin, 8, 2, 1, 1)
        self.forgetTracesCheck = QCheckBox(self.decimateGroup)
        self.forgetTracesCheck.setObjectName("forgetTracesCheck")
        self.gridLayout_4.addWidget(self.forgetTracesCheck, 9, 0, 1, 3)
        self.meanRadio = QRadioButton(self.decimateGroup)
        self.meanRadio.setObjectName("meanRadio")
        self.gridLayout_4.addWidget(self.meanRadio, 3, 1, 1, 2)
        self.subsampleRadio = QRadioButton(self.decimateGroup)
        self.subsampleRadio.setObjectName("subsampleRadio")
        self.gridLayout_4.addWidget(self.subsampleRadio, 2, 1, 1, 2)
        self.autoDownsampleCheck = QCheckBox(self.decimateGroup)
        self.autoDownsampleCheck.setChecked(True)
        self.autoDownsampleCheck.setObjectName("autoDownsampleCheck")
        self.gridLayout_4.addWidget(self.autoDownsampleCheck, 1, 2, 1, 1)
        spacerItem = QSpacerItem(30, 20, QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        self.gridLayout_4.addItem(spacerItem, 2, 0, 1, 1)
        self.downsampleSpin = QSpinBox(self.decimateGroup)
        self.downsampleSpin.setMinimum(1)
        self.downsampleSpin.setMaximum(100000)
        self.downsampleSpin.setProperty("value", 1)
        self.downsampleSpin.setObjectName("downsampleSpin")
        self.gridLayout_4.addWidget(self.downsampleSpin, 1, 1, 1, 1)
        self.transformGroup = QFrame(Form)
        self.transformGroup.setGeometry(QRect(10, 10, 171, 101))
        self.transformGroup.setObjectName("transformGroup")
        self.gridLayout = QGridLayout(self.transformGroup)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setSpacing(0)
        self.gridLayout.setObjectName("gridLayout")
        self.logYCheck = QCheckBox(self.transformGroup)
        self.logYCheck.setObjectName("logYCheck")
        self.gridLayout.addWidget(self.logYCheck, 2, 0, 1, 1)
        self.logXCheck = QCheckBox(self.transformGroup)
        self.logXCheck.setObjectName("logXCheck")
        self.gridLayout.addWidget(self.logXCheck, 1, 0, 1, 1)
        self.fftCheck = QCheckBox(self.transformGroup)
        self.fftCheck.setObjectName("fftCheck")
        self.gridLayout.addWidget(self.fftCheck, 0, 0, 1, 1)
        self.derivativeCheck = QCheckBox(self.transformGroup)
        self.derivativeCheck.setObjectName("derivativeCheck")
        self.gridLayout.addWidget(self.derivativeCheck, 3, 0, 1, 1)
        self.phasemapCheck = QCheckBox(self.transformGroup)
        self.phasemapCheck.setObjectName("phasemapCheck")
        self.gridLayout.addWidget(self.phasemapCheck, 4, 0, 1, 1)
        self.pointsGroup = QGroupBox(Form)
        self.pointsGroup.setGeometry(QRect(10, 550, 234, 58))
        self.pointsGroup.setCheckable(True)
        self.pointsGroup.setObjectName("pointsGroup")
        self.verticalLayout_5 = QVBoxLayout(self.pointsGroup)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.autoPointsCheck = QCheckBox(self.pointsGroup)
        self.autoPointsCheck.setChecked(True)
        self.autoPointsCheck.setObjectName("autoPointsCheck")
        self.verticalLayout_5.addWidget(self.autoPointsCheck)
        self.gridGroup = QFrame(Form)
        self.gridGroup.setGeometry(QRect(10, 460, 221, 81))
        self.gridGroup.setObjectName("gridGroup")
        self.gridLayout_2 = QGridLayout(self.gridGroup)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.xGridCheck = QCheckBox(self.gridGroup)
        self.xGridCheck.setObjectName("xGridCheck")
        self.gridLayout_2.addWidget(self.xGridCheck, 0, 0, 1, 2)
        self.yGridCheck = QCheckBox(self.gridGroup)
        self.yGridCheck.setObjectName("yGridCheck")
        self.gridLayout_2.addWidget(self.yGridCheck, 1, 0, 1, 2)
        self.gridAlphaSlider = QSlider(self.gridGroup)
        self.gridAlphaSlider.setMaximum(255)
        self.gridAlphaSlider.setProperty("value", 128)
        self.gridAlphaSlider.setOrientation(Qt.Orientation.Horizontal)
        self.gridAlphaSlider.setObjectName("gridAlphaSlider")
        self.gridLayout_2.addWidget(self.gridAlphaSlider, 2, 1, 1, 1)
        self.label = QLabel(self.gridGroup)
        self.label.setObjectName("label")
        self.gridLayout_2.addWidget(self.label, 2, 0, 1, 1)
        self.alphaGroup = QGroupBox(Form)
        self.alphaGroup.setGeometry(QRect(10, 390, 234, 60))
        self.alphaGroup.setCheckable(True)
        self.alphaGroup.setObjectName("alphaGroup")
        self.horizontalLayout = QHBoxLayout(self.alphaGroup)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.autoAlphaCheck = QCheckBox(self.alphaGroup)
        self.autoAlphaCheck.setChecked(False)
        self.autoAlphaCheck.setObjectName("autoAlphaCheck")
        self.horizontalLayout.addWidget(self.autoAlphaCheck)
        self.alphaSlider = QSlider(self.alphaGroup)
        self.alphaSlider.setMaximum(1000)
        self.alphaSlider.setProperty("value", 1000)
        self.alphaSlider.setOrientation(Qt.Orientation.Horizontal)
        self.alphaSlider.setObjectName("alphaSlider")
        self.horizontalLayout.addWidget(self.alphaSlider)

        self.retranslateUi(Form)
        QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "PyQtGraph"))
        self.averageGroup.setToolTip(_translate("Form", "Display averages of the curves displayed in this plot. The parameter list allows you to choose parameters to average over (if any are available)."))
        self.averageGroup.setTitle(_translate("Form", "Average"))
        self.clipToViewCheck.setToolTip(_translate("Form", "Plot only the portion of each curve that is visible. This assumes X values are uniformly spaced."))
        self.clipToViewCheck.setText(_translate("Form", "Clip to View"))
        self.maxTracesCheck.setToolTip(_translate("Form", "If multiple curves are displayed in this plot, check this box to limit the number of traces that are displayed."))
        self.maxTracesCheck.setText(_translate("Form", "Max Traces:"))
        self.downsampleCheck.setText(_translate("Form", "Downsample"))
        self.peakRadio.setToolTip(_translate("Form", "Downsample by drawing a saw wave that follows the min and max of the original data. This method produces the best visual representation of the data but is slower."))
        self.peakRadio.setText(_translate("Form", "Peak"))
        self.maxTracesSpin.setToolTip(_translate("Form", "If multiple curves are displayed in this plot, check \"Max Traces\" and set this value to limit the number of traces that are displayed."))
        self.forgetTracesCheck.setToolTip(_translate("Form", "If MaxTraces is checked, remove curves from memory after they are hidden (saves memory, but traces can not be un-hidden)."))
        self.forgetTracesCheck.setText(_translate("Form", "Forget hidden traces"))
        self.meanRadio.setToolTip(_translate("Form", "Downsample by taking the mean of N samples."))
        self.meanRadio.setText(_translate("Form", "Mean"))
        self.subsampleRadio.setToolTip(_translate("Form", "Downsample by taking the first of N samples. This method is fastest and least accurate."))
        self.subsampleRadio.setText(_translate("Form", "Subsample"))
        self.autoDownsampleCheck.setToolTip(_translate("Form", "Automatically downsample data based on the visible range. This assumes X values are uniformly spaced."))
        self.autoDownsampleCheck.setText(_translate("Form", "Auto"))
        self.downsampleSpin.setToolTip(_translate("Form", "Downsample data before plotting. (plot every Nth sample)"))
        self.downsampleSpin.setSuffix(_translate("Form", "x"))
        self.logYCheck.setText(_translate("Form", "Log Y"))
        self.logXCheck.setText(_translate("Form", "Log X"))
        self.fftCheck.setText(_translate("Form", "Power Spectrum (FFT)"))
        self.derivativeCheck.setText(_translate("Form", "dy/dx"))
        self.phasemapCheck.setText(_translate("Form", "Y vs. Y\'"))
        self.pointsGroup.setTitle(_translate("Form", "Points"))
        self.autoPointsCheck.setText(_translate("Form", "Auto"))
        self.xGridCheck.setText(_translate("Form", "Show X Grid"))
        self.yGridCheck.setText(_translate("Form", "Show Y Grid"))
        self.label.setText(_translate("Form", "Opacity"))
        self.alphaGroup.setTitle(_translate("Form", "Alpha"))
        self.autoAlphaCheck.setText(_translate("Form", "Auto"))


class FastPlotItem(pg.PlotItem):
 
    sigRangeChanged = pg.Qt.QtCore.Signal(object, object)    ## Emitted when the ViewBox range has changed
    sigYRangeChanged = pg.Qt.QtCore.Signal(object, object)   ## Emitted when the ViewBox Y range has changed
    sigXRangeChanged = pg.Qt.QtCore.Signal(object, object)   ## Emitted when the ViewBox X range has changed
        
    lastFileDir = None
    
    def __init__(self, parent=None, name=None, labels=None, title=None, viewBox=None, axisItems=None, enableMenu=True, **kargs):
        """
        Same class as pg.PlotItem, but removed a lot of stuff that slows down 
        the creation process (mainly context menu and some signals/slots).
        Creation speed increased ~2 times, and ~4 times when skipping
        AxisItems
        """
        
        pg.GraphicsWidget.__init__(self, parent)
        
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        ## Set up control buttons
        self.autoBtn = pg.ButtonItem(pg.icons.getGraphPixmap('auto'), 14, self)
        self.autoBtn.mode = 'auto'
        self.autoBtn.clicked.connect(self.autoBtnClicked)
        self.buttonsHidden = False ## whether the user has requested buttons to be hidden
        self.mouseHovering = False
        
        self.layout = QGraphicsGridLayout()
        self.layout.setContentsMargins(1,1,1,1)
        self.setLayout(self.layout)
        self.layout.setHorizontalSpacing(0)
        self.layout.setVerticalSpacing(0)

        if viewBox is None:
            viewBox = pg.ViewBox(parent=self, enableMenu=enableMenu)
        self.vb = viewBox
        self.vb.sigStateChanged.connect(self.viewStateChanged)

        # Enable or disable plotItem menu
        self.setMenuEnabled(enableMenu, None)
        
        if name is not None:
            self.vb.register(name)
        self.vb.sigRangeChanged.connect(self.sigRangeChanged)
        self.vb.sigXRangeChanged.connect(self.sigXRangeChanged)
        self.vb.sigYRangeChanged.connect(self.sigYRangeChanged)
        
        self.layout.addItem(self.vb, 2, 1)
        self.alpha = 1.0
        self.autoAlpha = True
        self.spectrumMode = False
        
        self.legend = None
        
        # Initialize axis items
        self.axes = {}
        # self.setAxisItems(axisItems)

        self.items = []
        self.curves = []
        self.itemMeta = weakref.WeakKeyDictionary()
        self.dataItems = []
        self.paramList = {}
        self.avgCurves = {}

        # self.ctrl = c = Ui_Form()

        if labels is None:
            labels = {}

        if len(kargs) > 0:
            self.plot(**kargs)

    def addItem(self, item, *args, **kargs):
        if item in self.items:
            warnings.warn('Item already added to PlotItem, ignoring.')
            return
        self.items.append(item)
        vbargs = {}
        if 'ignoreBounds' in kargs:
            vbargs['ignoreBounds'] = kargs['ignoreBounds']
        self.vb.addItem(item, *args, **vbargs)

    def setLabel(self, *args, **kwargs):
        return

    def setLabels(self, *args, **kwargs):
        return

class EEGRegionItem(pg.LinearRegionItem):
    def __init__(self, parent, **kwargs):
        super(EEGRegionItem, self).__init__(**kwargs)
        self.parent = parent
    
    def mouseClickEvent(self, ev):
        if ev.button() == Qt.RightButton:
            self.parent.remove_annotation(self)


class MyGraphicsLayoutWidget(pg.GraphicsLayoutWidget):
    def __init__(self, **kwargs):
        super(MyGraphicsLayoutWidget, self).__init__(**kwargs)
        self.scrollable = False

    def wheelEvent(self, ev):
        if self.scrollable:
            pg.GraphicsLayoutWidget.wheelEvent(self, ev)
    
    def SetScrollable(self, scrollable:bool):
        self.scrollable = scrollable


class MyScrollArea(QScrollArea):
    def __init__(self, *args, **kwargs):
        super(MyScrollArea, self).__init__(*args, **kwargs)
        self.scrollable = True
    
    def wheelEvent (self, *args, **kwargs):
        if self.scrollable:
            QScrollArea.wheelEvent(self, *args, **kwargs)
    
    def SetScrollable(self, scrollable:bool):
        self.scrollable = scrollable


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
    def __init__(self, uuid = None, parent=None):
        super(TabWidget, self).__init__(parent)
        self.tbar = TabBar(self)
        self.setTabBar(self.tbar)
        self.uuid_index_dict = {}
        # self.setDocumentMode(True)
        # self.setTabsClosable(True)


class EegPlotter(pg.PlotCurveItem):
    def __init__(self, eeg, channel:int=0, parent=None):
        super(EegPlotter,self).__init__()
        self.setSkipFiniteCheck(True)
        self.parent = parent
        self.vb = self.parent.getViewBox()
        self.vb.disableAutoRange()
        self.range_lines = []
        self.eeg = eeg
        self.nsamp = self.eeg.raw._last_samps[0] # read more about _raw_extras _raw_extras[0]['nsamples']
        self.channel = channel
        self.ch_name = self.eeg.raw.info['ch_names'][self.channel]

        self.last_pos = [None, None]
        self.window_len_sec = 10
        self.scroll_step = 1000 # make adapive?
        self.eeg_start = 5*int(eeg.raw.info['sfreq'])
        self.eeg_stop = self.window_len_sec*int(eeg.raw.info['sfreq'])
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
                orig_time = self.eeg.raw.annotations.orig_time)
        print(self.eeg.annotation_dict[self.ch_name][region.uuid])
        if region.uuid not in self.eeg.swd_uuid_dict[self.ch_name]:
            self.eeg.swd_uuid_dict[self.ch_name].append(region.uuid)
    
    def remove_annotation(self, item):
        self.eeg.annotation_dict[self.ch_name].pop(item.uuid, None)
        self.vb.removeItem(item)
        self.eeg.swd_uuid_dict[self.ch_name].remove(item.uuid)

    def update_plot(self, eeg_start=None, eeg_stop=None, caller:str=None, direction=None, init:bool=None):
        if init:
            y = self.eeg.raw._data[self.channel, self.eeg_start: self.eeg_stop]
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
        y = self.eeg.raw._data[self.channel, self.eeg_start: self.eeg_stop]
        
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
                delta_ticks_sec = (a[1] - a[0])/int(self.eeg.raw.info['sfreq'])
                if delta_ticks_sec > 60:
                    level = 'm'
                elif delta_ticks_sec < 1:
                    level = 'ms'
                else:
                    level = 's'

            tv = [[[v, func.timesrting_from_sample(v, self.eeg.raw.info['sfreq'], level)] for v in tick_level[1]] for tick_level in tv]
            ax.setTicks(tv)
        
        if self.eeg_stop:
            if (self.parent.parent()):
                mw = self.parent.parent().parent()
                percentage = self.eeg_stop/self.nsamp*100
                mw.setWindowTitle("{} {:.1f}%".format(mw.eeg.filename, percentage))

    def viewRangeChanged(self, *, caller:str=None):
        self.update_plot(caller=caller)
        self.vb.setRange(xRange=(self.eeg_start, self.eeg_stop), padding=0, update=False)