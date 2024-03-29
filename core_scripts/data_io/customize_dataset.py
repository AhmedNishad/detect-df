#!/usr/bin/env python
"""
customized dataset

NII_MergeDataSetLoader (to one minibatch): 
 We want to load dataset 1, 2, and 3, 
 We also want to draw sample from each dataset for one minibatch.
 One epoch over the merged datasets will be decided by the smallest dataset

"""

from __future__ import absolute_import

import os
import sys
import numpy as np
import torch
import torch.utils.data

import core_scripts.other_tools.display as nii_warn
import core_scripts.data_io.default_data_io as nii_default_dset
import core_scripts.data_io.customize_collate_fn as nii_collate_fn
import core_scripts.data_io.customize_sampler as nii_sampler_fn
import core_scripts.data_io.conf as nii_dconf
import core_scripts.data_io.seq_info as nii_seqinfo

__author__ = "Xin Wang"
__email__ = "wangxin@nii.ac.jp"
__copyright__ = "Copyright 2020, Xin Wang"


###############################################
# Dataset definition to merge multiple datasets
###############################################

class merge_loader():
    """ merge_loader
    Data loader for customized data with m_concate_set = None
    By default, draw equal number of samples from each subset

    __iter__():
    __next__(): load data and merge into minibatch

    Note: pay attention to adjust the data index in the dataset.
    See comment of adjust_utt_idx
    """
    def __init__(self, datasets):
        # list of datasets
        self.m_datasets = datasets
        # initialized iterators 
        self.m_loaders = [x.get_loader() for x in self.m_datasets]
        # utterance index shift
        # if we merge dataset 1, 2, 3, then
        #  index for dataset 2: index += dataset_1.get_seq_num()
        #  index for dataset 3: index += dataset_1 + dataset_2.get_seq_num()
        self.m_idx_shift = np.cumsum([0] + 
                                     [x.get_seq_num() for x in self.m_datasets])
        # total number of data
        self.m_data_num = np.sum([x.get_seq_num() for x in self.m_datasets])
        return

    def get_datasize(self):
        # return the total number of data 
        return self.m_data_num

    def get_dataset(self):
        # return the datasets
        return self.m_datasets

    def adjust_utt_idx(self, data_tuple, dataset_idx):
        """ adjust_utt_idx(data_tutple, dataset_idx)
        
        when merging dataset 1, 2, 3 ...
        index for dataset 2: index += dataset_1.get_seq_num()
        index for dataset 3: index += dataset_1 + dataset_2.get_seq_num()
        
        We have to call dataset.f_adjust_idx because it is the dataset itself
        that knows how to parse the data_tuple
        """
        return self.m_datasets[dataset_idx].get_dataset().f_adjust_idx(
            data_tuple, self.m_idx_shift[dataset_idx])

    def __iter__(self):
        """
        create the list of iterators
        """
        self.m_loader_iter = [iter(x) for x in self.m_loaders]
        return self

    def __next__(self):
        """ try to load data from m_datasets, and merge them into a 
        single minibatch
        """
        try:
            data_list = []
            for dataset_idx, dataloader in enumerate(self.m_loader_iter):
                data_list.append(
                    self.adjust_utt_idx(next(dataloader), dataset_idx))
            # 
            return nii_collate_fn.customize_collate_from_batch(data_list)
        except StopIteration:
            raise StopIteration

class ConcatDataset(torch.utils.data.Dataset):
    """ ConcatDataset
    
    Torch.Dataset that concatenate multiple sub-datasets.
    
    Adopted from 
    https://discuss.pytorch.org/t/train-simultaneously-on-two-datasets/649/2
    But here we concatenate data corpora directly. Minibatch may contain data
    from each sub corpus
    """
    def __init__(self, datasets):
        """ ConcatDataset(datasets)
        
        Args
        ----
          datasets: list of torch.utils.data.Dataset or derived classes
                    it must have __len__, __getitem__, and adjust_utt_idx
        """
        # all the sub sets
        self.datasets = datasets
        self.num_subset = len(datasets)
        # initial the len and len_top, len_bot
        self.__init_sub()
        return

    def __init_sub(self):
        # len of each sub set
        self.len_buffer = [x.__len__() for x in self.datasets]
        # for later use, to decide from which subset we draw the sample
        self.len_top = np.cumsum(self.len_buffer)
        self.len_bot = np.cumsum([0] + self.len_buffer[:-1])
        # name <--> idx mapper (idx in the whole dataset)
        self.name_idx_map = {}
        for idx_u, idx_d, subset in \
            zip(self.len_top, self.len_bot, self.datasets):
            data_name_list = subset.f_get_seq_name_list()
            for idx_data, data_name in enumerate(data_name_list):
                # similar to the login in getitem, we need to add the
                # shift idx_d for each subset
                self.name_idx_map[data_name] = idx_data + idx_d
        # done
        return
        
    def __getitem__(self, i):
        """ getitem from the corresponding subcorpus
        """
        # for example, data1 = [a], data2 = [b, c]
        # self.len_buffer = [1, 2]
        # self.len_top = [1, 3] 
        # self.len_bot = [0, 1]
        #  __getitem__(0) -> data1[0-0] = a
        #  __getitem__(1) -> data2[1-1] = b
        #  __getitem__(2) -> data2[2-1] = c
        # 
        # Notice that the index of b is 0 in data2 but 1 in concatenated set
        # The index must be adjusted using f_adjust_idx
        for idx_u, idx_d, subset in \
            zip(self.len_top, self.len_bot, self.datasets):
            if i < idx_u:
                # get the data from subdataset
                orig_data_tuple = subset.__getitem__(i - idx_d)
                # adjust the data idx 
                return subset.f_adjust_idx(orig_data_tuple, idx_d)
            else:
                # keep going to the next subset
                pass
        nii_warn.f_die("Merge dataset: fatal error in __getitem__")
        return None

    def __len__(self):
        return sum(self.len_buffer)

    def f_get_seq_len_list(self):
        """ length = f_get_seq_len_list()
        Total length of utterance in the merged dataset
        """
        tmp = []
        for sub_dataset in self.datasets:
            tmp += sub_dataset.f_get_seq_len_list()
        return tmp

    def f_get_updated_seq_len_for_sampler_list(self):
        """ Similar to f_get_seq_len_list
        but it returns the updated data sequence length only for 
        length-based shuffling in sampler
        """
        tmp = []
        for sub_dataset in self.datasets:
            tmp += sub_dataset.f_get_updated_seq_len_for_sampler_list()
        return tmp

    def f_update_seq_len_for_sampler_list(self, data_info):
        """
        """
        for one_info in data_info:
            data_idx = nii_seqinfo.parse_idx(one_info)
            data_len = nii_seqinfo.parse_length(one_info)
            for idx_u, idx_d, subset in \
                zip(self.len_top, self.len_bot, self.datasets):
                if data_idx < idx_u:
                    subset.f_update_seq_len_for_sampler_list(data_idx, data_len)
                    break
                else:
                    pass
        return

    def f_manage_data(self, lst_data_idx, opt):
        """ f_manage_data(self, lst_data_idx, opt)
        """
        # manage the data in each subset
        for idx_u, idx_d, subset in \
            zip(self.len_top, self.len_bot, self.datasets):
            # adjust the index for each sub dataset
            tmp_data_idx = [x - idx_d for x in lst_data_idx \
                            if x >= idx_d and x < idx_u]
            subset.f_manage_data(tmp_data_idx, opt)
        # re-initialize len, len_top, and len_bot
        self.__init_sub()
        return None


    def f_get_seq_idx_from_name(self, data_names):
        """ list_of_idx = f_get_seq_idx_from_name(data_names)
        """
        return [self.name_idx_map[x] for x in data_names]


class NII_MergeDataSetLoader():
    """ DatasetLoader for loading multiple data corpora as a single one

    Similar to NIIDataSetLoader, this merges the DataSet and DataLoader
    into a single class. 
    """
    def __init__(self,
                 dataset_name, \
                 list_file_list, \
                 list_input_dirs, input_exts, input_dims, input_reso, \
                 input_norm, \
                 list_output_dirs, output_exts, output_dims, output_reso, \
                 output_norm, \
                 stats_path, \
                 data_format = nii_dconf.h_dtype_str, \
                 params = None, \
                 truncate_seq = None, \
                 min_seq_len = None,
                 save_mean_std = True, \
                 wav_samp_rate = None, \
                 flag_lang = 'EN', \
                 way_to_merge = 'concatenate', 
                 global_arg = None,
                 dset_config = None,
                 input_augment_funcs = None,
                 output_augment_funcs = None,
                 inoutput_augment_func = None,
                 output_invtrans_funcs = None):
        """ Signature is similar to default_io.NIIDataSetLoader.
        file_list, input_dirs, and output_dirs are different.
        One additional optional argument is way_to_merge.

        Args
        ----
            data_set_name: a string to name this dataset
                           this will be used to name the statistics files
                           such as the mean/std for this dataset
            list_file_list: a list of file_name path
            list_input_dirs: a list of lists of dirs for input features
            input_exts: a list of input feature name extentions
            input_dims: a list of input feature dimensions
            input_reso: a list of input feature temporal resolution,
                        or None
            input_norm: a list of bool, whether normalize input feature or not

            list_output_dirs: a list of lists of dirs for output features
            output_exts: a list of output feature name extentions
            output_dims: a list of output feature dimensions
            output_reso: a list of output feature temporal resolution, 
                         or None
            output_norm: a list of bool, whether normalize target feature or not

            stats_path: path to the directory of statistics(mean/std)
            data_format: method to load the data
                    '<f4' (default): load data as float32m little-endian
                    'htk': load data as htk format
            params: parameter for torch.utils.data.DataLoader

            truncate_seq: None or int, 
                          truncate data sequence into smaller truncks
                          truncate_seq > 0 specifies the trunck length
            min_seq_len: None (default) or int, minimum length of an utterance
                         utterance shorter than min_seq_len will be ignored
            save_mean_std: bool, True (default): save mean and std 
            wav_samp_rate: None (default) or int, if input data has  waveform, 
                         please set sampling rate. It is used by _data_writer
            flag_lang: str, 'EN' (default), if input data has text, text will
                       be converted into code indices. flag_lang indicates the 
                     language for the text processer. It is used by _data_reader
            wav_to_merge: string, 'concatenate' (default) or 'merge'
                     'concatenate': simply concatenate multiple corpora
                     'merge': create minibatch by merging data from each copora
            global_arg: argument parser returned by arg_parse.f_args_parsed()
                      default None
            dset_config: object, data set configuration, default None
            input_augment_funcs: list of functions for input data transformation
                                 default None
            output_augment_funcs: list of output data transformation functions
                                 default None
            inoutput_augment_func: a single data augmentation function
                                 default None
            output_invtrans_funcs: list of functions for inverse transformation
                      of output features during inference. d
                      efault None
        Methods
        -------
            get_loader(): return a torch.util.data.DataLoader
            get_dataset(): return a torch.util.data.DataSet
        """ 
        ########
        # check whether input_dirs and output_dirs are lists
        if type(list_input_dirs[0]) is list and \
           type(list_output_dirs[0]) is list and \
           type(list_file_list) is list and \
           len(list_input_dirs) == len(list_output_dirs) and \
           len(list_input_dirs) == len(list_file_list):
            pass
        else:
            mes = "NII_MergeDataSetLoader: input_dirs, output_dirs, "
            mes += "and file_list should be list of lists. "
            mes += "They should have equal length. But we have:"
            mes += "{:s}\n{:s}\n{:s}".format(
                str(list_input_dirs), str(list_output_dirs), 
                str(list_file_list))
            nii_warn.f_die(mes)
        
        if type(dataset_name) is list:
            if len(dataset_name) != len(list_input_dirs):
                mes = "dataset_name should have {:d} elements. ".format(
                    len(list_file_list))
                mes += "But we have: {:s}".format(str(dataset_name))
                nii_warn.f_die(mes)
            elif len(list(set(dataset_name))) != len(list_input_dirs):
                mes = "dataset_name has duplicated elements: {:s}".format(
                    str(dataset_name))
                nii_warn.f_die(mes)
            else:
                tmp_dnames = dataset_name
        else:
            tmp_dnames = [dataset_name + '_sub_{:d}'.format(idx) \
                          for idx in np.arange(len(list_input_dirs))]
                
        #######
        # create individual datasets
        lst_dset = []
        cnt = 0
        for sub_input_dirs, sub_output_dirs, sub_file_list, tmp_name in \
            zip(list_input_dirs, list_output_dirs, list_file_list, tmp_dnames):
            
            # augmentation (transformation) function for input
            inaug = input_augment_funcs[cnt] if input_augment_funcs else None
            
            # augmentation (transformation) function for output 
            ouaug = output_augment_funcs[cnt] if output_augment_funcs else None
            
            # inverse transformation for output data during inference
            oinf = output_invtrans_funcs[cnt] if output_invtrans_funcs else None
            
            lst_dset.append(
                nii_default_dset.NIIDataSetLoader(
                    tmp_name, sub_file_list, \
                    sub_input_dirs, input_exts, input_dims, input_reso, \
                    input_norm, \
                    sub_output_dirs, output_exts, output_dims, output_reso, \
                    output_norm, \
                    stats_path, data_format, params, truncate_seq, min_seq_len,\
                    save_mean_std, wav_samp_rate, flag_lang, \
                    global_arg, dset_config, inaug, ouaug,\
                    inoutput_augment_func, oinf))
            cnt += 1

        # list of the datasets
        self.m_datasets = lst_dset
        
        #######
        # merge multiple datasets (i.e., build the DataLoader)
        self.way_to_merge = way_to_merge

        if way_to_merge == 'concatenate':
            # to create DataLoader, we need the pytorch.dataset
            self.m_concate_set = ConcatDataset(
                [x.get_dataset() for x in self.m_datasets])

            # concatenate multiple datasets
            if params is None:
                tmp_params = nii_dconf.default_loader_conf
            else:
                tmp_params = params.copy()                
            # save parameters
            self.m_params = tmp_params

            # create data loader
            self.m_loader = self.build_loader_concate_merge()
        else:
            self.m_concate_set = None
            # sample mini-batches of equal size from each sub dataset
            # use specific dataloader
            self.m_loader = merge_loader(lst_dset)
            self.m_params = lst_dset[0].get_loader_params()
        return


    def build_loader_concate_merge(self):
        """
        build dataloader for a merged dataset
        """            
        # legacy implementation, no need to use
        ####
        # Although members in l_dset have Dataloader, we need to 
        # create a dataloder for the concatenate dataset
        ###
        tmp_params = self.m_params.copy()
        # creatr sampler
        if 'sampler' in tmp_params:
            tmp_sampler = None
            if tmp_params['sampler'] == nii_sampler_fn.g_str_sampler_bsbl:
                if 'batch_size' in tmp_params \
                   and tmp_params['batch_size'] > 1:
                    # initialize the sampler
                    tmp_sampler = nii_sampler_fn.SamplerBlockShuffleByLen(
                        self.m_concate_set.f_get_seq_len_list(), 
                        tmp_params['batch_size'])
                    # turn off automatic shuffle
                    tmp_params['shuffle'] = False
                else:
                    nii_warn.f_print("{:s} off as batch-size is 1".format(
                        nii_sampler_fn.g_str_sampler_bsbl))
            tmp_params['sampler'] = tmp_sampler

        # collate function
        if 'batch_size' in tmp_params and tmp_params['batch_size'] > 1:
            # use customize_collate to handle data with unequal length
            #  we cannot use default collate_fn
            collate_fn = nii_collate_fn.customize_collate
        else:
            collate_fn = None
        
        # use default DataLoader
        return torch.utils.data.DataLoader(
            self.m_concate_set, collate_fn=collate_fn, **tmp_params)

        

    def get_loader_params(self):
        return self.m_params

    def get_loader(self):
        """ get_loader():
        Return the dataLoader (torch.util.data.DataLoader)
        """
        return self.m_loader
    
    def get_dataset(self):
        """ get_dataset():
        Return the dataset (torch.util.data.Dataset)
        """
        return self.m_datasets

    def get_data_mean_std(self):
        """
        """
        # temporary solution: just use the first one
        return self.m_datasets[0].get_data_mean_std()

    def print_info(self):
        """
        """
        nii_warn.f_print_message("Merge datasets by: " + self.way_to_merge)
        for dset in self.m_datasets:
            dset.print_info()
        return

    def putitem(self, output_data, save_dir, filename_prefix, data_infor_str):
        """ Decompose the output_data from network into
        separate files
        """
        # Since all datasets have similar configuration on feat dim,
        # use anyone is OK
        self.m_datasets[0].putitem(output_data, save_dir, filename_prefix,
                                   data_infor_str)

    def get_in_dim(self):
        """ Return the dimension of input features
        """ 
        # Since all datasets have similar configuration on feat dim,
        # use anyone is OK
        return self.m_datasets[0].get_in_dim()

    def get_out_dim(self):
        """ Return the dimension of output features
        """
        # Since all datasets have similar configuration on feat dim,
        # use anyone is OK
        return self.m_datasets[0].get_out_dim()

    def get_seq_num(self):
        """ Return the number of sequences (after truncation)
        """ 
        return sum([x.get_seq_num() for x in self.m_datasets])

    def get_seq_info(self):
        """ Return the full information of each data,
        including name, index, segmentation information
        """
        tmp = []
        for dataset in self.m_datasets:
            tmp += dataset.get_seq_info()
        return tmp

    def get_seq_name_list(self):
        """ list = get_seq_name_list()

        Return a list of data sequence name
        """
        tmp = []
        for dataset in self.m_datasets:
            tmp += dataset.get_seq_name_list()
        return tmp
    
    def get_seq_idx_from_name(self, data_names):
        """ idx = get_seq_idx_from_name(data_names)
        
        Return a list of data idx corresponding to the data file names
        """
        # re-build data loader
        if self.way_to_merge == 'concatenate':
            return self.m_concate_set.f_get_seq_idx_from_name(data_names)
        else:
            nii_warn.f_print("Not implemented get_seq_idx_from_name")
            nii_warn.f_die("--way-to-merge-datasets concatenate")
            return None
        

    def update_seq_len_in_sampler_sub(self, data_info):
        """
        """
        # assume data_info logs the new data length that can be used for
        # sampler shuffle_by_length
        if self.way_to_merge == 'concatenate':
            self.m_concate_set.f_update_seq_len_for_sampler_list(data_info)
        else:
            print("Not implemented")
            sys.exit(1)
        return

    def update_seq_len_in_sampler(self):
        """ update_seq_len()

        Update sequence length if sequence length has been changed
        (for example, during silence trim process)
        
        This is necessary when using shuffle_by_seq_length sampler
        and the sequences were trimmed in data augmentation function.
        """
        # call each subdataset and update the sequence length
        for idx, _ in enumerate(self.m_datasets):
            self.m_datasets[idx].update_seq_len_in_sampler()
        
        # update loader of this database
        if self.way_to_merge == 'concatenate':
            if self.m_params['sampler'] == nii_sampler_fn.g_str_sampler_bsbl \
               and hasattr(self.m_loader.sampler, 'update_seq_length'):
                self.m_loader.sampler.update_seq_length(
                    self.m_concate_set.f_get_updated_seq_len_for_sampler_list())
        return

    def manage_data(self, lst_data_idx, opt):
        """ manage_data(data_index_list, opt)

        Manage data in the dataset. Current, we can either keep or delete 
        the specified list of data 

        Args:
           lst_data_idx: list of data indices, lst_data_idx[n] is 
                  the index of the sample in the merged dataset
           opt: 'keep', keep only data in idx
                'delete', delete data in idx
        """            
        # re-build data loader
        if self.way_to_merge == 'concatenate':
            self.m_concate_set.f_manage_data(lst_data_idx, opt)
            if self.get_seq_num() < 1:
                # DataLoader will raise Error when no data is DataSet
                self.m_loader = None
            else:
                self.m_loader = self.build_loader_concate_merge()
        else:
            nii_warn.f_print("Active learning requires ")
            nii_warn.f_die("--way-to-merge-datasets concatenate")
        return


    def add_dataset(self, new_data_wrapper):
        """add_dataset(new_data_wrapper)
        
        Add an existing merged dataset to this dataset

        Args:
          new_data_wrapper: must be a NII_MergeDataSetLoader
        """
        self.m_datasets = self.m_datasets + new_data_wrapper.m_datasets
        if self.way_to_merge == 'concatenate':
            self.m_concate_set = ConcatDataset(
                [x.get_dataset() for x in self.m_datasets])
            self.m_loader = self.build_loader_concate_merge()
        else:
            nii_warn.f_print("Active learning requires ")
            nii_warn.f_die("--way-to-merge-datasets concatenate")
        return


if __name__ == "__main__":
    print("Definition of customized Pytorch dataset")
