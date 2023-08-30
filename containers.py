"""Structures for data analysis
"""

class SWDTabContainer():
    def __init__(self, filename:str, data:dict) -> None:
        """Container for SWD data related to single channel or dataset

        Args:
            filename (str): raw file name
            data (dict): dataset dictionary
        """        
        self.uuid = data['dataset_uuid']
        self.filename = filename
        self.annotation_dict = data['annotation_dict']
        self.swd_uuid_list = data['swd_uuid_list']
        self.swd_data = data['swd_data']
        self.swd_state = data['swd_state']
        self.raw_info = data['raw_info']
        self.ch_name = data['ch_name']
        self.dataset_name = data['dataset_name']
        self.updated = {'swd':True, 'spectrum':True} # do you need to replot swd and spectrum
        if 'welch' in list(data.keys()):
            self.welch = data['welch']

        if 'spectrum_x' in list(data.keys()):
            self.spectrum_x = data['spectrum_x']