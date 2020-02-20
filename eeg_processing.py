import mne
import pathlib

def open_eeg_file(filename: pathlib.Path=None):
    if filename.suffix == '.bdf':
        raw = mne.io.read_raw_bdf(filename, preload=True)
    elif filename.suffix == '.edf':
        raw = mne.io.read_raw_edf(filename, preload=True)
    return raw

def filter_eeg(eeg:mne.io.RawArray):
    eeg = eeg.filter(1, 40)
    return eeg
