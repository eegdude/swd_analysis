from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
import config

pg.setConfigOptions(enableExperimental=config.enablePyQTGraphExperimental)

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
    def __init__(self, parent=None):
        super(TabWidget, self).__init__(parent)
        self.tbar = TabBar(self)
        self.setTabBar(self.tbar)
        # self.setDocumentMode(True)
        # self.setTabsClosable(True)
