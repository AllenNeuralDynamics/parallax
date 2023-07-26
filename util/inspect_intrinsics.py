#!/usr/bin/python3

import pickle
import argparse


if __name__ == '__main__':

    # parse args
    parser = argparse.ArgumentParser(prog='inspect_intrinsics.py',
                                description='print the parameters from a Parallax intrinsics file')
    parser.add_argument('filename', help='the filename of the intrinsics file (.pkl)')

    args = parser.parse_args()

    with open(args.filename, 'rb') as f:
        cal = pickle.load(f)

    print('Intrinsic Parameters')
    print('---------------------')
    print('\tMTX:')
    print('\t\t', cal.mtx)
    print()
    print('\tDIST:')
    print('\t\t', cal.dist)
    print()
    print('\tRMSE:')
    print('\t\t', cal.rmse)
    print()
