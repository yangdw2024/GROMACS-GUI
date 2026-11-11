#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GROMACS GUI 程序入口"""

import multiprocessing
import sys
from gui.app import run_main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(run_main() or 0)
