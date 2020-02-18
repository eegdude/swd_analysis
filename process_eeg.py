import pathlib
import matplotlib
import mne
import numpy as np
from tkinter import filedialog
from tkinter import *
import argparse
import pickle

# from scipy import signal
# import matplotlib.pyplot as plt
# from PyEMD import EMD, EEMD, Visualisation


class FileReader():
    def __init__(self, filepath: pathlib.Path=None):
        self.open_eeg_file(filepath)
    
    def open_eeg_file(self, filepath: pathlib.Path=None):
        if filepath.suffix == '.bdf':
            self.raw = mne.io.read_raw_bdf(filepath, preload=False)
        elif filepath.suffix == '.edf':
            self.raw = mne.io.read_raw_edf(filepath, preload=False)

def plot(raw: mne.io.RawArray, picks: list=None, block=True):
    raw.plot(scalings=dict(eeg=5e-3), duration=60, block=block)

def select_channel(raw: mne.io.RawArray, picks: list=None):
    info = mne.create_info(['channel'], sfreq=raw.info['sfreq'], ch_types=['eeg'])
    channel_of_interest = raw.get_data(picks=picks)
    return mne.io.RawArray(channel_of_interest, info)

def cut_annotations(raw: mne.io.RawArray):
    annotations = raw.annotations
    sfreq = raw.info['sfreq']
    swd_list = [mne.io.RawArray(ch.get_data(start=int(sfreq*a['onset']),
                            stop=int(sfreq*(a['onset']+a['duration']))), raw.info, verbose=0)
                            for a in annotations]
    return swd_list

def save_file(swd_list:list):
    print (f"saving {len(swd_list)} swds")
    f = filedialog.asksaveasfile(mode='wb', filetypes = (("python files","*.pickle"),("all files","*.*")),
                                defaultextension='.pickle')
    pickle.dump(swd_list, f)

def raw_dsp(raw: mne.io.RawArray, channel:int=None):
    if channel:
        raw = select_channel(raw, picks=[channel-1])
    raw.load_data()
    raw=raw.resample(128)
    raw = raw.filter(1, 40)
    return raw

def detect_swd(raw):
    """
    WORK IN PROGRESS
    """
    sig = raw.crop(10, 2400)
    # plot(sig)
    sig= sig.get_data().ravel()
    
    emd = EMD()
    IMF = emd.emd(sig)
    print (IMF.shape)
    v = Visualisation(emd_instance=emd)
    v.plot_imfs()
    plt.show()

if __name__ == "__main__":

    root = Tk()
    root.withdraw()
    filename = filedialog.askopenfilename(initialdir = ".",title = "Select file")
    print (filename)

    channel = input('type channel number, press enter   ')
    f = FileReader(pathlib.Path(filename))
    ch = raw_dsp(f.raw, int(channel))
    plot(ch)
    swd_list = cut_annotations(ch)
    save_file(swd_list)

    # detect_swd(ch)
