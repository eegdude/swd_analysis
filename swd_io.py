"""IO functions for reading and writing files

Returns:
    [type]: [description]
"""
import pickle
import pathlib
import config
import containers
import func
import json
import numpy as np


def load_swd_from_pickle(filename):
    # print(filename)
    with open(filename, 'rb') as f:
        preprocessed_data = pickle.load(f)
        return preprocessed_data


def open_multiple_swd_pickles(filenames):
    return {filename:load_swd_from_pickle(filename) for filename in filenames}


def create_swd_containers_for_individual_channels(data:dict, selected_channels:dict):
    """Receive data dictionary from preprocesssed files, return dictionary
        of SwdTabContainer objects, holding everything related to specific channel

    Args:
        data (dict): data dictionary with preprocessed data from one or more files
        selected_channels (dict): {file:[channels selected for processing]}

    Returns:
        dict: return dictionary of SwdTabContainer objects
    """    

    channels_containers = {}
    for filename in selected_channels.keys():
            fn = pathlib.Path(filename).name
            for ch in selected_channels[filename]:
                data_tab = {'annotation_dict':data[filename]['annotation_dict'][ch],
                            'swd_uuid_list':data[filename]['swd_uuid_dict'][ch],
                            'swd_data':data[filename]['swd_data'][ch],
                            'swd_state':data[filename]['swd_state'][ch],
                            'raw_info':data[filename]['raw_info'],
                            'dataset_name':data[filename]['dataset_name'][ch],
                            'ch_name':ch,
                            'dataset_uuid': data[filename]['dataset_uuid'][ch],
                            }
                data_tab['welch'] = None
                data_tab['spectrum_x'] = None
                
                if 'welch' in list(data[filename].keys()):
                    if ch in data[filename]['welch']:
                        data_tab['welch'] = data[filename]['welch'][ch]
                        data_tab['spectrum_x'] = data[filename]['spectrum_x'][ch]

                if not data[filename]['swd_data'][ch]: #skip if no swd in channels
                    continue
                SwdTabData = containers.SWDTabContainer(filename, data_tab)
                tab_name = f"{fn}_{ch}"
                channels_containers[tab_name] = SwdTabData
    return channels_containers


def containers_to_dict(preprocessed_data, tabs_container):
    for uuid in tabs_container:
        preprocessed_data[tabs_container[uuid].filename]['welch'] = {}
    spectrum_x_dict = {tabs_container[uuid].ch_name: tabs_container[uuid].spectrum_x for uuid in tabs_container}

    for uuid in tabs_container:
        preprocessed_data[tabs_container[uuid].filename]['swd_state'][tabs_container[uuid].ch_name] = tabs_container[uuid].swd_state
        preprocessed_data[tabs_container[uuid].filename]['dataset_name'][tabs_container[uuid].ch_name] = tabs_container[uuid].dataset_name
    
        preprocessed_data[tabs_container[uuid].filename]['welch'][tabs_container[uuid].ch_name] =  tabs_container[uuid].welch
        preprocessed_data[tabs_container[uuid].filename]['spectrum_x'] = spectrum_x_dict

    return preprocessed_data


def eeg_to_dict(eeg) -> dict:
    jsondict = {key:value for key, value in eeg.__dict__.items() if key not in ['raw']}
    
    jsondict['raw_info'] = {key:value for key, value in eeg.raw.__dict__.items() if key not in ['_data',
        '_times',
        '_annotations',
        '_filenames',
        '_init_kwargs']}
    jsondict['version'] = config.__version__
    return jsondict


def save_eeg_processing(eeg, fn):
    payload = eeg_to_dict(eeg)
    with open (fn, 'wb') as f: #remove json, switch back to pickle and then to h5
        pickle.dump(payload, f)


def update_eeg_processing(payload):
    for filename in payload:
        with open (filename, 'wb') as f: #remove json, switch back to pickle and then to h5
            pickle.dump(payload[filename], f)
    print (f'saved processing in {list(payload.keys())}')


def export_stats(container, directory):
    # print (container)
    def gen_list(key:str):
        return [desc_stats[swd_uuid][key] if desc_stats[swd_uuid] else None for swd_uuid in desc_stats.keys()]
    
    if not hasattr(container, 'asymmetry'):
        print(f'No asymmetry data in {container}')
        return
    if container.asymmetry:
        # recepit = {}
    
        desc_stats = container.asymmetry
        if desc_stats:
            mask = [True if container.swd_state[swd_uuid] else False for swd_uuid in desc_stats.keys()]
            # recepit[container.swd_names[swd_uuid]] = [swd_id if container.swd_state[swd_uuid][swd_id] else False for swd_uuid in asymmetry.keys()]
            swd_uuid = gen_list('uuid')
            assym_peaks = gen_list('assym_peaks')
            spline_lower_integtal = gen_list('spline_lower_integtal')
            spline_upper_integtal = gen_list('spline_upper_integtal')
            minmax = gen_list('minmax')
            minmax_mean_peaks = gen_list('minmax_mean_peaks')
            minmax_spline = gen_list('minmax_spline')
            length = gen_list('length')

            data = np.array([swd_uuid, assym_peaks, spline_lower_integtal, spline_upper_integtal,
                minmax, minmax_mean_peaks, minmax_spline,
                length])
            header = ['swd_uuid', 'peaks', 'spline_l', 'spline_u',
                'minmax', 'mimax_peaks', 'minmax_spline',
                'length']

            data = data[:,mask]


            csv_path = directory / f"{container.filename.name}_{container.uuid}_stats.csv"
            # recepit_path = csv_path.parent / (csv_path.stem+'_asymmetry_log.json')
            
            # with open(recepit_path, 'w') as json_file:
            #     json.dump(recepit, json_file, indent=4)
            
            with open(csv_path, 'w') as f:
                func.write_csv_line(file_object=f, line=header)
                for line in data.T:
                    func.write_csv_line(file_object=f, line=line) # Excel dialect is not locale-aware :-(
