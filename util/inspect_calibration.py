#!/usr/bin/python3

import pickle
import argparse


if __name__ == '__main__':

    # parse args
    parser = argparse.ArgumentParser(prog='inspect_calibration.py',
                                description='print the parameters from a Parallax calibation file')
    parser.add_argument('filename', help='the filename of the calibration file (.pkl)')

    args = parser.parse_args()

    with open(args.filename, 'rb') as f:
        cal = pickle.load(f)

    print('Intrinsic Parameters')
    print('---------------------')
    print('\tCamera 1:')
    print('\t\t', cal.mtx1)
    print('\t\t', cal.dist1)
    print()
    print('\tCamera 2:')
    print('\t\t', cal.mtx2)
    print('\t\t', cal.dist2)
    print()
    print('Extrinsic Parameters')
    print('---------------------')
    print('\tCamera 1:')
    print('\t\t', cal.proj1)
    print()
    print('\tCamera 2:')
    print('\t\t', cal.proj2)
    print()
    print('here')
