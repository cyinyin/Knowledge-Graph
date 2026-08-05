import os
import sys


class Args:
    def __init__(self):
        # Get the current file path
        self._curr_dir, _curr_file_name = os.path.split(os.path.abspath(__file__))  # unit path.py

        # Root directory
        self._root = os.path.abspath(os.path.join(self._curr_dir, ".."))
        # print(self._root)
        # Source file
        self.data_path = os.path.join(self._root, 'data')
        self.unit_path = os.path.join(self._root, 'unit')
        self.gas = os.path.join(self.data_path, 'gas.xlsx')
        self.liquid = os.path.join(self.data_path, 'liquid.xlsx')

if __name__ =='__main__':
    Args()
